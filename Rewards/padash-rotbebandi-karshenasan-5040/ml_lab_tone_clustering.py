"""
ml_lab_tone_clustering.py - Phase 4 (Message Tone Selection) of the ML
learning track. Learning script, NOT part of the reward's 4-file contract.

Uses K-Means clustering to group کارشناسان into natural performance
segments (from the same period1/period2 weekly aggregates as
ml_lab_regression_weekly.py), then names each cluster and maps it to a
message tone - instead of hand-writing threshold rules ("if growth > X").

Concepts introduced here:
- Unsupervised clustering: no "correct" label per person is given - K-Means
  just groups people whose feature vectors are close together in space.
- StandardScaler: paid_sum (millions) and growth_rate (a small ratio like
  -0.3..2.0) live on wildly different scales - without scaling, K-Means'
  distance calculation would be dominated entirely by paid_sum and ignore
  growth_rate. Every clustering/distance-based method needs this; tree
  models (RandomForest) do NOT, which is why earlier scripts skipped it.
- Choosing k: there's no single right answer - here we fix k=4 and NAME
  the resulting clusters by inspecting their centers, rather than trusting
  a label like "cluster 2" blindly.
"""

import os

import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler

_DAILY_CSV = os.path.join(os.path.dirname(os.path.abspath(__file__)), "outputs", "ml_lab_daily_long.csv")

_PERIOD1_DAYS = {24, 25, 26, 27}
_PERIOD2_DAYS = {28, 29, 30, 31}

_N_CLUSTERS = 4

_TONE_BY_PROFILE = {
    "high_growing": ("تشویقی/تبریک", "رشد قوی و سطح وصولی بالا - قدردانی و تشویق به ادامه‌ی روند"),
    "high_stable": ("قدردانی آرام", "سطح وصولی بالا ولی رشد کم - تثبیت جایگاه، بدون فشار اضافه"),
    "low_declining": ("پیگیری/انگیزشی", "افت محسوس - پیام باید محرک و راهنما باشد، نه سرزنش‌گر"),
    "low_growing": ("تشویق مسیر رشد", "سطح پایین ولی در حال بهبود - تاکید روی روند مثبت، نه سطح فعلی"),
}


def _aggregate_period(df, days, suffix):
    subset = df[df["day"].isin(days)]
    agg = subset.groupby("کارشناس").agg(
        paid_sum=("paid", "sum"),
        calls_sum=("calls_count", "sum"),
        answered_sum=("answered_count", "sum"),
    )
    return agg.add_suffix(f"_{suffix}")


def _name_cluster(center_row, medians):
    """Name a cluster from its center vs the overall median - readable
    labels beat "cluster 0/1/2/3" for picking a tone mapping by hand.

    growth_rate uses an ABSOLUTE zero threshold, not the median: its median
    across all people is skewed way above zero by people with a near-zero
    paid_sum_p1 denominator (a tiny absolute increase reads as a huge
    ratio) - comparing to that skewed median mislabeled a cluster with a
    real +27% growth as "declining" (found 2026-09-26 by inspecting cluster
    centers before trusting the labels)."""
    is_high = center_row["paid_sum_p1"] >= medians["paid_sum_p1"]
    is_growing = center_row["growth_rate"] >= 0
    if is_high and is_growing:
        return "high_growing"
    if is_high and not is_growing:
        return "high_stable"
    if not is_high and is_growing:
        return "low_growing"
    return "low_declining"


def main():
    long_df = pd.read_csv(_DAILY_CSV, encoding="utf-8-sig")

    p1 = _aggregate_period(long_df, _PERIOD1_DAYS, "p1")
    p2 = _aggregate_period(long_df, _PERIOD2_DAYS, "p2")
    data = p1.join(p2, how="inner").reset_index()

    data["growth_rate"] = (data["paid_sum_p2"] - data["paid_sum_p1"]) / data["paid_sum_p1"].replace(0, np.nan)
    data["growth_rate"] = data["growth_rate"].fillna(0).clip(-1, 3)  # cap extreme ratios from near-zero p1
    data["answered_rate_p1"] = (data["answered_sum_p1"] / data["calls_sum_p1"].replace(0, np.nan)).fillna(0)

    feature_cols = ["paid_sum_p1", "growth_rate", "answered_rate_p1"]
    X = data[feature_cols]

    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)

    kmeans = KMeans(n_clusters=_N_CLUSTERS, random_state=42, n_init=10)
    data["cluster"] = kmeans.fit_predict(X_scaled)

    centers = pd.DataFrame(scaler.inverse_transform(kmeans.cluster_centers_), columns=feature_cols)
    medians = X.median()

    print("Cluster centers (un-scaled):")
    print(centers.to_string())
    print(f"\nOverall medians: {medians.to_dict()}\n")

    profile_by_cluster = {}
    for cluster_id, row in centers.iterrows():
        profile = _name_cluster(row, medians)
        profile_by_cluster[cluster_id] = profile
        tone, reason = _TONE_BY_PROFILE[profile]
        count = (data["cluster"] == cluster_id).sum()
        print(f"Cluster {cluster_id} -> profile='{profile}' -> tone='{tone}' ({count} نفر)")
        print(f"  paid_sum_p1={row['paid_sum_p1']:,.0f}  growth_rate={row['growth_rate']:.2f}  "
              f"answered_rate={row['answered_rate_p1']:.2f}")
        print(f"  reason: {reason}\n")

    data["tone"] = data["cluster"].map(lambda c: _TONE_BY_PROFILE[profile_by_cluster[c]][0])

    print("Sample assignments:")
    print(data[["کارشناس", "paid_sum_p1", "growth_rate", "tone"]].sample(10, random_state=1).to_string(index=False))

    out_path = os.path.join(os.path.dirname(_DAILY_CSV), "ml_lab_tone_assignments.csv")
    data.to_csv(out_path, index=False, encoding="utf-8-sig")
    print(f"\nSaved: {out_path}")


if __name__ == "__main__":
    main()
