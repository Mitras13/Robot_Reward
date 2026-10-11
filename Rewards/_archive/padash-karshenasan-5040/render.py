"""
padash-karshenasan-5040/render.py

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

Manager summary (added 2026-09-16, per user request, reusing the same
MANAGER_CONTACTS/greeting text approved for the sibling hamkadeh reward):
one extra message per entry in MANAGER_CONTACTS is prepended to the list,
before any کارشناس message, with slot-level aggregates instead of a
per-person report - total پورسانت برآوردی, total پاداش مازاد برآوردی, and
this slot's رتبه ۱ (name + ضریب وصول). No headcount/eligibility lines and
no وصول کل/کارتابلی lines - user explicitly asked to leave those out.
"""

import csv
import os

import pandas as pd

from Senders.message import OutboundMessage

TOP_RANK_MAX = 10
REWARD_RANGE_MAX_RANK = 550

# مسیر config/rewards.csv نسبت به همین فایل (Rewards/padash-karshenasan-5040/ ->
# دو پوشه بالاتر -> config/). فقط برای خوندن valid_from همین پاداش (تاریخ
# شروع بازه) - نه برای هیچ تصمیم زمان‌بندی‌ای، اونش کار tick.py/scheduling.py
# است.
_REWARDS_CSV_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "..", "config", "rewards.csv"
)

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
}

# مدیرانی که به‌جای پیام شخصی کارشناس، خلاصه‌ی مدیریتی همان اسلات را
# می‌گیرند. تا ۲۰۲۶-۰۹-۲۰ این خلاصه به ۴ مدیر جدا (فیضی/زمانی/مدنی/طارمی)
# فرستاده می‌شد؛ طبق تصمیم کاربر همان تاریخ، این ۴ نفر حذف و به‌جایش گروه
# «گزارشات پاداش» اضافه شد - میترا سرخوش (اضافه‌شده همان روز) جداگانه
# می‌ماند. contact برای اشخاص همان رشته‌ی دفترچه تلفن است؛ برای گروه چون سه
# entity هم‌نام («گزارشات پاداش» - دو کانال + یک گروه) در دایرکتوری هست،
# عمداً از Username دقیق (نه Alias) استفاده شده تا ابهامی نماند - تست شد،
# فقط همین یکی را برمی‌گرداند.
#
# نکته‌ی کلیدی که همین تصمیم را ممکن کرد: send_message_v2._clear_conversation
# از قبل، برای هر مخاطبی که IsEntity=True باشه (گروه/کانال)، پاک‌کردن
# تاریخچه رو خودکار رد می‌کنه (session_id گروه/کانال resolve نمی‌شه) - پس
# «این چت پاک نشه» نیازی به تغییر کد سندر نداشت، رفتار پیش‌فرض موجود همینه.
# گروه «گزارشات پاداش» موقتاً غیرفعاله (کاربر ۲۰۲۶-۰۹-۲۲: "برای گروه
# گزارشات پاداش فعلا هیچ پیامی ارسال نکن") - commentِ زیر نگه داشته شده تا
# راحت برگرده، حذف کامل نشده.
MANAGER_CONTACTS = [
    "میترا سرخوش",
    # "group-smrezvanmadani-1789890446796",
]

# گزارش جامع اکسل (builder.py: report["manager_excel_path"]) - جدا از
# MANAGER_CONTACTS بالا (که خلاصه‌ی متنی می‌گیرند) - طبق درخواست کاربر
# ۲۰۲۶-۰۹-۲۲، این دو مدیر فایل اکسل کامل رو به‌عنوان پیوست می‌گیرند.
EXCEL_REPORT_CONTACTS = [
    "مجتبی شیرازی فراشاه (مدیر فروش 5040)",
    "امید کاظمی (مدیر فروش 5040)",
]

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


