"""
ml_lab_anomaly.py - learning script, NOT part of the reward's 4-file contract.

Goal: learn anomaly detection by running it on this reward's real output
(outputs/1405_07_04_0000.csv). Does not touch builder.py/render.py or feed
into the actual pipeline - just prints findings for study.

Two classic methods, both "unsupervised" (no labeled "this is anomalous"
data needed - we just look at the shape of the distribution):

1. Z-score: how many standard deviations a value is from the mean.
   z = (x - mean) / std
   Rule of thumb: |z| > 3 is often called an outlier.

2. IQR (Interquartile Range): robust to extreme values because it's based
   on the median/quartiles, not the mean/std (which a single huge outlier
   can distort). Q1 = 25th percentile, Q3 = 75th percentile.
   IQR = Q3 - Q1
   Outlier if value < Q1 - 1.5*IQR  or  value > Q3 + 1.5*IQR
"""

import os

import pandas as pd

_OUTPUT_CSV = os.path.join(os.path.dirname(os.path.abspath(__file__)), "outputs", "1405_07_04_0000.csv")

_COLUMNS = ["paid_coe", "paid", "cartable_paid"]


def zscore_outliers(series, threshold=3.0):
    mean = series.mean()
    std = series.std()
    z = (series - mean) / std
    return z.abs() > threshold, z


def iqr_outliers(series, k=1.5):
    q1 = series.quantile(0.25)
    q3 = series.quantile(0.75)
    iqr = q3 - q1
    lower = q1 - k * iqr
    upper = q3 + k * iqr
    return (series < lower) | (series > upper)


def main():
    df = pd.read_csv(_OUTPUT_CSV, encoding="utf-8-sig")

    for col in _COLUMNS:
        print(f"\n=== {col} ===")
        print(f"mean={df[col].mean():,.1f}  std={df[col].std():,.1f}  "
              f"median={df[col].median():,.1f}")

        z_flags, z_values = zscore_outliers(df[col])
        iqr_flags = iqr_outliers(df[col])

        print(f"Z-score outliers ({z_flags.sum()}):")
        for name, z in zip(df.loc[z_flags, "کارشناس"], z_values[z_flags]):
            print(f"  {name}: z={z:.2f}, value={df.loc[df['کارشناس'] == name, col].values[0]:,.0f}")

        print(f"IQR outliers ({iqr_flags.sum()}):")
        for name in df.loc[iqr_flags, "کارشناس"]:
            print(f"  {name}: value={df.loc[df['کارشناس'] == name, col].values[0]:,.0f}")


if __name__ == "__main__":
    main()
