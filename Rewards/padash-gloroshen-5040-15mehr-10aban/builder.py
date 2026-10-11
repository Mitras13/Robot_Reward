"""
padash-gloroshen-5040-15mehr-10aban/builder.py

Ranking by number of collected کارتابلی invoices of the Glorsion
anti-dark-spot serum (user 2026-10-07):
  - product codes 9310895 (سرم ضد لک و روشن کننده گلورشن) and 9310894 (... 2)
    - both count. Only the "کد محصولات" column, NOT "کد هدایا": an invoice
    where the serum is only a gift does not count.
  - one invoice = 1, however many packs it has.
  - tie on invoice count -> higher total "مبلغ فاکتور" of those invoices wins
    (user); then name, just to keep the order stable.

An invoice counts only if:
  - its collection time ("تاریخ وصول") is in campaign start -> this slot.
    Collection time by payment type (user 2026-10-10, applies to every
    reward): آنلاین -> "تاریخ پرداخت", کارت به کارت -> "تاریخ ثبت اطلاعات
    پرداختی"; any other type (e.g. هدیه) keeps "تاریخ وضعیت مالی". The
    financial-approval time is NOT a limit - finance may approve later.
  - "نوع ثبت فاکتور" == کارتابلی
  - "وضعیت مالی" == تایید مالی
  - not cancelled ("وضعیت فاکتور" != لغو شده) and not returned ("فاکتور برگشتی" != 1)
Owner = "ثبت کننده"; test accounts ("(تست)" in the name) are dropped.

Prize tiers ("رتبه" 1..7 in the poster) by position:
  1 -> 3,000,000 | 2-3 -> 2,500,000 | 4-7 -> 2,000,000 | 8-12 -> 1,000,000
  13-17 -> 750,000 | 18-30 -> 500,000 | 31-40 -> 300,000 تومان
"""

import os
import re

import pandas as pd

PRODUCT_CODES = {"9310895", "9310894"}

# (first position, last position, tier, prize toman)
TIERS = [
    (1, 1, 1, 3_000_000),
    (2, 3, 2, 2_500_000),
    (4, 7, 3, 2_000_000),
    (8, 12, 4, 1_000_000),
    (13, 17, 5, 750_000),
    (18, 30, 6, 500_000),
    (31, 40, 7, 300_000),
]
PRIZED_COUNT = TIERS[-1][1]

_OWNER_COL = "ثبت کننده"
_APPROVAL_COL = "تاریخ وضعیت مالی"
_CODES_COL = "کد محصولات"
_SERIAL_COL = "سریال فاکتور"

_CODE_RE = re.compile(r"(\d+)\(\d+\)")

_HERE = os.path.dirname(os.path.abspath(__file__))
_OUTPUT_DIR = os.path.join(_HERE, "outputs")

_TS_FMT = "%Y/%m/%d %H:%M:%S"


def tier_for_position(position):
    for first, last, tier, prize in TIERS:
        if first <= position <= last:
            return tier, prize
    return 0, 0


def _has_product(codes_text):
    return any(c in PRODUCT_CODES for c in _CODE_RE.findall(str(codes_text)))


def _mode(series):
    s = series[series.str.strip() != ""]
    return s.mode().iloc[0] if not s.empty else ""


def _collection_time(df):
    kind = df["نوع پرداخت"].str.strip()
    out = df[_APPROVAL_COL].str.strip()
    out = out.mask(kind == "آنلاین", df["تاریخ پرداخت"].str.strip())
    return out.mask(kind == "کارت به کارت", df["تاریخ ثبت اطلاعات پرداختی"].str.strip())


def build(raw_paths, slot_jdt):
    from . import requirements as req

    start = req.CAMPAIGN_START.strftime(_TS_FMT)
    pay_end = req.period_end_for_slot(slot_jdt).strftime(_TS_FMT)

    df = pd.read_csv(raw_paths["54.FCP"], encoding="utf-8-sig", dtype=str).fillna("")
    pay = _collection_time(df)
    df = df[
        (pay >= start) & (pay <= pay_end)
        & (df["نوع ثبت فاکتور"].str.strip() == "کارتابلی")
        & (df["وضعیت مالی"].str.strip() == "تایید مالی")
        & (df["وضعیت فاکتور"].str.strip() != "لغو شده")
        & (df["فاکتور برگشتی"].str.strip() != "1")
        & (df[_OWNER_COL].str.strip() != "")
        & (~df[_OWNER_COL].str.contains("(تست)", regex=False))
        & (df[_CODES_COL].map(_has_product))
    ].drop_duplicates(_SERIAL_COL).copy()

    df[_OWNER_COL] = df[_OWNER_COL].str.strip()
    df["amount_toman"] = pd.to_numeric(df["مبلغ فاکتور"], errors="coerce").fillna(0) / 10

    table = (
        df.groupby(_OWNER_COL, as_index=False)
        .agg(invoices=(_SERIAL_COL, "nunique"),
             amount_toman=("amount_toman", "sum"),
             supervisor=("سوپروایزران سازنده فاکتور", _mode),
             sarparast=("سرپرست سازنده فاکتور", _mode))
        .rename(columns={_OWNER_COL: "کارشناس"})
    )
    table = table.sort_values(["invoices", "amount_toman", "کارشناس"],
                              ascending=[False, False, True]).reset_index(drop=True)
    table["position"] = table.index + 1
    tiers = table["position"].map(tier_for_position)
    table["tier"] = tiers.map(lambda t: t[0])
    table["prize_toman"] = tiers.map(lambda t: t[1])

    os.makedirs(_OUTPUT_DIR, exist_ok=True)
    table.to_csv(os.path.join(_OUTPUT_DIR, f"{slot_jdt.strftime('%Y_%m_%d_%H%M')}.csv"),
                 index=False, encoding="utf-8-sig")

    return {
        "slot_jdt": slot_jdt,
        "period_start": req.CAMPAIGN_START,
        "period_end": req.period_end_for_slot(slot_jdt),
        "is_final": slot_jdt >= req.FINAL_SLOT,
        "is_first": slot_jdt <= req.CAMPAIGN_START.replace(hour=19, minute=0),
        "table": table,
        "total_invoices": int(table["invoices"].sum()),
        "total_amount_toman": float(table["amount_toman"].sum()),
    }
