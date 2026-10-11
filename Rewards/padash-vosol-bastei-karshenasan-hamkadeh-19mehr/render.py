"""
padash-vosol-bastei-karshenasan-hamkadeh-19mehr/render.py

One message per کارشناس with at least one prize-eligible package - progress
updates at 13:00 / 15:00 / 17:00 / 19:00 / 21:00 and the final result at
1405/07/20 00:05 (report["is_final"]). Tone: friendly, same as the
announcement.

The first line must stay "سلام {name} عزیز ..." - Senders/send_message.py
uses it as the delivery-confirmation signature.

contact = panel_user_id = "ثبت کننده" exactly as in the raw HK.FCP export
(e.g. "زهرا لطفی DJ") - the same name-as-contact convention as the other
همکده کارشناس rewards. Only the greeting drops the team suffix.

Manager report (user 2026-10-11): every slot also sends one PDF (HTML page
screenshotted to PNG, wrapped in a PDF with img2pdf to avoid the messenger's
photo compression - same mechanism as the other comprehensive reports) to
the 3 همکده report channels + کارشناسان فروش همکده (CHANNEL_RECIPIENTS). Layout: همکده logo
header + window + data cut-off, 4 summary cards, per-package breakdown, then
every prized کارشناس, or only the top TOP_N once there are more
(user 2026-10-11). همکده red palette. A failure here never blocks
the personal messages.
"""

import base64
import logging
import os
import re

import img2pdf
from playwright.sync_api import sync_playwright

from Senders.message import OutboundMessage

from .builder import _OUTPUT_DIR, PRIZES_TOMAN, package_label

# Shown in every personal message - several rewards run at once, so each
# message names which one it is about (user 2026-10-11).
PLAN_NAME = "پاداش ویژه وصول کارتابلی کارشناسان همکده (یکشنبه ۱۹ مهر)"

logger = logging.getLogger(__name__)

CHANNEL_RECIPIENTS = [
    "کانال گزارشات روتین",
    "2کانال گزارشات سرپرستان همکده",
    "2 کانال گزارشات سوپروایزران همکده",
    "کارشناسان فروش همکده",
]
TOP_N = 50

_TEAM_SUFFIX_RE = re.compile(r"\s+[A-Za-z][A-Za-z0-9+]*(\s+\d+)?$")
_ACCOUNT_NUMBER_RE = re.compile(r"\s*\(?\d+\)?$")  # "فاطمه حیدری2", "... (2)"
_FA_DIGITS = str.maketrans("0123456789", "۰۱۲۳۴۵۶۷۸۹")

_HERE = os.path.dirname(os.path.abspath(__file__))
_LOGO_PATH = os.path.join(_HERE, "assets", "logo_icon.png")
_FONTS = r"C:\Windows\Fonts"
_DIGIT_RANGE = "U+0030-0039,U+06F0-06F9,U+0660-0669,U+066A-066C,U+0025,U+002B-002E,U+003A,U+2212"
_FILE_BASENAME = "گزارش جامع پاداش ویژه وصول کارتابلی همکده"
_MEDALS = {1: "🥇", 2: "🥈", 3: "🥉"}


def _fa(value):
    return str(value).translate(_FA_DIGITS)


def _money(toman):
    return _fa(f"{int(toman):,}")


def _display_name(name):
    short = _TEAM_SUFFIX_RE.sub("", " ".join(str(name).split()))
    return _ACCOUNT_NUMBER_RE.sub("", short) or name


def _lines(row):
    lines = []
    for key, qty in row["packages"].items():
        lines.append(
            f"📦 بسته {_fa(package_label(key))} جلسه: {_fa(qty)} عدد"
            f" ← {_money(PRIZES_TOMAN[key] * qty)} تومان"
        )
    return lines


def _progress_text(row, time_str):
    return "\n".join([
        f"سلام {_display_name(row['کارشناس'])} عزیز 🌸",
        "",
        f"🎯 {PLAN_NAME}",
        "",
        "ایول، امروز حسابی داری می‌ترکونی! 😍",
        f"تا ساعت {time_str} این بسته‌ها رو کارتابلی وصول کردی 👇",
        *_lines(row),
        "",
        f"💰 تا الان {_money(row['prize_toman'])} تومان پاداش برای خودت جمع کردی 👏👏",
        "",
        "هنوز تا ساعت ۲۳:۵۹ وقت داری، پس ول نکن! 🔥",
        "هر وصول یعنی یه پاداش دیگه تو جیبت 💸😉",
        "",
        "(یادت باشه فقط وصول کارتابلی از ساعت ۱۰:۳۰ امروز حساب می‌شه و بسته ۲ جلسه‌ای مشمول نیست)",
    ])


