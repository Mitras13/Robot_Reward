"""
padash-karshenasan-5040/builder.py

Reads SP.54.SPK (see API_Downloader/SP/54/SPK.py's column-list comment for
every raw field name/meaning) and produces a rank + tiered-commission table
for every eligible کارشناس, cumulative from campaign start through this slot.

Eligibility - same rule as the sibling report for this same company
(Robot_Analytics/Report_Builders/SahmieShomareVorodiKarshenasan54.py),
confirmed by the user 2026-09-15 to reuse as-is: only a name carrying at
least one English letter (their team-suffix) is a real کارشناس.

Ranking (explicit user spec, 2026-09-15) - sort descending by:
  1. ضریب وصول      raw "paid_coe" column (SPK's own ratio, used directly -
                     NOT recomputed from paid/answered_count, since SPK
                     already exposes a column named exactly "ضریب وصولی").
  2. مبلغ وصول کارتابلی   "cartable_paid" (tie-break #1)
  3. مبلغ وصول کل         "paid" (tie-break #2)
رتبه = 1..N by this order. Ties may land in an arbitrary relative order
(explicit user decision: "برام مهم نیست اگه کسی همه چیش برابر بود رتبه
متفاوت بگیره").

Commission - base is 15% of مبلغ وصول کل for every کارشناس; رتبه upgrades
this to a fixed FINAL percentage (not additive on top of 15%, replaces it):
  1-10    -> 30%      (+100%)
  11-30   -> 22.5%    (+50%)
  31-50   -> 18%      (+20%)
  51-100  -> 16.5%    (+10%)
  101-200 -> 16.2%    (+8%)
  201-350 -> 15.9%    (+6%)
  351-550 -> 15.75%   (+5%)
  551+    -> 15%      (base, no upgrade)
given directly by the user as final percentages (2026-09-15).

Money unit: SP.54.SPK's money columns come back in میلیون تومان (confirmed
for cartable_paid against Robot_Analytics's own reconciliation) - ×1,000,000
here for real تومان figures, same convention as that sibling report.
ASSUMPTION (not independently re-verified for "paid" specifically the way
cartable_paid was) - flag to the user if a produced number looks off by 1e6.

Output columns (per the user's explicit list, 2026-09-15):
  نام کارشناس, رتبه, ضریب وصول, درصد نهایی پورسانت,
  مبلغ پورسانت بر آوردی تا این لحظه, پاداش مازاد بر آوردی
    - مبلغ پورسانت بر آوردی تا این لحظه = مبلغ وصول کل × درصد نهایی
    - پاداش مازاد بر آوردی = مبلغ وصول کل × (درصد نهایی - ۱۵٪) - i.e. only
      the EXTRA amount beyond the base 15% every کارشناس already earns
      regardless of رتبه (base is not itself a "پاداش").

Writes the per-slot table to outputs/{slot label}.csv in this folder (same
convention as padash-tamdid-karshenasan-hamkadeh/builder.py) and returns
{"slot_jdt": slot_jdt, "table": DataFrame} as `report` for render.py
(not built yet - user asked for builder only for now).
"""

import os
import re

import pandas as pd
from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, Side
from openpyxl.utils import get_column_letter

BASE_PERCENT = 0.15

# (max_rank_inclusive, final_percent), ascending by rank. First tier whose
# max_rank_inclusive >= this کارشناس's رتبه wins; falls through to
# BASE_PERCENT if رتبه exceeds every tier (551+).
RANK_TIERS = [
    (10, 0.30),
    (30, 0.225),
    (50, 0.18),
    (100, 0.165),
    (200, 0.162),
    (350, 0.159),
    (550, 0.1575),
]

_OUTPUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "outputs")

# Same eligibility rule as SahmieShomareVorodiKarshenasan54 (Robot_Analytics)
# for this same company - any English letter anywhere in the name (their
# team-suffix), confirmed by the user 2026-09-15 to reuse unchanged.
_HAS_ENGLISH_LETTER = re.compile(r"[A-Za-z]")


def _is_eligible_karshenas(name):
    return bool(_HAS_ENGLISH_LETTER.search(str(name)))


def _final_percent_for_rank(rank):
    for max_rank, percent in RANK_TIERS:
        if rank <= max_rank:
            return percent
    return BASE_PERCENT


def _fmt_period_dt(dt):
    return f"{dt.year}/{dt.month:02d}/{dt.day:02d} {dt.hour:02d}:{dt.minute:02d}"


def _write_manager_excel(display_df, period_start, period_end, output_path, title):
    """Bordered, RTL .xlsx with a merged title row and a merged "بازه‌ی
    گزارش: از ... تا ..." row above the column headers - the comprehensive
    report attached to the manager contacts in render.py (user request
    2026-09-22, same helper duplicated as-is in the sibling hamkadeh
    builder.py - no shared core module for this, per project convention).
    Written alongside the existing per-slot CSV."""
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


