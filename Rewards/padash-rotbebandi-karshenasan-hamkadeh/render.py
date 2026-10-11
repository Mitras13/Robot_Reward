"""
padash-rotbebandi-karshenasan-hamkadeh/render.py

One OutboundMessage per کارشناس row from builder.py's table, naming all
three ranks (ضریب وصولی / وصولی کل / وصولی کارتابلی) with their values -
per the user's explicit instruction 2026-09-20 ("تو یدونه پیام نام کارشناس
وارد میشه و۳ تا رتبه‌بندی ... باید ۳ تاش تو یه پیام بشه").

As of 2026-09-20 the message is an IMAGE (not plain text) - the user
supplied a branded mockup (assets/template_source.jpg, a ChatGPT-generated
design using this exact wording/layout with sample data) and asked for the
real per-کارشناس values substituted into it every slot. There is no source
file for that mockup (no PSD/Figma, just a flattened JPG), so exact
pixel-for-pixel reproduction of its background isn't possible - what's
reused verbatim is the actual "همکده" logo lockup, cropped straight out of
the mockup into assets/header.png (this IS the real brand asset, not a
recreation); everything below it (greeting, 3 metric rows, closing pill) is
rebuilt in HTML/CSS to match the mockup's layout, colors and wording as
closely as achievable, then rendered via Playwright - same
HTML->Chromium->screenshot technique as the sibling project's reference
module (Rewards/padash-tamdid-karshenasan-hamkadeh/TamdidiHK.py), except the
browser is launched ONCE for the whole render() call and reused for every
row (486+ کارشناسان a slot - a fresh browser launch per row would be far
too slow).

contact = panel_user_id = کارشناس name exactly as SP.HK.SPK returns it
(AAName) - same identity convention as the other two رتبه‌بندی/تمدید
rewards in this project.

No message is currently sent by anyone (config/rewards.csv row for this
reward ships with enabled=0, per project convention, and the user
additionally asked 2026-09-20 not to send anything from this reward until
they explicitly approve) - render.py is fully implemented per the 4-file
reward contract so images can be reviewed before turning sending on.

NOTE: an earlier version of this file (same day) also sent a manager-summary
PNG to a group - the user cancelled that entirely ("کنسله گزارش مدیریتی
نمیخوام اصلا"), so this reward now only ever produces the per-کارشناس image.

Image size (2026-09-21, user decision): canvas shrunk 1122px -> 800px and
output switched PNG -> JPEG quality 85 - cuts each image from ~140KB to
~55KB (measured, side-by-side quality check approved by the user) with no
visible quality loss. Lighter upload = both faster AND less load on the
messenger's server per the user's own ask ("حجم عکس کمتر بشه") - unlike
send concurrency, there's no trade-off here.

Recipient filter (2026-09-28, user decision - widened from 25% to 50%, and
mirrors the same-day change on the sibling 5040 reward): union of top 50% on
ضریب وصولی, top 50% on وصولی کل, AND top 50% on وصولی کارتابلی (all three
metrics now, not just the first two) - rank-based cutoff, ties at the
boundary included, deduplicated so nobody gets more than one message even
if they qualify on all three. builder.py's full table (everyone) is still
written whole to outputs/{slot}.csv, untouched by this filter.

Message wording/layout (2026-09-28, user decision, mirrors 5040): plan name
is now a bold line reading "گزارش هفتگی رتبه‌بندی ( عملکرد ) فروش همکده -
{ماه}ماه", the covered date range is a separate bold parenthetical ("( از 1
مهر تا 11 مهر 1405 )" - always from day 1 of the month, since ranking is
month-to-date, not a rolling window) instead of the old "از تاریخ .. تا
تاریخ .. ساعت 23:59" phrasing. The champion footer now names WHICH
metric(s) earned the top-5 spot (e.g. «ضریب وصولی») instead of a generic
"این ماه". Sending cadence unchanged: هر شنبه ۰۰:۰۰ (schedule.csv),
catch-up-once already verified safe.
"""

import base64
import bisect
import math
import os
import re

from playwright.sync_api import sync_playwright

from Senders.message import OutboundMessage

MONTH_NAMES = [
    "", "فروردین", "اردیبهشت", "خرداد", "تیر", "مرداد", "شهریور",
    "مهر", "آبان", "آذر", "دی", "بهمن", "اسفند",
]

_ASSETS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets")
_OUTPUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "outputs")
_HEADER_IMAGE_PATH = os.path.join(_ASSETS_DIR, "header.png")

# W_yekan - the closest already-installed local font to the mockup's rounded
# look (B Titr, used by the sibling tamdid reward's PNG report, is a
# traditional bold headline font and doesn't match this design at all).
_FONT_REGULAR_PATH = r"C:\Windows\Fonts\W_yekan.ttf"
_FONT_BOLD_PATH = r"C:\Windows\Fonts\W_yekan Bold.ttf"

