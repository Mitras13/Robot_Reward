import base64
import os
import jdatetime
import pandas as pd
from playwright.sync_api import sync_playwright

REPORT_ID = "hk-tamdidi"
FCP_KEY = "HK.FCP"
EXT_KEY = "HK.EXT"

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUTPUT_DIR = os.path.join(_PROJECT_ROOT, "outputs", REPORT_ID)

# How many days back of ad-traffic (EXT) entries count as "this purchase came
# from an ad" for a given invoice's تاریخ وصول. Single place to change this -
# Reports/hk_tamdidi.py imports it from here so the period-download window
# and the row-level lookback logic never drift apart.
LOOKBACK_DAYS = 4

# ⚠️ B Titr is a bold-only display font - see Report_Builders/KharidMojaddad54.py
# for why this is embedded as base64 instead of referenced by name.
_FONT_PATH = r"C:\Windows\Fonts\BTitrBd.ttf"

WEEKDAY_FA = ["شنبه", "یکشنبه", "دوشنبه", "سه‌شنبه", "چهارشنبه", "پنج‌شنبه", "جمعه"]
MONTH_NAMES = [
    "", "فروردین", "اردیبهشت", "خرداد", "تیر", "مرداد", "شهریور",
    "مهر", "آبان", "آذر", "دی", "بهمن", "اسفند",
]
PERSIAN_DIGITS = str.maketrans("0123456789", "۰۱۲۳۴۵۶۷۸۹")

# Same visual style as Report_Builders/KharidMojaddad54.py, red theme instead
# of blue - per the user, this is now the standard palette to reuse whenever
# a future report calls for a "red theme" image.
TITLE_BG = "#e06666"
HEADER_BG = "#f4b8b8"

# One entry per output image: (group-by column in the raw FCP data, display
# label used in title/column header, name column label, output_id suffix).
GROUPS = [
    ("ثبت کننده", "کارشناسان", "نام کارشناس", "tamdidi_hk_karshenasan"),
    ("سوپروایزران ثبت کننده فاکتور", "سوپروایزران", "سوپروایزر", "tamdidi_hk_supervisorha"),
    ("سرپرستان ثبت کننده فاکتور", "سرپرستان", "سرپرست", "tamdidi_hk_sarparasan"),
    ("مدیر فروش", "مدیران", "مدیر", "tamdidi_hk_modiran"),
]


# ---------------------------------------------------------------------------
# Raw date columns come from the vendor as Jalali strings. Converted to
# pandas Timestamps (Gregorian) here ONLY as a parsing/comparison convenience
# for values INSIDE the downloaded data - period_start/period_end themselves
# stay Jalali (see Reports/hk_tamdidi.py). Same pattern as KharidMojaddad54.
# ---------------------------------------------------------------------------

def _jalali_col_to_gregorian(series):
    unique_vals = series.dropna().unique()
    mapping = {}
    for val in unique_vals:
        try:
            date_part, time_part = str(val).replace("/", "-").split(" ")
            y, m, d = map(int, date_part.split("-"))
            g_date = jdatetime.date(y, m, d).togregorian()
            mapping[val] = pd.Timestamp(f"{g_date} {time_part}")
        except Exception:
            mapping[val] = None
    return pd.to_datetime(series.map(mapping), errors="coerce")


def _gregorian_col_to_jalali(series):
    """Inverse of _jalali_col_to_gregorian - for writing a derived Gregorian
    pd.Timestamp column back out as a human-readable Jalali string (used for
    the manual-review PLUS csv, see run())."""
    unique_vals = series.dropna().unique()
    mapping = {}
    for val in unique_vals:
        try:
            dt = pd.to_datetime(val)
            j_date = jdatetime.date.fromgregorian(date=dt.date())
            mapping[val] = f"{j_date.strftime('%Y-%m-%d')} {dt.strftime('%H:%M:%S')}"
        except Exception:
            mapping[val] = None
    return series.map(mapping)


def _fa_number(n):
    return f"{int(n):,}".translate(PERSIAN_DIGITS)


