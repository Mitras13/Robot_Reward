"""
padash-sarparast-hamkadeh-11-30mehr/render.py

One text message per همکده سرپرست (6 teams). Same number conventions as the
supervisor rewards: Persian digits with a plain Latin "," separator (the
Arabic separator U+066C made the messenger reverse digit groups), no
parenthesis directly before a number, **bold** rendered by the messenger.

Rank-change line compares with the previous real slot table
(outputs/YYYY_MM_DD_HHMM.csv).

CONTACTS maps the panel team name (سرپرستان ثبت کننده فاکتور) to the exact
messenger alias of the سرپرست. A team missing from CONTACTS gets no
message (logged as a warning).
"""

import logging
import os
import re

import pandas as pd

from Senders.message import OutboundMessage

from .builder import _OUTPUT_DIR, PRIZES_MILLION_TOMAN, prize_for_rank

logger = logging.getLogger(__name__)

TITLE = "🏆 **رقابت رشد وصولی سرپرستان فروش همکده**"

_FA_DIGITS = str.maketrans("0123456789", "۰۱۲۳۴۵۶۷۸۹")
_SLOT_CSV_RE = re.compile(r"^\d{4}_\d{2}_\d{2}_\d{4}\.csv$")

MONTH_NAMES = [
    "", "فروردین", "اردیبهشت", "خرداد", "تیر", "مرداد", "شهریور",
    "مهر", "آبان", "آذر", "دی", "بهمن", "اسفند",
]

# panel team name (whitespace-normalized) -> exact messenger alias.
# team -> سرپرست given by the user 2026-10-04; aliases from the messenger
# directory (search "سرپرست همکده").
CONTACTS = {
    "رکورد E": "شهرزاد کلانکی (سرپرست همکده)",
    "پرسپولیس****A+": "مهدی نفری (سرپرست فروش همکده)",
    "ارتش ستاره‌ها** B": " آزاده غفاری  (سرپرست همکده)",
    "نوبل D": "فاطمه فریدونی (سرپرست همکده)",
    "ایگلز* C": "مهری کرمی (سرپرست همکده)",
    "زئوس A *": "امیرحسین باغبانیان (سرپرست همکده)",
}


def _fa(value):
    return str(value).translate(_FA_DIGITS)


def _fmt_pct(value):
    s = f"{abs(value):.1f}".rstrip("0").rstrip(".")
    return f"{_fa(s)}٪"


def _fmt_growth(value):
    if value >= 0:
        return f"{_fmt_pct(value)} رشد"
    return f"{_fmt_pct(value)} افت"


def _fmt_million(value):
    # rounded to 1,000 تومان - expected/needed amounts are estimates
    return _fa(f"{int(round(value * 1_000)) * 1_000:,}")


def _display_name(team):
    # "*" in team names would break the messenger's **bold** markup
    return " ".join(team.replace("*", " ").split())


def _is_final_slot(slot_jdt):
    from . import requirements as req
    return slot_jdt >= req.CAMPAIGN_END.replace(second=0)


def _previous_ranks(slot_jdt):
    current = f"{slot_jdt.strftime('%Y_%m_%d_%H%M')}.csv"
    try:
        names = sorted(f for f in os.listdir(_OUTPUT_DIR) if _SLOT_CSV_RE.match(f) and f < current)
    except OSError:
        return {}
    if not names:
        return {}
    prev = pd.read_csv(os.path.join(_OUTPUT_DIR, names[-1]), encoding="utf-8-sig")
    return {row["sarparast"]: int(row["rank"]) for _, row in prev.iterrows()}


def _status_line(rank, prev_rank, final):
    prize = prize_for_rank(rank)
    if final:
        if prize:
            return f"🎉 **تبریک! شما با رتبه {_fa(rank)} برنده پاداش {_fa(prize)} میلیون تومانی شدید.**"
        return "🙏 این دوره به پایان رسید؛ از تلاش شما و تیمتون سپاسگزاریم."
    if rank == 1:
        return "👑 **شما در صدر رقابت هستید!** با حفظ روند فعلی، جایگاه اول رو قطعی کنید."
    if prev_rank is None:
        return None
    if prize and prize_for_rank(prev_rank) == 0:
        return f"🎉 **تبریک! وارد جمع {_fa(len(PRIZES_MILLION_TOMAN))} تیم برنده شدید.**"
    if not prize and prize_for_rank(prev_rank):
        return f"⚠️ **از جمع {_fa(len(PRIZES_MILLION_TOMAN))} تیم برنده خارج شدید!** هنوز فرصت برگشت دارید."
    if rank < prev_rank:
        return f"📈 **رتبه شما از {_fa(prev_rank)} به {_fa(rank)} بهتر شد.**"
    if rank > prev_rank:
        return f"📉 **رتبه شما از {_fa(prev_rank)} به {_fa(rank)} رسید؛** رقبا در حال پیشی گرفتن هستن."
    return "✅ جایگاه‌تون نسبت به گزارش قبل حفظ شده."


