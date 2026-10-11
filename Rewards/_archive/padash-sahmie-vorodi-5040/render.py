"""
padash-sahmie-vorodi-5040/render.py

Turns builder.py's report ({"slot_jdt": jdatetime, "table": DataFrame} -
only qualifiers, already filtered by builder.py) into one personalized
congratulations OutboundMessage per کارشناس, announcing their مهر ماه
سهمیه‌ی تماس‌های ورودی - user asked for a personalized congrats text
2026-09-21, no fixed wording given.

contact = panel_user_id = the کارشناس name exactly as it appears in the raw
SP.54.SPK data ("AAName") - same identity convention as the sibling
padash-karshenasan-5040 reward for this same source/company.
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
        "خوشحالیم بهتون خبر بدیم که در طرح ویژه سهمیه تماس ورودی کارشناسان 5040 پذیرفته شدید!",
        f"مجموع وصولی کارتابلی شما تا تاریخ {date_str}، {amount_toman:,} تومان بود و از آستانه ۳۵۰ میلیون تومان عبور کرد.",
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
