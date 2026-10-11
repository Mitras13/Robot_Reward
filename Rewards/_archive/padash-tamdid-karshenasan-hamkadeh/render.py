"""
padash-tamdid-karshenasan-hamkadeh/render.py

Turns builder.py's report ({"slot_jdt": jdatetime, "table": DataFrame} - see
build()) into one OutboundMessage per کارشناس row, following the exact
3-block message spec the user gave 2026-09-15:

  Block 1 (fixed greeting + report date/time) - always present.
  Block 2 (performance numbers) - the "پاداش فعلی" line is OMITTED for
    anyone still below the first tier (reward_toman == 0), per the user's
    instruction; the "فاصله تا پله بعد" line is always present, since
    builder.py's invoices_to_next already measures distance to whichever
    tier is next (first tier if outside the reward, next tier if inside).
  Block 3 (exactly one of 7 analytical lines - no header line, per the
    user: "فقط خطوط متن تحلیلی میاد"), chosen by reward_toman and the size
    of the invoices_to_next gap:

    reward_toman == 0 (outside reward):
      1-2 invoices away -> scenario 1 | 3-4 -> scenario 2 | 5+ -> scenario 3
    reward_toman > 0 (inside reward):
      invoices_to_next is None (top tier reached) -> scenario 7
      1-2 invoices away -> scenario 4 | 3-4 -> scenario 5 | 5+ -> scenario 6
    Scenarios 4 and 5 name the NEXT tier's reward amount (the user's "y"/
    "غ" placeholders - both meant the same thing: پاداش پله بعد).

contact = panel_user_id = the کارشناس name exactly as it appears in the
raw HK.FCP data ("ثبت کننده") - the only identity this report has; the
sender searches contacts by this exact string (see Senders/message.py).

Manager summary (added 2026-09-16, per user request): for each entry in
MANAGER_CONTACTS, one extra message is prepended to the list (before any
کارشناس message) with slot-level aggregates instead of a per-person report
- total تمدیدی amount/count across all کارشناسان, total estimated reward,
headcount active/rewarded, average per active کارشناس, and the top
performer. `contact` stays the exact name the sender looks up in the
address book; `greeting` is a separate, hand-written name+title string
(these 4 people are hardcoded render inputs, not derived from builder.py's
output, so their text is customized by hand too, not by a general rule).

STILL PENDING from the user: real schedule.csv slot times.
"""

import csv
import os

from Senders.message import OutboundMessage

from .builder import TIERS

WEEKDAY_FA = ["شنبه", "یکشنبه", "دوشنبه", "سه‌شنبه", "چهارشنبه", "پنج‌شنبه", "جمعه"]
MONTH_NAMES = [
    "", "فروردین", "اردیبهشت", "خرداد", "تیر", "مرداد", "شهریور",
    "مهر", "آبان", "آذر", "دی", "بهمن", "اسفند",
]

# مسیر config/rewards.csv نسبت به همین فایل - فقط برای خوندن valid_from
# همین پاداش (تاریخ شروع بازه)، دقیقاً همون الگوی padash-karshenasan-5040.
_REWARDS_CSV_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "..", "config", "rewards.csv"
)

# مدیرانی که به‌جای پیام شخصی کارشناس، خلاصه‌ی مدیریتی همان اسلات را
# می‌گیرند. contact/panel_user_id همان نامی است که پیام‌رسان با آن در
# دفترچه تماس جست‌وجو می‌کند (قرارداد name-as-contact کارشناس‌ها).
# تا ۲۰۲۶-۰۹-۲۰ این خلاصه به ۴ مدیر جدا (فیضی/زمانی/مدنی/طارمی) فرستاده
# می‌شد؛ طبق تصمیم کاربر همان تاریخ، این ۴ نفر حذف و به‌جایش گروه «گزارشات
# پاداش» اضافه شد - میترا سرخوش جداگانه می‌ماند. برای گروه از Username دقیق
# استفاده شده (نه Alias) چون سه entity هم‌نام «گزارشات پاداش» در دایرکتوری
# هست - تست شد، فقط همین یکی را برمی‌گرداند. پاک‌شدن تاریخچه برای این گروه
# خودکار رد می‌شود (send_message_v2._clear_conversation برای IsEntity=True
# اصلاً session_id resolve نمی‌کند) - نیازی به تغییر کد سندر نبود.
# گروه «گزارشات پاداش» موقتاً غیرفعاله (کاربر ۲۰۲۶-۰۹-۲۲: "برای گروه
# گزارشات پاداش فعلا هیچ پیامی ارسال نکن") - commentِ زیر نگه داشته شده تا
# راحت برگرده، حذف کامل نشده.
MANAGER_CONTACTS = [
    "میترا سرخوش",
    # "group-smrezvanmadani-1789890446796",
]

