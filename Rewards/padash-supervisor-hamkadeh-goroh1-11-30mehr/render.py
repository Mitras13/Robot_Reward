"""
padash-supervisor-hamkadeh-goroh1-11-30mehr/render.py

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

Channel broadcast (user 2026-10-07): besides each supervisor's personal
message above, this reward ALSO sends one combined "جامع" (comprehensive)
ranking image - both گروه اول (this file's own report) AND گروه دوم
(padash-supervisor-hamkadeh-goroh2-11-30mehr's latest output for the SAME
slot) stacked in one table - to 3 channels: کانال گزارشات روتین, 2کانال
گزارشات سرپرستان همکده, 2 کانال گزارشات سوپروایزران همکده. goroh1 (this
file) owns sending it rather than goroh2, so it is never sent twice; it
reads goroh2's outputs/{slot_label}.csv directly (see _load_sibling_report
below) with a short retry, the same race-tolerance pattern already used by
builder.py's _read_spk() for the two groups' SP.HK.SPK file. If goroh2's
file never appears within the wait window, the channel broadcast is
skipped for that slot only - personal messages are never affected.
"""

import base64
import importlib
import logging
import os
import re
import time

import img2pdf
import pandas as pd
from playwright.sync_api import sync_playwright

from Senders.message import OutboundMessage

from .builder import _OUTPUT_DIR, COE_TOLERANCE_PCT, GROUP_DESC, GROUP_LABEL, PRIZES_MILLION_TOMAN, prize_for_rank

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


_SIBLING_REWARD_ID = "padash-supervisor-hamkadeh-goroh2-11-30mehr"
_SIBLING_WAIT_ATTEMPTS = 6
_SIBLING_WAIT_SECONDS = 5  # ~30s max - goroh1/goroh2 finish ~0.3s apart in practice (2026-10-07 sample)

_CHANNEL_RECIPIENTS = [
    "کانال گزارشات روتین",
    "2کانال گزارشات سرپرستان همکده",
    "2 کانال گزارشات سوپروایزران همکده",
]

_CHANNEL_TITLE = "گزارش جامع رقابت سوپروایزرهای همکده"
_CHANNEL_ACCENT = "#cf2547"
_CHANNEL_ACCENT_DARK = "#a31a37"
_CHANNEL_BAND_BG = "#fdeef1"
_CHANNEL_STRIPE_BG = "#fff6f7"

_ASSETS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets")
_LOGO_ICON_PATH = os.path.join(_ASSETS_DIR, "logo_icon.png")
_FONT_REGULAR_PATH = r"C:\Windows\Fonts\W_yekan.ttf"
_FONT_BOLD_PATH = r"C:\Windows\Fonts\W_yekan Bold.ttf"

_CHANNEL_OUTPUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "outputs", "channel")
_CHANNEL_OUTPUT_FILE_BASENAME = "گزارش جامع رقابت سوپروایزرهای همکده"

MONTH_NAMES = [
    "", "فروردین", "اردیبهشت", "خرداد", "تیر", "مرداد", "شهریور",
    "مهر", "آبان", "آذر", "دی", "بهمن", "اسفند",
]