# Same red brand palette as the mockup - همکده uses ONE accent color across
# all 3 rows (unlike the 5040 mockup, which color-codes each row - see the
# sibling render.py).
_ACCENT = "#cf2547"
_ROW_BG = "#fdeef1"
_ICON_BG = "#f8d9df"

_METRICS = [
    ("رتبه ضریب وصولی", "paid_coe", "ضریب وصولی", "📈"),
    ("رتبه وصولی کل", "paid", "مبلغ وصولی کل", "💰"),
    ("رتبه وصولی کارتابلی", "cartable_paid", "مبلغ وصولی کارتابلی", "🧾"),
]

_INVALID_FILENAME_CHARS = re.compile(r'[\\/:*?"<>|]')

# Tone selection (2026-09-26, user decision, thresholds widened 2026-09-28
# to match _select_recipients' new 50% cutoff, mirrors 5040): tone is
# computed from each person's PERCENTILE RANK across the full builder.py
# table (everyone, not just recipients), in 4 tiers - ready to serve the
# full population's worth of tones the moment _select_recipients is loosened
# further, with no code change needed here. Uses only this slot's own
# ranking table (no history needed) - چون همکده برخلاف 5040 اسنپ‌شات
# روزانه‌ی کافی برای مدل رشدمحور ندارد (raw_data/SPK/HK فقط snapshotهای
# تجمعی داره، نه روزانه‌ی جدا).
_CHAMPION_RANK_THRESHOLD = 5
_TOP_PERCENTILE = 0.5
_MIDDLE_PERCENTILE = 0.75

_FOOTER_BY_TIER = {
    "top": ("موفق و پرتلاش باشید", "در کنار شما، برای رشد و موفقیت بیشتر"),
    "middle": ("🙏 قدردان تلاش شما هستیم", "با ادامه‌ی روند، جایگاه بهتری در انتظارتونه"),
    "needs_encouragement": ("💪 فرصت رشد پیش روی شماست", "با کمی تلاش بیشتر می‌تونید جایگاهتون رو ارتقا بدید"),
}


def _champion_labels(row):
    """Which of the 3 metrics this person is top-5 in (2026-09-28, user
    decision, mirrors 5040) - names the exact metric(s) instead of a generic
    "این ماه" footer."""
    return [label for rank_col, _, label, *_ in _METRICS if row[rank_col] <= _CHAMPION_RANK_THRESHOLD]


def _pick_tone(row, total_count):
    """Best (lowest) percentile across all 3 ranks - same "union of top
    performers" shape as _select_recipients, just applied per-person instead
    of as a cutoff."""
    best_rank = min(row[rank_col] for rank_col, *_ in _METRICS)
    if best_rank <= _CHAMPION_RANK_THRESHOLD:
        return "champion"
    percentile = best_rank / total_count
    if percentile <= _TOP_PERCENTILE:
        return "top"
    if percentile <= _MIDDLE_PERCENTILE:
        return "middle"
    return "needs_encouragement"


def _footer_lines(row, total_count):
    tier = _pick_tone(row, total_count)
    if tier == "champion":
        labels_text = " و ".join(f"«{label}»" for label in _champion_labels(row))
        return "🏆 عملکرد فوق‌العاده!", f"جزو ۵ نفر برتر در {labels_text} هستید - همینطور بدرخشید"
    return _FOOTER_BY_TIER[tier]


def _period_label(period_start, period_end):
    """Plan title + date range (2026-09-28, user decision, mirrors 5040):
    replaces the old "از تاریخ .. تا تاریخ .. ساعت 23:59" caption with a bold
    parenthetical "( از 1 مهر تا 11 مهر 1405 )" - period_start is always day
    1 of the month (ranking is month-to-date, not a rolling window), so this
    range grows each week as more شنبه‌ها pass, ending at whatever day the
    report actually runs on rather than a hardcoded example day."""
    month_name = MONTH_NAMES[period_start.month]
    end_month_name = MONTH_NAMES[period_end.month]
    period_text = (
        f'( از <span class="num">{period_start.day}</span> {month_name} '
        f'تا <span class="num">{period_end.day}</span> {end_month_name} '
        f'<span class="num">{period_start.year}</span> )'
    )
    return month_name, period_text


def _format_coe(value):
    """No trailing .00 (2026-09-27, user decision, applies to every report
    that shows ضریب وصولی) - trims a zero fractional part but keeps real
    precision if the value isn't a round number."""
    s = f"{value:,.2f}"
    if "." in s:
        s = s.rstrip("0").rstrip(".")
    return s


def _format_toman(value):
    return f"{int(round(value)):,}"


