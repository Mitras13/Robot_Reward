"""
ml_lab_anomaly_month.py - learning script, NOT part of the reward's 4-file
contract. Runs IQR-based anomaly detection over the FULL Shahrivar month
(1405/06/01 -> 1405/06/31), using the raw cached SP.54.SPK response already
on disk (raw_data/SPK/54/54_SPK_140506010000_140506312359_14050701080000.csv)
instead of re-downloading.

Goal: find کارشناسان with outlier paid/paid_coe/cartable_paid over a full
month (more reliable than one week), then pull in context columns
(calls_count, answered_percent, manual_paid ratio) to help judge whether an
outlier looks like real top performance vs a suspicious pattern worth a
manual check - this script only flags candidates, it does not accuse anyone.
"""

import os

import pandas as pd

_RAW_CSV = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "raw_data", "SPK", "54",
    "54_SPK_140506010000_140506312359_14050701080000.csv",
)

_COMPANY_TOTAL_ROW_NAME = "5040"
MONEY_TO_TOMAN = 1_000_000

_METRIC_COLUMNS = ["paid_coe", "paid", "cartable_paid"]


def _load():
    df = pd.read_csv(_RAW_CSV, encoding="utf-8-sig")
    df = df[df["AAName"].notna() & (df["AAName"].astype(str).str.strip() != "")]
    df = df[df["AAName"].astype(str).str.strip() != _COMPANY_TOTAL_ROW_NAME]

    for col in _METRIC_COLUMNS + ["manual_paid", "calls_count", "answered_count", "answered_percent"]:
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0.0)

    df["paid"] = df["paid"] * MONEY_TO_TOMAN
    df["cartable_paid"] = df["cartable_paid"] * MONEY_TO_TOMAN
    df["manual_paid"] = df["manual_paid"] * MONEY_TO_TOMAN

    df = df[(df["paid_coe"] != 0) | (df["paid"] != 0) | (df["cartable_paid"] != 0)].copy()
    return df


def iqr_outliers(series, k=1.5):
    q1 = series.quantile(0.25)
    q3 = series.quantile(0.75)
    iqr = q3 - q1
    lower = q1 - k * iqr
    upper = q3 + k * iqr
    return (series < lower) | (series > upper)


def main():
    df = _load()
    print(f"Total کارشناسان with activity this month: {len(df)}\n")

    flagged_names = set()
    for col in _METRIC_COLUMNS:
        flags = iqr_outliers(df[col])
        flagged_names |= set(df.loc[flags, "AAName"])
        print(f"{col}: {flags.sum()} outliers")

    print(f"\nUnion of all outlier کارشناسان: {len(flagged_names)}\n")

    context_cols = ["AAName", "paid_coe", "paid", "cartable_paid", "manual_paid",
                     "calls_count", "answered_count", "answered_percent"]
    report = df[df["AAName"].isin(flagged_names)][context_cols].copy()

    # manual_paid ratio: manually-entered collections as a share of total paid.
    # A high ratio + low calls_count is the pattern worth a manual look -
    # money registered without matching call activity - not by itself proof
    # of anything, just a flag.
    report["manual_paid_ratio"] = (report["manual_paid"] / report["paid"].replace(0, pd.NA)).fillna(0)
    report["paid_per_call"] = (report["paid"] / report["calls_count"].replace(0, pd.NA)).fillna(0)

    report = report.sort_values("paid", ascending=False)

    pd.set_option("display.max_rows", None)
    pd.set_option("display.width", 200)
    print(report.to_string(index=False))

    report.to_csv(
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "ml_lab_month_outliers.csv"),
        index=False, encoding="utf-8-sig",
    )


if __name__ == "__main__":
    main()
