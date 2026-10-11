"""
The one and only place that calls into Senders/send_message.py.

send_message.py drives a real Playwright browser session bound to whatever
thread opened it - a previous version of that file used threading.Thread
for concurrency and crashed with "Cannot switch to a different thread" (see
its own header comment). Every reward runs its own pipeline in its own
thread (core/reward_runner.py), so nothing outside this module may call the
sender directly. Instead each reward's rendered output is pushed onto the
queue here, and ONE dedicated thread - started once, from main.py -
drains it and calls payamresan.send(). The sender's own internal
concurrency (multiple tabs via asyncio) still applies inside that single
thread (user decision 1405/06/24).

Durable outbox (added 1405/07/19, user decision - replaces the earlier
"deliberately deferred" note): the queue below is in-memory, so a crash/
restart between a reward's render and the end of its send used to lose
that batch for good (the slot was already "done" in slot_runs.csv, so
nothing re-ran it). Now submit() first writes the batch to
logs/outbox/pending/*.json (atomic), and the file is deleted only after
send() returns without raising. start() re-enqueues every pending file
from TODAY before the thread starts; older ones are moved to
logs/outbox/expired/ and never sent (a day-old report is wrong, not late).
Re-sending a recovered batch cannot duplicate already-delivered messages:
the run_id is the same content fingerprint, and both v1 and v2 skip every
item core.runlog already records as ok for that run_id (resume_done_keys).

Run logging (added 2026-09-16, user decision - see core/runlog.py): this is
also the one place that ties a batch to a run for logging purposes - it has
reward_id/slot (from the OutboundMessage list, before _to_rendered() strips
them) and is about to dispatch. It computes run_id once (the same
fingerprint payamresan.compute_run_id()/v1 internally use), starts the run,
builds the on_result callback that feeds every per-message result into
core.runlog.log_item(), and always finishes the run in a `finally` - so a
run is closed out (and moved into core.runlog's "recent" ring) even if
send() raises.
"""

import dataclasses
import json
import logging
import os
import queue
import threading

import jdatetime

from core import runlog
from . import payamresan
from .message import OutboundMessage

logger = logging.getLogger("Senders.sender_thread")

_queue = queue.Queue()
_started = False
_lock = threading.Lock()

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUTBOX_PENDING_DIR = os.path.join(_PROJECT_ROOT, "logs", "outbox", "pending")
OUTBOX_EXPIRED_DIR = os.path.join(_PROJECT_ROOT, "logs", "outbox", "expired")


def _persist_pending(messages):
    """Writes the batch to logs/outbox/pending/ (tmp + os.replace, never a
    half-written file) and returns its path. The name starts with the Jalali
    date so recovery can tell today's batches from stale ones."""
    os.makedirs(OUTBOX_PENDING_DIR, exist_ok=True)
    run_id = payamresan.compute_run_id(_to_rendered(messages))
    today = jdatetime.datetime.now().strftime("%Y%m%d")
    name = f"{today}__{messages[0].reward_id}__{messages[0].slot.replace(':', '')}__{run_id}.json"
    path = os.path.join(OUTBOX_PENDING_DIR, name)
    tmp_path = path + ".tmp"
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump([dataclasses.asdict(m) for m in messages], f, ensure_ascii=False)
    os.replace(tmp_path, path)
    return path


def submit(messages):
    """
    Called from any reward's own thread once it has produced
    list[core.message.OutboundMessage] (may be empty - a no-op then).
    Non-blocking: persists the batch to the outbox, then enqueues - the
    dedicated sender thread does the work.
    """
    if messages:
        messages = list(messages)
        try:
            path = _persist_pending(messages)
        except OSError:
            # Never lose the send itself over an outbox write problem.
            logger.exception("could not persist batch to outbox - sending without crash recovery")
            path = None
        _queue.put((messages, path))


def _recover_pending():
    """Re-enqueues today's unfinished batches from a previous process (see
    module docstring); moves older ones to logs/outbox/expired/. Called once
    from start(), before the sender thread exists."""
    if not os.path.isdir(OUTBOX_PENDING_DIR):
        return
    today = jdatetime.datetime.now().strftime("%Y%m%d")
    for name in sorted(n for n in os.listdir(OUTBOX_PENDING_DIR) if n.endswith(".json")):
        path = os.path.join(OUTBOX_PENDING_DIR, name)
        if not name.startswith(today + "__"):
            os.makedirs(OUTBOX_EXPIRED_DIR, exist_ok=True)
            os.replace(path, os.path.join(OUTBOX_EXPIRED_DIR, name))
            logger.warning("outbox: expired unsent batch moved aside, NOT sent: %s", name)
            continue
        try:
            with open(path, encoding="utf-8") as f:
                messages = [OutboundMessage(**m) for m in json.load(f)]
        except (OSError, ValueError, TypeError):
            logger.exception("outbox: unreadable pending batch left in place: %s", name)
            continue
        if messages:
            logger.warning("outbox: recovering unfinished batch from a previous run: %s (%d message(s))",
                           name, len(messages))
            _queue.put((messages, path))


def _to_rendered(messages):
    """OutboundMessage list -> the shape Senders/send_message.py (v1) and
    Senders/payamresan.py expect. contact/image/caption are what actually
    drives delivery. panel_user_id/chat_user_id are passed through (added
    2026-09-15) so payamresan.py can attempt a future panel_user_id ->
    chat_user_id directory lookup - see payamresan._resolve_chat_user_id.
    v1 safely ignores both (reads only contact/image/caption via .get()/
    [...], per Senders/message.py's own docstring). reward_id/slot are
    still identity/log fields only - not passed, not acted on by any sender."""
    return [
        {
            "contact": m.contact,
            "image": m.image or None,
            "caption": m.text,
            "panel_user_id": m.panel_user_id or None,
            "chat_user_id": m.chat_user_id or None,
        }
        for m in messages
    ]


def _drain_loop():
    while True:
        messages, pending_path = _queue.get()
        reward_id, slot = messages[0].reward_id, messages[0].slot
        rendered = _to_rendered(messages)
        sender_version = payamresan.current_sender_version()
        component = f"sender.v{sender_version}"
        run_id = payamresan.compute_run_id(rendered)

        runlog.start_run(run_id, component, meta={"reward_id": reward_id, "slot": slot}, total=len(rendered))
        try:
            payamresan.send(rendered, run_id=run_id,
                             on_result=lambda item: runlog.log_item(run_id, component, item))
            # Batch finished (per-item failures are already in runlog): drop
            # it from the outbox. On an exception the file stays, so a
            # restart later today picks it up again.
            if pending_path and os.path.exists(pending_path):
                os.remove(pending_path)
        except Exception:
            logger.exception("send() failed for a batch of %d message(s) (reward_id=%s, slot=%s, run_id=%s)",
                              len(messages), reward_id, slot, run_id)
        finally:
            runlog.finish_run(run_id, component)
            _queue.task_done()


def start():
    """
    Starts the single dedicated sender thread. Call exactly once, from
    main.py at startup. Idempotent - a second call is a no-op, so
    importing this module from a test or tool never accidentally spins up
    a second sender thread.
    """
    global _started
    with _lock:
        if _started:
            return
        _recover_pending()
        threading.Thread(target=_drain_loop, daemon=True, name="sender-thread").start()
        _started = True
