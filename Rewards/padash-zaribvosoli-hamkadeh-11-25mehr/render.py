"""
padash-zaribvosoli-hamkadeh-11-25mehr/render.py

One plain-text OutboundMessage per active کارشناس in builder.py's table
(everyone with paid_coe > 0, including those outside the top 250 - they get
the distance to rank 250 instead of a commission increase).

Message wording is the exact text the user gave 2026-10-03 (with **bold**,
rendered by the messenger; numbers in Persian digits). Variants derived from
that same text:
  - in a tier with a better tier above it: the "فقط یک قدم" block naming the
    next tier's last rank, the ضریب وصولی currently holding it, and its
    increase/final commission.
  - top tier (rank 1-2): no next tier - "بالاترین پله" block instead.
  - outside the top 250: base commission only, the step block targets
    entering the top 250.
  - final slot (1405/07/25 23:59): "نتیجه نهایی" wording, no step block,
    thank-you closing line.

The first line must stay "سلام {name} عزیز ..." - Senders/send_message.py
uses it as the delivery-confirmation signature.

contact = panel_user_id = کارشناس name exactly as SP.HK.SPK returns it
(AAName) - same identity convention as the other همکده rewards.
"""

import os
import re

import pandas as pd

from Senders.message import OutboundMessage

from .builder import _OUTPUT_DIR, BASE_COMMISSION_PCT, REWARDED_COUNT, TIERS, final_commission_pct

# Only real slot tables (outputs/YYYY_MM_DD_HHMM.csv) - preview_* files never
# count as the previous report.
_SLOT_CSV_RE = re.compile(r"^\d{4}_\d{2}_\d{2}_\d{4}\.csv$")

PLAN_NAME = "طرح رقابت ویژه ضریب وصولی همکده"

MONTH_NAMES = [
    "", "فروردین", "اردیبهشت", "خرداد", "تیر", "مرداد", "شهریور",
    "مهر", "آبان", "آذر", "دی", "بهمن", "اسفند",
]

# Thousands separator stays a plain Latin "," (user test in the messenger
# 2026-10-03): the Arabic separator U+066C made the messenger show the digit
# groups in reversed order (۴۰٬۹۸۰٬۰۰۰ -> ۰۰۰٬۹۸۰٬۴۰); "," renders correctly.
_FA_DIGITS = str.maketrans("0123456789", "۰۱۲۳۴۵۶۷۸۹")

# Panel name -> messenger name, where the two are spelled differently and the
# directory search finds nobody (user 2026-10-06).
CONTACT_OVERRIDES = {
    "زهرا درویش DJ": "زهرادرویش DJ",
    "مهنازخورشیدی‌ فر DJ": "مهناز خورشیدی‌ فر DJ",
}


def _fa(value):
    return str(value).translate(_FA_DIGITS)


def _fmt_pct(value):
    s = f"{value:.2f}".rstrip("0").rstrip(".")
    return f"{_fa(s)}٪"


def _fmt_coe(value):
    s = f"{value:,.2f}"
    if "." in s:
        s = s.rstrip("0").rstrip(".")
    return _fa(s)


def _is_final_slot(slot_jdt):
    from . import requirements as req
    return slot_jdt >= req.CAMPAIGN_END.replace(second=0)


def _next_tier(rank):
    """(target last-rank, increase %) of the next better tier, or None if
    already in the top tier."""
    better = None
    for last_rank, increase_pct in TIERS:
        if last_rank < rank:
            better = (last_rank, increase_pct)
        else:
            break
    return better


def _coe_at_rank(table, target_rank):
    """ضریب وصولی of whoever currently holds target_rank (or the closest
    rank above it, since tied ranks can skip numbers)."""
    held = table[table["rank"] <= target_rank]
    if held.empty:
        return None
    return float(held["paid_coe"].min())


def _previous_table(slot_jdt):
    """{name: (rank, final_commission_pct)} from the latest real slot table
    before this slot, or {} if this is the first report."""
    current = f"{slot_jdt.strftime('%Y_%m_%d_%H%M')}.csv"
    try:
        names = sorted(f for f in os.listdir(_OUTPUT_DIR) if _SLOT_CSV_RE.match(f) and f < current)
    except OSError:
        return {}
    if not names:
        return {}
    prev = pd.read_csv(os.path.join(_OUTPUT_DIR, names[-1]), encoding="utf-8-sig")
    return {
        row["کارشناس"]: (int(row["rank"]), float(row["final_commission_pct"]))
        for _, row in prev.iterrows()
    }


