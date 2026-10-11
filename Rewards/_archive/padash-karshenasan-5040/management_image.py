"""
padash-karshenasan-5040/management_image.py

End-of-campaign management-report IMAGE for گروه «گزارشات پاداش», per the
user's explicit spec (2026-09-22). Scope confirmed with the user: 5040 only
for now (hamkadeh deferred - it has no "ضریب" concept in its own data, user
wants to review that separately before it's built).

Only fires on the campaign's FINAL scheduled slot (see FINAL_SLOT below) -
every other slot, build() in builder.py just skips this entirely (no extra
download, no image). Called from builder.py with the already-computed
per-کارشناس `grouped` DataFrame for the campaign window (so "بازه پاداش"
numbers reuse data already downloaded for this slot - no extra request for
that side).

Business rules (all confirmed by the user 2026-09-22):
  - مبلغ پاداش (مازاد بر پورسانت) = sum of "پاداش مازاد بر آوردی" across
    every eligible کارشناس, campaign-window table (same "extra beyond base
    15%" concept builder.py already computes per-کارشناس).
  - درصد پاداش = مبلغ پاداش / مبلغ کل فروش، هر دو در همون بازه‌ی پاداش.
    "مبلغ کل فروش" = sum of "مبلغ وصول کل" (SP.54.SPK's "paid" column,
    already ×1,000,000'd) across the same table - confirmed by the user as
    the definition of "کل فروش" for 5040 specifically.
  - "قبل از پاداش" window = a window the SAME LENGTH as the campaign,
    immediately preceding it (confirmed 2026-09-22: campaign is 23->31
    شهریور, 9 days, so "قبل" is 14->22 شهریور).
  - "ضریب" (both windows) = per-کارشناس paid_coe, summed per-کارشناس (same
    grouping/eligibility as builder.py's campaign-window table - a کارشناس
    can appear on >1 row), then averaged (simple unweighted mean) across
    every eligible کارشناس. ⚠️ ASSUMPTION not explicitly specified by the
    user (they confirmed paid_coe as the metric, not this aggregation
    method) - a simple mean, not a وصولی-weighted mean. Flag to the user if
    this doesn't match their intent.
  - تاثیر پاداش فروش = (ضریب بازه − ضریب قبل) / ضریب قبل - confirmed
    2026-09-22 (user explicitly flipped the sign from their first draft so
    a positive number means the campaign helped).
  - Amount display: drop the last 6 digits (i.e. show in میلیون تومان); if
    that میلیون figure is >= 1000 (i.e. the original amount is >= 1
    میلیارد), show بجاش as X.X میلیارد تومان (one decimal) instead -
    confirmed 2026-09-22 with the 11.3میلیارد/772میلیون examples.
"""

import base64
import importlib
import os

import jdatetime
import pandas as pd
from playwright.sync_api import sync_playwright

from core import context as ctx

# دقیقاً همون اسلات آخر schedule.csv این پاداش (month:31, آخرین ساعتش
# 23:59) - این ثابت باید هم‌زمان با schedule.csv دستی سینک نگه داشته بشه،
# قراردادی جدا از اون فایل نیست (هیچ راهی برای خوندن "آخرین اسلات" از
# schedule.csv به‌صورت عمومی وجود نداره - mini-زبونش این مفهوم رو نداره).
FINAL_SLOT_DAY = 31
FINAL_SLOT_HOUR = 23
FINAL_SLOT_MINUTE = 59

CAMPAIGN_START_DATE = ctx.parse_jalali_date("1405/06/23")
CAMPAIGN_END_DATE = ctx.parse_jalali_date("1405/06/31")

# طول بازه‌ی پاداش = 9 روز (23 تا 31 شامل خودش) -> بازه‌ی "قبل" هم دقیقاً 9
# روز، بلافاصله قبل از شروع پاداش: 14 تا 22 شهریور - عیناً طبق مثال کاربر.
_CAMPAIGN_LEN_DAYS = (CAMPAIGN_END_DATE - CAMPAIGN_START_DATE).days + 1
PRE_PERIOD_END = CAMPAIGN_START_DATE - jdatetime.timedelta(seconds=1)
PRE_PERIOD_START = CAMPAIGN_START_DATE - jdatetime.timedelta(days=_CAMPAIGN_LEN_DAYS)

_OUTPUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "outputs")

_FONT_PATH = r"C:\Windows\Fonts\BTitrBd.ttf"
# تم رنگی آبی مخصوص 5040 (کاربر ۲۰۲۶-۰۹-۲۲: "شرکت 5040 باید تم رنگی آبی
# داشته باشه") - در مقابل تم قرمز که برای همکده نگه داشته شده.
TITLE_BG = "#3b72b8"
HEADER_BG = "#cde0f4"
# قالب/برند این گزارش تصویری مشخصاً برای شرکت 5040 است (کاربر ۲۰۲۶-۰۹-۲۲:
# "قالب مشخص هم بزار که این قالب شرکت 5040 بشه") - بج بالای تصویر.
COMPANY_LABEL = "5040"

MONTH_NAMES = [
    "", "فروردین", "اردیبهشت", "خرداد", "تیر", "مرداد", "شهریور",
    "مهر", "آبان", "آذر", "دی", "بهمن", "اسفند",
]
PERSIAN_DIGITS = str.maketrans("0123456789", "۰۱۲۳۴۵۶۷۸۹")


def is_final_slot(slot_jdt):
    return (
        slot_jdt.day == FINAL_SLOT_DAY
        and slot_jdt.hour == FINAL_SLOT_HOUR
        and slot_jdt.minute == FINAL_SLOT_MINUTE
    )


def _fa(text):
    return str(text).translate(PERSIAN_DIGITS)


def _fmt_toman_human(amount):
    """۶ رقم آخر حذف (میلیون تومان)؛ اگه >= ۱۰۰۰ میلیون بود (یعنی >= ۱
    میلیارد)، به میلیارد با یک رقم اعشار نشون بده - طبق مثال کاربر
    (۱۱.۳ میلیارد تومن / ۷۷۲ میلیون تومن)."""
    millions = round(amount / 1_000_000)
    if abs(millions) >= 1000:
        billions = millions / 1000
        return _fa(f"{billions:.1f}") + " میلیارد تومان"
    return _fa(f"{millions:,}") + " میلیون تومان"


def _fmt_toman_avg(amount):
    """مثل _fmt_toman_human ولی با یک رقم اعشار در محدوده‌ی میلیون هم (نه
    فقط میلیارد) - برای «متوسط پاداش هر نفر» که معمولاً چند میلیون تومانه و
    گرد کردن بدون اعشار (مثل _fmt_toman_human) خیلی نادقیق می‌شه (۲۰۲۶-۰۹-۲۳)."""
    millions = amount / 1_000_000
    if abs(millions) >= 1000:
        return _fa(f"{millions / 1000:.1f}") + " میلیارد تومان"
    return _fa(f"{millions:.2f}") + " میلیون تومان"


def _fmt_percent(fraction):
    """⚠️ باگ واقعی (۲۰۲۶-۰۹-۲۲، دیده‌شده در تست تصویر اول): بدون isolate،
    مرورگر ترتیب "+"/عدد/"٪" رو وسط متن فارسیِ RTL به‌هم می‌ریزه (مثلاً
    "+1.1٪" به‌صورت "+٪1.1" نمایش داده می‌شه) - همون کلاس مشکلی که
    render.py._bidi_isolate برای رشته‌های "HH:MM" حلش کرده بود، اینجا هم با
    <bdi dir="ltr"> (نسخه‌ی HTML/CSS همون ایزوله‌سازی، چون این متن با
    Playwright/Chromium رندر می‌شه نه کنسول) حل شده - "+" همیشه دقیقاً سمت
    چپ عدد، "٪" همیشه دقیقاً سمت راست عدد می‌مونه.
    رنگ: مثبت سبز، منفی قرمز - طبق درخواست کاربر ۲۰۲۶-۰۹-۲۲ ("+ ها به رنگ
    سبز بشن")."""
    sign = "+" if fraction > 0 else ("" if fraction == 0 else "-")
    color = "#1b8a2f" if fraction > 0 else ("#c62828" if fraction < 0 else "inherit")
    number = sign + _fa(f"{abs(fraction) * 100:.1f}") + "٪"
    return f'<bdi dir="ltr" style="unicode-bidi: isolate; color: {color};">{number}</bdi>'