def _scenario_text(rank, prev_rank, has_previous_table):
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

    if rank <= TOP_RANK_MAX:
        if movement is None or movement[0] == "same":
            return "👑 همچنان جایگاهت در ۱۰ نفر برتر حفظ شده. در این سطح، حتی تغییر کوچک در ضریب می‌تواند رتبه‌ها را جابه‌جا کند؛ حفظ کیفیت عملکرد کلیدی است."
        if movement[0] == "better":
            return "🏆 در جمع ۱۰ نفر برتر هستی و نسبت به گزارش قبلی هم جایگاهت بهتر شده. حالا مهم‌ترین هدف، تثبیت این عملکرد تا پایان مسابقه است."
        return "🔔 همچنان در جمع ۱۰ نفر برتر هستی، اما نسبت به گزارش قبلی رتبه‌ات کاهش پیدا کرده. رقابت در این محدوده نزدیک است و امکان بازیابی جایگاه وجود دارد."

    if rank <= REWARD_RANGE_MAX_RANK:
        was_in_range = prev_rank is not None and prev_rank <= REWARD_RANGE_MAX_RANK
        if not was_in_range:
            return "🎉 تبریک! با بهبود عملکردت تازه وارد محدوده پاداش شدی و از این گزارش مشمول پورسانت بالاتر هستی. حالا هدف بعدی، حفظ جایگاه و حرکت به پله بالاتر است."
        if movement is None or movement[0] == "same":
            return "✅ جایگاهت نسبت به گزارش قبلی حفظ شده. برای رفتن به پله بالاتر، حفظ کیفیت هر شماره و افزایش ضریب وصولی تعیین‌کننده است."
        if movement[0] == "better":
            return f"🚀 نسبت به گزارش قبلی {movement[1]} رتبه رشد کرده‌ای و وارد جایگاه بهتری شده‌ای. ادامه همین روند می‌تواند درصد پورسانت و مبلغ پاداشت را باز هم افزایش دهد."
        return f"⚠️ هنوز داخل محدوده پاداش هستی، اما نسبت به گزارش قبلی {movement[1]} رتبه افت کرده‌ای. فاصله قابل جبران است؛ هر بهبود در ضریب می‌تواند جایگاهت را دوباره بالا ببرد."

    was_in_range = prev_rank is not None and prev_rank <= REWARD_RANGE_MAX_RANK
    if was_in_range:
        return "⚠️ در این گزارش از محدوده پاداش خارج شده‌ای؛ اما فاصله هنوز قابل جبران است. با بهبود ضریب وصولی می‌توانی دوباره وارد محدوده پاداش شوی."
    if movement is None or movement[0] == "same":
        return "🎯 رتبه‌ات نسبت به گزارش قبلی تغییری نکرده و فعلاً خارج از محدوده پاداشی. برای ورود به رقابت، باید فاصله ضریب با نفرات بالاتر را کاهش بدهی."
    if movement[0] == "better":
        return f"🔥 هنوز وارد محدوده پاداش نشده‌ای، اما نسبت به گزارش قبلی {movement[1]} رتبه رشد کرده‌ای. مسیرت درست است؛ ادامه همین روند می‌تواند تو را وارد محدوده پورسانت بالاتر کند."
    return f"📌 نسبت به گزارش قبلی {movement[1]} رتبه پایین‌تر آمده‌ای و هنوز خارج از محدوده پاداش هستی. تمرکز روی استفاده بهتر از هر شماره می‌تواند مسیر بازگشت را سریع‌تر کند."


def _manager_summary_text(table, date_str, time_str, period_start_str):
    total_commission = int(table["مبلغ پورسانت بر آوردی تا این لحظه"].sum())
    total_extra_reward = int(table["پاداش مازاد بر آوردی"].sum())

    if period_start_str:
        period_line = f"از تاریخ {period_start_str} تا تاریخ {date_str} ساعت {time_str}"
    else:
        period_line = f"تا تاریخ {date_str} ساعت {time_str}"

    lines = [
        "با سلام و احترام",
        "📊 خلاصه‌ی مدیریتی پاداش ویژه فروش (5040)",
        period_line,
        "",
        f"💰 مجموع پورسانت برآوردی: {_fmt_amount(total_commission)} تومان",
        f"🎁 مجموع پاداش مازاد برآوردی: {_fmt_amount(total_extra_reward)} تومان",
    ]

    if not table.empty:
        top_row = table.loc[table["رتبه"].idxmin()]
        lines.append(
            f"👑 نفر اول این لحظه: {top_row['نام کارشناس']}، ضریب وصولی {_fmt_ratio(top_row['ضریب وصول'])}"
        )

    return "\n".join(lines)


def render(report, reward_id, slot):
    slot_jdt = report["slot_jdt"]
    table = report["table"]
    date_str, time_str = _report_date_time(slot_jdt)
    period_start_str = _period_start_date_str(reward_id)

    prev_table = _previous_table(slot_jdt)
    has_previous_table = prev_table is not None
    prev_rank_by_name = (
        dict(zip(prev_table["نام کارشناس"], prev_table["رتبه"])) if has_previous_table else {}
    )

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
                text=f"📎 گزارش جامع طرح ویژه پاداش رتبه‌بندی کارشناسان 5040 - {date_str} ساعت {time_str}",
                image=excel_path,
            ))

    # گزارش مدیریتی تصویری پایان بازه (فقط روی آخرین اسلات، management_image.py
    # وجودش رو تضمین می‌کنه) - مقصد نهایی طبق درخواست کاربر ۲۰۲۶-۰۹-۲۲ گروه
    # «گزارشات پاداش»ه، ولی چون همون گروه چند پیام قبل موقتاً غیرفعال شد و
    # کاربر صریحاً خواست این گزارش رو اول برای تست به میترا سرخوش بفرستم،
    # فعلاً مقصدش همینه - MANAGEMENT_IMAGE_TARGET رو به گروه (زیر، comment
    # شده) برگردون وقتی کاربر گزارش تست رو تایید کرد.
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
            text=f"🧪 تست گزارش مدیریتی پایان بازه - طرح 5040 ({date_str} ساعت {time_str})",
            image=management_image_path,
        ))

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
            _scenario_text(rank, prev_rank, has_previous_table),
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