def _make_tamdid_notice():
    """Same business-facing notice as Report_Builders/SahmieShomareVorodiKarshenasanHK.py's
    _make_tamdid_notice - explicit user instruction (2026-09-14) to add it to
    all 4 hk-tamdidi images too, since it's the exact same فاکتور تمدیدی
    calculation rule. This report hardcodes its own LOOKBACK_DAYS constant
    (not config-driven like the sahmie report's ext_lookback_days), so the
    day count is interpolated straight from it - stays accurate if that
    constant is ever changed."""
    days_fa = _fa_number(LOOKBACK_DAYS)
    return (
        "اطلاعیه:\n"
        "از تاریخ ۱۴۰۵/۰۳/۲۱، محاسبه فاکتورهای تمدیدی بر اساس فرمول جدید آقای ایمانی انجام می‌شود.\n"
        "مبنای محاسبه به این صورت است که ابتدا آخرین مشاور ثبت‌شده برای شماره مشتری بررسی می‌شود و در مرحله بعد، "
        f"شماره مشتری نباید در بازه {days_fa} روز قبل از تاریخ پرداخت از طریق واحد تبلیغات وارد شده باشد.\n"
        "در صورت برقرار بودن این شرایط، فاکتور به‌عنوان تمدیدی در نظر گرفته خواهد شد."
    )


def _font_base64():
    with open(_FONT_PATH, "rb") as f:
        return base64.b64encode(f.read()).decode("ascii")


def _make_title(group_label, period_end):
    """date_line/send_line are driven by period_end (the actual end of the
    data window), NOT the scheduled send time - on the 24h/yesterday cycle
    (10:00 run) these must show yesterday's date, not today's, since that's
    what the data actually covers. Per the org's own convention, "ساعت
    ارسال" means the end of the reporting period, not literally when the
    message gets sent - end-of-day (23:59) displays as ۲۴:۰۰."""
    weekday = WEEKDAY_FA[period_end.weekday()]
    date_line = f"{weekday} {str(period_end.day).translate(PERSIAN_DIGITS)} {MONTH_NAMES[period_end.month]}"

    if period_end.hour == 23 and period_end.minute == 59:
        time_str = "۲۴:۰۰"
    else:
        time_str = period_end.strftime("%H:%M").translate(PERSIAN_DIGITS)
    send_line = (
        f"ساعت ارسال : {str(period_end.day).translate(PERSIAN_DIGITS)} {MONTH_NAMES[period_end.month]} "
        f"ساعت {time_str}"
    )
    return f"آمار فاکتور های تمدیدی {group_label} همکده", date_line, send_line


# ---------------------------------------------------------------------------
# Business logic - ported from the legacy تمدیدی/Run_process reference
# script, unchanged except for wiring into this project's contracts.
# ---------------------------------------------------------------------------

def _add_collection_date(dff):
    """"تاریخ وصول" (collection date) - sourced from a different raw column
    depending on payment type. HK.FCP's own request params (status=paid,
    receipt_status=accepted) already scope the raw file to paid+accepted
    invoices, so no extra confirmation check is needed here (unlike the
    5040 version, which reads from an endpoint that isn't pre-filtered that way)."""
    dff["تاریخ وصول"] = pd.Series([pd.NA] * len(dff), index=dff.index, dtype="object")
    dff.loc[dff["نوع پرداخت"] == "آنلاین", "تاریخ وصول"] = dff["تاریخ پرداخت"]
    dff.loc[dff["نوع پرداخت"] == "کارت به کارت", "تاریخ وصول"] = dff["زمان ثبت اطلاعات واریزی"]
    return dff


def _filter_by_collection_date(dff, period_start, period_end):
    """Independent period filter on "تاریخ وصول" (both bounds), applied
    BEFORE renewal detection - per the project's standing rule that every
    Builder must filter every raw source it derives data from by its own
    requested period, never trust the raw file to already be scoped
    correctly (HK.FCP's own accept-action-date params should already match,
    but this is the authoritative check, not the server's). Applying it
    first (not after _mark_renewals) matters for two reasons: it skips the
    per-row EXT lookup for invoices that don't belong in this report at all
    (faster), and it avoids false "تمدیدی" positives - an invoice outside
    the report's period has no EXT data downloaded for its own lookback
    window (Reports/hk_tamdidi.py only downloads EXT for the report's own
    period), so it would wrongly look like "no matching ad" and get flagged
    a renewal by default."""
    start_miladi = pd.Timestamp(period_start.togregorian())
    end_miladi = pd.Timestamp(period_end.togregorian()) + pd.Timedelta(seconds=59)

    collection_dt = _jalali_col_to_gregorian(dff["تاریخ وصول"])
    mask = collection_dt.notna() & (collection_dt >= start_miladi) & (collection_dt <= end_miladi)
    out = dff[mask].copy()
    out["تاریخ وصول"] = collection_dt[mask]
    return out


