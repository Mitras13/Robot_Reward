"""
padash-rotbebandi-karshenasan-5040/render.py

Sibling of padash-rotbebandi-karshenasan-hamkadeh/render.py (company 5040
instead of همکده) - identical mechanism, see that file's docstring for the
full reasoning (confirmed by the user 2026-09-20): one IMAGE message per
کارشناس with all 3 ranks (ضریب وصولی / وصولی کل / وصولی کارتابلی), built
from the user's own 5040-branded mockup (assets/template_source.jpg) -
assets/header.png is the real "5040" logo lockup cropped straight out of
that mockup, everything below it rebuilt in HTML/CSS. One difference from
the همکده version, taken directly from the two mockups the user supplied:
5040's mockup color-codes each metric row differently (green/gold/blue)
instead of همکده's single red accent, and its closing pill has no second
line - _METRICS below carries each row's own color pair to match.

contact = panel_user_id = کارشناس name exactly as SP.54.SPK returns it
(AAName).

No message is currently sent by anyone (config/rewards.csv row for this
reward ships with enabled=0, and the user additionally asked 2026-09-20 not
to send anything from this reward until they explicitly approve).

Image size (2026-09-21, user decision): canvas shrunk 1122px -> 800px and
output switched PNG -> JPEG quality 85, same as the sibling همکده reward -
see that file's docstring for the measured before/after sizes.

Recipient filter (2026-09-28, user decision - widened from 25% to 50%):
union of top 50% on ضریب وصولی, top 50% on وصولی کل, AND top 50% on وصولی
کارتابلی (all three metrics now, not just the first two) - rank-based
cutoff, ties at the boundary included, deduplicated so nobody gets more
than one message even if they qualify on all three. builder.py's full table
(everyone) is still written whole to outputs/{slot}.csv, untouched by this
filter.

Message wording/layout (2026-09-28, user decision): plan name is now a bold
line reading "گزارش هفتگی رتبه‌بندی ( عملکرد ) فروش 5040 - {ماه}ماه", the
covered date range is a separate bold parenthetical ("( از 1 مهر تا 11 مهر
1405 )" - always from day 1 of the month, since ranking is month-to-date,
not a rolling window) instead of the old "از تاریخ .. تا تاریخ .. ساعت
23:59" phrasing. The champion footer now names WHICH metric(s) earned the
top-5 spot (e.g. «ضریب وصولی») instead of a generic "این طرح" - per the
user, a کارشناس reading "جزو ۵ نفر برتر این طرح" had no way to tell which of
the 3 numbers on the card made them a champion. Sending cadence unchanged:
هر شنبه ۰۰:۰۰ (schedule.csv), catch-up-once already verified safe.
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

_FONT_REGULAR_PATH = r"C:\Windows\Fonts\W_yekan.ttf"
_FONT_BOLD_PATH = r"C:\Windows\Fonts\W_yekan Bold.ttf"

_PAGE_BG = "#f7fafe"
_PILL_BG = "#ffffff"
_PILL_BORDER = "#e4ecf7"
_PILL_TEXT = "#c0392b"

# (rank column, value column, label, icon, row bg, icon-circle bg, accent color)
# colors match each row's own icon in the user's 5040 mockup (green / gold / blue).
_METRICS = [
    ("رتبه ضریب وصولی", "paid_coe", "ضریب وصولی", "📈", "#eafaf1", "#d3f3e0", "#219150"),
    ("رتبه وصولی کل", "paid", "مبلغ وصولی کل", "💰", "#fff8ec", "#ffe8bd", "#c98a1c"),
    ("رتبه وصولی کارتابلی", "cartable_paid", "مبلغ وصولی کارتابلی", "🧾", "#eaf3ff", "#d6e8ff", "#2f6fed"),
]

_INVALID_FILENAME_CHARS = re.compile(r'[\\/:*?"<>|]')

# Tone selection (2026-09-26, user decision, thresholds widened 2026-09-28
# to match _select_recipients' new 50% cutoff): tone is computed from each
# person's PERCENTILE RANK across the full builder.py table (everyone, not
# just recipients), in 4 tiers - ready to serve the full population's worth
# of tones the moment _select_recipients is loosened further, with no code
# change needed here. Uses only this slot's own ranking table (no
# historical data), unlike the ML clustering explored in ml/tone.py, which
# needs several weeks of daily history this reward doesn't have yet.
_CHAMPION_RANK_THRESHOLD = 5
_TOP_PERCENTILE = 0.5
_MIDDLE_PERCENTILE = 0.75

_FOOTER_BY_TIER = {
    "top": "⭐ موفق و پرتلاش باشید",
    "middle": "🙏 از تلاش شما سپاسگزاریم",
    "needs_encouragement": "💪 با کمی تلاش بیشتر، جای شما بین برترین‌هاست",
}


def _champion_labels(row):
    """Which of the 3 metrics this person is top-5 in (2026-09-28, user
    decision) - a کارشناس reading a generic "جزو ۵ نفر برتر این طرح" footer
    had no way to tell WHICH of the 3 numbers on their own card earned that;
    now the footer names the exact metric(s), e.g. «ضریب وصولی»."""
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


def _footer_text(row, total_count):
    tier = _pick_tone(row, total_count)
    if tier == "champion":
        labels_text = " و ".join(f"«{label}»" for label in _champion_labels(row))
        return f"🏆 عملکرد فوق‌العاده! جزو ۵ نفر برتر در {labels_text} هستید"
    return _FOOTER_BY_TIER[tier]


def _period_label(period_start, period_end):
    """Plan title + date range (2026-09-28, user decision): replaces the old
    "از تاریخ .. تا تاریخ .. ساعت 23:59" caption with a bold parenthetical
    "( از 1 مهر تا 11 مهر 1405 )" - period_start is always day 1 of the
    month (ranking is month-to-date, not a rolling window), so this range
    grows each week as more شنبه‌ها pass, ending at whatever day the report
    actually runs on rather than a hardcoded example day."""
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
  body {{ margin: 0; font-family: 'Yekan', Tahoma, sans-serif; background: {page_bg}; }}
  .wrap {{ width: 800px; background: {page_bg}; }}
  .header-img {{ width: 800px; display: block; }}
  .greeting {{ text-align: center; padding: 28px 60px 6px 60px; }}
  .greeting .name-line {{ font-size: 30px; font-weight: bold; color: #16233d; }}
  .greeting .name-line .sprout {{ font-size: 24px; }}
  .greeting .plan-title {{ font-size: 19px; font-weight: bold; color: #1c4fbf; margin-top: 12px; line-height: 1.7; }}
  .greeting .period {{ font-size: 17px; font-weight: bold; color: #16233d; margin-top: 4px; }}
  .greeting .caption {{ font-size: 17px; color: #3c4a63; line-height: 1.9; margin-top: 10px; }}
  .rows {{ padding: 10px 55px 0 55px; }}
  .row {{ display: flex; align-items: center; gap: 20px; border-radius: 20px; padding: 20px 26px; margin-bottom: 22px; }}
  .icon-circle {{ flex: 0 0 auto; width: 78px; height: 78px; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-size: 34px; }}
  .row-text {{ flex: 1 1 auto; text-align: right; }}
  .row-text .line1 {{ font-size: 19px; color: #222222; }}
  .row-text .line2 {{ font-size: 17px; color: #333333; margin-top: 6px; }}
  .neighbors {{ flex: 0 0 96px; display: flex; flex-direction: column; justify-content: center; gap: 4px;
                padding-left: 10px; border-left: 1px dashed #c7d1e0; font-size: 11px; color: #8a93a3; text-align: center; line-height: 1.3; }}
  .neighbors .n-line {{ white-space: nowrap; overflow: hidden; text-overflow: ellipsis; max-width: 96px; }}
  .neighbors .n-arrow {{ font-size: 10px; }}
  .neighbors .n-current {{ font-size: 11.5px; font-weight: bold; color: #16233d; }}
  .num {{ font-family: Tahoma, 'Segoe UI', sans-serif; }}
  .accent-num {{ font-weight: bold; font-size: 26px; font-family: Tahoma, 'Segoe UI', sans-serif; }}
  .accent-val {{ font-weight: bold; font-size: 22px; font-family: Tahoma, 'Segoe UI', sans-serif; }}
  .footer-pill {{ margin: 6px 60px 30px 60px; background: {pill_bg}; border: 2px solid {pill_border}; border-radius: 40px; padding: 18px; text-align: center; }}
  .footer-pill .line1 {{ font-size: 22px; font-weight: bold; color: {pill_text}; }}
</style>
</head>
<body>
<div class="wrap">
  <img class="header-img" src="data:image/png;base64,{header_b64}">
  <div class="greeting">
    <div class="name-line"><span class="sprout">🌱</span> سلام {name} عزیز</div>
    <div class="plan-title">گزارش هفتگی رتبه‌بندی ( عملکرد ) فروش <span class="num">5040</span> - {month_name}‌ماه</div>
    <div class="period">{period_text}</div>
    <div class="caption">
      نتایج رتبه‌بندی شما به شرح زیر است:
    </div>
  </div>
  <div class="rows">
    {rows_html}
  </div>
  <div class="footer-pill">
    <div class="line1">{footer_text}</div>
  </div>
</div>
</body>
</html>"""

