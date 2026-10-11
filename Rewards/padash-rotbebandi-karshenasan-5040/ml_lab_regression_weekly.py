"""
ml_lab_regression_weekly.py - Phase 3b (weekly-ahead prediction) of the ML
learning track. Learning script, NOT part of the reward's 4-file contract.

The daily model (ml_lab_regression.py) failed (negative R²) because daily
"paid" is too noisy over only 8 days of history. Here we aggregate the same
8 days into two 4-day halves - period1 (day 24-27) and period2 (day 28-31)
- and predict each person's period2 TOTAL from their period1 TOTALS. Summing
days smooths out single-day noise, which is exactly why this is expected to
work better than the daily version, not because the model itself changed.

This turns the problem cross-sectional (one row per person, no day-to-day
sequence) - so the train/test split can be a plain random split instead of
a time-based one; there is no "future leaking into past" risk here because
period1 always fully precedes period2 for every person alike.
"""

import os

import pandas as pd
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_absolute_error, r2_score
from sklearn.model_selection import train_test_split

_DAILY_CSV = os.path.join(os.path.dirname(os.path.abspath(__file__)), "outputs", "ml_lab_daily_long.csv")

_PERIOD1_DAYS = {24, 25, 26, 27}
_PERIOD2_DAYS = {28, 29, 30, 31}


def _aggregate_period(df, days, suffix):
    subset = df[df["day"].isin(days)]
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


def main():
    long_df = pd.read_csv(_DAILY_CSV, encoding="utf-8-sig")

    p1 = _aggregate_period(long_df, _PERIOD1_DAYS, "p1")
    p2 = _aggregate_period(long_df, _PERIOD2_DAYS, "p2")
    data = p1.join(p2, how="inner").reset_index()

    feature_cols = [c for c in data.columns if c.endswith("_p1")]
    target_col = "paid_sum_p2"

    X = data[feature_cols]
    y = data[target_col]

    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
    print(f"People: {len(data)}  |  Train: {len(X_train)}  Test: {len(X_test)}\n")

    baseline_pred = X_test["paid_sum_p1"]
    baseline_mae = mean_absolute_error(y_test, baseline_pred)
    baseline_r2 = r2_score(y_test, baseline_pred)
    print(f"Baseline (predict period2 = period1 total) MAE: {baseline_mae:,.0f} toman, R²={baseline_r2:.3f}")

    model = RandomForestRegressor(n_estimators=200, max_depth=6, random_state=42)
    model.fit(X_train, y_train)
    pred = model.predict(X_test)

    model_mae = mean_absolute_error(y_test, pred)
    model_r2 = r2_score(y_test, pred)
    print(f"Model (RandomForestRegressor) MAE: {model_mae:,.0f} toman, R²={model_r2:.3f}")

    improvement = (baseline_mae - model_mae) / baseline_mae * 100
    print(f"Improvement over baseline: {improvement:+.1f}%\n")

    print("Feature importances:")
    for col, importance in sorted(zip(feature_cols, model.feature_importances_), key=lambda x: -x[1]):
        print(f"  {col}: {importance:.3f}")


if __name__ == "__main__":
    main()
