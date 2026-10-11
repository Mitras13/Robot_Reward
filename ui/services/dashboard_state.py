"""
Read-only aggregation for the live status page (`/api/state`).

Moved verbatim from the old `ui/webserver.py` (1405/06/26 rewrite) when the
panel became a Flask app with multiple pages - same logic, same JSON
contract, just relocated so `ui/blueprints/status.py` stays a thin route
layer. See that module's docstring for the full data-source rationale:
`core/live_state.py` (render phase), `core/runlog.py` (send phase, live +
on-disk), `core/slot_log.py` + `core/scheduling.py` (today's slot history/
upcoming).
"""

import os
import time

import jdatetime

import tick as tick_module
from core import context as ctx
from core import live_state, reward_runner, runlog, scheduling, slot_log
from core.context import parse_jalali_date
from core.errors import RewardConfigError

_TERMINAL_SLOT_STATUSES = {"done", "failed", "skipped", "no_recipients", "download_failed", "build_failed"}


def _upcoming_by_reward(campaigns, schedule_rows, now_j):
    """{reward_id: [{"slot", "seconds_until"}, ...]} for the rest of today,
    across all active rewards - built once per request and handed to
    _reward_status() per reward. Reuses scheduling.upcoming_slots() as-is
    (window_minutes=1440 just means "anything left today", since that
    function already caps a window at today's own "24:00")."""
    pairs = scheduling.upcoming_slots(campaigns, schedule_rows, now_j, window_minutes=1440)
    result = {}
    for reward_id, slot in pairs:
        seconds_until = (scheduling.slot_to_jdatetime(now_j, slot) - now_j).total_seconds()
        result.setdefault(reward_id, []).append({"slot": slot, "seconds_until": round(seconds_until)})
    return result


def _next_slot_after_today(campaign, schedule_rows, now_j, max_days=14):
    """First (date, "HH:MM") slot strictly after today for one campaign -
    2026-09-30, user decision ("اگه اسلات برای امروز نداره ... بازه‌ی اجراش
    رو بنویس"): an enabled reward with nothing left today (e.g. a شنبه-only
    weekly schedule on a Tuesday) should show its real next occurrence, not
    just "nothing left today". Walks forward day by day (not a closed-form
    calc) because "days" can be an arbitrary "|"-separated set of weekday
    names/relative tokens (see core/scheduling.day_matches) - 14 days is
    comfortably more than a week so even a once-a-week schedule always finds
    its next hit."""
    for delta in range(1, max_days + 1):
        future_j = ctx.shift_days(now_j, delta)
        if not scheduling.is_campaign_active(campaign, future_j):
            continue
        times = scheduling.slots_for_day(campaign, schedule_rows, future_j)
        if times:
            return future_j, times[0]
    return None, None


def _today_run_summaries(reward_ids, since_ts):
    """{(reward_id, slot): summary} across both sender components, for runs
    that touched today - one directory scan per component per request
    (list_run_ids() is mtime-filtered so this stays cheap), not per reward."""
    summaries = {}
    for component in ("sender.v1", "sender.v2"):
        for run_id in runlog.list_run_ids(component, since_ts=since_ts):
            summary = runlog.load_run_summary(run_id, component)
            if not summary:
                continue
            meta = summary["meta"]
            if meta.get("reward_id") not in reward_ids:
                continue
            # last one wins (e.g. a slot that was cleared and re-triggered, as
            # happened once this session - the newer attempt is the relevant one)
            summaries[(meta.get("reward_id"), meta.get("slot"))] = summary
    return summaries


