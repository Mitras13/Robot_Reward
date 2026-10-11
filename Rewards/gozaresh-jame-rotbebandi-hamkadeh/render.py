"""
gozaresh-jame-rotbebandi-hamkadeh/render.py

Sibling of gozaresh-jame-rotbebandi-5040/render.py (company همکده instead of
5040, top 50 instead of top 100, red theme instead of blue) - identical
mechanism, see that file's docstring for the full reasoning on the PDF-not-
image fix, the file name convention, and why the recipient list below is
deliberately incomplete.

Recipients (2026-09-30, user decision - "گزارشات همکده به 4 گروه زیر ارسال
میشه"): 4 group names, given directly by the user as the exact directory
search strings - including the leading "2 کانال ..."/"2کانال ..." wording
itself being part of the literal group name (not a count to expand into two
separate entries):
    - کانال گزارشات روتین
    - کارشناسان فروش همکده
    - 2کانال گزارشات سرپرستان همکده
    - 2 کانال گزارشات سوپروایزران همکده
All 4 are wired into _RECIPIENTS below exactly as given.
"""

import base64
import os

import img2pdf
from playwright.sync_api import sync_playwright

from Senders.message import OutboundMessage

MONTH_NAMES = [
    "", "فروردین", "اردیبهشت", "خرداد", "تیر", "مرداد", "شهریور",
    "مهر", "آبان", "آذر", "دی", "بهمن", "اسفند",
]

_ASSETS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets")
_OUTPUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "outputs")
_LOGO_ICON_PATH = os.path.join(_ASSETS_DIR, "logo_icon.png")

_FONT_REGULAR_PATH = r"C:\Windows\Fonts\W_yekan.ttf"
_FONT_BOLD_PATH = r"C:\Windows\Fonts\W_yekan Bold.ttf"

_TOP_N = 50
_TITLE = "گزارش برترین‌های فروش همکده ( عملکرد )"
_ACCENT = "#cf2547"
_ACCENT_DARK = "#a31a37"
_BAND_BG = "#fdeef1"
_STRIPE_BG = "#fff6f7"
_PAGE_BG = "#ffffff"

_TOP5_ROW_BG = "#eef6f0"
_TOP5_TEXT = "#3f6b4d"

_MEDALS = {1: "🥇", 2: "🥈", 3: "🥉", 4: "🏅", 5: "🏅"}

_OUTPUT_FILE_BASENAME = "گزارش رتبه بندی (عملکرد) فروش همکده"

_RECIPIENTS = [
    "کانال گزارشات روتین",
    "کارشناسان فروش همکده",
    "2کانال گزارشات سرپرستان همکده",
    "2 کانال گزارشات سوپروایزران همکده",
]


def _file_base64(path):
    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode("ascii")


def _format_coe(value):
    s = f"{value:,.2f}"
    if "." in s:
        s = s.rstrip("0").rstrip(".")
    return s


def _format_toman(value):
    return f"{int(round(value)):,}"


