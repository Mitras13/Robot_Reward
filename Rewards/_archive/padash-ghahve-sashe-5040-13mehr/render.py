"""
padash-ghahve-sashe-5040-13mehr/render.py

One message per کارشناس with at least one counted sachet coffee - a progress
update at 11:00 / 13:00 / 14:00 and a final result at 15:00 (report["is_final"]).
Tone: friendly/informal (user 2026-10-05).

contact = panel_user_id = "ثبت کننده" exactly as in the raw 54.FCP export -
the same panel-name convention (e.g. "... RW"/"... NP") the other 5040
کارشناس rewards send to. Only the greeting drops the trailing team suffix
(user 2026-10-05) - contact keeps the full name, since that is what the
messenger chat is searched by.
"""

import re

from Senders.message import OutboundMessage

_TEAM_SUFFIX_RE = re.compile(r"\s+[A-Za-z][A-Za-z0-9+]*(\s+\d+)?$")
_ACCOUNT_NUMBER_RE = re.compile(r"\s*\(?\d+\)?$")  # "مریم گودرزی2", "... (2)"
_FA_DIGITS =str.maketrans("0123456789", "۰۱۲۳۴۵۶۷۸۹")


def _fa(value):
    return str(value).translate(_FA_DIGITS)


def _money(toman):
    return _fa(f"{int(toman):,}")


def _display_name(name):
    short = _TEAM_SUFFIX_RE.sub("", " ".join(str(name).split()))
    return _ACCOUNT_NUMBER_RE.sub("", short) or name


def _lines(row):
    lines = []
    if row["single_packs"]:
        lines.append(f"☕️ قهوه ساشه‌ای یک عددی: {_fa(int(row['single_packs']))} بسته")
    if row["double_packs"]:
        lines.append(f"☕️☕️ قهوه ساشه‌ای دو عددی: {_fa(int(row['double_packs']))} بسته")
    return lines


def _progress_text(row, time_str):
    return "\n".join([
        f"سلام {_display_name(row['کارشناس'])} عزیز 🌸",
        "",
        f"تا ساعت {time_str} امروز، این‌ها رو کارتابلی ثبت و وصول کردی 👇",
        *_lines(row),
        "",
        f"💰 پاداشت تا الان: {_money(row['prize_toman'])} تومان 👏",
        "",
        "هنوز تا ساعت ۱۵:۰۰ وقت داری که بیشترش کنی 🔥",
        "هر بسته یک عددی ۱۰۰ هزار و هر بسته دو عددی ۱۵۰ هزار تومان پاداش داره 😉",
        "(فقط فاکتورهایی حساب می‌شن که ثبت و وصولشون هر دو تا ساعت ۱۵ انجام شده باشه)",
    ])


def _final_text(row):
    return "\n".join([
        f"سلام {_display_name(row['کارشناس'])} عزیز 🌸",
        "",
        "پاداش ویژه قهوه ساشه‌ای تموم شد و این نتیجه‌ی کار امروزته 🏆",
        *_lines(row),
        "",
        f"🎁 پاداش نهایی تو: {_money(row['prize_toman'])} تومان",
        "",
        "دمت گرم، شروع فوق‌العاده‌ای برای محصول جدید بود 💪",
        "ممنون از زحمتت ❤️",
    ])


def render(report, reward_id, slot):
    table = report["table"]
    time_str = _fa(report["slot_jdt"].strftime("%H:%M"))

    messages = []
    for _, row in table.iterrows():
        name = row["کارشناس"]
        text = _final_text(row) if report["is_final"] else _progress_text(row, time_str)
        messages.append(OutboundMessage(
            reward_id=reward_id,
            slot=slot,
            panel_user_id=name,
            chat_user_id="",
            contact=name,
            text=text,
        ))
    return messages
