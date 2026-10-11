"""
gozaresh-jame-padash-zaribvosoli-5040/builder.py

Runs the SAME builder as padash-zaribvosoli-5040-18-30mehr, so this report
can never disagree with what the کارشناسان were told. The builder is loaded
as a PRIVATE module copy whose _OUTPUT_DIR points into this reward's own
outputs/ (same pattern as gozaresh-jame-padash-gloroshen-5040) - the live
reward's per-slot CSVs, which its render reads for rank-change lines, are
never touched.

Adds from the same raw SP.54.SPK file what the کارشناس table drops:
supervisor, وصولی کارتابلی / کل per کارشناس, and the company-wide ضریب
وصولی = Σ cartable_paid / Σ answered_count over eligible کارشناسان (the
panel's own per-person formula, paid_coe = cartable_paid / answered_count;
SPK returns no company-total row for this window).
"""

import importlib
import importlib.util
import os

import pandas as pd

from .requirements import CAMPAIGN_END, CAMPAIGN_START, SOURCE_REWARD, period_end_for_slot

_HERE = os.path.dirname(os.path.abspath(__file__))
_REWARDS_DIR = os.path.dirname(_HERE)
_WORK_DIR = os.path.join(_HERE, "outputs", "_tables")


def _private_builder():
    package = f"Rewards.{SOURCE_REWARD}"
    importlib.import_module(package)
    spec = importlib.util.spec_from_file_location(
        f"{package}._jame_builder_copy", os.path.join(_REWARDS_DIR, SOURCE_REWARD, "builder.py"),
    )
    module = importlib.util.module_from_spec(spec)
    module.__package__ = package
    spec.loader.exec_module(module)
    module._OUTPUT_DIR = _WORK_DIR
    return module


def _mode(series):
    s = series.dropna().astype(str).str.strip()
    s = s[s != ""]
    return s.mode().iloc[0] if not s.empty else ""


def build(raw_paths, slot_jdt):
    builder = _private_builder()
    report = builder.build(raw_paths, slot_jdt)
    table = report["table"]

    raw = pd.read_csv(raw_paths["SP.54.SPK"], encoding="utf-8-sig")
    raw = raw[raw["AAName"].map(builder._is_eligible_karshenas)].copy()
    for col in ("cartable_paid", "paid", "answered_count"):
        raw[col] = pd.to_numeric(raw[col], errors="coerce").fillna(0)
    extra = raw.groupby("AAName").agg(
        supervisor=("supervisor__name", _mode),
        cartable_toman=("cartable_paid", "sum"),
        paid_toman=("paid", "sum"),
    ).reset_index().rename(columns={"AAName": "نام کارشناس"})
    extra["cartable_toman"] = (extra["cartable_toman"] * 1_000_000).round()
    extra["paid_toman"] = (extra["paid_toman"] * 1_000_000).round()
    table = table.merge(extra, on="نام کارشناس", how="left")

    answered = raw["answered_count"].sum()
    company_coe = raw["cartable_paid"].sum() * 1000 / answered if answered else 0.0

    period_end = period_end_for_slot(slot_jdt)
    report.update({
        "table": table,
        "tiers": builder.RANK_TIERS,
        "base_percent": builder.BASE_PERCENT,
        "company_coe": company_coe,
        "period_start": CAMPAIGN_START,
        "period_end": period_end,
        "is_final": period_end >= CAMPAIGN_END,
    })
    return report