def _final_text(row):
    return "\n".join([
        f"سلام {_display_name(row['کارشناس'])} عزیز 🌸",
        "",
        f"🎯 {PLAN_NAME}",
        "",
        "این پاداش تموم شد و این نتیجه‌ی تلاش قشنگته 🏆",
        *_lines(row),
        "",
        f"🎁 پاداش نهایی تو: {_money(row['prize_toman'])} تومان 🎉",
        "",
        "دمت گرم، واقعاً ترکوندی 🚀",
        "حلالت باشه، ممنون از زحمتت ❤️",
    ])


# ---- manager / channel report -------------------------------------------

_CSS = """
@font-face { font-family: 'Y'; src: url(data:font/ttf;base64,{reg}) format('truetype'); font-weight: normal; }
@font-face { font-family: 'Y'; src: url(data:font/ttf;base64,{bold}) format('truetype'); font-weight: bold; }
@font-face { font-family: 'Y'; src: local('Tahoma'); unicode-range: {rng}; font-weight: normal; }
@font-face { font-family: 'Y'; src: local('Tahoma Bold'); unicode-range: {rng}; font-weight: bold; }
body { margin: 0; font-family: 'Y', Tahoma, sans-serif; background: #ffffff; color: #232323; }
.wrap { width: 1100px; background: #ffffff; padding-bottom: 26px; }
.band { background: linear-gradient(135deg, #cf2547 0%, #a31a37 100%); padding: 26px 40px 28px; text-align: center; }
.top { display: flex; align-items: center; justify-content: center; gap: 16px; }
.logo { background: #fff; border-radius: 16px; padding: 8px 16px; display: flex; align-items: center; box-shadow: 0 2px 8px rgba(0,0,0,.25); }
.logo img { height: 46px; display: block; }
.title { color: #fff; font-size: 30px; font-weight: bold; }
.sub { color: #ffe3e9; font-size: 19px; margin-top: 8px; font-weight: bold; }
.pills { display: flex; justify-content: center; gap: 12px; margin-top: 16px; flex-wrap: wrap; }
.pill { background: rgba(255,255,255,.16); border: 1px solid rgba(255,255,255,.45); border-radius: 30px; padding: 9px 22px; color: #fff; font-size: 16px; }
.cards { display: flex; gap: 14px; margin: 22px 30px 0; }
.card { flex: 1; border: 1px solid #f5c9d3; background: #fff6f7; border-radius: 14px; padding: 14px 10px; text-align: center; }
.card .k { font-size: 14px; color: #a31a37; }
.card .v { font-size: 25px; font-weight: bold; color: #a31a37; margin-top: 6px; }
.card .u { font-size: 13px; color: #c46479; }
h3 { margin: 22px 30px 0; padding: 8px 14px; background: #fdeef1; border-right: 4px solid #cf2547; border-radius: 6px; color: #a31a37; font-size: 18px; }
table { width: calc(100% - 60px); margin: 10px 30px 0; border-collapse: collapse; }
thead th { background: #a31a37; color: #fff; font-size: 15px; padding: 11px 6px; }
tbody td { font-size: 15px; padding: 8px 6px; text-align: center; border-bottom: 1px solid #f3e1e5; }
tbody tr:nth-child(even) { background: #fff6f7; }
td.name { text-align: right; padding-right: 14px; font-weight: bold; }
td.small { font-size: 13px; color: #5c5048; }
td.pk { font-size: 13px; }
td.prize { font-weight: bold; color: #a31a37; }
.empty { text-align: center; color: #8a7a66; padding: 26px; font-size: 16px; }
.foot { margin: 22px 30px 0; padding-top: 12px; border-top: 2px solid #cf2547; text-align: center; font-size: 15px; color: #a31a37; }
"""


def _b64(path):
    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode("ascii")


def _cutoff_text(report):
    if report["is_final"]:
        return "📌 <b>نتیجه نهایی</b>"
    return f"🕒 داده‌ها تا: <b>ساعت {_fa(report['slot_jdt'].strftime('%H:%M'))}</b>"


