"""
padash-zaribvosoli-5040-18-30mehr/render.py

Copied from padash-karshenasan-5040/render.py (user 2026-10-10: the same
reward repeated) - کارشناس message and the 15 scenarios unchanged. The
per-slot manager summary/xlsx/image messages are dropped: managers get the
daily comprehensive report (gozaresh-jame-padash-zaribvosoli-5040) instead.

Turns builder.py's report ({"slot_jdt": jdatetime, "table": DataFrame}) into
one OutboundMessage per کارشناس, following the exact spec given 2026-09-15.

Unlike the sibling hamkadeh reward, this reward's Block 3 depends on the
PREVIOUS slot's own output (builder.py already writes one outputs/{slot
label}.csv per run) - not just this slot's numbers. _previous_table() scans
outputs/ for every *.csv strictly older than the current slot and picks the
most recent one; by the time render() runs, builder.build() has ALREADY
written the current slot's own file into that same folder (see
core/reward_runner.py: build() then render()), so "strictly older" is what
keeps render() from comparing a slot against itself.

Block 1 (greeting + report date/time) - always present, fixed 4 lines.

Block 2 (current numbers) - always present, fixed 5 lines. For rank > 550
(outside the reward range) این پنج خط عوض نمی‌شن، فقط درصد/پاداش طبیعتاً
۱۵٪/۰ تومان از خود builder.py می‌آیند (پله‌بندی builder.py از قبل همین
مقادیر رو برای رتبه ۵۵۱+ تولید می‌کنه - نیازی به override جدا نیست).

Block 3 - exactly ONE of 15 analytical lines, chosen by a priority chain
(explicit user note: several scenarios can technically match the same
person at once, so priority order matters):

  1. no previous slot exists at all (this is the very first slot of the
     whole campaign)                                   -> scenario 15
  2. رتبه == 1 و قبلاً هم رتبه ۱ بوده                     -> scenario 12
  3. رتبه == 1 و قبلاً رتبه ۱ نبوده (یا داده‌ای نبوده)      -> scenario 13
  4. رتبه != 1 و قبلاً رتبه ۱ بوده                         -> scenario 14
  5. رتبه <= 10 (و به این نقطه نرسیده باشیم یعنی رتبه != ۱)  -> scenario 7/8/9
     بر اساس بهتر/ثابت/بدتر شدن نسبت به رتبه قبلی
  6. رتبه <= 550 (محدوده پاداش، نه top10):
       - قبلاً داخل محدوده نبوده (یا داده‌ای نبوده)          -> scenario 10
       - قبلاً هم داخل محدوده بوده                          -> scenario 1/2/3
  7. رتبه > 550 (خارج از محدوده پاداش):
       - قبلاً داخل محدوده بوده                             -> scenario 11
       - قبلاً هم خارج بوده (یا داده‌ای نبوده)                -> scenario 4/5/6

ASSUMPTION (not covered by the user's 15 scenarios): a کارشناس missing from
the previous slot's table entirely (not top10-transition, not #1-transition)
is treated as "رتبه ثابت" (neutral scenario 2/5/8) rather than inventing a
16th "new entrant" scenario - flag to the user if this should read
differently.
"""

import os

import pandas as pd

from Senders.message import OutboundMessage

TOP_RANK_MAX = 10
REWARD_RANGE_MAX_RANK = 550
BASE_PERCENT = 0.15

# Guide doc appended to the end of every کارشناس message (user 2026-10-10).
GUIDE_URL = "https://docs.google.com/document/d/1S6KlwWhbtiRAyx8KpJmmENhqiSq4_fcptnlaxGb_L34/edit?usp=sharing"

