"""
Anomaly/outlier detection, refactored from ml_lab_anomaly_month.py into a
reusable function. IQR chosen over Z-score - see ml_lab_anomaly.py's
findings (2026-09-23): one extreme outlier inflates std enough to mask
other real outliers under Z-score (the "masking effect"); IQR (median/
quartile based) doesn't have this weakness.
"""

import pandas as pd


def _iqr_outlier_mask(series, k=1.5):
    q1 = series.quantile(0.25)
    q3 = series.quantile(0.75)
    iqr = q3 - q1
    lower = q1 - k * iqr
    upper = q3 + k * iqr
    return (series < lower) | (series > upper)


def detect_anomalies(df, metric_columns=("paid_coe", "paid", "cartable_paid"), k=1.5):
    """df must have one row per کارشناس with metric_columns present, plus
    (if available) manual_paid and calls_count for the fraud-review flag.

    Returns df with an added 'is_outlier' bool column (union across
    metric_columns) and, when manual_paid/calls_count are present, a
    'manual_paid_ratio' column - a high ratio + low calls_count is the
    pattern worth a human look (money registered without matching call
    activity), not proof of anything by itself. See
    ml_lab_anomaly_month.py's 2026-09-23 findings for the reasoning."""
    result = df.copy()
    outlier_mask = pd.Series(False, index=df.index)
    for col in metric_columns:
        outlier_mask |= _iqr_outlier_mask(df[col], k=k)
    result["is_outlier"] = outlier_mask

    if "manual_paid" in df.columns and "paid" in df.columns:
        result["manual_paid_ratio"] = (df["manual_paid"] / df["paid"].replace(0, pd.NA)).fillna(0)

    return result
