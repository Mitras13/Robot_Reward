"""
gozaresh-jame-padash-zaribvosoli-5040/render.py

One PDF (HTML page screenshotted to PNG, wrapped losslessly in a PDF with
img2pdf - same mechanism and 5040 blue layout as
gozaresh-jame-padash-gloroshen-5040, sent as a file to avoid the messenger's
photo compression).

Layout (user 2026-10-10, kept lean): 5040 logo header, campaign window and
data cut-off, 4 summary cards (company ضریب وصولی, کارشناسان with a ratio,
total وصولی کل, total پاداش مازاد), then the top 40 (tier summary table
removed, top list 30 -> 40 - user 2026-10-10). Footer: «واحد سازنده گزارش: واحد آنالیز گزارشات».

Digits: W_yekan's Persian digits sit at uneven heights, so the page font "Y"
maps digit/number-punctuation code points to Tahoma via unicode-range and
everything else to W_yekan (same fix as gozaresh-jame-padash-gloroshen-5040).

Recipients (user 2026-10-10): exactly the Glorsion comprehensive report's -
both are 5040 reports - plus the «گزارشات پاداش» group.
"""

import base64
import os

import img2pdf
from playwright.sync_api import sync_playwright

from Senders.message import OutboundMessage

RECIPIENTS = [
    "کانال گزارشات روتین",
    "2کانال گزارشات سرپرستان 5040",
    "2 کانال گزارشات سوپروایزران 5040",
    "کارشناسان فروش 5040",
    "عرفان زمانی (مدیر ارشد فروش)",
    # گروه «گزارشات پاداش» (user 2026-10-10) - exact Username, not the alias:
    # two channels + one group share that name in the directory (same contact
    # string padash-karshenasan-5040 used for it).
    "group-smrezvanmadani-1789890446796",
]

TOP_N = 40

_HERE = os.path.dirname(os.path.abspath(__file__))
_OUTPUT_DIR = os.path.join(_HERE, "outputs")
_LOGO_PATH = os.path.join(_HERE, "assets", "logo_icon.png")
_FONTS = r"C:\Windows\Fonts"
_DIGIT_RANGE = "U+0030-0039,U+06F0-06F9,U+0660-0669,U+066A-066C,U+0025,U+002B-002E,U+003A,U+2212"

_FILE_BASENAME = "گزارش جامع رقابت ضریب وصولی کارشناسان 5040"

_FA = str.maketrans("0123456789", "۰۱۲۳۴۵۶۷۸۹")
MONTH_NAMES = [
    "", "فروردین", "اردیبهشت", "خرداد", "تیر", "مرداد", "شهریور",
    "مهر", "آبان", "آذر", "دی", "بهمن", "اسفند",
]

# 5040 blue, row tint fades from tier 1 to tier 7.
_TIER_COLORS = ["#d6e6ff", "#e0ecff", "#e8f1ff", "#eef5ff", "#f3f8ff", "#f7faff", "#fbfcff"]
_MEDALS = {1: "🥇", 2: "🥈", 3: "🥉"}


def fa(x):
    return str(x).translate(_FA)


def num(x):
    return fa(f"{int(round(x)):,}")


def pct(fraction):
    return fa(f"{round(fraction * 100, 2):g}") + "٪"


def _b64(path):
    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode("ascii")


def _when(jdt):
    return f"{fa(jdt.day)} {MONTH_NAMES[jdt.month]} ساعت {fa(jdt.strftime('%H:%M'))}"


