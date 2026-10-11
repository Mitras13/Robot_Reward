"""
Message tone selection via K-Means clustering, refactored from
ml_lab_tone_clustering.py.

Known limitation (found 2026-09-26, kept as-is - see module docstring in
the lab script): a cluster's tone reflects the GROUP's average behavior,
not a per-person guarantee - a person with a real drop can still land in
a "growing" cluster if their other features (e.g. high paid_sum) pull them
there. pick_tone() layers a safety-net rule on top for exactly this case:
a strongly negative individual growth_rate always forces the follow-up
tone, regardless of cluster.
"""

import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler

from .features import aggregate_period, growth_rate

_TONE_BY_PROFILE = {
    "high_growing": "تشویقی/تبریک",
    "high_stable": "قدردانی آرام",
    "low_growing": "تشویق مسیر رشد",
    "low_declining": "پیگیری/انگیزشی",
}

# Below this individual growth_rate, always use the follow-up tone -
# overrides whatever cluster the person landed in (see module docstring).
_SAFETY_NET_DECLINE_THRESHOLD = -0.30

# Absolute rank cutoff for the "champion" footer tone in the real render.py
# integration (2026-09-26) - separate from the clustering above, and the one
# actually wired into production. Both رتبه‌بندی renders only ever message
# the top 25% (_select_recipients), so growth-based clustering across the
# WHOLE population never matches the real recipient set; every recipient is
# already a good performer, so the only meaningful split left is "top 5
# overall" vs "rest of the top 25%" - needs only the current slot's own
# ranking table, no historical data (which همکده doesn't have at
# day-granularity anyway - see ml_lab_prepare_daily.py's HK gap).
CHAMPION_RANK_THRESHOLD = 5


def pick_tone_by_rank(row, rank_columns=("رتبه ضریب وصولی", "رتبه وصولی کل"), threshold=CHAMPION_RANK_THRESHOLD):
    """True (champion) if the person is ranked <= threshold on ANY of
    rank_columns - same "union of top performers" shape as
    _select_recipients in both render.py files, just a stricter cutoff."""
    return any(row[col] <= threshold for col in rank_columns)


def _name_cluster(center_row, paid_median):
    is_high = center_row["paid_sum_p1"] >= paid_median
    is_growing = center_row["growth_rate"] >= 0  # absolute, not median-relative - see features.growth_rate
    if is_high and is_growing:
        return "high_growing"
    if is_high and not is_growing:
        return "high_stable"
    if not is_high and is_growing:
        return "low_growing"
    return "low_declining"


def build_tone_table(daily_df, period1_days, period2_days, n_clusters=4, random_state=42):
    p1 = aggregate_period(daily_df, period1_days, "p1")
    p2 = aggregate_period(daily_df, period2_days, "p2")
    data = p1.join(p2, how="inner").reset_index()

    data["growth_rate"] = growth_rate(data["paid_sum_p1"], data["paid_sum_p2"])
    data["answered_rate_p1"] = (data["answered_sum_p1"] / data["calls_sum_p1"].replace(0, np.nan)).fillna(0)

    feature_cols = ["paid_sum_p1", "growth_rate", "answered_rate_p1"]
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(data[feature_cols])

    kmeans = KMeans(n_clusters=n_clusters, random_state=random_state, n_init=10)
    data["cluster"] = kmeans.fit_predict(X_scaled)

    centers = pd.DataFrame(scaler.inverse_transform(kmeans.cluster_centers_), columns=feature_cols)
    paid_median = data["paid_sum_p1"].median()
    profile_by_cluster = {i: _name_cluster(row, paid_median) for i, row in centers.iterrows()}

    data["tone"] = data["cluster"].map(lambda c: _TONE_BY_PROFILE[profile_by_cluster[c]])
    data.loc[data["growth_rate"] <= _SAFETY_NET_DECLINE_THRESHOLD, "tone"] = _TONE_BY_PROFILE["low_declining"]

    return data
