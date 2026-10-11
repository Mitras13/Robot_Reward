"""
ml_demo.py - runs anomaly.py / predict.py / tone.py together on the real
daily dataset, to sanity-check the refactored ml/ package. Not part of the
reward's 4-file contract, not wired into builder.py/render.py.
"""

import os

import pandas as pd

from ml.anomaly import detect_anomalies
from ml.features import aggregate_period
from ml.predict import build_training_table, fit_predictor, predict_next_period
from ml.tone import build_tone_table

_DAILY_CSV = os.path.join(os.path.dirname(os.path.abspath(__file__)), "outputs", "ml_lab_daily_long.csv")
_PERIOD1_DAYS = {24, 25, 26, 27}
_PERIOD2_DAYS = {28, 29, 30, 31}


def main():
    daily_df = pd.read_csv(_DAILY_CSV, encoding="utf-8-sig")

    print("=== Anomaly detection (whole month view, period2 totals) ===")
    p2 = aggregate_period(daily_df, _PERIOD2_DAYS, "p2").reset_index()
    p2 = p2.rename(columns={c: c.replace("_p2", "") for c in p2.columns if c.endswith("_p2")})
    anomalies = detect_anomalies(p2, metric_columns=("paid_coe_mean", "paid_sum", "cartable_paid_sum"))
    print(f"Outliers flagged: {anomalies['is_outlier'].sum()} / {len(anomalies)}\n")

    print("=== Prediction (train on period1 -> period2) ===")
    table = build_training_table(daily_df, _PERIOD1_DAYS, _PERIOD2_DAYS)
    model, feature_cols = fit_predictor(table)
    preds = predict_next_period(model, feature_cols, table)
    mae = (preds - table["paid_sum_p2"]).abs().mean()
    print(f"In-sample MAE: {mae:,.0f} toman (see ml_lab_regression_weekly.py for the real held-out test)\n")

    print("=== Tone assignment ===")
    tones = build_tone_table(daily_df, _PERIOD1_DAYS, _PERIOD2_DAYS)
    print(tones["tone"].value_counts().to_string())


if __name__ == "__main__":
    main()
