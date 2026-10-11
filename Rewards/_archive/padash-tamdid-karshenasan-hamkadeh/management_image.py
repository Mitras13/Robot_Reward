"""
padash-tamdid-karshenasan-hamkadeh/management_image.py

End-of-campaign management-report IMAGE for گروه «گزارشات پاداش» - hamkadeh
twin of padash-karshenasan-5040/management_image.py, same overall template,
but this company has no "ضریب" concept (confirmed by the user 2026-09-22 on
the 5040 version) - so the "before vs. during" comparison metric here is
تعداد فاکتور تمدیدی (renewal invoice COUNT), not a coefficient.

⚠️ Critical rule from the user (2026-09-22): the renewal-invoice count must
NEVER be read from any smart-panel-computed column - "ستون فاکتور تمدیدی که
از پنل هوشمند میگیری قابل استناد نیست". It must be independently computed
with the SAME renewal-detection algorithm this reward's own builder.py
already uses (HK.FCP + HK.EXT, EXT window extended LOOKBACK_DAYS earlier
than the invoice window, see builder.py's _mark_renewals) - reused directly
from builder.py here (import, not re-implemented) so there is exactly one
copy of that algorithm.

Business rules (mirrors the 5040 version, confirmed by the user 2026-09-22):
  - مبلغ پاداش = sum of "reward_toman" across every کارشناس with >=1
    تمدیدی invoice, campaign-window table. No "(مازاد بر پورسانت)" label
    here (unlike 5040) - hamkadeh's reward has no base-commission concept
    to be "extra" beyond; ASSUMPTION, not separately re-confirmed by the
    user for this exact wording - flag if they want it phrased differently.
  - درصد پاداش = مبلغ پاداش / مبلغ کل فروش، هر دو در بازه‌ی پاداش. "مبلغ کل
    فروش" = همه‌ی فاکتورهای HK.FCP (نه فقط تمدیدی‌ها) در بازه - قبلاً
    (۲۰۲۶-۰۹-۲۲) توسط کاربر تأیید شده.
  - "قبل از پاداش" window = همون طول بازه‌ی پاداش (۹ روز)، بلافاصله قبلش:
    ۱۴ تا ۲۲ شهریور - عیناً مثل نسخه‌ی 5040 (طول کمپین این دو پاداش یکسانه).
  - تاثیر پاداش = (تعداد فاکتور تمدیدی بازه‌ی جدید − تعداد فاکتور تمدیدی
    بازه‌ی قبل) / تعداد فاکتور تمدیدی بازه‌ی قبل - مثبت یعنی رشد (همون
    جهتی که کاربر برای نسخه‌ی 5040 تأیید کرد).
"""

import importlib
import os

import jdatetime
import pandas as pd
from playwright.sync_api import sync_playwright

from core import context as ctx
from . import builder as bldr

FINAL_SLOT_DAY = 31
FINAL_SLOT_HOUR = 23
FINAL_SLOT_MINUTE = 59

CAMPAIGN_START_DATE = ctx.parse_jalali_date("1405/06/23")
CAMPAIGN_END_DATE = ctx.parse_jalali_date("1405/06/31")

# طول بازه‌ی پاداش = 9 روز (23 تا 31 شامل خودش) -> بازه‌ی "قبل" هم دقیقاً 9
# روز، بلافاصله قبل از شروع پاداش: 14 تا 22 شهریور - عیناً مثل نسخه‌ی 5040
# (طول کمپین این دو پاداش یکسانه، هر دو 23->31 شهریورن).
_CAMPAIGN_LEN_DAYS = (CAMPAIGN_END_DATE - CAMPAIGN_START_DATE).days + 1
PRE_PERIOD_END = CAMPAIGN_START_DATE - jdatetime.timedelta(seconds=1)
PRE_PERIOD_START = CAMPAIGN_START_DATE - jdatetime.timedelta(days=_CAMPAIGN_LEN_DAYS)

_OUTPUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "outputs")

_FONT_PATH = r"C:\Windows\Fonts\BTitrBd.ttf"
TITLE_BG = "#e06666"
HEADER_BG = "#f4b8b8"
COMPANY_LABEL = "همکده"

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
    millions = round(amount / 1_000_000)
    if abs(millions) >= 1000:
        billions = millions / 1000
        return _fa(f"{billions:.1f}") + " میلیارد تومان"
    return _fa(f"{millions:,}") + " میلیون تومان"


