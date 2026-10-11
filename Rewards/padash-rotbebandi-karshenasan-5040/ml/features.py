"""
Shared aggregation helpers for anomaly.py / predict.py / tone.py - kept in
one place so all three build features the same way. Not part of the
reward's 4-file contract; consumed by ml_demo.py and, once approved for
real use, would be called from builder.py.
"""

import numpy as np
import pandas as pd


def aggregate_period(daily_df, days, suffix):
    """daily_df: long-format (کارشناس, day, paid, paid_coe, cartable_paid,
    manual_paid, calls_count, answered_count) - see
    ml_lab_prepare_daily.py for how this shape is built from raw snapshots."""
    subset = daily_df[daily_df["day"].isin(days)]
    agg = subset.groupby("کارشناس").agg(
        paid_sum=("paid", "sum"),
        paid_coe_mean=("paid_coe", "mean"),
        cartable_paid_sum=("cartable_paid", "sum"),
        manual_paid_sum=("manual_paid", "sum"),
        calls_sum=("calls_count", "sum"),
        answered_sum=("answered_count", "sum"),
        active_days=("paid", lambda s: (s > 0).sum()),
    )
    return agg.add_suffix(f"_{suffix}")


def growth_rate(paid_p1, paid_p2, clip=(-1, 3)):
    """(p2 - p1) / p1, clipped - an unclipped ratio blows up whenever p1 is
    near zero (a tiny absolute change reads as a huge percentage), which in
    practice skews any median/threshold computed over it. See
    ml_lab_tone_clustering.py's 2026-09-26 fix for the concrete bug this
    caused (a +27% growth cluster mislabeled "declining")."""
    ratio = (paid_p2 - paid_p1) / paid_p1.replace(0, np.nan)
    return ratio.fillna(0).clip(*clip)
