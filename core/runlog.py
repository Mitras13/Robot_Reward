"""
Generic, durable, resumable event log for any long-running batch operation
in this project - sender batches today, API downloaders or anything else
later (user decision 1405/06/24: this module must know nothing about
sending or downloading specifically, only about "a run made of items", so
it can be adopted by other parts of the project without changing it).

Concepts:
    component - a free-form dotted name the caller picks ("sender.v1",
                "sender.v2", later e.g. "downloader.HK.SCL"). Just a folder
                name; this module attaches no other meaning to it.
    run       - one batch/execution, identified by a run_id the *caller*
                computes (callers already have their own content-
                fingerprint schemes for this - not reinvented here).
    item      - one unit of work inside a run (one message sent, later
                maybe one page of a paginated download). Caller-defined
                dict; the only key this module ever reads is "ok": bool.
                A "resume_key" key, if present, is what resume_done_keys()
                uses - optional, since not every component needs resume.

Storage: logs/runs/{component}/{run_id}.jsonl, inside this project's own
logs/ folder (already covered by the blanket "logs/" entry in .gitignore).
One line per event: run_start / item / run_end.

This file IS the resume record - resume_done_keys() replays a run's own
item log and returns the resume_key of everything that already succeeded.
There is no second, separate resume file anywhere - this is the single
source of truth for "what already happened in this run", both for live
observability and for continuing after a crash/power loss.

In-memory state here is this module's own - separate from core/live_state.py's
older render-phase tracking (current_downloads/current_rewards), which this
module does not touch. Every boolean-valued field present on a logged item
is auto-tallied (true/false counts) into that run's live state, so any
future boolean a component invents (known_contact, permanent_failure, a
future downloader's from_cache, ...) becomes visible in snapshot()
automatically, with zero domain knowledge added here. Nothing reads
snapshot() yet (the dashboard is a separate, already-open task) - the shape
is just made ready for it now.
"""

import collections
import json
import logging
import os
import threading
import time

_logger = logging.getLogger("core.runlog")

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RUNS_DIR = os.path.join(_PROJECT_ROOT, "logs", "runs")

_lock = threading.Lock()
_current = {}                                          # component -> run dict
_recent = collections.defaultdict(lambda: collections.deque(maxlen=20))  # component -> deque[dict]


def _run_path(component, run_id):
    d = os.path.join(RUNS_DIR, component)
    os.makedirs(d, exist_ok=True)
    return os.path.join(d, f"{run_id}.jsonl")


def _append(path, event):
    event.setdefault("ts", time.time())
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(event, ensure_ascii=False) + "\n")
        f.flush()


def start_run(run_id, component, meta=None, total=None):
    """Call once, before the first item of a run. Idempotent on the durable
    file (always appends a fresh run_start line - if a run_id is reused
    deliberately for resume, that is expected and fine), but resets this
    component's in-memory "current run" unconditionally."""
    path = _run_path(component, run_id)
    _append(path, {"event": "run_start", "total": total, "meta": meta or {}})
    with _lock:
        _current[component] = {
            "run_id": run_id, "meta": meta or {}, "total": total,
            "ok": 0, "failed": 0, "tally": {}, "started_at": time.time(),
            "updated_at": time.time(), "last_item": None,
            "duration_sum": 0.0, "duration_count": 0,
        }


def log_item(run_id, component, item):
    """item must include "ok": bool; everything else is free-form and
    stored as-is. Also serves as this run's resume record - see
    resume_done_keys()."""
    path = _run_path(component, run_id)
    _append(path, {"event": "item", **item})
    with _lock:
        run = _current.get(component)
        if run is not None and run["run_id"] == run_id:
            run["ok" if item.get("ok") else "failed"] += 1
            run["updated_at"] = time.time()
            run["last_item"] = item
            # duration_sum/duration_count (1405/06/26): lets a still-running
            # batch estimate an ETA (avg item time * remaining count) for the
            # dashboard - the ok/failed counts alone give no time estimate.
            duration = item.get("duration_sec")
            if isinstance(duration, (int, float)):
                run["duration_sum"] += duration
                run["duration_count"] += 1
            for k, v in item.items():
                if isinstance(v, bool):
                    bucket = run["tally"].setdefault(k, {"true": 0, "false": 0})
                    bucket["true" if v else "false"] += 1


def finish_run(run_id, component, summary=None):
    """Call once after a run's last item (success, failure, or crash -
    always via `finally`). Moves the component's "current run" into its
    small "recent" ring for whatever later reads snapshot()."""
    path = _run_path(component, run_id)
    _append(path, {"event": "run_end", "summary": summary or {}})
    with _lock:
        run = _current.pop(component, None)
        if run is not None and run["run_id"] == run_id:
            run["finished_at"] = time.time()
            run["summary"] = summary or {}
            _recent[component].append(run)