def _recent_activity(reward_names, limit=1000, max_runs=6):
    """Newest-first flat list of individual send attempts (item events) from
    the most recently touched run files per sender component - a closer look
    than the per-slot success_pct summary, for the status page's "لاگ‌های
    اخیر" panel. Walks back through at most `max_runs` files per component
    (newest first) and stops as soon as `limit` items are collected, so a
    single small run no longer caps the panel to just its own few rows, while
    still never scanning every run on disk."""
    entries = []
    for component in ("sender.v1", "sender.v2"):
        run_ids = sorted(
            runlog.list_run_ids(component),
            key=lambda rid: runlog.run_mtime(rid, component),
            reverse=True,
        )[:max_runs]
        collected = 0
        for run_id in run_ids:
            if collected >= limit:
                break
            summary = runlog.load_run_summary(run_id, component)
            reward_id = (summary or {}).get("meta", {}).get("reward_id")
            slot = (summary or {}).get("meta", {}).get("slot")
            items = runlog.load_items(run_id, component)[-(limit - collected):]
            collected += len(items)
            for item in items:
                entries.append({
                    "ts": item.get("ts"),
                    "reward_name": reward_names.get(reward_id, reward_id),
                    "slot": slot,
                    "contact": item.get("contact"),
                    "ok": item.get("ok"),
                    "error": item.get("error"),
                })
    entries.sort(key=lambda e: e.get("ts") or 0, reverse=True)
    return entries[:limit]


def _current_send_status(reward_id):
    """None (idle), or {"phase": "sending", slot/total/ok/failed/percent/
    eta_seconds} from whichever sender component currently has an in-flight
    batch for this reward - core/runlog.py's own live counters, not
    recomputed here."""
    for component, info in runlog.snapshot().items():
        current = info.get("current")
        if not current or current.get("meta", {}).get("reward_id") != reward_id:
            continue
        total = current.get("total") or 0
        ok, failed = current.get("ok", 0), current.get("failed", 0)
        done = ok + failed
        percent = round((done / total) * 100, 1) if total else None
        avg_duration = (current["duration_sum"] / current["duration_count"]) if current.get("duration_count") else None
        eta_seconds = round(avg_duration * max(total - done, 0)) if avg_duration is not None else None
        return {
            "phase": "sending", "slot": current.get("meta", {}).get("slot"),
            "total": total, "ok": ok, "failed": failed, "percent": percent,
            "eta_seconds": eta_seconds,
        }
    return None


def _reward_status(reward_row, now_j, upcoming_by_reward, run_summaries, next_slot_by_reward):
    reward_id = reward_row["id"]

    if reward_id in live_state.current_rewards:
        current = {"phase": "rendering"}
    else:
        current = _current_send_status(reward_id)

    by_slot = {}
    for row in slot_log.today_rows(now_j):
        if row["reward_id"] == reward_id and row["status"] in _TERMINAL_SLOT_STATUSES:
            by_slot[row["slot"]] = row  # today_rows() is chronological - last write wins

    past_slots = []
    for slot in sorted(by_slot):
        row = by_slot[slot]
        entry = {"slot": slot, "status": row["status"], "detail": row["detail"]}
        summary = run_summaries.get((reward_id, slot))
        if summary:
            done = summary["ok"] + summary["failed"]
            entry["total"] = summary["total"] if summary["total"] is not None else done
            entry["ok"] = summary["ok"]
            entry["failed"] = summary["failed"]
            entry["success_pct"] = round((summary["ok"] / done) * 100, 1) if done else None
            entry["duration_sec"] = summary["duration_sec"]
        past_slots.append(entry)

    sent_slots = [e for e in past_slots if "total" in e]
    today_summary = None
    if sent_slots:
        total = sum(e["total"] for e in sent_slots)
        ok = sum(e["ok"] for e in sent_slots)
        today_summary = {
            "slots_sent": len(sent_slots),
            "total": total,
            "ok": ok,
            "failed": total - ok,
            "success_pct": round((ok / total) * 100, 1) if total else None,
        }

    return {
        "reward_id": reward_id,
        "name": reward_row.get("name", ""),
        "company": reward_row.get("company", ""),
        "level": reward_row.get("level", ""),
        "enabled": tick_module.is_enabled(reward_row),
        "current": current,
        "past_slots": past_slots,
        "upcoming": upcoming_by_reward.get(reward_id, []),
        "today_summary": today_summary,
        # next_slot (2026-09-30, user decision): only ever populated for an
        # ENABLED reward with nothing left today - next_slot_by_reward is
        # built in build_state_payload() only from active_rows, so a
        # disabled reward's id is simply never a key in it. A reward WITH
        # slots left today also has no key here (see build_state_payload) -
        # the dashboard shows one or the other, never both.
        "next_slot": next_slot_by_reward.get(reward_id),
    }


