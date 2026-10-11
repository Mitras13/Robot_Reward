"""
padash-tamdid-karshenasan-hamkadeh/builder.py

تمدید (renewal) detection ported from a reference module the user dropped in
this folder for algorithm reference only (TamdidiHK.py - belongs to a
different, older report/notification program; NOT imported here, since it
also builds a 4-level org hierarchy and renders PNG tables this reward
doesn't need - we only need the per-کارشناس numbers). Reused as-is:

  - "تاریخ وصول" (collection date): تاریخ پرداخت for آنلاین payments,
    زمان ثبت اطلاعات واریزی for کارت به کارت payments.
  - FCP invoices are filtered to [period_start, period_end] on تاریخ وصول -
    period_start/period_end here are the FCP requirement's own window
    (campaign start -> this slot, see requirements.py), applied
    independently rather than trusting the raw file's own scoping.
  - An invoice counts as تمدیدی (renewal) UNLESS the same mobile number has
    an EXT (ad-traffic) entry within [تاریخ وصول - LOOKBACK_DAYS, تاریخ
    وصول] - in which case the purchase is ad-attributed, not a renewal.
    EXT rows whose عاملیت is in EXCLUDED_AGENCIES never count as a matching
    ad (same exclusion list as the reference module).

Reward tiers (میلیون تومان جمع وصولی تمدیدی این کارشناس -> پاداش تومان).
Originally given by the user 2026-09-15; increased 20% flat across every
tier 2026-09-20 ("با هدف افزایش انگیزه بیشتر برای استفاده از فرصت روزهای
پایانی ماه") - a one-time announcement about this same change was sent to
all کارشناسان on that date (see git history/logs, not a repo file):
  10->1.2M, 15->1.8M, 20->2.64M, 25->3.6M, 30->4.8M, 37.5->6M, 45->7.8M,
  52.5->9.6M, 60->12M, 70->14.4M, 85->18M, 100+->24M, under 10->0.

For every کارشناس with at least one تمدیدی invoice this slot, computes:
  - count               تعداد فاکتور تمدیدی
  - amount_toman        مجموع مبلغ فاکتور تمدیدی (تومان)
  - reward_toman        مبلغ پاداش (از جدول پله‌ها)
  - invoices_to_next    تعداد فاکتور تقریبی تا پله بعدی =
                        ceil((next_tier_threshold - amount_toman) / avg),
                        avg = this کارشناس's own amount_toman / count.
                        None once already at/above the top tier.

Writes the per-slot table to outputs/{slot label}.csv in this folder (per
the user's request - "خروجیش بره تو یه پوشه که بعدا رندرساز ازش بخونه") and
also returns {"slot_jdt": slot_jdt, "table": DataFrame} as `report`, so
render.py gets the table directly (no re-reading the CSV) plus the labeled
slot time it needs for the report date/time line.

STILL PENDING from the user:
  - message text(s) (render.py)
  - real schedule.csv slot times
  - confirm the "پسوند حروف انگلیسی" filter below (_has_english_suffix)
    actually matches how real vs. test/duplicate کارشناس names look in the
    raw HK.FCP data - this project's own rule, replacing the reference
    module's test/آموزش-substring filter, per the user's explicit instruction.
"""

import math
import os
import re

import jdatetime
import pandas as pd
from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, Side
from openpyxl.utils import get_column_letter

EXCLUDED_AGENCIES = ["wordpress", "tamdid", "سایت همکده"]

# (min amount toman, reward toman), ascending. The reward for a given total
# is the LAST tier whose threshold is <= the total (highest reached, not
# first exceeded).
TIERS = [
    (10_000_000, 1_200_000),
    (15_000_000, 1_800_000),
    (20_000_000, 2_640_000),
    (25_000_000, 3_600_000),
    (30_000_000, 4_800_000),
    (37_500_000, 6_000_000),
    (45_000_000, 7_800_000),
    (52_500_000, 9_600_000),
    (60_000_000, 12_000_000),
    (70_000_000, 14_400_000),
    (85_000_000, 18_000_000),
    (100_000_000, 24_000_000),
]

_OUTPUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "outputs")

# Comprehensive/manager .xlsx export column mapping - drops the last column
# (invoices_to_next, per-کارشناس only, not manager-relevant) and translates
# the remaining English column names to Persian, per the user's request
# 2026-09-22. "کارشناس" -> "نام کارشناس" per the exact 4-column list the user
# gave.
MANAGER_EXCEL_COLUMNS = {
    "کارشناس": "نام کارشناس",
    "count": "تعداد فاکتور تمدیدی",
    "amount_toman": "مجموع مبلغ وصولی تمدیدی",
    "reward_toman": "پاداش فعلی",
}