_ROW_TEMPLATE = """<div class="row" style="background: {row_bg};">
      <div class="icon-circle" style="background: {icon_bg};">{icon}</div>
      <div class="row-text">
        <div class="line1">رتبه <span class="accent-num" style="color: {accent};">{rank}</span> را در «{label}» کسب کردید؛</div>
        <div class="line2">با {label} <span class="accent-val" style="color: {accent};">{value}</span>{unit}</div>
      </div>
      <div class="neighbors">{neighbors_html}</div>
    </div>"""


def _neighbors_html(name_by_rank, sorted_ranks, current_rank, current_name):
    """Small "who's just above/below you" ladder (2026-09-28, user decision)
    - the person one step ahead (better) on top, the کارشناس's OWN name
    highlighted in the middle (2026-09-28: added per user feedback - without
    it, it wasn't obvious the two names were "around" the reader rather than
    just two unrelated names), one step behind (worse) on the bottom. Looks
    up the nearest EXISTING rank value via bisect rather than a literal
    current_rank±1, because رتبه uses method="min": a tie at rank 298 means
    no one at all holds rank 299, so a plain dict.get(rank-1) would silently
    show nothing for the very next کارشناس. name_by_rank/sorted_ranks are
    precomputed once per metric for the whole slot (see render()), not
    re-scanned per person. Ties share a rank number, so when several people
    hold the same neighboring rank only one representative name is shown -
    there's no room to list them all in a 96px-wide ladder."""
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
    for rank_col, value_col, label, icon, row_bg, icon_bg, accent in _METRICS:
        formatter = _format_coe if value_col == "paid_coe" else _format_toman
        unit = "" if value_col == "paid_coe" else " تومان"
        current_rank = int(row[rank_col])
        name_by_rank, sorted_ranks = rank_lookup[rank_col]
        rows_html_parts.append(_ROW_TEMPLATE.format(
            icon=icon, rank=current_rank, label=label, value=formatter(row[value_col]), unit=unit,
            row_bg=row_bg, icon_bg=icon_bg, accent=accent,
            neighbors_html=_neighbors_html(name_by_rank, sorted_ranks, current_rank, row["کارشناس"]),
        ))

    html = _HTML_TEMPLATE.format(
        font_regular_b64=_file_base64(_FONT_REGULAR_PATH),
        font_bold_b64=_file_base64(_FONT_BOLD_PATH),
        header_b64=_file_base64(_HEADER_IMAGE_PATH),
        name=row["کارشناس"],
        month_name=month_name,
        period_text=period_text,
        page_bg=_PAGE_BG,
        pill_bg=_PILL_BG,
        pill_border=_PILL_BORDER,
        pill_text=_PILL_TEXT,
        footer_text=_footer_text(row, total_count),
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
                text=f"گزارش هفتگی رتبه‌بندی ( عملکرد ) فروش 5040 - {month_name}‌ماه",
                image=output_path,
            ))
        browser.close()

    return messages
