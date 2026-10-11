"""
elan-padash-zaribvosoli-5040-18mehr/requirements.py

One-off announcement (user 2026-10-10): tell every active 5040 کارشناس about
the collection-ratio (ضریب وصولی) ranking contest, 18 -> 30 مهر 1405.
Recipient list = every کارشناس active in the 5040 panel this month
(SP.54.SPK, 1 مهر 00:00 -> slot) - same source as
elan-padash-gloroshen-5040-15mehr.

The list is frozen to recipients_frozen.json on first build (see builder),
so a retry after an interrupted batch is the IDENTICAL batch (same run_id)
and resumes instead of resending - no second download once frozen.
"""

import os

from core import context as ctx

FROZEN_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "recipients_frozen.json")

PERIOD_START = ctx.parse_jalali_date("1405/07/01").replace(hour=0, minute=0, second=0)


def get_requirements(slot_jdt):
    if os.path.exists(FROZEN_PATH):
        return []
    return [{"downloader": "SP.54.SPK", "period_start": PERIOD_START, "period_end": slot_jdt}]
