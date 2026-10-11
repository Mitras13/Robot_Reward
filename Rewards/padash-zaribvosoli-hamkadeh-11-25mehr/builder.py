"""
padash-zaribvosoli-hamkadeh-11-25mehr/builder.py

Ranks every active کارشناس by ضریب وصولی (paid_coe from SP.HK.SPK,
cumulative from campaign start through this slot - see requirements.py).
Rank 1 = highest ضریب وصولی. Ranks are always unique (user 2026-10-03:
"رتبه‌ی تکراری نده") - ties on ضریب وصولی are broken by وصولی کل (paid,
higher first); if still equal, by وصولی کارتابلی, then by name, just so
the order is deterministic.

Commission tiers (user 2026-10-03). Base commission is 20%; the top
REWARDED_COUNT ranks get a percentage increase ON TOP of that base:
  rank 1-2      +150% -> 50%
  rank 3-10     +100% -> 40%
  rank 11-20    +50%  -> 30%
  rank 21-40    +20%  -> 24%
  rank 41-80    +10%  -> 22%
  rank 81-130   +8%   -> 21.6%
  rank 131-180  +6%   -> 21.2%
  rank 181-250  +5%   -> 21%
  rank 251+     no increase (base 20%)

Dropped before ranking: blank names, the aggregate company row ("همکده"),
and anyone with paid_coe == 0 (no collection at all this period).

Writes the full ranking to outputs/{slot label}.csv in this folder.
"""

import os

import pandas as pd

BASE_COMMISSION_PCT = 20
REWARDED_COUNT = 250

# (last rank inclusive, increase % over base commission), ascending by rank.
TIERS = [
    (2, 150),
    (10, 100),
    (20, 50),
    (40, 20),
    (80, 10),
    (130, 8),
    (180, 6),
    (250, 5),
]

_OUTPUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "outputs")
_RAW_COLUMNS = ["AAName", "paid_coe", "paid", "cartable_paid"]
_COMPANY_TOTAL_ROW_NAME = "همکده"


def increase_pct_for_rank(rank):
    for last_rank, increase_pct in TIERS:
        if rank <= last_rank:
            return increase_pct
    return 0


def final_commission_pct(increase_pct):
    return round(BASE_COMMISSION_PCT * (1 + increase_pct / 100), 2)


def build(raw_paths, slot_jdt):
    from . import requirements as req

    df = pd.read_csv(raw_paths["SP.HK.SPK"], encoding="utf-8-sig", usecols=_RAW_COLUMNS)
    df = df.rename(columns={"AAName": "کارشناس"})
    for col in ("paid_coe", "paid", "cartable_paid"):
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0.0)

    names = df["کارشناس"].astype(str).str.strip()
    df = df[df["کارشناس"].notna() & (names != "") & (names != _COMPANY_TOTAL_ROW_NAME)]
    df = df[df["paid_coe"] > 0].copy()

    df = df.sort_values(
        ["paid_coe", "paid", "cartable_paid", "کارشناس"],
        ascending=[False, False, False, True],
        kind="mergesort",
    ).reset_index(drop=True)
    df["rank"] = range(1, len(df) + 1)
    df["increase_pct"] = df["rank"].apply(increase_pct_for_rank)
    df["final_commission_pct"] = df["increase_pct"].apply(final_commission_pct)

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