# اسم خام از داده‌ی فروش (SP.54.SPK, فیلد AAName) -> اسم واقعی در پیام‌رسان.
# این ۵ نفر با اسم خام هیچ‌وقت در دایرکتوری پیام‌رسان پیدا نمی‌شدند (نه حتی
# با fallback حذف پسوند تیم توی Senders/send_message_v2.py) چون خودِ اسم
# غلط املایی/پسوند اشتباه داشت، نه فقط یک پسوند اضافه - تایید شده دستی توسط
# کاربر ۲۰۲۶-۰۹-۲۰ با سرچ مستقیم تو پیام‌رسان. فقط برای فیلد contact (سرچ/
# ارسال) استفاده می‌شه - کلید مقایسه‌ی رتبه با اسلات قبلی (prev_rank_by_name)
# و panel_user_id عمداً همون اسم خامِ فروش می‌مونن تا با تاریخچه‌ی
# outputs/*.csv (که با اسم خام نوشته شدن) قطع نشن.
CONTACT_NAME_CORRECTIONS = {
    "حانیه الهیاری سوره RW": "حانیه اللهیاری سوره RW",
    "رومینا ابشاری VP": "رومینا آبشاری VP",
    "سیده مریم راجزی همدانی RW": "مریم راجزی همدانی RW",
    "شیوا سلطانی آقاگلی NP (تست)": "شیوا سلطانی آقاگلی NP",
    "مائده سالمی مشهور NP": "مائده سالمی مشهور VP",
    # user 2026-10-10, checked by hand in the messenger after the
    # elan-padash-zaribvosoli-5040-18mehr announcement failed for them. No
    # other panel name equals any of these targets, so nobody gets two
    # messages. The نرگس entry only swaps the Arabic ي for the Persian ی
    # (the user confirmed the name; the raw spelling never matched).
    "ثمره حقگو RW1": "ثمره حقگو RW",
    "فاطمه موسوی RW1": "فاطمه موسوی RW",
    "نرگس مهتري علیائی RW": "نرگس مهتری علیائی RW",
}

_OUTPUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "outputs")

MONTH_NAMES = [
    "", "فروردین", "اردیبهشت", "خرداد", "تیر", "مرداد", "شهریور",
    "مهر", "آبان", "آذر", "دی", "بهمن", "اسفند",
]


def _bidi_isolate(text):
    """یه رشته‌ی عددی/لاتین (مثل "18:00") رو با LRM (U+200E) قبل و بعدش
    isolate می‌کنه تا داخل یه جمله‌ی فارسیِ RTL درست نمایش داده بشه.

    ⚠️ باگ واقعی که همین رو لازم کرد (۲۰۲۶-۰۹-۱۹، گزارش خلاصه‌ی مدیریتی):
    رشته‌ی "HH:MM" (دو عدد جدا با یه ":" خنثی) وقتی وسط متن فارسی می‌افتاد،
    الگوریتم bidi پیام‌رسان گاهی هر دو عدد رو کنار هم می‌چسبوند و ":" رو ته
    جمله می‌انداخت (مثلاً "1800:" به‌جای "18:00"). بدون این isolate، حتی
    strftime("%H:%M") کاملاً درست هم می‌تونه اونجا غلط نمایش داده بشه - این
    مشکل نمایش کلاینته، نه فرمت خودِ رشته."""
    return f"‎{text}‎"


def _fmt_hm(hour, minute):
    """"18:00" همیشه به فرم کامل HH:MM (دقیقه حذف نمی‌شه - طبق خواسته‌ی
    صریح کاربر ۲۰۲۶-۰۹-۲۰، برخلاف تلاش قبلی برای حذف دقیقه‌ی صفر). خروجی
    bidi-isolate شده."""
    return _bidi_isolate(f"{hour:02d}:{minute:02d}")


def _report_date_time(slot_jdt):
    date_str = f"{slot_jdt.day} {MONTH_NAMES[slot_jdt.month]} {slot_jdt.year}"
    if slot_jdt.hour == 23 and slot_jdt.minute == 59:
        time_str = _bidi_isolate("24:00")
    else:
        time_str = _fmt_hm(slot_jdt.hour, slot_jdt.minute)
    return date_str, time_str


def _parse_slot_label(filename):
    """"1405_06_24_1300.csv" -> (1405, 6, 24, 13, 0), or None if unparsable."""
    label = os.path.splitext(filename)[0]
    parts = label.split("_")
    if len(parts) != 4 or len(parts[3]) != 4:
        return None
    try:
        year, month, day = int(parts[0]), int(parts[1]), int(parts[2])
        hour, minute = int(parts[3][:2]), int(parts[3][2:])
    except ValueError:
        return None
    return (year, month, day, hour, minute)


