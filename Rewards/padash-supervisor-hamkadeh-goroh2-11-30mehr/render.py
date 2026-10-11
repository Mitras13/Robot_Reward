"""
padash-supervisor-hamkadeh-goroh2-11-30mehr/render.py

One text message per ELIGIBLE team only (ضریب within tolerance - user
2026-10-03: "پیام فقط برای افراد واجد شرایط ارسال بشه"). Ineligible teams
get no message.

Layout = خانم فیضی's proposed supervisor text (user 2026-10-03), with:
  - "پاداش برآوردی در صورت تثبیت رتبه فعلی" wording (her suggestion)
  - one analytic line chosen by comparing with the previous real slot table
    (outputs/YYYY_MM_DD_HHMM.csv), first match wins:
      final slot > rank 1 > first report > newly ranked / entered prize
      zone > left prize zone > bigger prize > rank down > rank up > stable
  - a step line naming the average needed for the next better-paid rank

Numbers: Persian digits with a plain Latin "," thousands separator - the
Arabic separator U+066C made the messenger reverse the digit groups (tested
in the messenger 2026-10-03). No parenthesis directly before a number, same
reason.

Contacts: messenger aliases are "{name} (سوپروایزر همکده)" - looked up in the
company directory 2026-10-03 (CONTACTS below). A supervisor missing from
CONTACTS gets no message (logged as a warning).
"""

import logging
import os
import re

import pandas as pd

from Senders.message import OutboundMessage

from .builder import _OUTPUT_DIR, COE_TOLERANCE_PCT, GROUP_LABEL, PRIZES_MILLION_TOMAN, prize_for_rank

logger = logging.getLogger(__name__)

TITLE = f"🏆 گزارش رقابت سوپروایزرهای همکده | {GROUP_LABEL}"

_FA_DIGITS = str.maketrans("0123456789", "۰۱۲۳۴۵۶۷۸۹")
_SUFFIX_RE = re.compile(r"[\s\*]*(A\+|A|B|C|D|E)?\s*$")
_SLOT_CSV_RE = re.compile(r"^\d{4}_\d{2}_\d{2}_\d{4}\.csv$")

MONTH_NAMES = [
    "", "فروردین", "اردیبهشت", "خرداد", "تیر", "مرداد", "شهریور",
    "مهر", "آبان", "آذر", "دی", "بهمن", "اسفند",
]

# cleaned panel name -> exact messenger alias (directory lookup 2026-10-03).
# Not found in the directory: مژگان فلاح نژاد کفشگر کلائی.
CONTACTS = {
    "احسان زارعی": "احسان زارعی (سوپروایزر همکده)",
    "احسان شریف زاده": "احسان شریف زاده (سوپروایزر همکده)",
    "الهام اسماعیلی": "الهام اسماعیلی (سوپروایزر همکده)",
    "امید حیدرپور": "امید حیدرپور (سوپروایزر همکده)",
    "امیرحسن خدادادی": "امیرحسن خدادادی (سوپروایزر همکده)",
    "امین افخمی": "امین افخمی نائینی (سوپروایزر همکده)",
    "بهنام ساری نژاد": "بهنام ساری نژاد (سوپروایزر همکده)",
    "زهرا زنگنه": "زهرا زنگنه (سوپروایزر همکده)",
    "سارا بنیاد": "سارا بنیاد (سوپروایزر همکده)",
    "ساغر مهین دوست": "ساغر مهین دوست (سوپروایزر همکده)",
    "سحر حبیبی فیضی": "سحر حبیبی فیضی (سوپروایزر همکده)",
    "سهند صدری": "سهند صدری (سوپروایزر همکده)",
    "سپیده سیفی بجه میر": "سپیده سیفی بجه میر (سوپروایزر همکده)",
    "سکینه یحیایی": "سکینه یحیائی (سوپروایزر همکده)",  # messenger spells it with ئ
    "شیدا گودرزی": "شیدا گودرزی (سوپروایزر همکده)",
    "صبا افشاری": "صبا افشاری (سوپروایزر همکده)",
    "طاها طاهایی": "طاها طاهایی (سوپروایزر همکده)",
    "طیبه عبدالملکی": "طیبه عبدالملکی (سوپروایزر همکده)",
    "علیرضا هادلی": "علیرضا هادلی (سوپروایزر همکده)",
    "علیرضا کرمی": "علیرضا کرمی (سوپروایزر همکده)",
    "فاطمه جعفری": "فاطمه جعفری (سوپروایزر همکده)",
    "فاطمه صحرایی": "فاطمه صحرایی (سوپروایزر همکده)",
    "فرزان گلپایگانی": "فرزان گلپایگانی (سوپروایزر همکده)",
    "لیلا رضایی": "لیلا رضایی (سوپروایزر همکده)",
    "محدثه شادمانی": "محدثه شادمانی (سوپروایزر همکده)",
    "محمد فتحعلی": "محمد فتحعلی (سوپروایزر همکده )",
    "معصومه جعفری": "معصومه جعفری (سوپروایزر همکده)",
    "مهدی زیدی": "مهدی زیدی (سوپروایزر همکده)",
    "مهدی سپه وند": "مهدی سپه وند (سوپروایزر همکده)",
    "مهدیه بختیاری": "مهدیه بختیاری (سوپروایزر همکده)",
    "میرحجت سید حمزه": "میرحجت سید حمزه (سوپروایزر همکده)",
    "میلاد نظری": "میلاد نظری (سوپروایزر همکده)",
    "نسیم فاتح نیا": "نسیم فاتح نیا راویز (سوپروایزر همکده)",
    "نسیم نظریان": "نسیم نظریان (سوپروایزر همکده)",
    "نگین رسولی": "نگین رسولی (سوپروایزر همکده)",
}


