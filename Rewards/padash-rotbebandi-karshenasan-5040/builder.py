"""
padash-rotbebandi-karshenasan-5040/builder.py

Sibling of padash-rotbebandi-karshenasan-hamkadeh/builder.py (company 5040
instead of همکده) - identical ranking logic, see that file's docstring for
the full reasoning (confirmed by the user 2026-09-20): pure ranking on
paid_coe / paid / cartable_paid (no reward tiers/money), zero-activity
کارشناسان dropped before ranking, ties share the same rank, full table
written to outputs/{slot label}.csv as the "گزارش جامع".

SP.54.SPK's raw response also includes ONE aggregate "whole company" row
whose AAName is literally "5040" (found by inspecting a real response
2026-09-20, same quirk as HK.SPK's "همکده" row) - dropped by exact name
(_COMPANY_TOTAL_ROW_NAME) before ranking, or it would win رتبه ۱ on
paid/cartable_paid every time since it's the sum of everyone.
"""

import os

import pandas as pd

MONEY_TO_TOMAN = 1_000_000

_OUTPUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "outputs")

_RAW_COLUMNS = ["AAName", "paid_coe", "paid", "cartable_paid"]

_COMPANY_TOTAL_ROW_NAME = "5040"


def _rank_desc(series):
    """Rank 1 = highest value, ties share the same rank (see module docstring)."""
    return series.rank(method="min", ascending=False).astype(int)


def build(raw_paths, slot_jdt):
    from . import requirements as req

    df = pd.read_csv(raw_paths["SP.54.SPK"], encoding="utf-8-sig", usecols=_RAW_COLUMNS)
    df = df.rename(columns={"AAName": "کارشناس"})

    df["paid_coe"] = pd.to_numeric(df["paid_coe"], errors="coerce").fillna(0.0)
    df["paid"] = pd.to_numeric(df["paid"], errors="coerce").fillna(0.0) * MONEY_TO_TOMAN
    df["cartable_paid"] = pd.to_numeric(df["cartable_paid"], errors="coerce").fillna(0.0) * MONEY_TO_TOMAN

    df = df[df["کارشناس"].notna() & (df["کارشناس"].astype(str).str.strip() != "")]
    df = df[df["کارشناس"].astype(str).str.strip() != _COMPANY_TOTAL_ROW_NAME]
    df = df[(df["paid_coe"] != 0) | (df["paid"] != 0) | (df["cartable_paid"] != 0)].copy()

    df["رتبه ضریب وصولی"] = _rank_desc(df["paid_coe"])
    df["رتبه وصولی کل"] = _rank_desc(df["paid"])
    df["رتبه وصولی کارتابلی"] = _rank_desc(df["cartable_paid"])

    df = df.sort_values("رتبه ضریب وصولی").reset_index(drop=True)

    os.makedirs(_OUTPUT_DIR, exist_ok=True)
    slot_label = slot_jdt.strftime("%Y_%m_%d_%H%M")
    df.to_csv(os.path.join(_OUTPUT_DIR, f"{slot_label}.csv"), index=False, encoding="utf-8-sig")

    period_start, period_end = req.period_for_slot(slot_jdt)
    return {
        "slot_jdt": slot_jdt,
        "period_start": period_start,
        "period_end": period_end,
        "table": df,
    }