# گزارش جامع اکسل (builder.py: report["manager_excel_path"]) - جدا از
# MANAGER_CONTACTS بالا (که خلاصه‌ی متنی می‌گیرند) - طبق درخواست کاربر
# ۲۰۲۶-۰۹-۲۲، این دو مدیر فایل اکسل کامل رو به‌عنوان پیوست می‌گیرند. رشته‌ها
# دقیقاً همون چیزیه که کاربر داد (شامل فاصله/بدون‌فاصله‌ی قبل از پرانتز) -
# این عیناً رشته‌ی جست‌وجوی پیام‌رسانه، تغییرش نده مگر ارسال شکست بخوره.
EXCEL_REPORT_CONTACTS = [
    "عرفان مهدی پور (مدیرفروش همکده)",
    "شاهین قاسمی ده چشمه(مدیر فروش همکده)",
]


def _report_date_time(slot_jdt):
    date_str = f"{slot_jdt.day} {MONTH_NAMES[slot_jdt.month]} {slot_jdt.year}"
    # end-of-day slots (23:59) display as 24:00 - same convention as the
    # reference module (TamdidiHK.py's _make_title).
    if slot_jdt.hour == 23 and slot_jdt.minute == 59:
        time_str = "24:00"
    else:
        time_str = slot_jdt.strftime("%H:%M")
    return date_str, time_str


def _period_start_date_str(reward_id):
    """تاریخ شروع بازه‌ی همین پاداش (ستون valid_from در config/rewards.csv)
    به فرمت "23 شهریور 1405" - برای خط «از تاریخ ... تا تاریخ ... ساعت ...»
    تو خلاصه‌ی مدیریتی. None اگه ردیف/فایل پیدا نشد (نباید عملاً پیش بیاد)."""
    try:
        with open(_REWARDS_CSV_PATH, encoding="utf-8-sig") as f:
            for row in csv.DictReader(f):
                if row.get("id") == reward_id:
                    year, month, day = (int(p) for p in row["valid_from"].split("/"))
                    return f"{day} {MONTH_NAMES[month]} {year}"
    except (OSError, ValueError, KeyError):
        return None
    return None


def _next_tier_reward(amount_toman):
    for threshold, reward in TIERS:
        if amount_toman < threshold:
            return reward
    return None  # already at/above the top tier


def _scenario_text(reward_toman, invoices_to_next, amount_toman):
    if reward_toman == 0:
        if invoices_to_next <= 2:
            return (
                f"🔥 خیلی به اولین پله پاداش نزدیک شدی؛ با حدود {invoices_to_next} "
                "فاکتور تمدیدی دیگر می‌توانی وارد محدوده پاداش شوی."
            )
        if invoices_to_next <= 4:
            return (
                f"🎯 فاصله‌ات تا ورود به پاداش حدود {invoices_to_next} فاکتور است؛ "
                "با پیگیری مراجع تمدیدی، رسیدن به اولین پله کاملاً در دسترس است."
            )
        return "🚀 هنوز تا اولین پله پاداش فاصله داری؛ هر تمدیدی جدید این فاصله را کمتر می‌کند."

    if invoices_to_next is None:
        return (
            "👑 تبریک! به بالاترین پله پاداش رسیده‌ای. حالا هدف، حفظ همین عملکرد "
            "قدرتمند و افزایش هرچه بیشتر وصولی تمدیدی تا پایان طرح است."
        )

    next_reward = _next_tier_reward(amount_toman)
    if invoices_to_next <= 2:
        return (
            f"⭐️ پاداشت فعال است و فقط حدود {invoices_to_next} فاکتور دیگر تا پله بعد "
            f"فاصله داری؛ با عبور از این مرز، مبلغ پاداشت {next_reward:,} تومان می‌شود."
        )
    if invoices_to_next <= 4:
        return (
            f"💪 در محدوده پاداش هستی و حدود {invoices_to_next} فاکتور تا پله بعد "
            f"فاصله داری؛ ادامه همین روند می‌تواند تو را به جایزه بالاتر یعنی "
            f"{next_reward:,} تومان برساند."
        )
    return (
        "🎯 پاداش فعلی‌ات قطعی‌تر شده؛ هدف بعدی پله بالاتر است و هر تمدیدی جدید، "
        "فاصله تو را با پاداش بیشتر کاهش می‌دهد."
    )


