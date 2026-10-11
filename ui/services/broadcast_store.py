"""
Read/write access to Rewards/{reward_id}/broadcasts.json - the history of
one-off bulk messages sent to a reward's whole recipient list (not a
per-slot report), e.g. the 2026-09-20 20%-reward-increase announcement to
every hamkadeh کارشناس.

Display-only for now (user decision 2026-09-20): the panel only SHOWS this
history, it does not trigger a send itself - sending is still done by hand
(a one-off script calling Senders/payamresan.send()), which is expected to
call append_broadcast() right after finishing so the panel has something to
show. A future version will read the recipient list from a real contact-
list API and let the panel trigger the send itself; nothing here should
assume that exists yet.

One JSON file per reward (not one shared file) so each reward's history
stays scoped to its own Rewards/{id}/ folder, same placement rule as
outputs/*.csv. Plain utf-8, no BOM - this file has no other reader to stay
compatible with (unlike config/rewards.csv or sender_version.txt).
"""

import json
import os
import threading

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
REWARDS_ROOT = os.path.join(_PROJECT_ROOT, "Rewards")

_write_lock = threading.Lock()


def _broadcasts_path(reward_id):
    """Rewards/{id}/broadcasts.json, or - once the reward has been archived
    (1405/07/19) - Rewards/_archive/{id}/broadcasts.json, so the panel keeps
    showing a finished reward's broadcast history."""
    path = os.path.join(REWARDS_ROOT, reward_id, "broadcasts.json")
    archived = os.path.join(REWARDS_ROOT, "_archive", reward_id, "broadcasts.json")
    if not os.path.isfile(path) and os.path.isfile(archived):
        return archived
    return path


def list_broadcasts(reward_id):
    """Newest first. Empty list if the reward has never had a broadcast (or
    reward_id doesn't exist) - not an error, just nothing to show yet."""
    path = _broadcasts_path(reward_id)
    if not os.path.isfile(path):
        return []
    try:
        with open(path, encoding="utf-8") as f:
            records = json.load(f)
    except (OSError, json.JSONDecodeError):
        return []
    return sorted(records, key=lambda r: r.get("sent_at", ""), reverse=True)


def append_broadcast(reward_id, record):
    """record: {"sent_at" (ISO string), "subject" (short one-line summary
    for list views - optional, the panel falls back to the raw text if
    missing), "text", "recipient_count", "ok_count", "fail_count", "source"
    (free text - where the recipient list came from, e.g. a filename, since
    there's no contact-list API yet)}. Appends - never overwrites earlier
    history."""
    path = _broadcasts_path(reward_id)
    with _write_lock:
        existing = []
        if os.path.isfile(path):
            try:
                with open(path, encoding="utf-8") as f:
                    existing = json.load(f)
            except (OSError, json.JSONDecodeError):
                existing = []
        existing.append(record)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        tmp_path = path + ".tmp"
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(existing, f, ensure_ascii=False, indent=2)
        os.replace(tmp_path, path)