def _fmt_period_dt(dt):
    return f"{dt.year}/{dt.month:02d}/{dt.day:02d} {dt.hour:02d}:{dt.minute:02d}"


def _write_manager_excel(display_df, period_start, period_end, output_path, title):
    """Bordered, RTL .xlsx with a merged title row and a merged "بازه‌ی
    گزارش: از ... تا ..." row above the column headers - the comprehensive
    report attached to the manager contacts in render.py (user request
    2026-09-22), written alongside the existing per-slot CSV."""
    wb = Workbook()
    ws = wb.active
    ws.sheet_view.rightToLeft = True
    ws.title = "گزارش"

    n_cols = max(1, len(display_df.columns))
    thin = Side(style="thin", color="999999")
    border = Border(left=thin, right=thin, top=thin, bottom=thin)

    ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=n_cols)
    title_cell = ws.cell(row=1, column=1, value=title)
    title_cell.font = Font(bold=True, size=13)
    title_cell.alignment = Alignment(horizontal="center")

    ws.merge_cells(start_row=2, start_column=1, end_row=2, end_column=n_cols)
    period_cell = ws.cell(
        row=2, column=1,
        value=f"بازه‌ی گزارش: از {_fmt_period_dt(period_start)} تا {_fmt_period_dt(period_end)}",
    )
    period_cell.alignment = Alignment(horizontal="center")

    header_row = 3
    for col_idx, col_name in enumerate(display_df.columns, start=1):
        cell = ws.cell(row=header_row, column=col_idx, value=col_name)
        cell.font = Font(bold=True)
        cell.alignment = Alignment(horizontal="center")
        cell.border = border

    for row_offset, (_, row) in enumerate(display_df.iterrows(), start=header_row + 1):
        for col_idx, col_name in enumerate(display_df.columns, start=1):
            cell = ws.cell(row=row_offset, column=col_idx, value=row[col_name])
            cell.alignment = Alignment(horizontal="center")
            cell.border = border

    for col_idx, col_name in enumerate(display_df.columns, start=1):
        ws.column_dimensions[get_column_letter(col_idx)].width = max(14, len(str(col_name)) + 4)

    wb.save(output_path)

# Real کارشناس accounts are assumed to end their name with an English-letter
# token (with or without trailing parenthesis); blank/pure-Persian/test-style
# names are dropped. ADJUST if this doesn't match the real raw data.
_ENGLISH_SUFFIX_RE = re.compile(r"[A-Za-z]\)?\s*$")


def _jalali_col_to_gregorian(series):
    """Vendor date columns come back as Jalali strings ("1405-06-25 14:30:00")
    - convert to Gregorian pd.Timestamp for comparison/arithmetic only."""
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


def _add_collection_date(dff):
    dff["تاریخ وصول"] = pd.Series([pd.NA] * len(dff), index=dff.index, dtype="object")
    dff.loc[dff["نوع پرداخت"] == "آنلاین", "تاریخ وصول"] = dff["تاریخ پرداخت"]
    dff.loc[dff["نوع پرداخت"] == "کارت به کارت", "تاریخ وصول"] = dff["زمان ثبت اطلاعات واریزی"]
    return dff


def _filter_by_collection_date(dff, period_start, period_end):
    start_miladi = pd.Timestamp(period_start.togregorian())
    end_miladi = pd.Timestamp(period_end.togregorian()) + pd.Timedelta(seconds=59)

    collection_dt = _jalali_col_to_gregorian(dff["تاریخ وصول"])
    mask = collection_dt.notna() & (collection_dt >= start_miladi) & (collection_dt <= end_miladi)
    out = dff[mask].copy()
    out["تاریخ وصول"] = collection_dt[mask]
    return out


def _mark_renewals(dff, dfe, lookback_days):
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


def _has_english_suffix(name):
    return bool(_ENGLISH_SUFFIX_RE.search(str(name).strip()))


def _reward_for_amount(amount_toman):
    reward = 0
    for threshold, amount in TIERS:
        if amount_toman >= threshold:
            reward = amount
        else:
            break
    return reward


def _next_tier_threshold(amount_toman):
    for threshold, _ in TIERS:
        if amount_toman < threshold:
            return threshold
    return None  # already at/above the top tier