def _previous_table(slot_jdt):
    """Most recent outputs/*.csv strictly older than slot_jdt, or None if
    this is the first slot ever run (no earlier file exists)."""
    if not os.path.isdir(_OUTPUT_DIR):
        return None

    current_key = (slot_jdt.year, slot_jdt.month, slot_jdt.day, slot_jdt.hour, slot_jdt.minute)
    best_key, best_path = None, None
    for filename in os.listdir(_OUTPUT_DIR):
        if not filename.endswith(".csv"):
            continue
        key = _parse_slot_label(filename)
        if key is None or key >= current_key:
            continue
        if best_key is None or key > best_key:
            best_key, best_path = key, os.path.join(_OUTPUT_DIR, filename)

    if best_path is None:
        return None
    return pd.read_csv(best_path, encoding="utf-8-sig")


def _fmt_amount(value):
    return f"{int(round(value)):,}"


def _fmt_percent(fraction):
    return f"{fraction * 100:g}"


def _fmt_ratio(value):
    """2 decimals, trailing zeros/point trimmed (e.g. 1200.00 -> 1,200)."""
    return f"{value:,.2f}".rstrip("0").rstrip(".")


def _rank_movement(rank, prev_rank):
    """None if no comparable previous rank; else ("better"|"same"|"worse", delta)."""
    if prev_rank is None:
        return None
    delta = prev_rank - rank
    if delta > 0:
        return ("better", delta)
    if delta < 0:
        return ("worse", -delta)
    return ("same", 0)


def _scenario_text(rank, prev_rank, has_previous_table, in_range, was_in_range):
    """in_range/was_in_range: درصد نهایی > پایه (now / previous slot) - not
    rank <= 550, because a zero ضریب وصول is outside the range whatever its
    rank (builder.py, user 2026-10-10)."""
    if not has_previous_table:
        return (
            "🚀 رقابت پاداش ویژه آغاز شد.\n"
            "از این گزارش به بعد، ضریب وصولی، رتبه، درصد نهایی پورسانت و پاداش برآوردی شما "
            "به‌صورت دوره‌ای محاسبه و اعلام می‌شود.\n"
            "هرچه ضریب بهتر شود، امکان رسیدن به رتبه و درصد پورسانت بالاتر بیشتر خواهد شد."
        )

    if rank == 1 and prev_rank == 1:
        return "👑 همچنان رتبه ۱ مسابقه در اختیار توست. حالا رقابت اصلی برای حفظ این جایگاه تا پایان طرح است؛ فاصله با رقبا را حفظ کن."
    if rank == 1:
        return "🥇 تبریک! با عملکرد این دوره به رتبه ۱ مسابقه رسیده‌ای. حالا هدف، تثبیت این جایگاه تا پایان رقابت است."
    if prev_rank == 1:
        return "🔥 رقابت در صدر جدول نزدیک شده و در این گزارش رتبه ۱ را واگذار کرده‌ای. فاصله قابل جبران است و با بهبود ضریب می‌توانی دوباره به صدر برگردی."

    movement = _rank_movement(rank, prev_rank)

    if in_range and rank <= TOP_RANK_MAX:
        if movement is None or movement[0] == "same":
            return "👑 همچنان جایگاهت در ۱۰ نفر برتر حفظ شده. در این سطح، حتی تغییر کوچک در ضریب می‌تواند رتبه‌ها را جابه‌جا کند؛ حفظ کیفیت عملکرد کلیدی است."
        if movement[0] == "better":
            return "🏆 در جمع ۱۰ نفر برتر هستی و نسبت به گزارش قبلی هم جایگاهت بهتر شده. حالا مهم‌ترین هدف، تثبیت این عملکرد تا پایان مسابقه است."
        return "🔔 همچنان در جمع ۱۰ نفر برتر هستی، اما نسبت به گزارش قبلی رتبه‌ات کاهش پیدا کرده. رقابت در این محدوده نزدیک است و امکان بازیابی جایگاه وجود دارد."

    if in_range:
        if not was_in_range:
            return "🎉 تبریک! با بهبود عملکردت تازه وارد محدوده پاداش شدی و از این گزارش مشمول پورسانت بالاتر هستی. حالا هدف بعدی، حفظ جایگاه و حرکت به پله بالاتر است."
        if movement is None or movement[0] == "same":
            return "✅ جایگاهت نسبت به گزارش قبلی حفظ شده. برای رفتن به پله بالاتر، حفظ کیفیت هر شماره و افزایش ضریب وصولی تعیین‌کننده است."
        if movement[0] == "better":
            return f"🚀 نسبت به گزارش قبلی {movement[1]} رتبه رشد کرده‌ای و وارد جایگاه بهتری شده‌ای. ادامه همین روند می‌تواند درصد پورسانت و مبلغ پاداشت را باز هم افزایش دهد."
        return f"⚠️ هنوز داخل محدوده پاداش هستی، اما نسبت به گزارش قبلی {movement[1]} رتبه افت کرده‌ای. فاصله قابل جبران است؛ هر بهبود در ضریب می‌تواند جایگاهت را دوباره بالا ببرد."

    if was_in_range:
        return "⚠️ در این گزارش از محدوده پاداش خارج شده‌ای؛ اما فاصله هنوز قابل جبران است. با بهبود ضریب وصولی می‌توانی دوباره وارد محدوده پاداش شوی."
    if movement is None or movement[0] == "same":
        return "🎯 رتبه‌ات نسبت به گزارش قبلی تغییری نکرده و فعلاً خارج از محدوده پاداشی. برای ورود به رقابت، باید فاصله ضریب با نفرات بالاتر را کاهش بدهی."
    if movement[0] == "better":
        return f"🔥 هنوز وارد محدوده پاداش نشده‌ای، اما نسبت به گزارش قبلی {movement[1]} رتبه رشد کرده‌ای. مسیرت درست است؛ ادامه همین روند می‌تواند تو را وارد محدوده پورسانت بالاتر کند."
    return f"📌 نسبت به گزارش قبلی {movement[1]} رتبه پایین‌تر آمده‌ای و هنوز خارج از محدوده پاداش هستی. تمرکز روی استفاده بهتر از هر شماره می‌تواند مسیر بازگشت را سریع‌تر کند."


