"""
padash-zaribvosoli-5040-18-30mehr/builder.py

Copied from padash-karshenasan-5040/builder.py (user 2026-10-10: the same
reward repeated) - ranking, tiers and money logic unchanged. Dropped: the
per-slot manager .xlsx and the end-of-campaign management image (the
comprehensive report is its own reward now, gozaresh-jame-padash-
zaribvosoli-5040, which runs THIS builder).

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
{"slot_jdt": slot_jdt, "table": DataFrame} as `report` for render.py.
"""

import os
import re

import pandas as pd

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


def build(raw_paths, slot_jdt):
    raw_df = pd.read_csv(raw_paths["SP.54.SPK"], encoding="utf-8-sig")

    if raw_df.empty:
        table = pd.DataFrame(columns=[
            "نام کارشناس", "رتبه", "ضریب وصول", "درصد نهایی پورسانت",
            "مبلغ پورسانت بر آوردی تا این لحظه", "پاداش مازاد بر آوردی",
        ])
        return {"slot_jdt": slot_jdt, "table": table}

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
    # User 2026-10-10: a zero ضریب وصول is outside the reward range whatever
    # its رتبه - ranking already puts every zero after every non-zero, but
    # while fewer than 550 have a ratio (campaign start) zeros would land
    # inside the tiers. They stay on the base 15% until their ratio is > 0.
    grouped.loc[grouped["ضریب وصول"] <= 0, "درصد نهایی پورسانت"] = BASE_PERCENT
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

    return {"slot_jdt": slot_jdt, "table": table}
