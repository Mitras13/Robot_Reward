"""
The sender's accepted input contract - lives here, not in core/, because the
sender owns its own architecture end to end (logging, failure behaviour,
whether/how it resolves a directory) and that includes what it accepts as
input (user decision 1405/06/24). Every reward's `render` step must produce
`list[OutboundMessage]`, this exact shape and nothing more, and hand it to
`Senders/`. A reward knows nothing about how the sender delivers, retries, or
dedups; the sender knows nothing about how a reward computed anything.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class OutboundMessage:
    """
    reward_id:      which reward produced this (identity/log field - never
        used by the reward itself, never affects delivery).
    slot:           "HH:MM" of the slot this message belongs to (see
        core/scheduling.py) - identity/log field, together with reward_id +
        panel_user_id this is what a future anti-duplicate design would use
        to tell "already sent" from "not yet". Does not affect delivery.
    panel_user_id:  stable identity of the person in the source panel -
        identity/log field, never used by the sender to find or reach them.
    chat_user_id:   the future real delivery destination (e.g. a phonebook-
        resolved chat id), once routing is wired up. Column exists now,
        unused by the sender today.
    contact:        CRITICAL - the exact name Senders/send_message.py
        searches for, opens the chat by, and verifies before sending. This
        is the only field the current sender version actually acts on to
        find who to send to.
    text:           final, already personalised message text -> handed to
        the sender as "caption".
    image:          path to an image to send alongside `text`, or "" for
        text-only. Reserved for later - no reward uses this yet.
    """
    reward_id: str
    slot: str
    panel_user_id: str
    chat_user_id: str
    contact: str
    text: str
    image: str = ""