def render(report, reward_id, slot):
    slot_jdt = report["slot_jdt"]
    table = report["table"]
    date_str, time_str = _report_date_time(slot_jdt)

    prev_table = _previous_table(slot_jdt)
    has_previous_table = prev_table is not None
    prev_rank_by_name = (
        dict(zip(prev_table["نام کارشناس"], prev_table["رتبه"])) if has_previous_table else {}
    )
    prev_percent_by_name = (
        dict(zip(prev_table["نام کارشناس"], prev_table["درصد نهایی پورسانت"])) if has_previous_table else {}
    )

    messages = []
    for _, row in table.iterrows():
        name = row["نام کارشناس"]
        contact_name = CONTACT_NAME_CORRECTIONS.get(name, name)
        rank = int(row["رتبه"])
        prev_rank = prev_rank_by_name.get(name)
        if prev_rank is not None:
            prev_rank = int(prev_rank)

        lines = [
            f"سلام {contact_name} عزیز 🌱",
            "🏆 گزارش پاداش ویژه فروش",
            f"📅 تاریخ گزارش: {date_str}",
            f"⏰ محاسبه تا ساعت: {time_str}",
            "",
            f"📊 رتبه فعلی: {rank}",
            f"🎯 ضریب وصولی فعلی: {_fmt_ratio(row['ضریب وصول'])}",
            f"💰 درصد نهایی پورسانت: {_fmt_percent(row['درصد نهایی پورسانت'])}٪",
            f"💵 پورسانت برآوردی تا این لحظه: {_fmt_amount(row['مبلغ پورسانت بر آوردی تا این لحظه'])} تومان",
            f"🎁 پاداش مازاد برآوردی: {_fmt_amount(row['پاداش مازاد بر آوردی'])} تومان",
            "",
            _scenario_text(
                rank, prev_rank, has_previous_table,
                in_range=float(row["درصد نهایی پورسانت"]) > BASE_PERCENT,
                was_in_range=float(prev_percent_by_name.get(name, 0)) > BASE_PERCENT,
            ),
            "",
            "📘 راهنمای رقابت:",
            GUIDE_URL,
        ]

        messages.append(OutboundMessage(
            reward_id=reward_id,
            slot=slot,
            panel_user_id=name,
            chat_user_id="",
            contact=contact_name,
            text="\n".join(lines),
        ))
    return messages
