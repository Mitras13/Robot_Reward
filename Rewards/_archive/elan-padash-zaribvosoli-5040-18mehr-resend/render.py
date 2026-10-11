"""
elan-padash-zaribvosoli-5040-18mehr-resend/render.py

Same approved text as elan-padash-zaribvosoli-5040-18mehr (imported from it,
not copied, so the two can never differ).
"""

import importlib

from Senders.message import OutboundMessage

TEXT = importlib.import_module("Rewards.elan-padash-zaribvosoli-5040-18mehr.render").TEXT


def render(report, reward_id, slot):
    return [
        OutboundMessage(reward_id=reward_id, slot=slot, panel_user_id=name,
                        chat_user_id="", contact=name, text=TEXT)
        for name in report["recipients"]
    ]
