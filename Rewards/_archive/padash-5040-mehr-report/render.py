"""
padash-5040-mehr-report/render.py

Only the "send" phase (08:30) produces a message - the "build" phase
(00:00) returns [] (nothing to send yet, just froze/cached the image).

مقصد فعلاً فقط میترا سرخوش - طبق درخواست صریح کاربر ۲۰۲۶-۰۹-۲۲: اول برای
میترا سرخوش برو، بعد از تاییدش دستی برای گروه «گزارشات پاداش» فرستاده
می‌شه (این پروژه راهی برای تشخیص خودکار تایید چت نداره).
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
            text="📊 گزارش مدیریتی پایان بازه‌ی طرح ویژه افزایش رقابت براساس ضریب وصولی کارشناسان ۵۰۴۰ - لطفاً بررسی و تایید کن تا برای گروه گزارشات پاداش هم ارسال بشه.",
            image=image_path,
        )
    ]
