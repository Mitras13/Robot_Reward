"""
logs/slot_runs.csv - one append-only, greppable file recording every slot
attempt, replacing the sibling project's hundreds of zero-byte
logs/slot_*.done marker files.

Improvement over the sibling project: a row is written with status
"running" BEFORE a slot's requirements/download/engine work starts, not
only at the very end. This closes (for slot-level catch-up-once purposes)
the "duplicate-send on restart" class of bug the sibling project still has
open - a crash mid-slot no longer makes that slot look never-attempted on
the next tick, so it will not be silently recomputed and re-dispatched from
scratch. Per-message duplicate protection belongs to the sender side
(Senders/sender_thread.py's durable outbox + core/runlog.py resume); this
file only answers "should this slot even run again".
"""

import csv
import os

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SLOT_LOG_PATH = os.path.join(_PROJECT_ROOT, "logs", "slot_runs.csv")

FIELDS = ["date", "reward_id", "slot", "ts", "status", "detail"]

# Any of these statuses counts as "this slot was already attempted today" -
# for catch-up-once purposes it does not matter whether it finished cleanly.
_ATTEMPTED_STATUSES = {"running", "done", "skipped", "no_recipients",
                        "download_failed", "build_failed", "dispatch_failed"}


def _ensure_dir():
    os.makedirs(os.path.dirname(SLOT_LOG_PATH), exist_ok=True)


def record(reward_id, slot, now_j, status, detail=""):
    """Append one row. Flushed and fsynced immediately - this is a durability
    record, not a buffer."""
    _ensure_dir()
    file_exists = os.path.isfile(SLOT_LOG_PATH)
    with open(SLOT_LOG_PATH, "a", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS)
        if not file_exists:
            writer.writeheader()
        writer.writerow({
            "date": now_j.strftime("%Y/%m/%d"),
            "reward_id": reward_id,
            "slot": slot,
            "ts": now_j.strftime("%H:%M:%S"),
            "status": status,
            "detail": detail,
        })
        f.flush()
        os.fsync(f.fileno())


def load_today(now_j):
    """
    reward_id -> set of "HH:MM" slots already attempted today (any status in
    _ATTEMPTED_STATUSES). Empty dict if the file does not exist yet.
    """
    if not os.path.isfile(SLOT_LOG_PATH):
        return {}
    today = now_j.strftime("%Y/%m/%d")
    result = {}
    with open(SLOT_LOG_PATH, encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            if row["date"] != today:
                continue
            if row["status"] not in _ATTEMPTED_STATUSES:
                continue
            result.setdefault(row["reward_id"], set()).add(row["slot"])
    return result


def today_rows(now_j):
    """All of today's rows, newest last - for the dashboard."""
    if not os.path.isfile(SLOT_LOG_PATH):
        return []
    today = now_j.strftime("%Y/%m/%d")
    with open(SLOT_LOG_PATH, encoding="utf-8-sig") as f:
        return [row for row in csv.DictReader(f) if row["date"] == today]
