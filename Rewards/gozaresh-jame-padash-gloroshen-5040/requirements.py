"""
gozaresh-jame-padash-gloroshen-5040/requirements.py

Comprehensive report (PDF) of padash-gloroshen-5040-15mehr-10aban, user
2026-10-07: once a day at 09:05 (user: offset from the reward's own 09:00
download, avoids HTTP 429) from 16 مهر except Fridays, plus the final at
10 آبان 23:59.
Same data and window as the reward itself - delegated to its requirements so
the two can never drift apart.
"""

import importlib

SOURCE_REWARD = "padash-gloroshen-5040-15mehr-10aban"

_src = importlib.import_module(f"Rewards.{SOURCE_REWARD}.requirements")
CAMPAIGN_START = _src.CAMPAIGN_START
CAMPAIGN_END = _src.CAMPAIGN_END
FINAL_SLOT = _src.FINAL_SLOT
period_end_for_slot = _src.period_end_for_slot


def get_requirements(slot_jdt):
    return _src.get_requirements(slot_jdt)