def _read_events(path):
    """Yields every parseable event dict in a run's file, in order. A line
    that fails to parse (1405/06/25: a real crash/power-loss can truncate
    the OS write of the last line mid-write) is skipped with a warning, not
    treated as failing the whole file - the entire point of this file is to
    still answer "what already happened" right after exactly that kind of
    interruption, so one bad line must never take down every other line
    around it. Shared by load_items() and load_run_summary()."""
    with open(path, encoding="utf-8") as f:
        for line_no, line in enumerate(f, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                yield json.loads(line)
            except json.JSONDecodeError:
                _logger.warning("skipping corrupt line %d in %s (likely a crash mid-write)", line_no, path)


def load_items(run_id, component):
    """All logged item events for a run, in order - the durable record this
    module writes, read back. Empty list if the run has no log yet."""
    path = _run_path(component, run_id)
    if not os.path.isfile(path):
        return []
    return [event for event in _read_events(path) if event.get("event") == "item"]


def list_run_ids(component, since_ts=None):
    """run_ids on disk for a component, optionally filtered to files
    modified at/after since_ts (a run's file is appended to throughout its
    life, so its mtime always reflects its LAST write - a cheap way for a
    caller like the dashboard to skip opening/parsing days-old runs without
    needing any separate index). [] if the component has no directory yet."""
    d = os.path.join(RUNS_DIR, component)
    if not os.path.isdir(d):
        return []
    run_ids = []
    for name in os.listdir(d):
        if not name.endswith(".jsonl"):
            continue
        full = os.path.join(d, name)
        if since_ts is not None and os.path.getmtime(full) < since_ts:
            continue
        run_ids.append(name[: -len(".jsonl")])
    return run_ids


def run_mtime(run_id, component):
    """Last-write time of a run's file (0.0 if it has none) - public so
    readers like the dashboard can order runs without reaching into
    _run_path()."""
    path = os.path.join(RUNS_DIR, component, f"{run_id}.jsonl")
    return os.path.getmtime(path) if os.path.isfile(path) else 0.0


def load_run_summary(run_id, component):
    """Reads a run's whole file and replays it into one dashboard-shaped
    dict: {run_id, component, meta, total, ok, failed, started_at,
    finished_at, duration_sec, summary}. finished_at/duration_sec are None
    if the run never reached a run_end (crashed, or still running - check
    snapshot()'s "current" for that instead). None if the run has no file
    at all. This is what lets the dashboard show a past slot's real
    ok/failed/duration even after a restart, when the in-memory "recent"
    ring (only populated for runs finished by *this* process) is empty but
    the .jsonl file from before the restart is still on disk."""
    path = _run_path(component, run_id)
    if not os.path.isfile(path):
        return None
    result = {
        "run_id": run_id, "component": component, "meta": {}, "total": None,
        "ok": 0, "failed": 0, "started_at": None, "finished_at": None,
        "duration_sec": None, "summary": None,
    }
    for event in _read_events(path):
        kind = event.get("event")
        if kind == "run_start":
            result["meta"] = event.get("meta") or {}
            result["total"] = event.get("total")
            result["started_at"] = event.get("ts")
        elif kind == "item":
            result["ok" if event.get("ok") else "failed"] += 1
        elif kind == "run_end":
            result["finished_at"] = event.get("ts")
            result["summary"] = event.get("summary") or {}
    if result["started_at"] is not None and result["finished_at"] is not None:
        result["duration_sec"] = round(result["finished_at"] - result["started_at"], 3)
    return result


def resume_done_keys(run_id, component, key_fn=lambda item: item.get("resume_key"),
                      predicate=lambda item: item.get("ok")):
    """Replays a run's own durable item log (the SAME file log_item() wrote)
    and returns the set of key_fn(item) for every item matching predicate
    (default: every successful item). This is the entire "continue after
    crash/power loss" mechanism - one read of the run's own log, nothing
    else."""
    return {key_fn(item) for item in load_items(run_id, component) if predicate(item)}


def snapshot():
    """Dashboard-shaped state - not consumed by any UI yet.
    {component: {"current": {...} | None, "recent": [...]}}"""
    with _lock:
        components = set(_current) | set(_recent)
        return {
            c: {
                "current": dict(_current[c]) if c in _current else None,
                "recent": list(_recent.get(c, [])),
            }
            for c in components
        }