def build(raw_paths, slot_jdt):
    from . import requirements as req

    raw_df = pd.read_csv(raw_paths["SP.54.SPK"], encoding="utf-8-sig")

    if raw_df.empty:
        table = pd.DataFrame(columns=[
            "نام کارشناس", "رتبه", "ضریب وصول", "درصد نهایی پورسانت",
            "مبلغ پورسانت بر آوردی تا این لحظه", "پاداش مازاد بر آوردی",
        ])
        return {"slot_jdt": slot_jdt, "table": table}

    # raw_df (unfiltered) is kept around for the AAName=="5040" company-total
    # row, used below for the end-of-campaign management image - that row
    # has no English letter in its name, so the eligibility filter below
    # would otherwise silently drop it.
    df = raw_df[raw_df["AAName"].map(_is_eligible_karshenas)].copy()

    df["paid_coe"] = pd.to_numeric(df["paid_coe"], errors="coerce").fillna(0)
    df["cartable_paid"] = pd.to_numeric(df["cartable_paid"], errors="coerce").fillna(0)
    df["paid"] = pd.to_numeric(df["paid"], errors="coerce").fillna(0)

    # A handful of names can appear on more than one row (seen for the
    # sibling 5040 report, e.g. a mid-campaign supervisor change) - summed
    # per کارشناس, same as that report.
    grouped = df.groupby("AAName").agg(
        paid_coe=("paid_coe", "sum"),
        cartable_paid=("cartable_paid", "sum"),
        paid=("paid", "sum"),
    ).reset_index().rename(columns={"AAName": "نام کارشناس"})

    grouped["مبلغ وصول کارتابلی"] = (grouped["cartable_paid"] * 1_000_000).round().astype(int)
    grouped["مبلغ وصول کل"] = (grouped["paid"] * 1_000_000).round().astype(int)
    grouped["ضریب وصول"] = grouped["paid_coe"]

    grouped = grouped.sort_values(
        by=["ضریب وصول", "مبلغ وصول کارتابلی", "مبلغ وصول کل"],
        ascending=[False, False, False],
    ).reset_index(drop=True)
    grouped["رتبه"] = range(1, len(grouped) + 1)

    grouped["درصد نهایی پورسانت"] = grouped["رتبه"].apply(_final_percent_for_rank)
    grouped["مبلغ پورسانت بر آوردی تا این لحظه"] = (
        grouped["مبلغ وصول کل"] * grouped["درصد نهایی پورسانت"]
    ).round().astype(int)
    grouped["پاداش مازاد بر آوردی"] = (
        grouped["مبلغ وصول کل"] * (grouped["درصد نهایی پورسانت"] - BASE_PERCENT)
    ).round().astype(int)

    table = grouped[[
        "نام کارشناس", "رتبه", "ضریب وصول", "درصد نهایی پورسانت",
        "مبلغ پورسانت بر آوردی تا این لحظه", "پاداش مازاد بر آوردی",
    ]].copy()

    os.makedirs(_OUTPUT_DIR, exist_ok=True)
    slot_label = slot_jdt.strftime("%Y_%m_%d_%H%M")
    output_path = os.path.join(_OUTPUT_DIR, f"{slot_label}.csv")
    table.to_csv(output_path, index=False, encoding="utf-8-sig")

    # Comprehensive/manager .xlsx export - drops the last column (پاداش
    # مازاد بر آوردی, per-کارشناس only) per the user's request 2026-09-22;
    # every remaining column is already Persian-named, so no rename map
    # needed here (unlike the hamkadeh twin).
    display_df = table.iloc[:, :-1].copy()
    excel_path = os.path.join(_OUTPUT_DIR, f"{slot_label}_report.xlsx")
    _write_manager_excel(
        display_df, req.CAMPAIGN_START, slot_jdt, excel_path,
        title="گزارش جامع طرح ویژه پاداش رتبه‌بندی کارشناسان 5040",
    )

    report = {"slot_jdt": slot_jdt, "table": table, "manager_excel_path": excel_path}

    # گزارش مدیریتی تصویری پایان بازه (management_image.py) - فقط دقیقاً روی
    # آخرین اسلات کمپین اجرا می‌شه (یک‌بار، نه هر اسلات) - طبق درخواست کاربر
    # ۲۰۲۶-۰۹-۲۲. فقط برای 5040 - همکده فعلاً عمداً کنار گذاشته شده (نبود
    # مفهوم «ضریب» تو دیتای همکده، در انتظار بررسی کاربر).
    from . import management_image as mgmt_img
    if mgmt_img.is_final_slot(slot_jdt):
        total_reward_toman = int(grouped["پاداش مازاد بر آوردی"].sum())
        # "کل فروش"/"ضریب وصولی کل" این بازه از ردیف AAName=="5040" خودِ
        # همین raw_df می‌آد (نه جمع‌زدن ردیف‌های تک‌تک کارشناسا) - طبق تصحیح
        # صریح کاربر ۲۰۲۶-۰۹-۲۲: SP.54.SPK یک ردیف کل-شرکت آماده برمی‌گردونه
        # که باید مرجع هر عدد «کل» باشه، نه یک تقریب محاسبه‌شده.
        totals_now = mgmt_img.company_totals_from_df(raw_df)
        koeff_during, total_sales_toman = totals_now if totals_now else (None, 0)
        # درصد کارشناسان شامل پاداش (۲۰۲۶-۰۹-۲۳): مخرج = همه‌ی کارشناسان
        # واجد شرایط این بازه (grouped، قبل از هر فیلتر پاداش) - صورت = چندتاشون
        # پاداش مازاد بر آوردی‌شون > ۰ شده.
        total_count = len(grouped)
        rewarded_count = int((grouped["پاداش مازاد بر آوردی"] > 0).sum())
        result = mgmt_img.build_report_image(
            "طرح ویژه افزایش رقابت براساس ضریب وصولی کارشناسان ۵۰۴۰",
            total_reward_toman, total_sales_toman, koeff_during, slot_jdt,
            rewarded_count=rewarded_count, total_count=total_count,
        )
        if result:
            image_path, stats = result
            report["management_image_path"] = image_path
            report["management_image_stats"] = stats

    return report