def _fa(value):
    return str(value).translate(_FA_DIGITS)


def _toman(value):
    return _fa(f"{int(round(value)):,}")


def _prize_toman(million):
    return f"{_toman(million * 1_000_000)} تومان"


def _pct(value):
    return _fa(f"{abs(value):.1f}".rstrip("0").rstrip(".")) + "٪"


def display_name(supervisor):
    return re.sub(r"\s+", " ", _SUFFIX_RE.sub("", supervisor.replace("*", " "))).strip()


def _is_final_slot(slot_jdt):
    from . import requirements as req
    return slot_jdt >= req.CAMPAIGN_END.replace(second=0)


def _previous_ranks(slot_jdt):
    """{supervisor: rank or None(ineligible)} from the latest real slot table
    before this one; {} if none (= first report)."""
    current = f"{slot_jdt.strftime('%Y_%m_%d_%H%M')}.csv"
    try:
        names = sorted(f for f in os.listdir(_OUTPUT_DIR) if _SLOT_CSV_RE.match(f) and f < current)
    except OSError:
        return {}
    if not names:
        return {}
    prev = pd.read_csv(os.path.join(_OUTPUT_DIR, names[-1]), encoding="utf-8-sig")
    return {" ".join(str(r["supervisor"]).split()): (int(r["rank"]) if pd.notna(r["rank"]) else None)
            for _, r in prev.iterrows()}


def _target_rank(rank):
    """Nearest better rank whose prize is bigger than this rank's."""
    current = prize_for_rank(rank)
    for t in range(rank - 1, 0, -1):
        if prize_for_rank(t) > current:
            return t
    return None


def _analytic_lines(rank, prev_rank, has_previous, final, prize_count):
    prize = prize_for_rank(rank)
    if final:
        if prize:
            return [f"🏁 رقابت به پایان رسید. تیم شما با رتبه {_fa(rank)} پاداش {_prize_toman(prize)} را کسب کرد! 🎉"]
        return ["🏁 رقابت به پایان رسید. از تلاش شما و تیمتان در این رقابت سپاسگزاریم."]
    if rank == 1:
        return ["🏆🔥 تیم شما در صدر رقابت قرار دارد.",
                "برای حفظ این جایگاه تا پایان رقابت پرقدرت ادامه دهید."]
    if not has_previous:
        return ["🚀 رقابت آغاز شده است.",
                "رتبه فعلی تیم شما نقطه شروع است و تا پایان طرح می‌تواند تغییر کند."]
    if prev_rank is None:
        # not ranked in the previous report (ineligible or new)
        if prize:
            return [f"🎉 تبریک! تیم شما وارد جمع {_fa(prize_count)} تیم برتر شد.",
                    "با حفظ و بهبود میانگین وصولی، جایگاه خود را ارتقا دهید."]
        return ["🚀 تیم شما وارد رتبه‌بندی رقابت شد.",
                "با افزایش میانگین وصولی، به محدوده پاداش نزدیک‌تر شوید."]
    prev_prize = prize_for_rank(prev_rank)
    if prize and not prev_prize:
        return [f"🎉 تبریک! تیم شما وارد جمع {_fa(prize_count)} تیم برتر شد.",
                "با حفظ و بهبود میانگین وصولی، جایگاه خود را ارتقا دهید."]
    if prev_prize and not prize:
        return ["🔄 در گزارش فعلی تیم شما از محدوده پاداش خارج شده است.",
                f"فاصله تا ورود مجدد: {_fa(rank - prize_count)} رتبه"]
    if prize > prev_prize:
        return ["🚀 عملکرد تیم شما باعث ارتقا به پاداش بالاتر شده است.",
                "رتبه بهتر، پاداش بیشتری برای شما می‌سازد."]
    if rank > prev_rank:
        return [f"⚠️ رتبه تیم شما نسبت به گزارش قبل از {_fa(prev_rank)} به {_fa(rank)} کاهش یافته است.",
                "با افزایش میانگین وصولی امکان جبران وجود دارد."]
    if rank < prev_rank:
        return [f"📈 رتبه تیم شما نسبت به گزارش قبل از {_fa(prev_rank)} به {_fa(rank)} بهتر شده است."]
    return ["✅ جایگاه تیم شما نسبت به گزارش قبل ثابت مانده است.",
            "برای رسیدن به رتبه بالاتر، همچنان فرصت دارید."]


