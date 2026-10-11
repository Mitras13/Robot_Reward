"""
TEMPLATE/render.py - turn this reward's report into personalised messages,
ready for the sender. This is the LAST step this reward folder controls -
core/reward_runner.py takes whatever list this returns and hands it,
untouched, to Senders.sender_thread.submit().

Contract: render(report, reward_id, slot) -> list[Senders.message.OutboundMessage]

    One OutboundMessage per person (or per broadcast, if this reward ever
    needs that - just build one OutboundMessage per intended destination,
    there is no separate broadcast mechanism to plug into).

    contact:       CRITICAL - the exact name Senders/send_message.py
        searches for and opens the chat by. This is the field that actually
        determines who receives the message today.
    panel_user_id: this person's stable identity in the source panel -
        required, this IS their identity key (log/identity only).
    chat_user_id:  the future real delivery destination once a central
        phonebook exists. Leave "" for now - not used by the sender yet.
    image:         path to an image to send alongside the text, or leave
        the default "" for text-only.
"""

from Senders.message import OutboundMessage


def render(report, reward_id, slot):
    raise NotImplementedError("copy this folder and implement render()")