def _file_base64(path):
    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode("ascii")


def _sanitize_filename(name):
    return _INVALID_FILENAME_CHARS.sub("_", name).strip()


def _select_recipients(table):
    """Union of the top 50% by رتبه ضریب وصولی, top 50% by رتبه وصولی کل,
    and top 50% by رتبه وصولی کارتابلی - see module docstring. Rank-based
    cutoff (inclusive of ties at the boundary), not a hard head(n) slice;
    deduplicated by pandas' boolean-OR mask so someone qualifying on two or
    three metrics still gets exactly one message."""
    if len(table) == 0:
        return table

    cutoff_count = math.ceil(len(table) * 0.5)

    mask = None
    for rank_col, *_ in _METRICS:
        cutoff_rank = table[rank_col].nsmallest(cutoff_count).max()
        col_mask = table[rank_col] <= cutoff_rank
        mask = col_mask if mask is None else (mask | col_mask)
    return table[mask]


_HTML_TEMPLATE = """<!DOCTYPE html>
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
  .wrap {{ width: 800px; background: #ffffff; }}
  .header-img {{ width: 800px; display: block; }}
  .greeting {{ text-align: center; padding: 28px 60px 6px 60px; }}
  .greeting .name-line {{ font-size: 30px; font-weight: bold; color: #1a1a1a; }}
  .greeting .name-line .sprout {{ font-size: 24px; }}
  .greeting .plan-title {{ font-size: 19px; font-weight: bold; color: {accent}; margin-top: 12px; line-height: 1.7; }}
  .greeting .period {{ font-size: 17px; font-weight: bold; color: #1a1a1a; margin-top: 4px; }}
  .greeting .caption {{ font-size: 17px; color: #444444; line-height: 1.9; margin-top: 10px; }}
  .rows {{ padding: 10px 55px 0 55px; }}
  .row {{ display: flex; align-items: center; gap: 20px; background: {row_bg}; border-radius: 20px; padding: 20px 26px; margin-bottom: 22px; }}
  .icon-circle {{ flex: 0 0 auto; width: 78px; height: 78px; border-radius: 50%; background: {icon_bg}; display: flex; align-items: center; justify-content: center; font-size: 34px; }}
  .row-text {{ flex: 1 1 auto; text-align: right; }}
  .row-text .line1 {{ font-size: 19px; color: #222222; }}
  .row-text .line2 {{ font-size: 17px; color: #333333; margin-top: 6px; }}
  .neighbors {{ flex: 0 0 96px; display: flex; flex-direction: column; justify-content: center; gap: 4px;
                padding-left: 10px; border-left: 1px dashed #e3b9c3; font-size: 11px; color: #a98a90; text-align: center; line-height: 1.3; }}
  .neighbors .n-line {{ white-space: nowrap; overflow: hidden; text-overflow: ellipsis; max-width: 96px; }}
  .neighbors .n-arrow {{ font-size: 10px; }}
  .neighbors .n-current {{ font-size: 11.5px; font-weight: bold; color: #1a1a1a; }}
  .num {{ font-family: Tahoma, 'Segoe UI', sans-serif; }}
  .accent-num {{ font-weight: bold; color: {accent}; font-size: 26px; font-family: Tahoma, 'Segoe UI', sans-serif; }}
  .accent-val {{ font-weight: bold; color: {accent}; font-size: 22px; font-family: Tahoma, 'Segoe UI', sans-serif; }}
  .footer-pill {{ margin: 6px 60px 30px 60px; background: {row_bg}; border-radius: 40px; padding: 18px; text-align: center; }}
  .footer-pill .line1 {{ font-size: 22px; font-weight: bold; color: {accent}; }}
  .footer-pill .line2 {{ font-size: 14px; color: #666666; margin-top: 6px; }}
</style>
</head>
<body>
<div class="wrap">
  <img class="header-img" src="data:image/png;base64,{header_b64}">
  <div class="greeting">
    <div class="name-line"><span class="sprout">🌱</span> سلام {name} عزیز</div>
    <div class="plan-title">گزارش هفتگی رتبه‌بندی ( عملکرد ) فروش همکده - {month_name}‌ماه</div>
    <div class="period">{period_text}</div>
    <div class="caption">
      نتایج رتبه‌بندی شما به شرح زیر است:
    </div>
  </div>
  <div class="rows">
    {rows_html}
  </div>
  <div class="footer-pill">
    <div class="line1">{footer_line1}</div>
    <div class="line2">{footer_line2}</div>
  </div>
</div>
</body>
</html>"""

_ROW_TEMPLATE = """<div class="row">
      <div class="icon-circle">{icon}</div>
      <div class="row-text">
        <div class="line1">رتبه <span class="accent-num">{rank}</span> را در «{label}» کسب کردید؛</div>
        <div class="line2">با {label} <span class="accent-val">{value}</span>{unit}</div>
      </div>
      <div class="neighbors">{neighbors_html}</div>
    </div>"""


