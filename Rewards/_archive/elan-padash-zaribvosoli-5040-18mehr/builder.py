"""
elan-padash-zaribvosoli-5040-18mehr/builder.py

Recipient list: unique "AAName" from SP.54.SPK (same panel-name convention
as the 5040 reward messages' contact), test accounts ("تست") dropped.
Frozen to FROZEN_PATH on first build so a resumed batch is identical.
"""

import json
import os

import pandas as pd

from .requirements import FROZEN_PATH


def build(raw_paths, slot_jdt):
    if os.path.exists(FROZEN_PATH):
        with open(FROZEN_PATH, encoding="utf-8") as f:
            return {"slot_jdt": slot_jdt, "recipients": json.load(f)}
    df = pd.read_csv(raw_paths["SP.54.SPK"], encoding="utf-8-sig", dtype=str).fillna("")
    names = df["AAName"].str.strip()
    names = names[(names != "") & (~names.str.contains("تست", regex=False))]
    recipients = sorted(set(names))
    with open(FROZEN_PATH, "w", encoding="utf-8") as f:
        json.dump(recipients, f, ensure_ascii=False, indent=0)
    return {"slot_jdt": slot_jdt, "recipients": recipients}