def _reward_sort_key(reward_row):
    """Status page ordering (user request): enabled rewards before disabled
    ones, then by campaign start date (valid_from) ascending within each
    group - a malformed/missing valid_from sorts last within its group
    rather than crashing the page."""
    try:
        start = parse_jalali_date(reward_row.get("valid_from", ""))
    except ValueError:
        start = jdatetime.datetime(9000, 1, 1)  # sentinel: sorts after any real date
    return (0 if tick_module.is_enabled(reward_row) else 1, start)


def build_state_payload(state, lock):
    """The full `/api/state` JSON body. `state`/`lock` are main.py's
    shared dict + its lock (token status, last error, uptime bookkeeping)."""
    with lock:
        snapshot = dict(state)

    now_j = jdatetime.datetime.now()
    rewards = tick_module.load_rewards()
    rewards.sort(key=_reward_sort_key)
    active_rows = [r for r in rewards if tick_module.is_enabled(r)]
    reward_names = {r["id"]: r.get("name", r["id"]) for r in rewards}

    campaigns = [{**r, "reward_id": r["id"]} for r in active_rows]
    schedule_rows = []
    for r in active_rows:
        try:
            schedule_rows.extend(reward_runner.load_schedule(r["id"]))
        except RewardConfigError:
            continue  # a broken schedule.csv just means no upcoming/next-slot shown for it

    upcoming_by_reward = _upcoming_by_reward(campaigns, schedule_rows, now_j)

    # next_slot_by_reward (2026-09-30, user decision - "فقط گزارش‌های فعال
    # اسلات بعدی اجراشون مشخص باشه"): only for an ENABLED reward (campaigns
    # is built from active_rows only) that has nothing left TODAY - a
    # reward whose schedule still has a slot later today keeps showing that
    # via upcoming_by_reward instead, per _reward_status()'s docstring note.
    next_slot_by_reward = {}
    for campaign in campaigns:
        reward_id = campaign["reward_id"]
        if upcoming_by_reward.get(reward_id):
            continue
        future_j, slot = _next_slot_after_today(campaign, schedule_rows, now_j)
        if future_j and slot:
            next_slot_by_reward[reward_id] = {
                "date": future_j.strftime("%Y/%m/%d"),
                "weekday": scheduling.WEEKDAY_FA[future_j.weekday()],
                "slot": slot,
            }

    since_ts = ctx.start_of_day(now_j).togregorian().timestamp()
    run_summaries = _today_run_summaries({r["id"] for r in rewards}, since_ts)

    live_snapshot = live_state.snapshot()

    return {
        "now": now_j.strftime("%Y/%m/%d %H:%M:%S"),
        "last_activity_at": snapshot.get("last_activity_at", "-"),
        "uptime_seconds": time.monotonic() - snapshot.get("started_at", time.monotonic()),
        "last_error": snapshot.get("last_error"),
        "token_status": snapshot.get("token_status", {}),
        "next_token_check_in": snapshot.get("next_token_check_at", time.monotonic()) - time.monotonic(),
        "downloads": [
            {"downloader": d["downloader"], "reward_id": d["reward_id"],
             "reward_name": reward_names.get(d["reward_id"], d["reward_id"])}
            for d in live_snapshot["downloads"]
        ],
        "reward_status": [
            _reward_status(r, now_j, upcoming_by_reward, run_summaries, next_slot_by_reward) for r in rewards
        ],
        "active_count": len(active_rows),
        "recent_activity": _recent_activity(reward_names),
    }