def _html(report):
    table = report["table"]
    totals = report["package_totals"]

    cards = [
        ("کارشناسان مشمول پاداش", _money(len(table)), "نفر"),
        ("تعداد بسته‌های وصول‌شده", _money(sum(totals.values())), "بسته"),
        ("تعداد فاکتورها", _money(table["invoices"].sum() if len(table) else 0), "فاکتور"),
        ("مجموع پاداش", _money(table["prize_toman"].sum() if len(table) else 0), "تومان"),
    ]
    cards_html = "".join(
        f'<div class="card"><div class="k">{k}</div><div class="v">{v}</div><div class="u">{u}</div></div>'
        for k, v, u in cards)

    pkg_rows = "".join(
        f'<tr><td>بسته {_fa(package_label(key))} جلسه</td><td>{_money(PRIZES_TOMAN[key])}</td>'
        f'<td><b>{_money(totals.get(key, 0))}</b></td>'
        f'<td class="prize">{_money(PRIZES_TOMAN[key] * totals.get(key, 0))}</td></tr>'
        for key in PRIZES_TOMAN)

    top_rows = []
    for i, (_, r) in enumerate(table.head(TOP_N).iterrows(), start=1):
        pk = "، ".join(f"{_fa(package_label(k))} جلسه: {_fa(q)} عدد" for k, q in r["packages"].items())
        top_rows.append(
            f'<tr><td>{_MEDALS.get(i, "")} {_fa(i)}</td>'
            f'<td class="name">{r["کارشناس"]}</td>'
            f'<td class="small">{r["supervisor"]}</td>'
            f'<td class="small">{r["sarparast"]}</td>'
            f'<td class="pk">{pk}</td>'
            f'<td><b>{_fa(int(r["package_count"]))}</b></td>'
            f'<td class="prize">{_money(r["prize_toman"])}</td></tr>')
    top_title = (f"{_fa(TOP_N)} کارشناس برتر (بر اساس مبلغ پاداش)" if len(table) > TOP_N
                 else "کارشناسان مشمول پاداش (بر اساس مبلغ پاداش)")
    top_body = "".join(top_rows) or '<tr><td colspan="7" class="empty">هنوز فاکتور واجد شرایطی ثبت نشده است.</td></tr>'

    css = (_CSS.replace("{reg}", _b64(os.path.join(_FONTS, "W_yekan.ttf")))
               .replace("{bold}", _b64(os.path.join(_FONTS, "W_yekan Bold.ttf")))
               .replace("{rng}", _DIGIT_RANGE))
    return f"""<!DOCTYPE html><html dir="rtl" lang="fa"><head><meta charset="utf-8"><style>{css}</style></head>
<body><div class="wrap">
  <div class="band">
    <div class="top"><div class="logo"><img src="data:image/png;base64,{_b64(_LOGO_PATH)}"></div>
      <div class="title">گزارش جامع پاداش ویژه کارشناسان فروش همکده 🏆</div></div>
    <div class="sub">وصول فاکتورهای کارتابلی - یکشنبه ۱۹ مهر</div>
    <div class="pills"><div class="pill">📅 بازه اجرای پاداش: <b>۱۹ مهر ساعت ۱۰:۳۰ تا ۲۳:۵۹</b></div>
      <div class="pill">{_cutoff_text(report)}</div></div>
  </div>
  <div class="cards">{cards_html}</div>
  <h3>تفکیک بسته‌ها</h3>
  <table><thead><tr><th>بسته</th><th>پاداش هر بسته (تومان)</th><th>تعداد وصول‌شده</th><th>مجموع پاداش (تومان)</th></tr></thead>
  <tbody>{pkg_rows}</tbody></table>
  <h3>{top_title}</h3>
  <table><thead><tr><th>رتبه</th><th>کارشناس</th><th>سوپروایزر</th><th>سرپرست</th><th>بسته‌ها</th>
    <th>تعداد بسته</th><th>پاداش (تومان)</th></tr></thead>
  <tbody>{top_body}</tbody></table>
  <div class="foot">واحد سازنده گزارش: <b>واحد آنالیز گزارشات</b></div>
</div></body></html>"""


def _caption(report):
    if report["is_final"]:
        return f"{_FILE_BASENAME} - نتیجه نهایی (۱۹ مهر ۱۰:۳۰ تا ۲۳:۵۹)"
    return f"{_FILE_BASENAME} - وضعیت تا ساعت {_fa(report['slot_jdt'].strftime('%H:%M'))} ۱۹ مهر"


def build_channel_pdf(report):
    out_dir = os.path.join(_OUTPUT_DIR, "channel", report["slot_jdt"].strftime("%Y_%m_%d_%H%M"))
    os.makedirs(out_dir, exist_ok=True)
    png_path = os.path.join(out_dir, f"{_FILE_BASENAME}.png")
    pdf_path = os.path.join(out_dir, f"{_FILE_BASENAME}.pdf")
    with sync_playwright() as p:
        browser = p.chromium.launch(channel="chrome")
        page = browser.new_page(device_scale_factor=3)
        page.set_content(_html(report))
        page.locator(".wrap").screenshot(path=png_path, type="png")
        browser.close()
    with open(pdf_path, "wb") as f:
        f.write(img2pdf.convert(png_path))
    return pdf_path


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

    try:
        pdf_path = build_channel_pdf(report)
        caption = _caption(report)
        messages += [
            OutboundMessage(reward_id=reward_id, slot=slot, panel_user_id=name,
                            chat_user_id="", contact=name, text=caption, image=pdf_path)
            for name in CHANNEL_RECIPIENTS
        ]
    except Exception:
        logger.exception("'%s': channel report failed - personal messages still go out", reward_id)

    return messages