def _fmt_toman_avg(amount):
    """مثل _fmt_toman_human ولی با یک رقم اعشار در محدوده‌ی میلیون هم - برای
    «متوسط پاداش هر نفر» که معمولاً چند میلیون تومانه و گرد کردن بدون اعشار
    خیلی نادقیق می‌شه (همون فیکس نسخه‌ی 5040، ۲۰۲۶-۰۹-۲۳)."""
    millions = amount / 1_000_000
    if abs(millions) >= 1000:
        return _fa(f"{millions / 1000:.1f}") + " میلیارد تومان"
    return _fa(f"{millions:.2f}") + " میلیون تومان"


def _fmt_percent(fraction):
    """برای درصدهای "تغییر/تاثیر" (با علامت +/-). <bdi dir=ltr> isolate -
    همون فیکس bidi تأییدشده روی نسخه‌ی 5040 (۲۰۲۶-۰۹-۲۲)، تا "+"/عدد/"٪"
    وسط متن فارسی به‌هم نریزه. رنگ: مثبت سبز، منفی قرمز - طبق درخواست کاربر
    ۲۰۲۶-۰۹-۲۲ ("+ ها به رنگ سبز بشن")."""
    sign = "+" if fraction > 0 else ("" if fraction == 0 else "-")
    color = "#1b8a2f" if fraction > 0 else ("#c62828" if fraction < 0 else "inherit")
    number = sign + _fa(f"{abs(fraction) * 100:.1f}") + "٪"
    return f'<bdi dir="ltr" style="unicode-bidi: isolate; color: {color};">{number}</bdi>'


def _fmt_percent_plain(fraction):
    """برای درصدهای توصیفیِ ساده (نه دلتا/تغییر) - بدون علامت + همیشگی،
    چون این‌ها خودشون یه مقدار مثبتِ ثابتن (مثل «درصد تمدیدی از فروش کل»),
    نه یک تغییر نسبت به چیزی."""
    number = _fa(f"{fraction * 100:.1f}") + "٪"
    return f'<bdi dir="ltr" style="unicode-bidi: isolate;">{number}</bdi>'


def _fmt_count(n):
    return _fa(f"{int(n):,}") + " فاکتور"


def _period_label(start_date, end_date):
    return (
        f"از {_fa(start_date.day)} {MONTH_NAMES[start_date.month]} "
        f"تا {_fa(end_date.day)} {MONTH_NAMES[end_date.month]} {_fa(start_date.year)}"
    )


def _renewal_stats_for_period(period_start, period_end, lookback_days):
    """(renewal_count, renewal_amount_toman, total_sales_toman) for
    [period_start, period_end], using builder.py's OWN renewal-detection
    functions (imported, not duplicated) - never a smart-panel column, per
    the user's explicit instruction 2026-09-22. total_sales_toman is EVERY
    HK.FCP invoice in the window (تمدیدی یا نه), same definition already
    confirmed for "کل فروش" elsewhere in this reward."""
    fcp = importlib.import_module("API_Downloader.HK.FCP")
    ext = importlib.import_module("API_Downloader.HK.EXT")
    fcp_path = fcp.fetch(None, period_start, period_end)
    ext_path = ext.fetch(None, ctx.shift_days(period_start, -lookback_days), period_end)

    dff = pd.read_csv(fcp_path, encoding="utf-8-sig")
    dfe = pd.read_csv(ext_path, encoding="utf-8-sig", usecols=["تاریخ ورود", "موبایل", "عاملیت"])
    dfe = dfe[~dfe["عاملیت"].isin(bldr.EXCLUDED_AGENCIES)].copy()
    dfe["تاریخ ورود"] = bldr._jalali_col_to_gregorian(dfe["تاریخ ورود"])

    dff = bldr._add_collection_date(dff)
    dff = bldr._filter_by_collection_date(dff, period_start, period_end)
    dff = bldr._mark_renewals(dff, dfe, lookback_days)

    total_sales_toman = int(dff["مبلغ فاکتور"].sum() / 10)

    df = dff[dff["فاکتور تمدید"] == "تمدیدی"].copy()
    df = df[df["ثبت کننده"].apply(bldr._has_english_suffix)]
    renewal_amount_toman = int(df["مبلغ فاکتور"].sum() / 10)
    return len(df), renewal_amount_toman, total_sales_toman


