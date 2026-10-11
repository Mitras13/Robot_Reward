"""
padash-sahmie-vorodi-hamkadeh/builder.py

Twin of padash-sahmie-vorodi-5040/builder.py for company همکده (SP.HK.SPK
instead of SP.54.SPK) - same "AAName"/"cartable_paid" column names assumed
(same SPK report-code shape as the 54 twin, per API_Downloader/SP/HK/SPK.py's
own comment that it mirrors SP.54.SPK's body/response shape), NOT
independently re-confirmed against a real HK response yet.

⚠️ UNVERIFIED (flagged explicitly by the user 2026-09-21, "مطمئن نیستم، اول
یک اسلات تست بزن"): whether HK's cartable_paid uses the same ×1,000,000
(میلیون تومان) convention already confirmed for SP.54.SPK, or is already a
real تومان figure. THRESHOLD_TOMAN below (۲۵۰ میلیون) assumes the same
×1,000,000 scale as the 5040 twin - MUST be confirmed with a real test slot
before this reward is ever enabled; if the raw cartable_paid numbers turn
out to already be تومان, remove the ×1,000,000 multiplication in build().

Eligibility filter (real کارشناس vs. test/duplicate rows) reused as-is from
padash-karshenasan-5040/builder.py for the same reason it applies there -
any English letter in AAName (their team-suffix). NOT independently
re-verified against real HK names either - check the test slot's raw AAName
values look right before enabling.

Threshold: STRICTLY more than THRESHOLD_TOMAN (>, not >=) - matches the
announcement's "بیش از ۲۵۰ میلیون تومان" wording, same convention as the
5040 twin. Non-qualifiers are dropped entirely here - render.py never sees
them (same "فقط واجدین پیام بگیرن" decision as the 5040 twin, 2026-09-21).

Writes the per-slot table to outputs/{slot label}.csv and returns
{"slot_jdt": slot_jdt, "table": DataFrame} for render.py.
"""

import os
import re

import pandas as pd

THRESHOLD_TOMAN = 250_000_000

_OUTPUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "outputs")

_HAS_ENGLISH_LETTER = re.compile(r"[A-Za-z]")


def _is_eligible_karshenas(name):
    return bool(_HAS_ENGLISH_LETTER.search(str(name)))


def build(raw_paths, slot_jdt):
    df = pd.read_csv(raw_paths["SP.HK.SPK"], encoding="utf-8-sig")

    if df.empty:
        table = pd.DataFrame(columns=["نام کارشناس", "مبلغ وصول کارتابلی"])
        return {"slot_jdt": slot_jdt, "table": table}

    df = df[df["AAName"].map(_is_eligible_karshenas)].copy()
    df["cartable_paid"] = pd.to_numeric(df["cartable_paid"], errors="coerce").fillna(0)

    grouped = df.groupby("AAName").agg(
        cartable_paid=("cartable_paid", "sum"),
    ).reset_index().rename(columns={"AAName": "نام کارشناس"})

    # ⚠️ see module docstring - ×1,000,000 scale is UNVERIFIED for HK.
    grouped["مبلغ وصول کارتابلی"] = (grouped["cartable_paid"] * 1_000_000).round().astype(int)
    grouped = grouped[grouped["مبلغ وصول کارتابلی"] > THRESHOLD_TOMAN].copy()
    grouped = grouped.sort_values(by="مبلغ وصول کارتابلی", ascending=False).reset_index(drop=True)

    table = grouped[["نام کارشناس", "مبلغ وصول کارتابلی"]].copy()

    os.makedirs(_OUTPUT_DIR, exist_ok=True)
    slot_label = slot_jdt.strftime("%Y_%m_%d_%H%M")
    output_path = os.path.join(_OUTPUT_DIR, f"{slot_label}.csv")
    table.to_csv(output_path, index=False, encoding="utf-8-sig")

    return {"slot_jdt": slot_jdt, "table": table}
