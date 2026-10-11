"""
padash-gloroshen-5040-15mehr-10aban/render.py

One message per کارشناس in the current top 40 (prized positions only, user
2026-10-07). Progress messages on every slot, a final result on 10 آبان
23:59 (report["is_final"]). Text only - the poster is never sent (user 2026-10-07).

Each progress message: invoice count, position + prize tier, prize so far,
change vs the previous slot's position, and the gap to the next better tier.

contact = panel_user_id = "ثبت کننده" exactly as in the raw 54.FCP export -
the same convention the other 5040 کارشناس rewards send to; only the
greeting drops the team suffix.
"""

import glob
import os
import re

import pandas as pd

from Senders.message import OutboundMessage

from .builder import TIERS

_HERE = os.path.dirname(os.path.abspath(__file__))
_OUTPUT_DIR = os.path.join(_HERE, "outputs")

# panel name -> exact messenger chat name, where the two differ (user
# 2026-10-10: the panel's "ابشاری" is "آبشاری" in the messenger directory).
# Only `contact` uses this; panel_user_id keeps the panel name.
CONTACT_OVERRIDES = {
    "رومینا ابشاری VP": "رومینا آبشاری VP",
}

_TEAM_SUFFIX_RE = re.compile(r"\s+[A-Za-z][A-Za-z0-9+]*(\s+\d+)?$")
_ACCOUNT_NUMBER_RE = re.compile(r"\s*\(?\d+\)?$")
_FA_DIGITS = str.maketrans("0123456789", "۰۱۲۳۴۵۶۷۸۹")

MONTH_NAMES = [
    "", "فروردین", "اردیبهشت", "خرداد", "تیر", "مرداد", "شهریور",
    "مهر", "آبان", "آذر", "دی", "بهمن", "اسفند",
]

_RULE_LINE = ("📌 ملاک: فقط تعداد فاکتورهای وصولی کارتابلی پک ضد لک گلورشن "
              "با تاریخ وصول ۱۵ مهر تا ۱۰ آبان (تاریخ ثبت مهم نیست). "
              "در تعداد برابر، مبلغ کل همین فاکتورها تعیین‌کننده است.")


def _fa(value):
    return str(value).translate(_FA_DIGITS)


def _money(toman):
    return _fa(f"{int(toman):,}")


def _display_name(name):
    short = _TEAM_SUFFIX_RE.sub("", " ".join(str(name).split()))
    return _ACCOUNT_NUMBER_RE.sub("", short) or name


def _when(jdt):
    return f"{_fa(jdt.day)} {MONTH_NAMES[jdt.month]} ساعت {_fa(jdt.strftime('%H:%M'))}"


def _previous_positions(slot_jdt):
    label = slot_jdt.strftime("%Y_%m_%d_%H%M")
    older = sorted(p for p in glob.glob(os.path.join(_OUTPUT_DIR, "*.csv"))
                   if os.path.basename(p)[:-4] < label and not os.path.basename(p).startswith("messages_"))
    if not older:
        return None
    prev = pd.read_csv(older[-1], encoding="utf-8-sig")
    return dict(zip(prev["کارشناس"], prev["position"]))


def _change_line(name, position, prev):
    if prev is None:
        return None
    before = prev.get(name)
    if before is None or before > 40:
        return "🚀 تازه وارد جمع ۴۰ نفر برتر شدی، آفرین!"
    if position < before:
        return f"📈 نسبت به گزارش قبل {_fa(before - position)} پله بالاتر اومدی 👏"
    if position > before:
        return f"📉 نسبت به گزارش قبل {_fa(position - before)} پله پایین‌تر رفتی، وقت جبرانه 💪"
    return "↔️ جایگاهت نسبت به گزارش قبل ثابت مونده"


def _gap_line(row, table):
    tier = int(row["tier"])
    if tier == 1:
        return "👑 الان صدرنشین طرحی! جایگاهت رو تا آخر طرح حفظ کن 🔥"
    _, boundary_pos, better_tier, better_prize = TIERS[tier - 2]
    boundary = table.loc[table["position"] == boundary_pos].iloc[0]
    gap = int(boundary["invoices"]) - int(row["invoices"])
    head = f"🎯 برای رسیدن به رتبه‌ی {_fa(better_tier)} (پاداش {_money(better_prize)} تومان) "
    if gap <= 0:
        return head + f"با نفر {_fa(boundary_pos)} هم‌تعداد هستی؛ با فقط ۱ فاکتور دیگه ازش جلو می‌زنی!"
    return head + f"فقط {_fa(gap)} فاکتور با نفر {_fa(boundary_pos)} فاصله داری."


def _progress_text(row, table, report, prev):
    lines = [
        f"سلام {_display_name(row['کارشناس'])} عزیز 🌸",
        "",
        "✨ پاداش ویژه کارشناسان فروش ۵۰۴۰ - ضد لک گلورشن",
        f"📊 وضعیت تو تا {_when(report['slot_jdt'])}:",
        "",
        f"🧴 فاکتورهای وصولی کارتابلی پک ضد لک گلورشن: {_fa(int(row['invoices']))} فاکتور",
        f"🏅 جایگاه فعلی: نفر {_fa(int(row['position']))} (رتبه‌ی {_fa(int(row['tier']))} پاداش)",
        f"💰 پاداش تو تا این لحظه: {_money(row['prize_toman'])} تومان",
    ]
    change = _change_line(row["کارشناس"], int(row["position"]), prev)
    if change:
        lines.append(change)
    lines += [
        _gap_line(row, table),
        "",
        "⏳ طرح تا ۱۰ آبان ساعت ۲۳:۵۹ ادامه داره؛ هر فاکتور می‌تونه جایگاهت رو عوض کنه 💪",
        "",
        _RULE_LINE,
    ]
    return "\n".join(lines)


def _final_text(row):
    return "\n".join([
        f"سلام {_display_name(row['کارشناس'])} عزیز 🌸",
        "",
        "🏁 پاداش ویژه ضد لک گلورشن (۱۵ مهر تا ۱۰ آبان) به پایان رسید و این نتیجه‌ی نهایی توئه 🏆",
        "",
        f"🧴 فاکتورهای وصولی کارتابلی پک ضد لک گلورشن: {_fa(int(row['invoices']))} فاکتور",
        f"🏅 جایگاه نهایی: نفر {_fa(int(row['position']))} (رتبه‌ی {_fa(int(row['tier']))} پاداش)",
        f"🎁 پاداش نهایی تو: {_money(row['prize_toman'])} تومان",
        "",
        "دمت گرم، ممنون از تلاشت ❤️",
    ])


def render(report, reward_id, slot):
    table = report["table"]
    prev = None if report["is_final"] else _previous_positions(report["slot_jdt"])

    messages = []
    for _, row in table[table["tier"] > 0].iterrows():
        name = row["کارشناس"]
        text = _final_text(row) if report["is_final"] else _progress_text(row, table, report, prev)
        messages.append(OutboundMessage(
            reward_id=reward_id,
            slot=slot,
            panel_user_id=name,
            chat_user_id="",
            contact=CONTACT_OVERRIDES.get(name, name),
            text=text,
        ))
    return messages
