"""
payamresan.py - Senders/{platform}.py contract: send(rendered).

Thin adapter around the vendored Senders/send_message.py, same pattern as
Robot_Analytics/Senders/chat5040.py. clear_after_send=True (turned back on
2026-09-15, user decision) so each sent chat's history is cleared afterward;
num_tabs=2 (changed 2026-09-15, user decision) to send with two parallel
isolated tabs instead of one.

The ONLY caller of send() is Senders/sender_thread.py's dedicated thread -
see that module for why (send_message.py's Playwright session is bound to
one specific thread). Nothing else should import send() directly.

compute_run_id() is the fingerprint scheme send_message.py (v1) itself uses
for message identity - sender_thread.py calls it once per batch so both the
core.runlog run_id and v1's own internal identity scheme are always the
same value. check_delivered() (2026-09-16: now backed by core.runlog, see
that module) answers "did this message actually go out" for anti-duplicate-
send work, whenever that gets designed inside the Sender's own architecture
(deliberately not wired up yet - user decision 1405/06/24).

Sender version flag (added 2026-09-15, user decision): send() re-reads
config/sender_version.txt on every call (not just at import) - so a rollback
to v1 takes effect on the next queued batch without restarting main.py.
"2" -> Senders/send_message_v2.py (imported lazily, only when selected, so a
bug in v2 at import time can never break v1). Anything else (missing file,
"1", garbage) -> v1. v2 must expose send_message(rendered, agents_csv_path,
num_tabs, clear_after_send) with the same signature/contract as v1's.

run_id/on_result (added 2026-09-16, user decision - see core/runlog.py):
this is a pure passthrough layer. Senders/sender_thread.py computes run_id
once per batch and builds the on_result callback (which feeds
core.runlog.log_item); send() just hands both to whichever version is
active. Neither v1 nor v2 fall back to computing their own run_id anymore
when it's not given by the caller in this project - sender_thread.py always
gives one.

panel_user_id -> chat_user_id lookup (added 2026-09-15, user decision): this
is where that matching belongs - not in any render.py/builder.py (directory/
routing is the sender's own business, see project decision 1405/06/24), and
not inside v1 or v2 themselves (keeps both versions oblivious to where an id
came from). _resolve_chat_user_id() reads config/chat_directory.csv
(implemented 1405/07/19 - was a stub). A person listed there is sent to
directly by messenger username in v2 (no name search, so no wrong-person
match); anyone not listed falls back to name search, unchanged. v1 safely
ignores chat_user_id (reads only contact/image/caption).
"""

import csv
import os

from core import runlog
from .send_message import send_message, _compute_run_id, _resume_key

PLATFORM = "payamresan"

_SENDER_VERSION_FILE = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "config", "sender_version.txt"
)


def current_sender_version() -> str:
    """Public (renamed from _current_sender_version 2026-09-16) - sender_thread.py
    reads this once per batch to name the core.runlog component
    ("sender.v1"/"sender.v2")."""
    try:
        with open(_SENDER_VERSION_FILE, encoding="utf-8") as f:
            return f.read().strip()
    except OSError:
        return "1"


_CHAT_DIRECTORY_FILE = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "config", "chat_directory.csv"
)


def _load_chat_directory() -> dict:
    """config/chat_directory.csv (utf-8-sig, columns panel_user_id,
    chat_user_id) -> {panel_user_id: chat_user_id}. chat_user_id is the
    messenger USERNAME (what v2's direct send uses as "Username"). Re-read
    on every batch (cheap, no restart needed after an edit, same convention
    as rewards.csv). Missing file or bad rows -> those people simply fall
    back to name search, exactly the pre-directory behaviour."""
    try:
        with open(_CHAT_DIRECTORY_FILE, encoding="utf-8-sig", newline="") as f:
            rows = list(csv.DictReader(f))
    except OSError:
        return {}
    return {
        (r.get("panel_user_id") or "").strip(): (r.get("chat_user_id") or "").strip()
        for r in rows
        if (r.get("panel_user_id") or "").strip() and (r.get("chat_user_id") or "").strip()
    }


def _resolve_chat_user_id(panel_user_id: str, directory: dict = None):
    """Implemented 1405/07/19 (user decision) - was a stub. Looks the person
    up in config/chat_directory.csv; None when not listed (name search is
    then used, unchanged)."""
    if directory is None:
        directory = _load_chat_directory()
    return directory.get(str(panel_user_id).strip())


def _enrich_with_chat_user_id(rendered: list):
    """For each item missing chat_user_id but carrying panel_user_id, try the
    lookup above. Mutates in place - cheap, and rendered is already a
    throwaway list built fresh per batch by sender_thread._to_rendered()."""
    directory = _load_chat_directory()
    if not directory:
        return
    for item in rendered:
        if not item.get("chat_user_id") and item.get("panel_user_id"):
            resolved = _resolve_chat_user_id(item["panel_user_id"], directory)
            if resolved:
                item["chat_user_id"] = resolved


def send(rendered: list, num_tabs: int = 2, run_id: str = None, on_result=None):
    """rendered: [{"contact", "image", "caption", "panel_user_id"?, "chat_user_id"?}, ...]
    run_id/on_result: see core/runlog.py - passed straight through to
    whichever version is active."""
    _enrich_with_chat_user_id(rendered)
    if current_sender_version() == "2":
        from .send_message_v2 import send_message as send_message_v2
        return send_message_v2(rendered, agents_csv_path="", num_tabs=num_tabs, clear_after_send=True,
                                run_id=run_id, on_result=on_result)
    else:
        return send_message(rendered, agents_csv_path="", num_tabs=num_tabs, clear_after_send=True,
                             run_id=run_id, on_result=on_result)


def compute_run_id(rendered: list) -> str:
    """The exact fingerprint send_message() (v1) uses internally for message
    identity. Called once per batch by Senders/sender_thread.py, before
    dispatch - see module docstring above."""
    return _compute_run_id(rendered)


def check_delivered(run_id: str, contact: str, caption: str):
    """
    True  - this exact (contact, caption) message is recorded as
            successfully sent in that run's log (core.runlog).
    False - the run has a log but this message is not in it as a success
            (that run's attempt reached this message's turn and it
            failed, or never got there before a crash).
    None  - core.runlog has no log at all for this run_id/version. Not
            called by anything yet - see module docstring.
    """
    component = f"sender.v{current_sender_version()}"
    if not runlog.load_items(run_id, component):
        return None
    key = _resume_key(contact, caption)
    return key in runlog.resume_done_keys(run_id, component)