def _step_line(eligible, rank):
    target = _target_rank(rank) if rank > 1 else None
    if target is None:
        return None
    target_avg = eligible[eligible["rank"] == target]["avg_toman"].iloc[0]
    return (f"🎯 با رسیدن میانگین وصولی به بیش از {_toman(target_avg)} تومان، "
            f"به رتبه {_fa(target)} و پاداش {_prize_toman(prize_for_rank(target))} می‌رسید.")


def _team_text(eligible, team, slot_jdt, final, prev_rank, has_previous):
    rank = int(team["rank"])
    prize = prize_for_rank(rank)
    prize_count = len(PRIZES_MILLION_TOMAN)
    coe_change = team["coe_vs_overall_pct"]
    coe_word = "بالاتر از" if coe_change >= 0 else "پایین‌تر از"
    time_str = "۲۴:۰۰" if (slot_jdt.hour == 23 and slot_jdt.minute == 59) else _fa(slot_jdt.strftime("%H:%M"))

    lines = [
        TITLE if not final else f"{TITLE} | نتیجه نهایی",
        f"👤 {display_name(team['supervisor'])}",
        f"🕒 گزارش تا: {_fa(slot_jdt.day)} {MONTH_NAMES[slot_jdt.month]} ساعت {time_str}",
        "",
        f"👥 تعداد کارشناسان مبنا: {_fa(int(team['base_count']))} نفر",
        f"💰 وصولی تیم: {_toman(team['paid_toman'])} تومان",
        f"📊 میانگین وصولی به ازای کارشناس: {_toman(team['avg_toman'])} تومان",
        f"📈 تغییر ضریب وصولی: {_pct(coe_change)} {coe_word} میانگین کل",
        f"🏆 رتبه {'نهایی' if final else 'فعلی'}: {_fa(rank)}",
    ]
    if final:
        lines.append(f"🎁 پاداش نهایی: {_prize_toman(prize)}" if prize else f"🎁 پاداش: خارج از {_fa(prize_count)} رتبه برتر")
    else:
        lines.append(
            f"🎁 پاداش برآوردی در صورت تثبیت رتبه فعلی: {_prize_toman(prize)}" if prize
            else f"🎁 پاداش برآوردی: فعلاً خارج از {_fa(prize_count)} رتبه برتر"
        )
    lines.append(f"📌 شرط دریافت پاداش: افت ضریب حداکثر {_fa(COE_TOLERANCE_PCT)}٪ نسبت به میانگین کل")
    lines += [""] + _analytic_lines(rank, prev_rank, has_previous, final, prize_count)
    if not final:
        step = _step_line(eligible, rank)
        if step:
            lines += ["", step]
    lines += ["", "🔥 میانگین وصولی بالاتر + حفظ ضریب = رتبه و پاداش بهتر"]
    return "\n".join(lines)


def render(report, reward_id, slot):
    teams = report["teams"]
    slot_jdt = report["slot_jdt"]
    final = _is_final_slot(slot_jdt)
    previous = _previous_ranks(slot_jdt)
    has_previous = bool(previous)
    eligible = teams[teams["eligible"]]

    messages = []
    for _, team in eligible.iterrows():
        name = display_name(team["supervisor"])
        contact = CONTACTS.get(name)
        if not contact:
            logger.warning("'%s': no messenger contact for supervisor '%s' - skipped", reward_id, team["supervisor"])
            continue
        prev_rank = previous.get(" ".join(str(team["supervisor"]).split())) if has_previous else None
        messages.append(OutboundMessage(
            reward_id=reward_id,
            slot=slot,
            panel_user_id=team["supervisor"],
            chat_user_id="",
            contact=contact,
            text=_team_text(eligible, team, slot_jdt, final, prev_rank, has_previous),
        ))
    return messages
