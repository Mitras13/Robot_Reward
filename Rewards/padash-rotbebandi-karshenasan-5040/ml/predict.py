"""
Performance prediction, refactored from ml_lab_regression_weekly.py. Only
the PERIOD-aggregated (not daily) version - the daily one got a negative
R² (2026-09-26 finding: daily "paid" is too noisy over short history) and
isn't worth carrying into reusable code.
"""

from sklearn.ensemble import RandomForestRegressor

from .features import aggregate_period, growth_rate


def build_training_table(daily_df, period1_days, period2_days):
    """One row per کارشناس: period1 aggregates as features, period2
    paid_sum as the target. period1 must fully precede period2 for every
    person alike - no time-based split needed on top of this (see
    ml_lab_regression_weekly.py's docstring)."""
    p1 = aggregate_period(daily_df, period1_days, "p1")
    p2 = aggregate_period(daily_df, period2_days, "p2")
    data = p1.join(p2, how="inner").reset_index()
    return data


def fit_predictor(training_table, feature_cols=None, target_col="paid_sum_p2", random_state=42):
    feature_cols = feature_cols or [c for c in training_table.columns if c.endswith("_p1")]
    model = RandomForestRegressor(n_estimators=200, max_depth=6, random_state=random_state)
    model.fit(training_table[feature_cols], training_table[target_col])
    return model, feature_cols


def predict_next_period(model, feature_cols, current_period_table):
    """current_period_table: same shape as build_training_table's p1 half
    (one row per کارشناس, *_p1-suffixed columns) for the period whose
    NEXT period hasn't happened yet - i.e. real forward prediction, not
    backtesting against a period we already have the answer for."""
    return model.predict(current_period_table[feature_cols])