def _fmt_percent_plain(fraction):
    """برای درصد توصیفیِ ساده (نه دلتا/تغییر) - بدون علامت + همیشگی، چون
    خودش یه مقدار مثبتِ ثابته (مثل «درصد کارشناسان شامل پاداش»), نه یک
    تغییر نسبت به چیزی."""
    number = _fa(f"{fraction * 100:.1f}") + "٪"
    return f'<bdi dir="ltr" style="unicode-bidi: isolate;">{number}</bdi>'


def _fmt_koeff(value):
    """بدون اعشار - طبق درخواست کاربر ۲۰۲۶-۰۹-۲۲ ("اعشار ضریب وصولی حذف
    بشه و عدد رند بشه")."""
    return _fa(f"{round(value):,}")


def _period_label(start_date, end_date):
    return (
        f"از {_fa(start_date.day)} {MONTH_NAMES[start_date.month]} "
        f"تا {_fa(end_date.day)} {MONTH_NAMES[end_date.month]} {_fa(start_date.year)}"
    )


# SP.54.SPK's raw response carries one extra row, AAName == "5040" exactly
# (not a per-کارشناس row - all its other identity columns like
# supervisor__name/CPC are blank), with every "کل" (company-wide total)
# number the smart panel itself already computed - paid_coe (ضریب وصولی
# کل), paid (مبلغ وصولی کل), cartable_paid (وصولی کارتابلی کل), etc.
# Confirmed by the user 2026-09-22, after my first version wrongly
# approximated "ضریب وصولی کل" as a simple mean across eligible کارشناسان
# (which doesn't match the panel's own authoritative total - off by ~2%
# for ضریب, and the equivalent مبلغ وصول کل approximation was off by ~8%).
# ANY "کل" metric for this company must come from this row, never be
# summed/averaged from the per-کارشناس rows.
COMPANY_TOTAL_ROW_NAME = "5040"


def company_totals_from_df(df):
    """(paid_coe, paid_toman) from the AAName=="5040" row of an already-
    loaded SP.54.SPK DataFrame, or None if that row isn't present (should
    not happen in practice)."""
    total_rows = df[df["AAName"] == COMPANY_TOTAL_ROW_NAME]
    if total_rows.empty:
        return None
    row = total_rows.iloc[0]
    paid_coe = float(pd.to_numeric(row["paid_coe"], errors="coerce") or 0)
    paid_toman = int(round(float(pd.to_numeric(row["paid"], errors="coerce") or 0) * 1_000_000))
    return paid_coe, paid_toman


def _koeff_for_period(period_start, period_end):
    """Downloads SP.54.SPK fresh for [period_start, period_end] (NOT the
    campaign-window raw_paths already given to build() - this is a
    different window) and returns that period's company-total ضریب وصولی
    (the AAName=="5040" row's paid_coe, see company_totals_from_df)."""
    spk = importlib.import_module("API_Downloader.SP.54.SPK")
    raw_path = spk.fetch(None, period_start, period_end)
    df = pd.read_csv(raw_path, encoding="utf-8-sig")
    if df.empty:
        return 0.0
    totals = company_totals_from_df(df)
    return totals[0] if totals else 0.0


# ۲۰۲۶-۰۹-۲۳: متن تحلیل قبلی (تیرهای پویا + _CONFOUND_NOTE حدسی درباره‌ی
# سرپرستان تبلیغات) جایگزین شد با این پیام ثابت - خروجی نهاییِ یک تحلیل
# عمیق مدیریتی (Volume vs Efficiency، Before/During کامل با تمام ستون‌های
# SP.54.SPK، Reward Tier breakdown، بازبینی چندمرحله‌ای توسط کاربر) که
# کاربر صریحاً بعد از دیدن و اصلاح چند نسخه تأیید کرد و گفت همین متن برای
# بخش تحلیل عکس مدیریتی مناسب است. دیگر بر مبنای impact_fraction/
# reward_percent پویا محاسبه نمی‌شود - چون خودِ این متن حاصل جمع‌بندی آن
# اعداد است، نه یک قاعده‌ی عمومی برای هر کمپین آینده.
_MANAGEMENT_ANALYSIS_TEXT = (
    "کمپین در دوره‌ی مورد بررسی با افزایش ضریب وصولی و بهبود شاخص‌های کارایی همراه بوده است، "
    "اما هم‌زمان تعداد شماره‌های تبلیغاتی دریافتی و تعداد تماس‌ها به‌طور قابل‌توجهی (حدود ۳۵ تا ۳۷ درصد) "
    "کاهش یافته و در نتیجه مبلغ وصولی کل ۵.۲۵٪ افت کرده است. بنابراین داده‌های موجود بهبود کارایی را "
    "نشان می‌دهند، اما برای تعیین سهم واقعی کمپین در این تغییرات، کنترل اثر کاهش تبلیغات و طراحی "
    "baseline/control مناسب در کمپین‌های بعدی ضروری است."
)