# ۲۰۲۶-۰۹-۲۳: متن تحلیل قبلی (تیرهای پویا + _CONFOUND_NOTE) جایگزین شد با
# این پیام ثابت - خروجی یک تحلیل عمیق مدیریتی (Volume vs Efficiency،
# Before/During کامل روی HK.FCP/HK.EXT، Reward Tier breakdown، بررسی سطح-
# کارشناس نشون‌دهنده‌ی این‌که اکثریت کارشناسان دارای سابقه در واقع افت سهم
# تمدیدی داشتن) که کاربر صریحاً تأیید کرد و خواست همین متن برای بخش تحلیل
# عکس مدیریتی استفاده بشه - همون الگوی نسخه‌ی 5040.
_MANAGEMENT_ANALYSIS_TEXT = (
    "کمپین در دوره‌ی مورد بررسی با افزایش سهم تمدیدی از فروش همراه بوده است، اما این رشد عمدتاً ناشی از "
    "افت سریع‌تر کل فروش نسبت به افت مبلغ تمدیدی است، نه بهبود مطلق در رفتار تمدید. اکثریت کارشناسان "
    "دارای سابقه در این بازه در واقع افت سهم تمدیدی داشته‌اند و رشد سطح‌شرکت عمدتاً از عملکرد تعداد "
    "محدودی از کارشناسان می‌آید. بنابراین داده‌های موجود نمی‌توانند اثر خالص کمپین را از اثر هم‌زمان "
    "کاهش فروش کل جدا کنند و طراحی baseline/control مناسب در کمپین‌های بعدی ضروری است."
)


