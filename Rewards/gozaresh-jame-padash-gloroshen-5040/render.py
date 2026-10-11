"""
gozaresh-jame-padash-gloroshen-5040/render.py

One PDF (HTML page screenshotted to PNG, wrapped losslessly in a PDF with
img2pdf - same mechanism as gozaresh-jame-rotbebandi-5040, sent as a file to
avoid the messenger's photo compression).

Layout (user 2026-10-07): 5040 logo header, the exact campaign window and the
data cut-off time, 4 summary cards, then the full table of the 40 prized
positions (tier cards and the ranking-rule note removed - user 2026-10-07). 5040 blue palette. Footer: «واحد سازنده گزارش: واحد آنالیز گزارشات».

Digits: W_yekan's Persian digits sit at uneven heights, so the page font "Y"
maps digit/number-punctuation code points to Tahoma via unicode-range and
everything else to W_yekan (same fix as gozaresh-jame-padash-hamkadeh-mehr).

Recipients (user 2026-10-07): the 4 groups already used by
gozaresh-jame-rotbebandi-5040, plus عرفان زمانی.
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
]

_HERE = os.path.dirname(os.path.abspath(__file__))
_OUTPUT_DIR = os.path.join(_HERE, "outputs")
_LOGO_PATH = os.path.join(_HERE, "assets", "logo_icon.png")
_FONTS = r"C:\Windows\Fonts"
_DIGIT_RANGE = "U+0030-0039,U+06F0-06F9,U+0660-0669,U+066A-066C,U+0025,U+002B-002E,U+003A,U+2212"

_FILE_BASENAME = "گزارش جامع پاداش ضد لک گلورشن 5040"

_FA = str.maketrans("0123456789", "۰۱۲۳۴۵۶۷۸۹")
MONTH_NAMES = [
    "", "فروردین", "اردیبهشت", "خرداد", "تیر", "مرداد", "شهریور",
    "مهر", "آبان", "آذر", "دی", "بهمن", "اسفند",
]

# 5040 blue (user 2026-10-07) - same accent as gozaresh-jame-rotbebandi-5040;
# row tint fades from tier 1 to tier 7.
_TIER_COLORS = {1: "#d6e6ff", 2: "#e0ecff", 3: "#e8f1ff", 4: "#eef5ff",
                5: "#f3f8ff", 6: "#f7faff", 7: "#fbfcff"}
_MEDALS = {1: "🥇", 2: "🥈", 3: "🥉"}


def fa(x):
    return str(x).translate(_FA)


def num(x):
    return fa(f"{int(round(x)):,}")


def _b64(path):
    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode("ascii")


def _when(jdt, with_seconds=False):
    fmt = "%H:%M:%S" if with_seconds else "%H:%M"
    return f"{fa(jdt.day)} {MONTH_NAMES[jdt.month]} ساعت {fa(jdt.strftime(fmt))}"


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
table { width: calc(100% - 60px); margin: 16px 30px 0; border-collapse: collapse; }
thead th { background: #1c4fbf; color: #fff; font-size: 15px; padding: 12px 6px; }
tbody td { font-size: 15px; padding: 9px 6px; text-align: center; border-bottom: 1px solid #e3ebf7; }
td.name { text-align: right; padding-right: 14px; font-weight: bold; }
td.small { font-size: 13px; color: #5c5048; }
td.prize { font-weight: bold; color: #1c4fbf; }
.empty { text-align: center; color: #8a7a66; padding: 26px; font-size: 16px; }
.foot { margin: 22px 30px 0; padding-top: 12px; border-top: 2px solid #2f6fed; text-align: center; font-size: 15px; color: #1c4fbf; }
"""


def _html(report):
    table = report["table"]
    prized = table[table["tier"] > 0]
    is_final = report["is_final"]

    window = f"بازه اجرای طرح: <b>{_when(report['period_start'])} تا 10 آبان ساعت 23:59:59</b>"
    window = window.translate(_FA)
    cutoff = ("📌 <b>نتیجه نهایی طرح</b>" if is_final
              else f"🕒 داده‌ها تا: <b>{_when(report['period_end'])}</b>")

    cards = [
        ("تعداد کل فاکتورهای وصولی کارتابلی", num(report["total_invoices"]), "فاکتور"),
        ("کارشناسان با حداقل ۱ فاکتور", num(len(table)), "نفر"),
        ("مبلغ کل همین فاکتورها", num(report["total_amount_toman"]), "تومان"),
        ("مجموع پاداش نفرات برتر", num(prized["prize_toman"].sum()), "تومان"),
    ]
    cards_html = "".join(
        f'<div class="card"><div class="k">{k}</div><div class="v">{v}</div><div class="u">{u}</div></div>'
        for k, v, u in cards)


    rows = []
    for _, r in prized.iterrows():
        pos = int(r["position"])
        rows.append(
            f'<tr style="background:{_TIER_COLORS[int(r["tier"])]}">'
            f'<td>{_MEDALS.get(pos, "")} {fa(pos)}</td>'
            f'<td>{fa(int(r["tier"]))}</td>'
            f'<td class="name">{r["کارشناس"]}</td>'
            f'<td class="small">{r["supervisor"]}</td>'
            f'<td class="small">{r["sarparast"]}</td>'
            f'<td><b>{fa(int(r["invoices"]))}</b></td>'
            f'<td>{num(r["amount_toman"])}</td>'
            f'<td class="prize">{num(r["prize_toman"])}</td></tr>')
    body = "".join(rows) or '<tr><td colspan="8" class="empty">هنوز فاکتور واجد شرایطی ثبت نشده است.</td></tr>'

    css = (_CSS.replace("{reg}", _b64(os.path.join(_FONTS, "W_yekan.ttf")))
               .replace("{bold}", _b64(os.path.join(_FONTS, "W_yekan Bold.ttf")))
               .replace("{rng}", _DIGIT_RANGE))
    return f"""<!DOCTYPE html><html dir="rtl" lang="fa"><head><meta charset="utf-8"><style>{css}</style></head>
<body><div class="wrap">
  <div class="band">
    <div class="top"><div class="logo"><img src="data:image/png;base64,{_b64(_LOGO_PATH)}"></div>
      <div class="title">گزارش جامع پاداش ویژه کارشناسان فروش ۵۰۴۰ 🏆</div></div>
    <div class="sub">ضد لک گلورشن</div>
    <div class="pills"><div class="pill">📅 {window}</div><div class="pill">{cutoff}</div></div>
  </div>
  <div class="cards">{cards_html}</div>
  <table><thead><tr><th>جایگاه</th><th>رتبه پاداش</th><th>کارشناس</th><th>سوپروایزر</th><th>سرپرست</th>
    <th>تعداد فاکتور</th><th>مبلغ فاکتورها (تومان)</th><th>پاداش (تومان)</th></tr></thead>
  <tbody>{body}</tbody></table>
  <div class="foot">واحد سازنده گزارش: <b>واحد آنالیز گزارشات</b></div>
</div></body></html>"""


def _caption(report):
    if report["is_final"]:
        return f"{_FILE_BASENAME} - نتیجه نهایی (۱۵ مهر تا ۱۰ آبان)"
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
