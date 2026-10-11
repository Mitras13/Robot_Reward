"""
padash-ghahve-sashe-5040-13mehr/builder.py

Per-coffee bonus for the new sachet coffee (user 2026-10-05):
  - 9360993 = قهوه ساشه‌ای یک عددی  -> 100,000 تومان per pack
  - 9360992 = قهوه ساشه‌ای دو عددی  -> 150,000 تومان per pack
Matched by product CODE, not name - the panel renamed the product mid-morning
on 13 مهر ("...لاغری" -> "...لاغری ساشه ای") under the same codes.

Quantity: "کد محصولات" looks like "9360993(1), 9360992(2)". For the
single pack the number in parentheses is the pack count; for the two-pack
it is the coffee count (one دو عددی pack = "(2)", seen in live data), so
packs = qty / 2. Every pack counts separately, whether in one invoice or in
several (user: 3 single packs in one invoice = 300,000).

An invoice counts only if (all inside 1405/07/13 09:00:00 -> 15:00:00):
  - "تاریخ ثبت"        (registration)        in window
  - "تاریخ وضعیت مالی"  (payment acceptance)  in window and <= this slot
  - "نوع ثبت فاکتور" == کارتابلی
  - "وضعیت مالی" == تایید مالی
  - not cancelled ("وضعیت فاکتور" != لغو شده) and not returned ("فاکتور برگشتی" != 1)
Owner = "ثبت کننده"; test accounts ("(تست)" in the name) are dropped.
"""

import os
import re

import pandas as pd

SINGLE_CODE = "9360993"
DOUBLE_CODE = "9360992"
SINGLE_PRIZE_TOMAN = 100_000
DOUBLE_PRIZE_TOMAN = 150_000

_OWNER_COL = "ثبت کننده"
_REG_COL = "تاریخ ثبت"
_PAY_COL = "تاریخ وضعیت مالی"
_CODES_COL = "کد محصولات"

_CODE_RE = re.compile(r"(\d+)\((\d+)\)")

_HERE = os.path.dirname(os.path.abspath(__file__))
_OUTPUT_DIR = os.path.join(_HERE, "outputs")

_TS_FMT = "%Y/%m/%d %H:%M:%S"


def _code_qty(codes_text, code):
    return sum(int(q) for c, q in _CODE_RE.findall(str(codes_text)) if c == code)


def build(raw_paths, slot_jdt):
    from . import requirements as req

    start = req.CAMPAIGN_START.strftime(_TS_FMT)
    end = req.CAMPAIGN_END.strftime(_TS_FMT)
    pay_end = req.period_end_for_slot(slot_jdt).strftime(_TS_FMT)

    df = pd.read_csv(raw_paths["54.FCP"], encoding="utf-8-sig", dtype=str).fillna("")
    reg = df[_REG_COL].str.strip()
    pay = df[_PAY_COL].str.strip()
    df = df[
        (reg >= start) & (reg <= end)
        & (pay >= start) & (pay <= pay_end)
        & (df["نوع ثبت فاکتور"].str.strip() == "کارتابلی")
        & (df["وضعیت مالی"].str.strip() == "تایید مالی")
        & (df["وضعیت فاکتور"].str.strip() != "لغو شده")
        & (df["فاکتور برگشتی"].str.strip() != "1")
        & (df[_OWNER_COL].str.strip() != "")
        & (~df[_OWNER_COL].str.contains("(تست)", regex=False))
    ].copy()

    df["single_packs"] = df[_CODES_COL].map(lambda t: _code_qty(t, SINGLE_CODE))
    df["double_packs"] = df[_CODES_COL].map(lambda t: _code_qty(t, DOUBLE_CODE) // 2)
    df = df[(df["single_packs"] > 0) | (df["double_packs"] > 0)]

    table = (
        df.groupby(_OWNER_COL, as_index=False)
        .agg(single_packs=("single_packs", "sum"), double_packs=("double_packs", "sum"),
             invoices=("سریال فاکتور", "nunique"))
        .rename(columns={_OWNER_COL: "کارشناس"})
    )
    table["prize_toman"] = (table["single_packs"] * SINGLE_PRIZE_TOMAN
                            + table["double_packs"] * DOUBLE_PRIZE_TOMAN)
    table = table.sort_values(["prize_toman", "کارشناس"], ascending=[False, True]).reset_index(drop=True)

    os.makedirs(_OUTPUT_DIR, exist_ok=True)
    table.to_csv(os.path.join(_OUTPUT_DIR, f"{slot_jdt.strftime('%Y_%m_%d_%H%M')}.csv"),
                 index=False, encoding="utf-8-sig")

    return {
        "slot_jdt": slot_jdt,
        "is_final": slot_jdt >= req.CAMPAIGN_END,
        "table": table,
    }