def _analysis_text(impact_fraction, reward_percent, percent_before, percent_now, count_before, count_now):
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
  .count-row {{ display: flex; justify-content: space-around; padding: 12px 4px; background: {header_bg}; border-radius: 6px; margin: 8px 4px; font-size: 14px; color: #000000; font-weight: bold; text-align: center; }}
  .period-note {{ display: block; font-size: 11px; font-weight: normal; color: #555555; margin-top: 3px; }}
  .count-row-small {{ display: flex; justify-content: space-around; padding: 8px 4px; background: {header_bg}; border-radius: 6px; margin: 6px 4px; font-size: 12px; color: #000000; font-weight: bold; text-align: center; opacity: .85; }}
  .count-row-small .period-note {{ font-size: 10px; }}
  .analysis {{ box-sizing: border-box; margin: 10px 18px 16px; padding: 10px 12px; border: 1px solid #000000; background: #fff7f7; color: #000000; font-size: 13px; line-height: 1.8; }}
</style>
</head>
<body>
<div class="wrap">
  <div class="company-badge">{company_label}</div>
  <div class="title">{title}<br>{period_line}</div>
  <div class="subtitle">گزارش مدیریتی</div>
  <div class="rows">
    <div class="row"><span class="label">🎁 مبلغ پاداش</span><span class="value">{reward_amount}</span></div>
    <div class="row"><span class="label">📊 درصد پاداش از کل فروش</span><span class="value">{reward_percent}</span></div>
    <div class="row"><span class="label">📈 تاثیر پاداش (رشد سهم تمدیدی از فروش)</span><span class="value">{percent_impact}</span></div>
    <div class="row"><span class="label">👥 کارشناسان شامل پاداش</span><span class="value">{coverage}</span></div>
    <div class="row"><span class="label">💵 متوسط پاداش به ازای هر کارشناس مشمول</span><span class="value">{cost_per_rewarded}</span></div>
    <div class="count-row">
      <span>درصد تمدیدی از فروش کل: {percent_before}<span class="period-note">(بازه‌ی ۹ روزه‌ی قبل)</span></span>
      <span>درصد تمدیدی از فروش کل: {percent_during}<span class="period-note">(بازه‌ی ۹ روزه‌ی پاداش)</span></span>
    </div>
    <div class="count-row-small">
      <span>تعداد فاکتور تمدیدی: {count_before}<span class="period-note">(بازه‌ی ۹ روزه‌ی قبل)</span></span>
      <span>تعداد فاکتور تمدیدی: {count_during}<span class="period-note">(بازه‌ی ۹ روزه‌ی پاداش)</span></span>
    </div>
  </div>
  <div class="analysis">{analysis}</div>
</div>
</body>
</html>"""


def build_report_image(reward_title, total_reward_toman, total_sales_toman,
                        renewal_count_now, renewal_amount_toman_now, slot_jdt,
                        rewarded_count=None, total_count=None):
    """total_sales_toman/renewal_count_now/renewal_amount_toman_now are the
    CURRENT-period (بازه‌ی پاداش) numbers - passed in by builder.py from
    data it already downloaded for this slot (no extra download needed for
    that side). Downloads+computes the pre-period stats separately
    (different window, LOOKBACK_DAYS=4 same as builder.py's own), renders
    the PNG, saves it to outputs/, and returns (image_path, stats_dict) - or
    None if total_sales_toman is 0.

    ۲۰۲۶-۰۹-۲۲ (تصحیح کاربر): "تاثیر پاداش" دیگه بر مبنای رشد تعداد فاکتور
    تمدیدی نیست - بر مبنای رشد «درصد تمدیدی از کل فروش» (renewal_amount /
    total_sales، هر دو بازه) حساب می‌شه. تعداد فاکتور همچنان به‌صورت
    اطلاعاتی (نه مبنای تاثیر) نمایش داده می‌شه.

    rewarded_count/total_count (۲۰۲۶-۰۹-۲۳، درخواست کاربر): تعداد کارشناسانی
    که reward_toman‌شون > ۰ شده، تقسیم بر کل ثبت‌کننده‌های واجد شرایط این
    بازه (همه‌ی فاکتورها، نه فقط تمدیدی - چون فقط کسایی که حداقل یه فاکتور
    تمدیدی داشتن وارد grouped می‌شن، طبق تأیید کاربر مخرج باید از کل dff
    قبل از فیلتر تمدیدی بیاد، نه از grouped). اختیاری (None) تا زنگ نزنه
    اگه builder.py قدیمی صداش بزنه."""
    if total_sales_toman <= 0:
        return None

    from . import requirements as req
    renewal_count_before, renewal_amount_toman_before, total_sales_toman_before = _renewal_stats_for_period(
        PRE_PERIOD_START, PRE_PERIOD_END, req.LOOKBACK_DAYS,
    )

    reward_percent = total_reward_toman / total_sales_toman
    percent_before = (
        renewal_amount_toman_before / total_sales_toman_before if total_sales_toman_before else 0.0
    )
    percent_now = renewal_amount_toman_now / total_sales_toman
    percent_impact = (percent_now - percent_before) / percent_before if percent_before else 0.0
    coverage_fraction = (rewarded_count / total_count) if total_count else 0.0

    period_line = _period_label(CAMPAIGN_START_DATE, CAMPAIGN_END_DATE)

    if total_count:
        coverage = f"{_fa(rewarded_count)} از {_fa(total_count)} نفر ({_fmt_percent_plain(coverage_fraction)})"
    else:
        coverage = "-"

    # متوسط پاداش به ازای هر کارشناس مشمول (۲۰۲۶-۰۹-۲۳، همون افزودنی‌ای که
    # روی نسخه‌ی 5040 هم اضافه شد - کل مبلغ پاداش تقسیم بر تعداد کارشناسان
    # مشمول، نه کل کارشناسان).
    cost_per_rewarded = (
        _fmt_toman_avg(total_reward_toman / rewarded_count) if rewarded_count else "-"
    )

    html = _HTML_TEMPLATE.format(
        font_b64=_font_b64_cached(),
        title_bg=TITLE_BG, header_bg=HEADER_BG, company_label=COMPANY_LABEL,
        title=reward_title, period_line=period_line,
        reward_amount=_fmt_toman_human(total_reward_toman),
        reward_percent=_fmt_percent_plain(reward_percent),
        percent_impact=_fmt_percent(percent_impact),
        coverage=coverage,
        cost_per_rewarded=cost_per_rewarded,
        percent_before=_fmt_percent_plain(percent_before),
        percent_during=_fmt_percent_plain(percent_now),
        count_before=_fmt_count(renewal_count_before),
        count_during=_fmt_count(renewal_count_now),
        analysis=_analysis_text(
            percent_impact, reward_percent, percent_before, percent_now,
            renewal_count_before, renewal_count_now,
        ),
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
        "renewal_count_before": renewal_count_before,
        "renewal_count_now": renewal_count_now,
        "percent_before": percent_before,
        "percent_now": percent_now,
        "percent_impact": percent_impact,
        "rewarded_count": rewarded_count,
        "total_count": total_count,
        "coverage_fraction": coverage_fraction,
    }
    return image_path, stats


_font_cache = None


def _font_b64_cached():
    global _font_cache
    if _font_cache is None:
        import base64
        with open(_FONT_PATH, "rb") as f:
            _font_cache = base64.b64encode(f.read()).decode("ascii")
    return _font_cache
