"""
gozaresh-jame-padash-zaribvosoli-5040/requirements.py

Comprehensive report (PDF) of padash-zaribvosoli-5040-18-30mehr, user
2026-10-10: every morning at 08:40 (the managers' 08:30 / 08:35 / 08:40
block) from 19 مهر, except Friday 24 مهر, plus the final result on
1 آبان 08:40 (window clamped to 30 مهر 23:59:59). Replaces the old
per-slot manager xlsx of padash-karshenasan-5040.
Same data and window as the reward itself - delegated to its requirements so
the two can never drift apart.
"""

import importlib

SOURCE_REWARD = "padash-zaribvosoli-5040-18-30mehr"

_src = importlib.import_module(f"Rewards.{SOURCE_REWARD}.requirements")
CAMPAIGN_START = _src.CAMPAIGN_START
CAMPAIGN_END = _src.CAMPAIGN_END
period_end_for_slot = _src.period_end_for_slot


def get_requirements(slot_jdt):
    return _src.get_requirements(slot_jdt)
