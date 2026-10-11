"""
ml_lab_prepare_daily.py - Phase 1 (Data Preparation) of the ML learning
track. Learning script, NOT part of the reward's 4-file contract.

Builds a clean per-کارشناس DAILY time series (1405/06/24 -> 1405/06/31)
from the single-calendar-day raw SP.54.SPK snapshots already cached in
raw_data/SPK/54/ (period_start date == period_end date, e.g.
54_SPK_140506240000_140506242359_*.csv = just the 24th).

Concepts introduced here:
- Long format: one row per (person, day) - the natural shape for a time
  series with many entities, and what every ML library (scikit-learn,
  pandas groupby/rolling) expects.
- Wide format: one row per person, one column per day - easier for a human
  to eyeball, useless for feeding a model directly.
- When a day has multiple raw snapshots (re-downloaded same day), we keep
  only the LATEST one (highest download timestamp in the filename) - same
  "latest wins" rule the real pipeline uses implicitly by always fetching
  fresh.
"""

import glob
import os
import re

import pandas as pd

_RAW_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "raw_data", "SPK", "54",
)

_OUTPUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "outputs")

_COMPANY_TOTAL_ROW_NAME = "5040"
MONEY_TO_TOMAN = 1_000_000

_METRIC_COLUMNS = ["paid_coe", "paid", "cartable_paid", "manual_paid", "calls_count", "answered_count"]

# period_start date == period_end date -> a single calendar day's snapshot.
_SINGLE_DAY_PATTERN = re.compile(r"^54_SPK_(\d{8})0000_(\d{8})2359_(\d{14})\.csv$")


def _find_single_day_files():
    """Returns {day_number (int, Jalali day-of-month): latest_file_path}."""
    best_by_day = {}
    for path in glob.glob(os.path.join(_RAW_DIR, "54_SPK_*.csv")):
        name = os.path.basename(path)
        m = _SINGLE_DAY_PATTERN.match(name)
        if not m or m.group(1) != m.group(2):
            continue
        day_str, _, download_ts = m.groups()
        day_number = int(day_str[-2:])
        if day_number not in best_by_day or download_ts > best_by_day[day_number][1]:
            best_by_day[day_number] = (path, download_ts)
    return {day: path for day, (path, _ts) in best_by_day.items()}


def _load_one_day(path, day_number):
    df = pd.read_csv(path, encoding="utf-8-sig")
    df = df[df["AAName"].notna() & (df["AAName"].astype(str).str.strip() != "")]
    df = df[df["AAName"].astype(str).str.strip() != _COMPANY_TOTAL_ROW_NAME]

    for col in _METRIC_COLUMNS:
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0.0)
    df["paid"] = df["paid"] * MONEY_TO_TOMAN
    df["cartable_paid"] = df["cartable_paid"] * MONEY_TO_TOMAN
    df["manual_paid"] = df["manual_paid"] * MONEY_TO_TOMAN

    df = df.rename(columns={"AAName": "کارشناس"})
    df["day"] = day_number
    return df[["کارشناس", "day"] + _METRIC_COLUMNS]


def _fill_missing_days(long_df, all_days):
    """A person missing from a day's raw snapshot had zero activity that day
    (confirmed assumption, 2026-09-26 user decision) - reindex every person
    across the full day range and fill the gaps with 0, rather than leaving
    a shorter, ragged series per person (which every rolling/lag feature
    downstream would otherwise have to special-case)."""
    all_names = long_df["کارشناس"].unique()
    full_index = pd.MultiIndex.from_product([all_names, all_days], names=["کارشناس", "day"])
    filled = (
        long_df.set_index(["کارشناس", "day"])
        .reindex(full_index, fill_value=0.0)
        .reset_index()
    )
    return filled


def build_daily_long():
    files_by_day = _find_single_day_files()
    print(f"Found single-day snapshots for {len(files_by_day)} days: {sorted(files_by_day)}")

    frames = [_load_one_day(path, day) for day, path in sorted(files_by_day.items())]
    long_df = pd.concat(frames, ignore_index=True)
    long_df = _fill_missing_days(long_df, sorted(files_by_day))
    long_df = long_df.sort_values(["کارشناس", "day"]).reset_index(drop=True)
    return long_df


def main():
    long_df = build_daily_long()

    print(f"\nLong-format rows: {len(long_df)} "
          f"({long_df['کارشناس'].nunique()} people x {long_df['day'].nunique()} days)")
    print("\nSample (one person's daily rows):")
    sample_name = long_df["کارشناس"].iloc[0]
    print(long_df[long_df["کارشناس"] == sample_name].to_string(index=False))

    os.makedirs(_OUTPUT_DIR, exist_ok=True)
    out_path = os.path.join(_OUTPUT_DIR, "ml_lab_daily_long.csv")
    long_df.to_csv(out_path, index=False, encoding="utf-8-sig")
    print(f"\nSaved: {out_path}")


if __name__ == "__main__":
    main()