def build(raw_paths, slot_jdt):
    from . import requirements as req

    dff = pd.read_csv(raw_paths["HK.FCP"], encoding="utf-8-sig")
    dfe = pd.read_csv(raw_paths["HK.EXT"], encoding="utf-8-sig", usecols=["تاریخ ورود", "موبایل", "عاملیت"])
    dfe = dfe[~dfe["عاملیت"].isin(EXCLUDED_AGENCIES)].copy()
    dfe["تاریخ ورود"] = _jalali_col_to_gregorian(dfe["تاریخ ورود"])

    dff = _add_collection_date(dff)
    dff = _filter_by_collection_date(dff, req.CAMPAIGN_START, slot_jdt)
    dff = _mark_renewals(dff, dfe, req.LOOKBACK_DAYS)

    df = dff[dff["فاکتور تمدید"] == "تمدیدی"].copy()
    df = df[df["ثبت کننده"].apply(_has_english_suffix)]

    grouped = (
        df.groupby("ثبت کننده")
        .agg(count=("مبلغ فاکتور", "size"), amount_rial=("مبلغ فاکتور", "sum"))
        .reset_index()
        .rename(columns={"ثبت کننده": "کارشناس"})
    )
    grouped["amount_toman"] = (grouped["amount_rial"] / 10).round().astype(int)
    grouped["reward_toman"] = grouped["amount_toman"].apply(_reward_for_amount)

    def _invoices_to_next(row):
        next_threshold = _next_tier_threshold(row["amount_toman"])
        if next_threshold is None or row["count"] == 0:
            return None
        avg_invoice = row["amount_toman"] / row["count"]
        if avg_invoice <= 0:
            return None
        gap = next_threshold - row["amount_toman"]
        return math.ceil(gap / avg_invoice)

    grouped["invoices_to_next"] = grouped.apply(_invoices_to_next, axis=1)
    grouped = grouped.drop(columns=["amount_rial"])
    grouped = grouped.sort_values(by=["amount_toman"], ascending=False).reset_index(drop=True)

    os.makedirs(_OUTPUT_DIR, exist_ok=True)
    slot_label = slot_jdt.strftime("%Y_%m_%d_%H%M")
    output_path = os.path.join(_OUTPUT_DIR, f"{slot_label}.csv")
    grouped.to_csv(output_path, index=False, encoding="utf-8-sig")

    display_df = grouped.iloc[:, :-1].rename(columns=MANAGER_EXCEL_COLUMNS)
    excel_path = os.path.join(_OUTPUT_DIR, f"{slot_label}_report.xlsx")
    _write_manager_excel(
        display_df, req.CAMPAIGN_START, slot_jdt, excel_path,
        title="گزارش جامع طرح پاداش تمدیدی کارشناسان همکده",
    )

    report = {"slot_jdt": slot_jdt, "table": grouped, "manager_excel_path": excel_path}

    # گزارش مدیریتی تصویری پایان بازه (management_image.py) - فقط دقیقاً روی
    # آخرین اسلات کمپین اجرا می‌شه، طبق درخواست کاربر ۲۰۲۶-۰۹-۲۲. "کل فروش"
    # = همه‌ی فاکتورهای HK.FCP این بازه (dff، قبل از فیلتر تمدیدی-فقط) - نه
    # فقط تمدیدی‌ها - طبق تأیید صریح کاربر همون روز.
    from . import management_image as mgmt_img
    if mgmt_img.is_final_slot(slot_jdt):
        total_reward_toman = int(grouped["reward_toman"].sum())
        total_sales_toman = int((dff["مبلغ فاکتور"].sum() / 10))
        renewal_count_now = int(grouped["count"].sum())
        renewal_amount_toman_now = int(grouped["amount_toman"].sum())
        # درصد کارشناسان شامل پاداش (۲۰۲۶-۰۹-۲۳): مخرج = همه‌ی ثبت‌کننده‌های
        # واجد شرایط کل فاکتورهای این بازه (dff، قبل از فیلتر تمدیدی-فقط) -
        # چون فقط کسایی که حداقل یه فاکتور تمدیدی داشتن وارد grouped می‌شن؛
        # صورت = چندتاشون reward_toman‌شون > ۰ شده.
        total_count = int(dff[dff["ثبت کننده"].apply(_has_english_suffix)]["ثبت کننده"].nunique())
        rewarded_count = int((grouped["reward_toman"] > 0).sum())
        result = mgmt_img.build_report_image(
            "طرح ویژه پاداش تمدیدی کارشناسان همکده",
            total_reward_toman, total_sales_toman, renewal_count_now, renewal_amount_toman_now, slot_jdt,
            rewarded_count=rewarded_count, total_count=total_count,
        )
        if result:
            image_path, stats = result
            report["management_image_path"] = image_path
            report["management_image_stats"] = stats

    return report