def _mark_renewals(dff, dfe, lookback_days):
    """Flags each invoice "تمدیدی" (renewal) unless a matching ad-traffic
    entry (dfe) for the same mobile number exists within
    [تاریخ وصول - lookback_days, تاریخ وصول] - in which case the purchase is
    attributed to that ad instead. dff must already be period-filtered (see
    _filter_by_collection_date) and dff/dfe's date columns must already be
    Gregorian pd.Timestamp."""

    def is_tamdidi(row):
        if pd.isna(row["آخرین مشاوره"]):
            return ""

        mobile = row["شماره مشتری"]
        vasool_date = row["تاریخ وصول"]
        if pd.isna(mobile) or pd.isna(vasool_date):
            return ""

        start_date = vasool_date - pd.Timedelta(days=lookback_days)
        mobile_rows = dfe[dfe["موبایل"] == mobile]
        date_rows = mobile_rows[
            (mobile_rows["تاریخ ورود"] >= start_date) & (mobile_rows["تاریخ ورود"] <= vasool_date)
        ]

        return "" if len(date_rows) > 0 else "تمدیدی"

    dff["فاکتور تمدید"] = dff.apply(is_tamdidi, axis=1)
    return dff


# Substrings that flag a placeholder/non-real value in an org-hierarchy
# column. "موزش" alone (without the leading ا/آ) deliberately covers every
# spelling variant seen in the raw data: آموزش, اموزش, آموزشی, اموزشی.
_PLACEHOLDER_PATTERNS = ["test", "تست", "موزش"]

# Every group-by column, in one place - used both to build the 4 outputs and
# to filter out rows before any of them are built (see _filter_valid_hierarchy).
HIERARCHY_COLS = [group_col for group_col, *_ in GROUPS]


def _filter_valid_hierarchy(df, hierarchy_cols):
    """Same as KharidMojaddad54._filter_valid_hierarchy - drops any row where
    ONE of the org-hierarchy columns (کارشناس/سوپروایزر/سرپرست/مدیر) is blank
    or a placeholder value (test/آموزش-family), applied ONCE before any
    per-group table is built, so all 4 outputs' totals stay equal."""
    out = df.copy()
    mask = pd.Series(True, index=out.index)
    for col in hierarchy_cols:
        values = out[col].astype(str).str.strip()
        is_blank = out[col].isna() | (values == "") | (values.str.lower() == "nan")
        is_placeholder = values.str.contains("|".join(_PLACEHOLDER_PATTERNS), case=False, na=False)
        mask &= ~(is_blank | is_placeholder)
    return out[mask]


def _build_group_table(df, group_col):
    grouped = (
        df.groupby(group_col)
        .agg(count=("مبلغ فاکتور", "size"), amount=("مبلغ فاکتور", "sum"))
        .reset_index()
        .rename(columns={group_col: "name"})
    )
    grouped["amount"] = (grouped["amount"] / 10).round().astype(int)  # rial -> toman

    # Primary sort: تعداد (count) desc. Tiebreaker: مبلغ (amount) desc.
    grouped = grouped.sort_values(by=["count", "amount"], ascending=[False, False]).reset_index(drop=True)
    grouped["rank"] = grouped.index + 1

    total_count = int(grouped["count"].sum())
    total_amount = int(grouped["amount"].sum())

    return grouped, total_count, total_amount


