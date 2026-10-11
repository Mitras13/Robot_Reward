"""
padash-hamkadeh-mehr-report/render.py - twin of padash-5040-mehr-report's,
see that file's docstring.
"""

from Senders.message import OutboundMessage

MITRA_CONTACT = "میترا سرخوش"


def render(report, reward_id, slot):
    if report.get("phase") != "send":
        return []
    image_path = report.get("image_path")
    if not image_path:
        return []

    return [
        OutboundMessage(
            reward_id=reward_id,
            slot=slot,
            panel_user_id=MITRA_CONTACT,
            chat_user_id="",
            contact=MITRA_CONTACT,
            text="📊 گزارش مدیریتی پایان بازه‌ی طرح ویژه پاداش تمدیدی کارشناسان همکده - لطفاً بررسی و تایید کن تا برای گروه گزارشات پاداش هم ارسال بشه.",
            image=image_path,
        )
    ]
