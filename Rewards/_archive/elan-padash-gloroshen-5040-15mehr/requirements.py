"""
elan-padash-gloroshen-5040-15mehr/requirements.py

One-off announcement (user 2026-10-07): tell every 5040 کارشناس that the
Glorsion anti-dark-spot reward (padash-gloroshen-5040-15mehr-10aban) is
running. Recipient list = every کارشناس active in the 5040 panel this month
(SP.54.SPK, 1 مهر 00:00 -> slot) - user-chosen source. Single slot on 15 مهر.
"""

import os

from core import context as ctx

# The 18:56 send was cut off by an app restart at 18:59 (181/1208 sent). To
# resume rather than resend, the retry must be the IDENTICAL batch (same
# contacts, same order -> same run_id 59615ea8baff, whose runlog skips
# everyone already sent). So the 18:56 recipient list is frozen in
# recipients_frozen.json and nothing is downloaded again.
FROZEN_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "recipients_frozen.json")

PERIOD_START = ctx.parse_jalali_date("1405/07/01").replace(hour=0, minute=0, second=0)


def get_requirements(slot_jdt):
    if os.path.exists(FROZEN_PATH):
        return []
    return [{"downloader": "SP.54.SPK", "period_start": PERIOD_START, "period_end": slot_jdt}]