_CHANNEL_HTML_TEMPLATE = """<!DOCTYPE html>
<html dir="rtl" lang="fa">
<head>
<meta charset="utf-8">
<style>
  @font-face {{
    font-family: 'Yekan';
    src: url(data:font/ttf;base64,{font_regular_b64}) format('truetype');
    font-weight: normal;
  }}
  @font-face {{
    font-family: 'Yekan';
    src: url(data:font/ttf;base64,{font_bold_b64}) format('truetype');
    font-weight: bold;
  }}
  body {{ margin: 0; font-family: 'Yekan', Tahoma, sans-serif; background: #ffffff; }}
  .wrap {{ width: 900px; background: #ffffff; padding: 0 0 24px 0; }}
  .band {{ background: linear-gradient(135deg, {accent} 0%, {accent_dark} 100%);
           padding: 26px 40px 26px 40px; text-align: center; }}
  .band .badge-row {{ display: flex; align-items: center; justify-content: center; gap: 14px; }}
  .band .logo-badge {{ background: #ffffff; border-radius: 16px; padding: 8px 16px; height: 42px;
                        box-sizing: content-box; display: flex; align-items: center; justify-content: center;
                        box-shadow: 0 2px 8px rgba(0,0,0,0.18); }}
  .band .logo-badge img {{ height: 38px; display: block; }}
  .band .title {{ color: #ffffff; font-size: 26px; font-weight: bold; }}
  .band .pill-row {{ display: flex; align-items: center; justify-content: center; gap: 12px; margin-top: 14px; flex-wrap: wrap; }}
  .band .pill {{ display: flex; align-items: center; height: 18px; box-sizing: content-box;
                 background: rgba(255,255,255,0.18); border: 1px solid rgba(255,255,255,0.4);
                 border-radius: 30px; padding: 8px 20px; color: #ffffff; font-size: 14px; }}
  .num {{ font-family: Tahoma, 'Segoe UI', sans-serif; }}
  .group-head {{ margin: 24px 40px 0 40px; padding: 10px 16px; background: {band_bg};
                 border-right: 4px solid {accent}; border-radius: 6px; }}
  .group-head .g-title {{ font-size: 18px; font-weight: bold; color: {accent_dark}; }}
  .group-head .g-desc {{ font-size: 13px; color: #555555; margin-top: 2px; }}
  table {{ width: calc(100% - 80px); margin: 10px 40px 0 40px; border-collapse: collapse; }}
  thead th {{ background: {band_bg}; color: {accent_dark}; font-size: 14px; font-weight: bold;
              padding: 10px 8px; text-align: center; border-bottom: 2px solid {accent}; }}
  tbody td {{ font-size: 14px; color: #232323; padding: 9px 8px; text-align: center;
              border-bottom: 1px solid #eeeeee; }}
  tbody tr:nth-child(even) {{ background: {stripe_bg}; }}
  tbody tr.row-ineligible td {{ color: #999999; }}
  .rank-cell {{ font-weight: bold; color: {accent_dark}; font-size: 14px; }}
  .row-ineligible .rank-cell {{ color: #aaaaaa; }}
  .name-cell {{ text-align: right !important; padding-right: 14px !important; }}
  .val-cell {{ font-weight: bold; }}
  .bar-cell {{ background-repeat: no-repeat; }}
  .coe-pos {{ color: #1a7a3c; font-weight: bold; }}
  .coe-neg {{ color: #c62828; font-weight: bold; }}
  .row-ineligible .coe-pos, .row-ineligible .coe-neg {{ color: #999999; }}
  .foot {{ margin: 20px 40px 0 40px; padding-top: 10px; border-top: 2px solid {accent}; text-align: center; font-size: 14px; color: {accent_dark}; }}
</style>
</head>
<body>
<div class="wrap">
  <div class="band">
    <div class="badge-row">
      <div class="logo-badge"><img src="data:image/png;base64,{logo_b64}"></div>
      <div class="title">📊 {title}</div>
    </div>
    <div class="pill-row">
      <div class="pill">{period_text}</div>
    </div>
  </div>
  {groups_html}
  <div class="foot">واحد سازنده گزارش: <b>واحد آنالیز گزارشات</b></div>
</div>
</body>
</html>"""

_CHANNEL_GROUP_TEMPLATE = """
  <div class="group-head">
    <div class="g-title">{group_label}</div>
    <div class="g-desc">{group_desc}</div>
  </div>
  <table>
    <thead>
      <tr>
        <th>رتبه</th>
        <th class="name-cell">سوپروایزر</th>
        <th>تعداد کارشناس مبنا</th>
        <th>میانگین وصولی (تومان)</th>
        <th>تغییر ضریب</th>
        <th>{prize_header}</th>
      </tr>
    </thead>
    <tbody>
      {rows_html}
    </tbody>
  </table>"""

_CHANNEL_ROW_TEMPLATE = """<tr class="{row_class}">
        <td class="rank-cell">{rank}</td>
        <td class="name-cell">{name}</td>
        <td class="num">{base_count}</td>
        <td class="val-cell num bar-cell" style="background: linear-gradient(to left, {bar_color} {bar_pct}%, transparent {bar_pct}%);">{avg_toman}</td>
        <td class="num {coe_class}">{coe_pct}</td>
        <td class="val-cell num">{prize}</td>
      </tr>"""

_BAR_COLOR = "rgba(26, 122, 60, 0.16)"
_COE_POS_COLOR = "#1a7a3c"
_COE_NEG_COLOR = "#c62828"


def _file_base64(path):
    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode("ascii")


def _channel_period_text(period_start, period_end, slot_jdt):
    month_name = MONTH_NAMES[period_start.month]
    time_str = "۲۴:۰۰" if (slot_jdt.hour == 23 and slot_jdt.minute == 59) else _fa(slot_jdt.strftime("%H:%M"))
    return f"از {period_start.day} الی {period_end.day} {month_name} ساعت {time_str}"


def _channel_group_rows_html(teams, prize_fn, final):
    max_avg = float(teams["avg_toman"].max()) if len(teams) else 0.0
    rows = []
    for _, team in teams.iterrows():
        eligible = bool(team["eligible"])
        rank = team.get("rank")
        rank_display = _fa(int(rank)) if eligible and pd.notna(rank) else "–"
        prize_million = prize_fn(int(rank)) if eligible and pd.notna(rank) else 0
        prize_display = _prize_toman(prize_million) if prize_million else ("واجد شرایط نیست" if not eligible else "–")
        coe_change = team["coe_vs_overall_pct"]
        coe_sign = "+" if coe_change >= 0 else "-"
        bar_pct = (team["avg_toman"] / max_avg * 100) if max_avg > 0 else 0
        rows.append(_CHANNEL_ROW_TEMPLATE.format(
            row_class="" if eligible else "row-ineligible",
            rank=rank_display,
            name=display_name(str(team["supervisor"])),
            base_count=_fa(int(team["base_count"])),
            avg_toman=_toman(team["avg_toman"]),
            bar_color=_BAR_COLOR,
            bar_pct=f"{bar_pct:.1f}",
            coe_class="coe-pos" if coe_change >= 0 else "coe-neg",
            coe_pct=f"{coe_sign}{_pct(coe_change)}",
            prize=prize_display,
        ))
    prize_header = "پاداش نهایی" if final else "پاداش برآوردی"
    return "\n      ".join(rows), prize_header


