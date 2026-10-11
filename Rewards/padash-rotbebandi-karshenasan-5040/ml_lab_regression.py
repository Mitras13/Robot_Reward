"""
ml_lab_regression.py - Phase 3 (Performance Prediction) of the ML learning
track. Learning script, NOT part of the reward's 4-file contract.

Reads the clean daily panel built by ml_lab_prepare_daily.py
(outputs/ml_lab_daily_long.csv, 1163 people x 8 days: 24->31 Shahrivar) and
trains a model to predict a person's "paid" TOMORROW from their own recent
history.

Concepts introduced here:
- Lag features: paid_lag1/2/3 = paid on day-1/-2/-3 relative to the row
  being predicted. You can never use the SAME day's own paid as a feature
  to predict that day's paid - that would be leaking the answer.
- Rolling mean: paid_roll_mean3 = average of the last 3 days - smooths out
  single-day noise, often more predictive than any single lag alone.
- Time-based train/test split: for time series, splitting randomly leaks
  the future into training (the model would implicitly "see" patterns from
  test-period days via other people's same-day rows). Instead we train on
  earlier target days and test on the latest ones only.
- Baseline comparison: "predict tomorrow = same as yesterday" (naive lag-1
  baseline) is the bar a real model has to beat to be worth using at all.
"""

import os

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_absolute_error, r2_score

_DAILY_CSV = os.path.join(os.path.dirname(os.path.abspath(__file__)), "outputs", "ml_lab_daily_long.csv")

_N_LAGS = 3
_TEST_DAYS = {30, 31}  # last two days held out - never seen during training


def _build_features(long_df):
    df = long_df.sort_values(["کارشناس", "day"]).copy()
    grouped = df.groupby("کارشناس")["paid"]

    for lag in range(1, _N_LAGS + 1):
        df[f"paid_lag{lag}"] = grouped.shift(lag)

    df["paid_roll_mean3"] = grouped.shift(1).rolling(3).mean().reset_index(level=0, drop=True)
    df["calls_lag1"] = df.groupby("کارشناس")["calls_count"].shift(1)

    feature_cols = [f"paid_lag{lag}" for lag in range(1, _N_LAGS + 1)] + ["paid_roll_mean3", "calls_lag1"]
    df = df.dropna(subset=feature_cols)
    return df, feature_cols


def main():
    long_df = pd.read_csv(_DAILY_CSV, encoding="utf-8-sig")
    df, feature_cols = _build_features(long_df)

    print(f"Rows usable for training (need {_N_LAGS} prior days of history): {len(df)}")
    print(f"Target days available: {sorted(df['day'].unique())}")
    print(f"Feature columns: {feature_cols}\n")

    train = df[~df["day"].isin(_TEST_DAYS)]
    test = df[df["day"].isin(_TEST_DAYS)]
    print(f"Train rows: {len(train)} (days {sorted(train['day'].unique())})")
    print(f"Test rows:  {len(test)} (days {sorted(test['day'].unique())})\n")

    X_train, y_train = train[feature_cols], train["paid"]
    X_test, y_test = test[feature_cols], test["paid"]

    # Naive baseline: "tomorrow = same as yesterday" - what a model MUST beat.
    baseline_pred = X_test["paid_lag1"]
    baseline_mae = (baseline_pred - y_test).abs().mean()
    print(f"Baseline (predict = yesterday's paid) MAE: {baseline_mae:,.0f} toman")

    df.to_csv(os.path.join(os.path.dirname(_DAILY_CSV), "ml_lab_features.csv"), index=False, encoding="utf-8-sig")

    # random_state fixed so re-running this script gives the same numbers to
    # compare against - a real deployment would still fix it, for
    # reproducibility, not just for this learning exercise.
    model = RandomForestRegressor(n_estimators=200, max_depth=6, random_state=42)
    model.fit(X_train, y_train)
    model_pred = model.predict(X_test)

    model_mae = mean_absolute_error(y_test, model_pred)
    model_r2 = r2_score(y_test, model_pred)

    print(f"\nModel (RandomForestRegressor) MAE: {model_mae:,.0f} toman")
    print(f"Model R² (test set): {model_r2:.3f}")
    improvement = (baseline_mae - model_mae) / baseline_mae * 100
    print(f"Improvement over baseline: {improvement:+.1f}%")

    print("\nFeature importances:")
    for col, importance in sorted(zip(feature_cols, model.feature_importances_), key=lambda x: -x[1]):
        print(f"  {col}: {importance:.3f}")

    return X_train, y_train, X_test, y_test, baseline_mae, model


if __name__ == "__main__":
    main()
