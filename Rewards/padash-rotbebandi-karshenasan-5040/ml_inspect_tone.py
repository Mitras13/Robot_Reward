"""
ml_inspect_tone.py - shows exactly what each tone was matched against:
per-cluster criteria (paid level / growth direction / answered rate) and
a full per-person table. Not part of the reward's 4-file contract.
"""

import os

import pandas as pd

from ml.tone import build_tone_table, _SAFETY_NET_DECLINE_THRESHOLD

_DAILY_CSV = os.path.join(os.path.dirname(os.path.abspath(__file__)), "outputs", "ml_lab_daily_long.csv")
_PERIOD1_DAYS = {24, 25, 26, 27}
_PERIOD2_DAYS = {28, 29, 30, 31}


def main():
    daily_df = pd.read_csv(_DAILY_CSV, encoding="utf-8-sig")
    data = build_tone_table(daily_df, _PERIOD1_DAYS, _PERIOD2_DAYS)

    print("=== معیار هر خوشه (میانگین رفتار اعضای همون خوشه) ===")
    summary = data.groupby(["cluster", "tone"]).agg(
        نفرات=("کارشناس", "count"),
        میانگین_وصولی_هفته_قبل=("paid_sum_p1", "mean"),
        میانگین_رشد=("growth_rate", "mean"),
        میانگین_نرخ_پاسخگویی=("answered_rate_p1", "mean"),
    ).round(2)
    print(summary.to_string())

    print(f"\n=== قانون Safety-net ===")
    print(f"اگه growth_rate فرد <= {_SAFETY_NET_DECLINE_THRESHOLD} باشه (افت شدید)، "
          f"صرف‌نظر از خوشه، لحن 'پیگیری/انگیزشی' اجباری می‌شه.")
    overridden = data[data["growth_rate"] <= _SAFETY_NET_DECLINE_THRESHOLD]
    print(f"تعداد افرادی که با این قانون override شدن: {len(overridden)}")

    print("\n=== جدول کامل هر نفر (نمونه‌ی ۲۰ نفر) ===")
    cols = ["کارشناس", "paid_sum_p1", "paid_sum_p2", "growth_rate", "answered_rate_p1", "cluster", "tone"]
    print(data[cols].sample(20, random_state=7).to_string(index=False))

    out_path = os.path.join(os.path.dirname(_DAILY_CSV), "ml_lab_tone_assignments.csv")
    data[cols].to_csv(out_path, index=False, encoding="utf-8-sig")
    print(f"\nجدول کامل ({len(data)} نفر) ذخیره شد: {out_path}")


if __name__ == "__main__":
    main()