def _manager_summary_text(table, date_str, time_str, period_start_str):
    total_amount = int(table["amount_toman"].sum())
    total_count = int(table["count"].sum())
    total_reward = int(table["reward_toman"].sum())
    active_experts = len(table)
    rewarded_count = int((table["reward_toman"] > 0).sum())

    if period_start_str:
        period_line = f"از تاریخ {period_start_str} تا تاریخ {date_str} ساعت {time_str}"
    else:
        period_line = f"تا تاریخ {date_str} ساعت {time_str}"

    lines = [
        "با سلام و احترام",
        "خلاصه‌ی مدیریتی طرح پاداش تمدیدی کارشناسان همکده",
        period_line,
        "",
        f"💰 مجموع وصولی فاکتورهای تمدیدی: {total_amount:,} تومان",
        f"🧾 تعداد فاکتورهای تمدیدی وصول‌شده: {total_count} فاکتور",
        f"🎁 مبلغ پاداش برآوردی این لحظه: {total_reward:,} تومان",
        f"👥 تعداد کارشناسان فعال (حداقل یک فاکتور تمدیدی): {active_experts} نفر",
        f"✅ تعداد کارشناسان واجد شرایط پاداش: {rewarded_count} نفر",
    ]

    if active_experts > 0:
        top_row = table.loc[table["amount_toman"].idxmax()]
        avg_amount = round(total_amount / active_experts)
        lines.append("")
        lines.append(f"📊 میانگین وصولی به ازای هر کارشناس فعال: {avg_amount:,} تومان")
        lines.append(
            f"🏆 کارشناس برتر این لحظه: {top_row['کارشناس']} با "
            f"{int(top_row['amount_toman']):,} تومان وصولی"
        )

    return "\n".join(lines)


def render(report, reward_id, slot):
    slot_jdt = report["slot_jdt"]
    table = report["table"]
    date_str, time_str = _report_date_time(slot_jdt)
    period_start_str = _period_start_date_str(reward_id)

    messages = []
    for manager_contact in MANAGER_CONTACTS:
        messages.append(OutboundMessage(
            reward_id=reward_id,
            slot=slot,
            panel_user_id=manager_contact,
            chat_user_id="",
            contact=manager_contact,
            text=_manager_summary_text(table, date_str, time_str, period_start_str),
        ))

    excel_path = report.get("manager_excel_path")
    if excel_path:
        for manager_contact in EXCEL_REPORT_CONTACTS:
            messages.append(OutboundMessage(
                reward_id=reward_id,
                slot=slot,
                panel_user_id=manager_contact,
                chat_user_id="",
                contact=manager_contact,
                text=f"📎 گزارش جامع طرح پاداش تمدیدی کارشناسان همکده - {date_str} ساعت {time_str}",
                image=excel_path,
            ))

    # گزارش مدیریتی تصویری پایان بازه (فقط روی آخرین اسلات، management_image.py
    # وجودش رو تضمین می‌کنه) - مقصد نهایی طبق درخواست کاربر ۲۰۲۶-۰۹-۲۲ گروه
    # «گزارشات پاداش»ه، ولی فعلاً برای تست به میترا سرخوش می‌ره - همون الگوی
    # نسخه‌ی 5040. وقتی گزارش تست تایید شد، MANAGEMENT_IMAGE_TARGET رو به
    # گروه (زیر، comment شده) برگردون.
    MANAGEMENT_IMAGE_TARGET = "میترا سرخوش"
    # MANAGEMENT_IMAGE_TARGET = "group-smrezvanmadani-1789890446796"
    management_image_path = report.get("management_image_path")
    if management_image_path:
        messages.append(OutboundMessage(
            reward_id=reward_id,
            slot=slot,
            panel_user_id=MANAGEMENT_IMAGE_TARGET,
            chat_user_id="",
            contact=MANAGEMENT_IMAGE_TARGET,
            text=f"🧪 تست گزارش مدیریتی پایان بازه - طرح تمدید همکده ({date_str} ساعت {time_str})",
            image=management_image_path,
        ))

    for _, row in table.iterrows():
        name = row["کارشناس"]
        amount_toman = int(row["amount_toman"])
        count = int(row["count"])
        reward_toman = int(row["reward_toman"])
        raw_gap = row["invoices_to_next"]
        invoices_to_next = None if raw_gap is None or raw_gap != raw_gap else int(raw_gap)  # NaN check

        lines = [
            f"سلام {name} عزیز 🌱",
            "گزارش شما در طرح پاداش تمدیدی کارشناسان همکده ",
            f"در تاریخ {date_str} تا ساعت {time_str} به شرح زیر است:",
            "",
            f"💰 مجموع وصولی تمدیدی: {amount_toman:,} تومان",
            f"🧾 تعداد فاکتورهای تمدیدی: {count} فاکتور",
        ]
        if reward_toman > 0:
            lines.append(f"🎁 پاداش فعلی: {reward_toman:,} تومان")
        if invoices_to_next is not None:
            lines.append(f"🎯 فاصله تقریبی تا پله بعد: {invoices_to_next} فاکتور")

        lines.append("")
        lines.append(_scenario_text(reward_toman, invoices_to_next, amount_toman))

        messages.append(OutboundMessage(
            reward_id=reward_id,
            slot=slot,
            panel_user_id=name,
            chat_user_id="",
            contact=name,
            text="\n".join(lines),
        ))
    return messages