def _analysis_text(impact_fraction, reward_percent, koeff_before, koeff_during):
    return _MANAGEMENT_ANALYSIS_TEXT


_HTML_TEMPLATE = """<!DOCTYPE html>
<html dir="rtl" lang="fa">
<head>
<meta charset="utf-8">
<style>
  @font-face {{
    font-family: 'BTitr';
    src: url(data:font/ttf;base64,{font_b64}) format('truetype');
    font-weight: bold;
  }}
  body {{ margin: 0; font-family: 'BTitr', Tahoma, sans-serif; background: #ffffff; }}
  .wrap {{ position: relative; display: flex; flex-direction: column; width: 640px; background: #ffffff; border: 1px solid #000000; }}
  .company-badge {{
    position: absolute; top: 10px; left: 10px; background: #ffffff; color: {title_bg};
    border: 2px solid #ffffff; border-radius: 999px; padding: 4px 14px; font-size: 14px; font-weight: bold;
  }}
  .title {{ background: {title_bg}; color: #ffffff; font-weight: bold; font-size: 19px; padding: 14px; line-height: 1.9; text-align: center; }}
  .subtitle {{ background: {header_bg}; color: #000000; font-weight: bold; font-size: 15px; padding: 10px; text-align: center; }}
  .rows {{ padding: 16px 18px; }}
  .row {{ display: flex; justify-content: space-between; align-items: center; padding: 10px 4px; border-bottom: 1px solid #dddddd; font-size: 15px; color: #000000; }}
  .row:last-child {{ border-bottom: none; }}
  .row .label {{ font-weight: bold; }}
  .row .value {{ font-weight: bold; }}
  .koeff-row {{ display: flex; justify-content: space-around; padding: 12px 4px; background: {header_bg}; border-radius: 6px; margin: 8px 4px; font-size: 15px; color: #000000; font-weight: bold; text-align: center; }}
  .period-note {{ display: block; font-size: 11px; font-weight: normal; color: #555555; margin-top: 3px; }}
  .analysis {{ box-sizing: border-box; margin: 10px 18px 16px; padding: 10px 12px; border: 1px solid #000000; background: #fff7f7; color: #000000; font-size: 13px; line-height: 1.8; }}
</style>
</head>
<body>
<div class="wrap">
  <div class="company-badge">{company_label}</div>
  <div class="title">{title}<br>{period_line}</div>
  <div class="subtitle">گزارش مدیریتی</div>
  <div class="rows">
    <div class="row"><span class="label">🎁 مبلغ پاداش (مازاد بر پورسانت)</span><span class="value">{reward_amount}</span></div>
    <div class="row"><span class="label">📊 درصد پاداش از کل فروش</span><span class="value">{reward_percent}</span></div>
    <div class="row"><span class="label">📈 تاثیر پاداش اعلامی</span><span class="value">{sales_impact}</span></div>
    <div class="row"><span class="label">👥 کارشناسان شامل پاداش</span><span class="value">{coverage}</span></div>
    <div class="row"><span class="label">💵 متوسط پاداش به ازای هر کارشناس مشمول</span><span class="value">{cost_per_rewarded}</span></div>
    <div class="koeff-row">
      <span>ضریب وصولی: {koeff_before}<span class="period-note">(بازه‌ی ۹ روزه‌ی قبل)</span></span>
      <span>ضریب وصولی: {koeff_during}<span class="period-note">(بازه‌ی ۹ روزه‌ی پاداش)</span></span>
    </div>
  </div>
  <div class="analysis">{analysis}</div>
</div>
</body>
</html>"""