def _period_text(period_start, period_end):
    month_name = MONTH_NAMES[period_start.month]
    return f"از {period_start.day} الی {period_end.day} {month_name} ساعت 24:00"


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
  .wrap {{ width: 1040px; background: {page_bg}; padding: 0 0 30px 0; }}
  .band {{ background: linear-gradient(135deg, {accent} 0%, {accent_dark} 100%);
           padding: 28px 40px 30px 40px; text-align: center; }}
  .band .badge-row {{ display: flex; align-items: center; justify-content: center; gap: 14px; }}
  .band .logo-badge {{ background: #ffffff; border-radius: 16px; padding: 8px 16px; height: 42px;
                        box-sizing: content-box; display: flex; align-items: center; justify-content: center;
                        box-shadow: 0 2px 8px rgba(0,0,0,0.18); }}
  .band .logo-badge img {{ height: 38px; display: block; }}
  .band .title {{ color: #ffffff; font-size: 30px; font-weight: bold; }}
  .band .pill-row {{ display: flex; align-items: center; justify-content: center; gap: 12px; margin-top: 16px; flex-wrap: wrap; }}
  .band .pill {{ display: flex; align-items: center; height: 20px; box-sizing: content-box;
                 background: rgba(255,255,255,0.18); border: 1px solid rgba(255,255,255,0.4);
                 border-radius: 30px; padding: 9px 22px; color: #ffffff; font-size: 15px; }}
  .num {{ font-family: Tahoma, 'Segoe UI', sans-serif; }}
  table {{ width: 100%; border-collapse: collapse; margin-top: 0; }}
  thead th {{ background: {band_bg}; color: {accent_dark}; font-size: 16px; font-weight: bold;
              padding: 15px 10px; text-align: center; border-bottom: 2px solid {accent}; }}
  tbody td {{ font-size: 16px; color: #232323; padding: 12px 10px; text-align: center;
              border-bottom: 1px solid #eeeeee; }}
  tbody tr:nth-child(even) {{ background: {stripe_bg}; }}
  tbody tr.row-top5 {{ background: {top5_row_bg} !important; }}
  .rank-cell {{ font-weight: bold; color: {accent_dark}; font-size: 16px; }}
  .row-top5 .rank-cell {{ color: {top5_text}; }}
  .name-wrap {{ display: flex; align-items: center; justify-content: flex-start; gap: 6px; min-width: 0; }}
  .name-wrap span {{ overflow: hidden; text-overflow: ellipsis; white-space: nowrap; min-width: 0; }}
  .name-wrap span.top3-name {{ font-weight: bold; }}
  .medal {{ flex: 0 0 auto; font-size: 15px; }}
  .name-cell {{ text-align: right !important; padding-right: 16px !important; max-width: 175px; }}
  .val-cell {{ font-weight: bold; color: #232323; }}
  .col-sep {{ border-right: 2px solid {accent}; }}
  .foot {{ margin: 22px 40px 0 40px; padding-top: 12px; border-top: 2px solid {accent}; text-align: center; font-size: 15px; color: {accent_dark}; }}
</style>
</head>
<body>
<div class="wrap">
  <div class="band">
    <div class="badge-row">
      <div class="logo-badge"><img src="data:image/png;base64,{logo_b64}"></div>
      <div class="title">{title} 🏆</div>
    </div>
    <div class="pill-row">
      <div class="pill">{period_text}</div>
      <div class="pill">👥 {top_n} نفر برتر</div>
    </div>
  </div>
  <table>
    <thead>
      <tr>
        <th>رتبه</th>
        <th class="name-cell">کارشناس</th>
        <th>ضریب وصولی</th>
        <th class="name-cell col-sep">کارشناس</th>
        <th>وصولی کل (تومان)</th>
        <th class="name-cell col-sep">کارشناس</th>
        <th>وصولی کارتابلی (تومان)</th>
      </tr>
    </thead>
    <tbody>
      {rows_html}
    </tbody>
  </table>
  <div class="foot">واحد سازنده گزارش: <b>واحد آنالیز گزارشات</b></div>
</div>
</body>
</html>"""

_ROW_TEMPLATE = """<tr class="{row_class}">
        <td class="rank-cell">{rank}</td>
        <td class="name-cell"><div class="name-wrap">{badge}<span class="{name_class}">{name_coe}</span></div></td>
        <td class="val-cell num">{val_coe}</td>
        <td class="name-cell col-sep"><div class="name-wrap">{badge}<span class="{name_class}">{name_paid}</span></div></td>
        <td class="val-cell num">{val_paid}</td>
        <td class="name-cell col-sep"><div class="name-wrap">{badge}<span class="{name_class}">{name_cartable}</span></div></td>
        <td class="val-cell num">{val_cartable}</td>
      </tr>"""


def _build_table_png(table, period_start, period_end, output_path):
    top_n = min(_TOP_N, len(table))
    by_coe = table.sort_values("رتبه ضریب وصولی").head(top_n).reset_index(drop=True)
    by_paid = table.sort_values("رتبه وصولی کل").head(top_n).reset_index(drop=True)
    by_cartable = table.sort_values("رتبه وصولی کارتابلی").head(top_n).reset_index(drop=True)

    rows_html_parts = []
    for i in range(top_n):
        rank = i + 1
        medal = _MEDALS.get(rank, "")
        badge_html = f'<span class="medal">{medal}</span>' if medal else ""
        name_class = "top3-name" if rank <= 3 else ""
        rows_html_parts.append(_ROW_TEMPLATE.format(
            row_class="row-top5" if rank <= 5 else "",
            rank=rank,
            badge=badge_html,
            name_class=name_class,
            name_coe=by_coe.loc[i, "کارشناس"],
            val_coe=_format_coe(by_coe.loc[i, "paid_coe"]),
            name_paid=by_paid.loc[i, "کارشناس"],
            val_paid=_format_toman(by_paid.loc[i, "paid"]),
            name_cartable=by_cartable.loc[i, "کارشناس"],
            val_cartable=_format_toman(by_cartable.loc[i, "cartable_paid"]),
        ))

    html = _HTML_TEMPLATE.format(
        font_regular_b64=_file_base64(_FONT_REGULAR_PATH),
        font_bold_b64=_file_base64(_FONT_BOLD_PATH),
        logo_b64=_file_base64(_LOGO_ICON_PATH),
        title=_TITLE,
        top_n=top_n,
        period_text=_period_text(period_start, period_end),
        page_bg=_PAGE_BG,
        accent=_ACCENT,
        accent_dark=_ACCENT_DARK,
        band_bg=_BAND_BG,
        stripe_bg=_STRIPE_BG,
        top5_row_bg=_TOP5_ROW_BG,
        top5_text=_TOP5_TEXT,
        rows_html="\n      ".join(rows_html_parts),
    )

    with sync_playwright() as p:
        browser = p.chromium.launch(channel="chrome")
        page = browser.new_page(device_scale_factor=3)
        page.set_content(html)
        page.locator(".wrap").screenshot(path=output_path, type="png")
        browser.close()


def render(report, reward_id, slot):
    table = report["table"]
    slot_jdt = report["slot_jdt"]
    period_start = report["period_start"]
    period_end = report["period_end"]

    slot_label = slot_jdt.strftime("%Y_%m_%d_%H%M")
    out_dir = os.path.join(_OUTPUT_DIR, slot_label)
    os.makedirs(out_dir, exist_ok=True)

    png_path = os.path.join(out_dir, f"{_OUTPUT_FILE_BASENAME}.png")
    pdf_path = os.path.join(out_dir, f"{_OUTPUT_FILE_BASENAME}.pdf")

    _build_table_png(table, period_start, period_end, png_path)
    with open(pdf_path, "wb") as f:
        f.write(img2pdf.convert(png_path))

    caption = f"{_OUTPUT_FILE_BASENAME} - {_period_text(period_start, period_end)}"

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
        for group_name in _RECIPIENTS
    ]