_CSS = """
@font-face { font-family: 'Y'; src: url(data:font/ttf;base64,{reg}) format('truetype'); font-weight: normal; }
@font-face { font-family: 'Y'; src: url(data:font/ttf;base64,{bold}) format('truetype'); font-weight: bold; }
@font-face { font-family: 'Y'; src: local('Tahoma'); unicode-range: {rng}; font-weight: normal; }
@font-face { font-family: 'Y'; src: local('Tahoma Bold'); unicode-range: {rng}; font-weight: bold; }
body { margin: 0; font-family: 'Y', Tahoma, sans-serif; background: #ffffff; color: #232323; }
.wrap { width: 1100px; background: #ffffff; padding-bottom: 26px; }
.band { background: linear-gradient(135deg, #2f6fed 0%, #1c4fbf 100%); padding: 26px 40px 28px; text-align: center; }
.top { display: flex; align-items: center; justify-content: center; gap: 16px; }
.logo { background: #fff; border-radius: 16px; padding: 8px 16px; display: flex; align-items: center; box-shadow: 0 2px 8px rgba(0,0,0,.25); }
.logo img { height: 46px; display: block; }
.title { color: #fff; font-size: 30px; font-weight: bold; }
.sub { color: #dce9ff; font-size: 19px; margin-top: 8px; font-weight: bold; }
.pills { display: flex; justify-content: center; gap: 12px; margin-top: 16px; flex-wrap: wrap; }
.pill { background: rgba(255,255,255,.16); border: 1px solid rgba(255,255,255,.45); border-radius: 30px; padding: 9px 22px; color: #fff; font-size: 16px; }
.pill b { color: #ffffff; }
.cards { display: flex; gap: 14px; margin: 22px 30px 0; }
.card { flex: 1; border: 1px solid #cfe0fb; background: #f5f9ff; border-radius: 14px; padding: 14px 10px; text-align: center; }
.card .k { font-size: 14px; color: #1c4fbf; }
.card .v { font-size: 25px; font-weight: bold; color: #1c4fbf; margin-top: 6px; }
.card .u { font-size: 13px; color: #5b7fc7; }
.sec { margin: 24px 30px 0; font-size: 18px; font-weight: bold; color: #1c4fbf; }
table { width: calc(100% - 60px); margin: 10px 30px 0; border-collapse: collapse; }
thead th { background: #1c4fbf; color: #fff; font-size: 15px; padding: 12px 6px; }
tbody td { font-size: 15px; padding: 9px 6px; text-align: center; border-bottom: 1px solid #e3ebf7; }
td.name { text-align: right; padding-right: 14px; font-weight: bold; }
td.small { font-size: 13px; color: #5c5048; }
td.prize { font-weight: bold; color: #1c4fbf; }
.empty { text-align: center; color: #8a7a66; padding: 26px; font-size: 16px; }
.foot { margin: 22px 30px 0; padding-top: 12px; border-top: 2px solid #2f6fed; text-align: center; font-size: 15px; color: #1c4fbf; }
"""


def _top_rows(table, tiers):
    top = table[(table["رتبه"] <= TOP_N) & (table["ضریب وصول"] > 0)]
    rows = []
    for _, r in top.iterrows():
        rank = int(r["رتبه"])
        tier_idx = next((i for i, (high, _) in enumerate(tiers) if rank <= high), len(tiers) - 1)
        rows.append(
            f'<tr style="background:{_TIER_COLORS[tier_idx]}">'
            f'<td>{_MEDALS.get(rank, "")} {fa(rank)}</td>'
            f'<td class="name">{r["نام کارشناس"]}</td>'
            f'<td class="small">{r["supervisor"]}</td>'
            f'<td><b>{num(r["ضریب وصول"])}</b></td>'
            f'<td>{num(r["cartable_toman"])}</td>'
            f'<td>{num(r["paid_toman"])}</td>'
            f'<td>{pct(r["درصد نهایی پورسانت"])}</td>'
            f'<td class="prize">{num(r["پاداش مازاد بر آوردی"])}</td></tr>')
    return "".join(rows) or '<tr><td colspan="8" class="empty">هنوز ضریب وصولی ثبت نشده است.</td></tr>'