def _change_line(prev, rank, final_pct):
    """Rank-change line vs. the previous report (user 2026-10-03, all 5
    proposed scenarios approved). None when unchanged/no previous."""
    if prev is None:
        return None
    prev_rank, prev_pct = prev
    if rank == prev_rank:
        return None
    if prev_rank <= REWARDED_COUNT < rank:
        return (
            f"⚠️ **از جمع {_fa(REWARDED_COUNT)} نفر برتر خارج شدید و افزایش پورسانت‌تون فعلاً متوقف شده!** "
            "با کمی تلاش می‌تونید دوباره برگردید."
        )
    if final_pct < prev_pct:
        return (
            f"⚠️ **رتبه شما از {_fa(prev_rank)} به {_fa(rank)} رسید و پورسانت نهایی‌تون از "
            f"{_fmt_pct(prev_pct)} به {_fmt_pct(final_pct)} کاهش پیدا کرد!** "
            "همکاراتون در حال پیشی‌گرفتن هستن؛ هنوز فرصت برگشت دارید."
        )
    if final_pct > prev_pct:
        return (
            f"🎉 **تبریک! رتبه شما از {_fa(prev_rank)} به {_fa(rank)} رسید و پورسانت نهایی‌تون از "
            f"{_fmt_pct(prev_pct)} به {_fmt_pct(final_pct)} افزایش پیدا کرد!**"
        )
    if rank > prev_rank:
        return f"📉 رتبه شما از {_fa(prev_rank)} به {_fa(rank)} رسید؛ هنوز در همین پله هستید، مراقب جایگاه‌تون باشید."
    return f"📈 رتبه شما از {_fa(prev_rank)} به {_fa(rank)} بهتر شد."


def _step_block(table, rank):
    target = _next_tier(rank)
    if target is None:
        top_final = final_commission_pct(TIERS[0][1])
        return [
            "🎯 **شما در بالاترین پله پاداش هستید!**",
            "",
            f"با حفظ ضریب وصولی، جایگاهتون رو تا پایان طرح نگه دارید و پورسانت **{_fmt_pct(top_final)}** رو قطعی کنید! 👑",
        ]
    target_rank, target_increase = target
    target_coe = _coe_at_rank(table, target_rank)
    target_final = final_commission_pct(target_increase)
    if rank > REWARDED_COUNT:
        goal = f"وارد جمع {_fa(REWARDED_COUNT)} نفر برتر بشید"
    else:
        goal = f"به رتبه {_fa(target_rank)} برسید"
    return [
        "🎯 **فقط یک قدم تا پورسانت بیشتر!**",
        "",
        f"با رسیدن ضریب وصولی شما به بیش از **{_fmt_coe(target_coe)}**، می‌تونید {goal} "
        f"و افزایش پورسانت‌تون رو به **{_fmt_pct(target_increase)}** برسونید؛ "
        f"یعنی پورسانت نهایی **{_fmt_pct(target_final)}**! 🚀",
    ]


def _person_text(table, row, slot_jdt, final, prev):
    rank = int(row["rank"])
    increase_pct = row["increase_pct"]

    lines = [
        f"سلام {row['کارشناس']} عزیز 🌱",
        "",
        f"🏁 **{PLAN_NAME}**",
        "",
    ]
    if final:
        lines.append(f"نتیجه نهایی شما از {_fa(11)} مهر تا پایان {_fa(slot_jdt.day)} {MONTH_NAMES[slot_jdt.month]}:")
    else:
        lines.append(f"گزارش عملکرد شما از {_fa(11)} مهر تا ساعت {_fa(slot_jdt.strftime('%H:%M'))} امروز:")
    lines += [
        "",
        f"📈 **ضریب وصولی:** {_fmt_coe(row['paid_coe'])}",
        f"🏅 **رتبه {'نهایی' if final else 'فعلی'}:** {_fa(rank)} از {_fa(len(table))} نفر",
    ]
    if increase_pct > 0:
        lines += [
            f"⬆️ **افزایش پورسانت:** {_fmt_pct(increase_pct)}",
            f"💰 **پورسانت نهایی شما:** {_fmt_pct(row['final_commission_pct'])} (پورسانت پایه: {_fmt_pct(BASE_COMMISSION_PCT)})",
        ]
    else:
        lines += [
            f"⬆️ **افزایش پورسانت:** فعلاً خارج از جمع {_fa(REWARDED_COUNT)} نفر برتر",
            f"💰 **پورسانت شما:** {_fmt_pct(BASE_COMMISSION_PCT)} (پورسانت پایه)",
        ]

    change = _change_line(prev, rank, float(row["final_commission_pct"]))
    if change:
        lines += ["", change]

    if final:
        lines += [
            "",
            "💡 یادتون باشه: ضریب وصولی بالاتر = رتبه بهتر = پورسانت بیشتر",
            "",
            "**از تلاش و همراهی شما در این طرح سپاسگزاریم! 🙏**",
        ]
    else:
        lines += [""] + _step_block(table, rank) + [
            "",
            "💡 یادتون باشه: ضریب وصولی بالاتر = رتبه بهتر = پورسانت بیشتر",
            "",
            "**با قدرت ادامه بدید؛ فرصت پیشرفت هنوز باقیه! 💪**",
        ]
    return "\n".join(lines)


def render(report, reward_id, slot):
    table = report["table"]
    slot_jdt = report["slot_jdt"]
    final = _is_final_slot(slot_jdt)
    previous = _previous_table(slot_jdt)

    messages = []
    for _, row in table.iterrows():
        name = row["کارشناس"]
        messages.append(OutboundMessage(
            reward_id=reward_id,
            slot=slot,
            panel_user_id=name,
            chat_user_id="",
            contact=CONTACT_OVERRIDES.get(name, name),
            text=_person_text(table, row, slot_jdt, final, previous.get(name)),
        ))
    return messages