# ---------------------------------------------------------------------------
# HTML/CSS table -> PNG screenshot (Playwright) - identical layout to
# Report_Builders/KharidMojaddad54.py, red theme via TITLE_BG/HEADER_BG.
# ---------------------------------------------------------------------------

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
  .wrap {{ display: flex; flex-direction: column; width: fit-content; background: #ffffff; }}
  table {{ border-collapse: collapse; width: 620px; }}
  td {{ border: 1px solid #000000; padding: 8px 10px; text-align: center; font-size: 15px; color: #000000; }}
  .title {{ background: {title_bg}; color: #ffffff; font-weight: bold; font-size: 18px; padding: 12px; line-height: 1.8; }}
  .col-header {{ background: {header_bg}; color: #000000; font-weight: bold; }}
  .name-cell {{ text-align: center; }}
  .total-row td {{ background: {header_bg}; color: #000000; font-weight: bold; }}
  .notice {{ box-sizing: border-box; width: 620px; margin-top: 14px; padding: 8px 10px; border: 1px solid #000000; background: #ffffff; color: #000000; font-size: 10px; line-height: 1.7; white-space: pre-line; }}
</style>
</head>
<body>
<div class="wrap">
<table>
  <tr><td class="title" colspan="4">{title}<br>{date_line}<br>{send_line}</td></tr>
  <tr class="col-header">
    <td>رتبه</td>
    <td>{name_col_label}</td>
    <td>تعداد تمدید</td>
    <td>مبلغ تمدید (تومان)</td>
  </tr>
  {rows_html}
  <tr class="total-row">
    <td colspan="2">مجموع</td>
    <td>{total_count}</td>
    <td>{total_amount}</td>
  </tr>
</table>
<div class="notice">{notice}</div>
</div>
</body>
</html>"""

_ROW_TEMPLATE = """<tr>
    <td>{rank}</td>
    <td class="name-cell">{name}</td>
    <td>{count}</td>
    <td>{amount}</td>
  </tr>"""


def _render_table_image(title, date_line, send_line, name_col_label, grouped, total_count, total_amount, output_path):
    rows_html = "\n  ".join(
        _ROW_TEMPLATE.format(
            rank=_fa_number(row["rank"]),
            name=row["name"],
            count=_fa_number(row["count"]),
            amount=_fa_number(row["amount"]),
        )
        for _, row in grouped.iterrows()
    )
    html = _HTML_TEMPLATE.format(
        title=title, date_line=date_line, send_line=send_line, name_col_label=name_col_label,
        rows_html=rows_html, total_count=_fa_number(total_count), total_amount=_fa_number(total_amount),
        font_b64=_font_base64(), title_bg=TITLE_BG, header_bg=HEADER_BG, notice=_make_tamdid_notice(),
    )

    with sync_playwright() as p:
        browser = p.chromium.launch(channel="chrome")
        page = browser.new_page()
        page.set_content(html)
        page.locator(".wrap").screenshot(path=output_path)
        browser.close()


def _save_plus_csv(dff, fcp_path):
    """Saves every FCP invoice (not just the ones flagged تمدیدی) with its
    two derived columns (تاریخ وصول, فاکتور تمدید) next to the source FCP raw
    file, for manual spot-checking - matches the legacy reference script's
    "_PLUS.csv" output exactly. "تاریخ وصول" is converted back to a Jalali
    string here since dff carries it as a Gregorian pd.Timestamp internally."""
    out = dff.copy()
    out["تاریخ وصول"] = _gregorian_col_to_jalali(out["تاریخ وصول"])

    plus_filename = os.path.basename(fcp_path).replace(".csv", "_PLUS.csv")
    plus_path = os.path.join(os.path.dirname(fcp_path), plus_filename)
    out.to_csv(plus_path, index=False, encoding="utf-8-sig")
    return plus_path


# ---------------------------------------------------------------------------
# Standard contract every Report Builder implements.
# ---------------------------------------------------------------------------

def run(inputs, context):
    """
    inputs: {"HK.FCP": {"path": ..., "period_start": jdatetime(...), "period_end": jdatetime(...)},
             "HK.EXT": {"path": ..., "period_start": jdatetime(...), "period_end": jdatetime(...)}}

    Returns: [(output_id, filepath, caption), ...] - one per group (4 total).
    """
    fcp = inputs[FCP_KEY]
    ext = inputs[EXT_KEY]

    dff = pd.read_csv(fcp["path"])
    dfe = pd.read_csv(ext["path"], usecols=["تاریخ ورود", "موبایل", "عاملیت"])
    dfe = dfe[~dfe["عاملیت"].isin(["wordpress", "tamdid", "سایت همکده"])].copy()
    dfe["تاریخ ورود"] = _jalali_col_to_gregorian(dfe["تاریخ ورود"])

    dff = _add_collection_date(dff)
    dff = _filter_by_collection_date(dff, fcp["period_start"], fcp["period_end"])
    dff = _mark_renewals(dff, dfe, LOOKBACK_DAYS)

    _save_plus_csv(dff, fcp["path"])

    # Only actual renewals (not ad-attributed purchases) count toward the report.
    df = dff[dff["فاکتور تمدید"] == "تمدیدی"].copy()
    df = _filter_valid_hierarchy(df, HIERARCHY_COLS)

    period_end = fcp["period_end"]
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    outputs = []
    for group_col, group_label, name_col_label, output_id in GROUPS:
        grouped, total_count, total_amount = _build_group_table(df, group_col)
        title, date_line, send_line = _make_title(group_label, period_end)

        file_name = f"{output_id}_{context['run_time'].strftime('%Y_%m_%d_%H%M')}.png"
        output_path = os.path.join(OUTPUT_DIR, file_name)
        _render_table_image(title, date_line, send_line, name_col_label, grouped, total_count, total_amount, output_path)

        caption = f"{title}\n{date_line}\n{send_line}"
        outputs.append((output_id, output_path, caption))

    return outputs