def _neighbors_html(name_by_rank, sorted_ranks, current_rank, current_name):
    """Small "who's just above/below you" ladder with the کارشناس's own name
    highlighted in the middle (2026-09-28, user decision, mirrors 5040) -
    see the sibling render.py's docstring for the full reasoning (bisect to
    the nearest EXISTING rank, since رتبه uses method="min" and a tie can
    make current_rank±1 belong to no one)."""
    idx = bisect.bisect_left(sorted_ranks, current_rank)
    prev_name = name_by_rank[sorted_ranks[idx - 1]] if idx > 0 else None
    next_name = name_by_rank[sorted_ranks[idx + 1]] if idx + 1 < len(sorted_ranks) else None
    parts = []
    if prev_name:
        parts.append(f'<div class="n-line"><span class="n-arrow">▲</span> {prev_name}</div>')
    parts.append(f'<div class="n-line n-current">{current_name}</div>')
    if next_name:
        parts.append(f'<div class="n-line"><span class="n-arrow">▼</span> {next_name}</div>')
    return "".join(parts)


def _build_person_image(page, row, month_name, period_text, total_count, rank_lookup, output_path):
    rows_html_parts = []
    for rank_col, value_col, label, icon in _METRICS:
        formatter = _format_coe if value_col == "paid_coe" else _format_toman
        unit = "" if value_col == "paid_coe" else " تومان"
        current_rank = int(row[rank_col])
        name_by_rank, sorted_ranks = rank_lookup[rank_col]
        rows_html_parts.append(_ROW_TEMPLATE.format(
            icon=icon, rank=current_rank, label=label, value=formatter(row[value_col]), unit=unit,
            neighbors_html=_neighbors_html(name_by_rank, sorted_ranks, current_rank, row["کارشناس"]),
        ))

    footer_line1, footer_line2 = _footer_lines(row, total_count)
    html = _HTML_TEMPLATE.format(
        font_regular_b64=_file_base64(_FONT_REGULAR_PATH),
        font_bold_b64=_file_base64(_FONT_BOLD_PATH),
        header_b64=_file_base64(_HEADER_IMAGE_PATH),
        name=row["کارشناس"],
        month_name=month_name,
        period_text=period_text,
        row_bg=_ROW_BG,
        icon_bg=_ICON_BG,
        accent=_ACCENT,
        footer_line1=footer_line1,
        footer_line2=footer_line2,
        rows_html="\n    ".join(rows_html_parts),
    )
    page.set_content(html)
    page.locator(".wrap").screenshot(path=output_path, type="jpeg", quality=85)


def render(report, reward_id, slot):
    table = report["table"]
    slot_jdt = report["slot_jdt"]
    period_start = report["period_start"]
    period_end = report["period_end"]
    month_name, period_text = _period_label(period_start, period_end)

    recipients = _select_recipients(table)

    # one (name_by_rank, sorted unique ranks) lookup per metric, built once
    # for the whole slot instead of per-person (see _neighbors_html's
    # docstring for why sorted_ranks is needed, not just the dict).
    rank_lookup = {}
    for rank_col, *_ in _METRICS:
        name_by_rank = table.groupby(rank_col)["کارشناس"].first().to_dict()
        rank_lookup[rank_col] = (name_by_rank, sorted(name_by_rank.keys()))

    slot_label = slot_jdt.strftime("%Y_%m_%d_%H%M")
    images_dir = os.path.join(_OUTPUT_DIR, "cards", slot_label)
    os.makedirs(images_dir, exist_ok=True)

    # Fonts/header are re-encoded to base64 once per row above for simplicity
    # (readable, and cheap relative to the screenshot itself) - the browser
    # itself is launched ONCE and reused for every row, which is the actual
    # bottleneck at 486+ کارشناسان a slot.
    messages = []
    with sync_playwright() as p:
        browser = p.chromium.launch(channel="chrome")
        page = browser.new_page()
        for i, (_, row) in enumerate(recipients.iterrows()):
            name = row["کارشناس"]
            output_path = os.path.join(images_dir, f"{i:04d}_{_sanitize_filename(name)}.jpg")
            _build_person_image(page, row, month_name, period_text, len(table), rank_lookup, output_path)
            messages.append(OutboundMessage(
                reward_id=reward_id,
                slot=slot,
                panel_user_id=name,
                chat_user_id="",
                contact=name,
                text=f"گزارش هفتگی رتبه‌بندی ( عملکرد ) فروش همکده - {month_name}‌ماه",
                image=output_path,
            ))
        browser.close()

    return messages