def _load_sibling_report(slot_jdt):
    """Polls for goroh2's own output CSV for this exact slot - see module
    docstring. Returns the teams DataFrame plus goroh2's group metadata, or
    None if it never showed up within the wait window."""
    sibling_builder = importlib.import_module(f"Rewards.{_SIBLING_REWARD_ID}.builder")
    slot_label = slot_jdt.strftime("%Y_%m_%d_%H%M")
    path = os.path.join(sibling_builder._OUTPUT_DIR, f"{slot_label}.csv")
    for attempt in range(_SIBLING_WAIT_ATTEMPTS):
        if os.path.exists(path):
            df = pd.read_csv(path, encoding="utf-8-sig")
            return {
                "teams": df,
                "group_label": sibling_builder.GROUP_LABEL,
                "group_desc": sibling_builder.GROUP_DESC,
                "prize_for_rank": sibling_builder.prize_for_rank,
            }
        if attempt < _SIBLING_WAIT_ATTEMPTS - 1:
            time.sleep(_SIBLING_WAIT_SECONDS)
    logger.warning(
        "channel report: goroh2 output for slot %s not found after %d attempts - skipping channel broadcast this slot",
        slot_label, _SIBLING_WAIT_ATTEMPTS,
    )
    return None


def _build_channel_png(own_teams, sibling, period_start, period_end, slot_jdt, final, output_path):
    own_rows_html, prize_header = _channel_group_rows_html(own_teams, prize_for_rank, final)
    groups_html = _CHANNEL_GROUP_TEMPLATE.format(
        group_label=GROUP_LABEL, group_desc=GROUP_DESC,
        prize_header=prize_header, rows_html=own_rows_html,
    )
    if sibling:
        sib_rows_html, sib_prize_header = _channel_group_rows_html(
            sibling["teams"], sibling["prize_for_rank"], final
        )
        groups_html += _CHANNEL_GROUP_TEMPLATE.format(
            group_label=sibling["group_label"], group_desc=sibling["group_desc"],
            prize_header=sib_prize_header, rows_html=sib_rows_html,
        )

    html = _CHANNEL_HTML_TEMPLATE.format(
        font_regular_b64=_file_base64(_FONT_REGULAR_PATH),
        font_bold_b64=_file_base64(_FONT_BOLD_PATH),
        logo_b64=_file_base64(_LOGO_ICON_PATH),
        title=_CHANNEL_TITLE,
        period_text=_channel_period_text(period_start, period_end, slot_jdt),
        accent=_CHANNEL_ACCENT,
        accent_dark=_CHANNEL_ACCENT_DARK,
        band_bg=_CHANNEL_BAND_BG,
        stripe_bg=_CHANNEL_STRIPE_BG,
        groups_html=groups_html,
    )

    with sync_playwright() as p:
        browser = p.chromium.launch(channel="chrome")
        page = browser.new_page(device_scale_factor=3)
        page.set_content(html)
        page.locator(".wrap").screenshot(path=output_path, type="png")
        browser.close()


def _build_channel_messages(report, reward_id, slot, slot_jdt, final):
    from . import requirements as req

    sibling = _load_sibling_report(slot_jdt)
    period_start, period_end = req.period_for_slot(slot_jdt)

    slot_label = slot_jdt.strftime("%Y_%m_%d_%H%M")
    out_dir = os.path.join(_CHANNEL_OUTPUT_DIR, slot_label)
    os.makedirs(out_dir, exist_ok=True)
    png_path = os.path.join(out_dir, f"{_CHANNEL_OUTPUT_FILE_BASENAME}.png")
    pdf_path = os.path.join(out_dir, f"{_CHANNEL_OUTPUT_FILE_BASENAME}.pdf")

    _build_channel_png(report["teams"], sibling, period_start, period_end, slot_jdt, final, png_path)
    with open(pdf_path, "wb") as f:
        f.write(img2pdf.convert(png_path))

    caption = f"{_CHANNEL_OUTPUT_FILE_BASENAME} - {_channel_period_text(period_start, period_end, slot_jdt)}"
    return [
        OutboundMessage(
            reward_id=reward_id,
            slot=slot,
            panel_user_id=group_name,
            chat_user_id="",
            contact=group_name,
            text=caption,
            image=pdf_path,
        )
        for group_name in _CHANNEL_RECIPIENTS
    ]


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

    try:
        messages += _build_channel_messages(report, reward_id, slot, slot_jdt, final)
    except Exception:
        logger.exception("'%s': channel broadcast failed - personal messages still go out", reward_id)

    return messages
