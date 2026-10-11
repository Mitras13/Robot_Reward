"""
padash-sahmie-vorodi-hamkadeh/render.py

Twin of padash-sahmie-vorodi-5040/render.py for company همکده - only
message-text wording differs (company name), same personalized congrats
approach (user asked for this 2026-09-21, no fixed wording given).

contact = panel_user_id = the کارشناس name exactly as it appears in the raw
SP.HK.SPK data ("AAName").
"""

from Senders.message import OutboundMessage

MONTH_NAMES = [
    "", "فروردین", "اردیبهشت", "خرداد", "تیر", "مرداد", "شهریور",
    "مهر", "آبان", "آذر", "دی", "بهمن", "اسفند",
]


def _report_date_str(slot_jdt):
    return f"{slot_jdt.day} {MONTH_NAMES[slot_jdt.month]} {slot_jdt.year}"


def _congrats_text(name, amount_toman, date_str):
    return "\n".join([
        f"سلام {name} عزیز 🌟",
        "خوشحالیم بهتون خبر بدیم که در طرح ویژه سهمیه تماس ورودی کارشناسان همکده پذیرفته شدید!",
        f"مجموع وصولی کارتابلی شما تا تاریخ {date_str}، {amount_toman:,} تومان بود و از آستانه ۲۵۰ میلیون تومان عبور کرد.",
        "",
        "🎁 به همین مناسبت، از مهرماه سهمیه تماس‌های ورودی ماهانه‌تون فعال می‌شود.",
        "این نتیجه‌ی مستقیم تلاش و پیگیری مستمر شماست - تبریک می‌گوییم!",
    ])


def render(report, reward_id, slot):
    slot_jdt = report["slot_jdt"]
    table = report["table"]
    date_str = _report_date_str(slot_jdt)

    messages = []
    for _, row in table.iterrows():
        name = row["نام کارشناس"]
        amount_toman = int(row["مبلغ وصول کارتابلی"])
        messages.append(OutboundMessage(
            reward_id=reward_id,
            slot=slot,
            panel_user_id=name,
            chat_user_id="",
            contact=name,
            text=_congrats_text(name, amount_toman, date_str),
        ))
    return messages