def _step_line(teams, row):
    rank = int(row["rank"])
    if rank == 1:
        return None
    above = teams[teams["rank"] == rank - 1].iloc[0]
    # actual needed to match the team above's growth on this team's own expected base
    needed = (above["growth_pct"] / 100 + 1) * row["expected_million"] - row["actual_million"]
    prize_above = prize_for_rank(rank - 1)
    prize_text = f" و پاداش {_fa(prize_above)} میلیون تومان" if prize_above else ""
    return (
        f"🎯 **فاصله تا رتبه {_fa(rank - 1)}{prize_text}:** حدود "
        f"**{_fmt_million(max(needed, 0))} تومان** وصولی بیشتر "
        f"یعنی رسیدن به {_fmt_growth(above['growth_pct'])}"
    )


def _person_text(teams, row, slot_jdt, final, prev_rank, overall_growth_pct):
    rank = int(row["rank"])
    prize = prize_for_rank(rank)
    if final:
        when = f"نتیجه نهایی از {_fa(11)} تا {_fa(30)} مهر"
    else:
        when = f"گزارش از {_fa(11)} مهر تا ساعت {_fa(slot_jdt.strftime('%H:%M'))} امروز {_fa(slot_jdt.day)} {MONTH_NAMES[slot_jdt.month]}"

    lines = [
        TITLE,
        "",
        f"👤 سرپرست تیم **{_display_name(row['sarparast'])}**",
        f"🕒 {when}",
        "",
        f"💰 **وصولی کل تیم:** {_fmt_million(row['actual_million'])} تومان",
        f"📊 **وصولی بازه قبل در همین مدت:** {_fmt_million(row['expected_million'])} تومان",
        f"📈 **نسبت رشد وصولی:** {_fmt_growth(row['growth_pct'])}",
        f"🏆 **رتبه {'نهایی' if final else 'فعلی'}:** {_fa(rank)} از {_fa(len(teams))}",
    ]
    if prize:
        label = "پاداش" if final else "پاداش برآوردی در صورت تثبیت رتبه فعلی"
        lines.append(f"🎁 **{label}:** {_fa(prize)} میلیون تومان")
    else:
        lines.append(f"🎁 **پاداش:** فعلاً خارج از جمع {_fa(len(PRIZES_MILLION_TOMAN))} تیم برنده")

    status = _status_line(rank, prev_rank, final)
    if status:
        lines += ["", status]
    if not final:
        step = _step_line(teams, row)
        if step:
            lines += ["", step]
        lines += [
            "",
            "📌 نسبت رشد = وصولی بازه جاری منهای وصولی بازه قبل، تقسیم بر وصولی بازه قبل - بازه قبل از ۲۱ شهریور و با همین تعداد روز و تا همین ساعت حساب می‌شه.",
            "",
            "🔥 **رشد وصولی بیشتر = رتبه بهتر = پاداش بیشتر**",
        ]
    return "\n".join(lines)


def render(report, reward_id, slot):
    teams = report["teams"]
    slot_jdt = report["slot_jdt"]
    final = _is_final_slot(slot_jdt)
    previous = _previous_ranks(slot_jdt)

    messages = []
    for _, row in teams.iterrows():
        name = row["sarparast"]
        contact = CONTACTS.get(name)
        if not contact:
            logger.warning("no messenger contact for sarparast team %r - skipped", name)
            continue
        messages.append(OutboundMessage(
            reward_id=reward_id,
            slot=slot,
            panel_user_id=name,
            chat_user_id="",
            contact=contact,
            text=_person_text(teams, row, slot_jdt, final, previous.get(name), report["overall_growth_pct"]),
        ))
    return messages