def build_report_image(reward_title, total_reward_toman, total_sales_toman, koeff_during, slot_jdt,
                        rewarded_count=None, total_count=None):
    """total_sales_toman/koeff_during are the CURRENT-period (بازه‌ی پاداش)
    company totals - passed in by builder.py from the AAName=="5040" row of
    the SP.54.SPK data it already downloaded for this slot (see
    company_totals_from_df) - no extra download needed for this side.
    Downloads the pre-period SPK data separately (different window),
    computes every number, renders the PNG, saves it to outputs/, and
    returns (image_path, stats_dict) - or None if total_sales_toman/
    koeff_during aren't usable (نباید پیش بیاد عملاً - یعنی ردیف کل شرکت
    تو داده‌ی خام نبوده).

    rewarded_count/total_count (۲۰۲۶-۰۹-۲۳، درخواست کاربر): تعداد کارشناسانی
    که پاداش مازاد بر آوردی‌شون > ۰ شده، تقسیم بر کل کارشناسان واجد شرایط
    این بازه (len(grouped) در builder.py - همون جدولی که همه‌ی کارشناسان
    واجد شرایط توش هستن، صرف‌نظر از این‌که پاداشی گرفتن یا نه) - به تفکیک
    همین شرکت. اختیاری (None) تا زنگ نزنه اگه builder.py قدیمی صداش بزنه."""
    if total_sales_toman <= 0 or koeff_during is None:
        return None

    koeff_before = _koeff_for_period(PRE_PERIOD_START, PRE_PERIOD_END)

    reward_percent = total_reward_toman / total_sales_toman
    sales_impact = (koeff_during - koeff_before) / koeff_before if koeff_before else 0.0
    coverage_fraction = (rewarded_count / total_count) if total_count else 0.0

    period_line = _period_label(CAMPAIGN_START_DATE, CAMPAIGN_END_DATE)

    if total_count:
        coverage = f"{_fa(rewarded_count)} از {_fa(total_count)} نفر ({_fmt_percent_plain(coverage_fraction)})"
    else:
        coverage = "-"

    # متوسط پاداش به ازای هر کارشناس مشمول (۲۰۲۶-۰۹-۲۳، درخواست کاربر بعد از
    # تحلیل مدیریتی کامل - "Cost per Rewarded Expert") = کل مبلغ پاداش تقسیم
    # بر تعداد کارشناسان مشمول، نه کل کارشناسان - عددی ساده‌تر از درصدها برای
    # خوانش مدیریتی.
    cost_per_rewarded = (
        _fmt_toman_avg(total_reward_toman / rewarded_count) if rewarded_count else "-"
    )

    html = _HTML_TEMPLATE.format(
        font_b64=_font_b64_cached(),
        title_bg=TITLE_BG, header_bg=HEADER_BG, company_label=COMPANY_LABEL,
        title=reward_title, period_line=period_line,
        reward_amount=_fmt_toman_human(total_reward_toman),
        reward_percent=_fmt_percent(reward_percent),
        sales_impact=_fmt_percent(sales_impact),
        coverage=coverage,
        cost_per_rewarded=cost_per_rewarded,
        koeff_before=_fmt_koeff(koeff_before),
        koeff_during=_fmt_koeff(koeff_during),
        analysis=_analysis_text(sales_impact, reward_percent, koeff_before, koeff_during),
    )

    os.makedirs(_OUTPUT_DIR, exist_ok=True)
    slot_label = slot_jdt.strftime("%Y_%m_%d_%H%M")
    image_path = os.path.join(_OUTPUT_DIR, f"{slot_label}_management_report.png")

    with sync_playwright() as p:
        browser = p.chromium.launch(channel="chrome")
        page = browser.new_page()
        page.set_content(html)
        page.locator(".wrap").screenshot(path=image_path)
        browser.close()

    stats = {
        "total_reward_toman": total_reward_toman,
        "total_sales_toman": total_sales_toman,
        "reward_percent": reward_percent,
        "koeff_before": koeff_before,
        "koeff_during": koeff_during,
        "sales_impact": sales_impact,
        "rewarded_count": rewarded_count,
        "total_count": total_count,
        "coverage_fraction": coverage_fraction,
    }
    return image_path, stats


_font_cache = None


def _font_b64_cached():
    global _font_cache
    if _font_cache is None:
        with open(_FONT_PATH, "rb") as f:
            _font_cache = base64.b64encode(f.read()).decode("ascii")
    return _font_cache
