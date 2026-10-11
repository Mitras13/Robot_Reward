"""
padash-rotbebandi-karshenasan-hamkadeh/builder.py

Pure ranking report (no reward tiers/money in this reward - user 2026-09-20:
"این سه تا باید هرکدوم جداگانه sort بشن و از نفر اول لیست رتبه ی یک بگیره
به ترتیب تا اخر"). Reads SP.HK.SPK's per-کارشناس summary (already scoped to
this slot's period by requirements.py) and ranks every کارشناس independently
on three metrics:

  - paid_coe        ضریب وصولی      -> رتبه ضریب وصولی
  - paid            وصولی کل        -> رتبه وصولی کل
  - cartable_paid   وصولی کارتابلی  -> رتبه وصولی کارتابلی

paid / cartable_paid come back from the panel in میلیون تومان (see
API_Downloader/SP/54/SPK.py's column comment - convention confirmed for
cartable_paid, applied the same way to paid here) - multiplied by
MONEY_TO_TOMAN before ranking/display so render.py's amounts are already
real تومان. paid_coe is a coefficient, not money - used as-is.

Rank 1 = best (highest) on that metric, ties share the same rank
(pandas .rank(method="min"), matching "نفر اول لیست رتبه‌ی یک بگیرد").

A کارشناس with all three metrics at zero (no calls/collection at all this
period) is dropped entirely before ranking - confirmed by the user
2026-09-20 ("از لیست حذف شود") - so ranks are computed only over کارشناسان
who were actually active.

SP.HK.SPK's raw response also includes ONE aggregate "whole company" row
whose AAName is literally "همکده" (found by inspecting a real response
2026-09-20 - not documented anywhere in the endpoint's own column list) -
dropped by exact name (_COMPANY_TOTAL_ROW_NAME) before ranking, or it would
win رتبه ۱ on paid/cartable_paid every time since it's the sum of everyone.

Writes the full per-slot ranking table to outputs/{slot label}.csv in this
folder - this IS the "گزارش جامع" the user asked for (their own overview),
per their explicit instruction 2026-09-20 ("فقط فایل CSV در outputs/") - no
message is sent for it.
"""

import os

import pandas as pd

MONEY_TO_TOMAN = 1_000_000

_OUTPUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "outputs")

_RAW_COLUMNS = ["AAName", "paid_coe", "paid", "cartable_paid"]

_COMPANY_TOTAL_ROW_NAME = "همکده"


def _rank_desc(series):
    """Rank 1 = highest value, ties share the same rank (see module docstring)."""
    return series.rank(method="min", ascending=False).astype(int)


def build(raw_paths, slot_jdt):
    from . import requirements as req

    df = pd.read_csv(raw_paths["SP.HK.SPK"], encoding="utf-8-sig", usecols=_RAW_COLUMNS)
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
