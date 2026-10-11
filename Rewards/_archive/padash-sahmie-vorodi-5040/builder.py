"""
padash-sahmie-vorodi-5040/builder.py

Reads SP.54.SPK (see API_Downloader/SP/54/SPK.py's column-list comment) and
picks every کارشناس whose cumulative "وصولی کارتابلی" (cartable_paid) over
the whole شهریور window (see requirements.py) is STRICTLY more than
THRESHOLD_TOMAN - matches the announcement's "بیش از ۳۵۰ میلیون تومان"
wording (>, not >=), confirmed by the user 2026-09-21. Non-qualifiers are
dropped entirely here - render.py never sees them (user confirmed 2026-09-21:
"نه، فقط واجدین پیام بگیرن").

Eligibility filter (real کارشناس vs. test/duplicate rows) reused as-is from
the sibling padash-karshenasan-5040/builder.py for this same company/source -
any English letter in AAName (their team-suffix).

Money unit: cartable_paid comes back in میلیون تومان, same confirmed
convention as padash-karshenasan-5040/builder.py - ×1,000,000 here for a
real تومان figure.

Writes the per-slot table to outputs/{slot label}.csv (same convention as
every other reward in this project) and returns
{"slot_jdt": slot_jdt, "table": DataFrame} for render.py.
"""

import os
import re

import pandas as pd

THRESHOLD_TOMAN = 350_000_000

_OUTPUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "outputs")

_HAS_ENGLISH_LETTER = re.compile(r"[A-Za-z]")


def _is_eligible_karshenas(name):
    return bool(_HAS_ENGLISH_LETTER.search(str(name)))


def build(raw_paths, slot_jdt):
    df = pd.read_csv(raw_paths["SP.54.SPK"], encoding="utf-8-sig")

    if df.empty:
        table = pd.DataFrame(columns=["نام کارشناس", "مبلغ وصول کارتابلی"])
        return {"slot_jdt": slot_jdt, "table": table}

    df = df[df["AAName"].map(_is_eligible_karshenas)].copy()
    df["cartable_paid"] = pd.to_numeric(df["cartable_paid"], errors="coerce").fillna(0)

    grouped = df.groupby("AAName").agg(
        cartable_paid=("cartable_paid", "sum"),
    ).reset_index().rename(columns={"AAName": "نام کارشناس"})

    grouped["مبلغ وصول کارتابلی"] = (grouped["cartable_paid"] * 1_000_000).round().astype(int)
    grouped = grouped[grouped["مبلغ وصول کارتابلی"] > THRESHOLD_TOMAN].copy()
    grouped = grouped.sort_values(by="مبلغ وصول کارتابلی", ascending=False).reset_index(drop=True)

    table = grouped[["نام کارشناس", "مبلغ وصول کارتابلی"]].copy()

    os.makedirs(_OUTPUT_DIR, exist_ok=True)
    slot_label = slot_jdt.strftime("%Y_%m_%d_%H%M")
    output_path = os.path.join(_OUTPUT_DIR, f"{slot_label}.csv")
    table.to_csv(output_path, index=False, encoding="utf-8-sig")

    return {"slot_jdt": slot_jdt, "table": table}
