"""
elan-padash-gloroshen-5040-15mehr/builder.py

Recipient list: unique "AAName" from SP.54.SPK (same panel-name convention
as the 5040 reward messages' contact), test accounts ("تست") dropped.
"""

import json
import os

import pandas as pd

from .requirements import FROZEN_PATH


def build(raw_paths, slot_jdt):
    if os.path.exists(FROZEN_PATH):  # resume of the interrupted 18:56 batch
        with open(FROZEN_PATH, encoding="utf-8") as f:
            return {"slot_jdt": slot_jdt, "recipients": json.load(f)}
    df = pd.read_csv(raw_paths["SP.54.SPK"], encoding="utf-8-sig", dtype=str).fillna("")
    names = df["AAName"].str.strip()
    names = names[(names != "") & (~names.str.contains("تست", regex=False))]
    return {"slot_jdt": slot_jdt, "recipients": sorted(set(names))}