def _html(report):
    table = report["table"]
    with_ratio = table[table["ضریب وصول"] > 0]

    window = fa(f"بازه رقابت: <b>{_when(report['period_start'])} تا 30 مهر ساعت 23:59</b>")
    cutoff = ("📌 <b>نتیجه نهایی رقابت</b>" if report["is_final"]
              else f"🕒 داده‌ها تا: <b>{_when(report['period_end'])}</b>")

    cards = [
        ("ضریب وصولی کل کارشناسان ۵۰۴۰", num(report["company_coe"]), "وصولی کارتابلی تقسیم بر تماس پاسخ‌داده"),
        ("کارشناسان دارای ضریب وصولی", num(len(with_ratio)), f"از {num(len(table))} نفر"),
        ("وصولی کل کارشناسان", num(table["paid_toman"].sum()), "تومان"),
        ("مجموع پاداش مازاد برآوردی", num(table["پاداش مازاد بر آوردی"].sum()), "تومان"),
    ]
    cards_html = "".join(
        f'<div class="card"><div class="k">{k}</div><div class="v">{v}</div><div class="u">{u}</div></div>'
        for k, v, u in cards)

    css = (_CSS.replace("{reg}", _b64(os.path.join(_FONTS, "W_yekan.ttf")))
               .replace("{bold}", _b64(os.path.join(_FONTS, "W_yekan Bold.ttf")))
               .replace("{rng}", _DIGIT_RANGE))
    return f"""<!DOCTYPE html><html dir="rtl" lang="fa"><head><meta charset="utf-8"><style>{css}</style></head>
<body><div class="wrap">
  <div class="band">
    <div class="top"><div class="logo"><img src="data:image/png;base64,{_b64(_LOGO_PATH)}"></div>
      <div class="title">گزارش جامع رقابت کارشناسان فروش ۵۰۴۰ 🏆</div></div>
    <div class="sub">افزایش ضریب وصولی</div>
    <div class="pills"><div class="pill">📅 {window}</div><div class="pill">{cutoff}</div></div>
  </div>
  <div class="cards">{cards_html}</div>
  <div class="sec">{fa(TOP_N)} نفر برتر</div>
  <table><thead><tr><th>رتبه</th><th>کارشناس</th><th>سوپروایزر</th><th>ضریب وصولی</th>
    <th>وصولی کارتابلی (تومان)</th><th>وصولی کل (تومان)</th><th>درصد نهایی</th><th>پاداش مازاد (تومان)</th></tr></thead>
  <tbody>{_top_rows(table, report["tiers"])}</tbody></table>
  <div class="foot">واحد سازنده گزارش: <b>واحد آنالیز گزارشات</b></div>
</div></body></html>"""


def _caption(report):
    if report["is_final"]:
        return f"{_FILE_BASENAME} - نتیجه نهایی (۱۸ تا ۳۰ مهر)"
    return f"{_FILE_BASENAME} - وضعیت تا {_when(report['period_end'])}"


def render(report, reward_id, slot):
    out_dir = os.path.join(_OUTPUT_DIR, report["slot_jdt"].strftime("%Y_%m_%d_%H%M"))
    os.makedirs(out_dir, exist_ok=True)
    html_path = os.path.join(out_dir, f"{_FILE_BASENAME}.html")
    png_path = os.path.join(out_dir, f"{_FILE_BASENAME}.png")
    pdf_path = os.path.join(out_dir, f"{_FILE_BASENAME}.pdf")

    html = _html(report)
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(html)
    with sync_playwright() as p:
        browser = p.chromium.launch(channel="chrome")
        page = browser.new_page(device_scale_factor=3)
        page.set_content(html)
        page.locator(".wrap").screenshot(path=png_path, type="png")
        browser.close()
    with open(pdf_path, "wb") as f:
        f.write(img2pdf.convert(png_path))

    caption = _caption(report)
    return [
        OutboundMessage(reward_id=reward_id, slot=slot, panel_user_id=name,
                        chat_user_id="", contact=name, text=caption, image=pdf_path)
        for name in RECIPIENTS
    ]
