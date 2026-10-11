"""
padash-tamdid-karshenasan-hamkadeh/requirements.py

Reward: "طرح ویژه تمدید کارشناسان همکده" - company همکده (HK), level کارشناس.
Campaign window: 1405/06/23 17:00 -> end of day 1405/06/31 (see config/rewards.csv
valid_from/valid_to, which is whole-day inclusive; the 17:00 start-of-day-23
precision lives only here, not in the campaign-level window).

Calculated based on تمدید (renewal), cumulative from campaign start through
the current slot (running total over the whole campaign, not a rolling
per-slot window) - confirmed by the user 2026-09-15:
  - HK.FCP window: [campaign start, this slot]
  - HK.EXT window: [campaign start - LOOKBACK_DAYS, this slot] - EXT needs
    to reach LOOKBACK_DAYS earlier than FCP because builder.py's renewal
    check looks LOOKBACK_DAYS back from each invoice's own تاریخ وصول, and
    the earliest possible تاریخ وصول is the campaign start itself.

STILL PENDING from the user (do not guess):
  - message text(s)
  - real schedule.csv slot times (see schedule.csv in this folder - currently
    a placeholder)
"""

from core import context as ctx

CAMPAIGN_START = ctx.parse_jalali_date("1405/06/23").replace(hour=17, minute=0, second=0)

# See builder.py's renewal-detection rule - an EXT entry counts as "matching"
# a purchase if it's within this many days before the invoice's تاریخ وصول.
LOOKBACK_DAYS = 4


def get_requirements(slot_jdt):
    return [
        {
            "downloader": "HK.EXT",
            "period_start": ctx.shift_days(CAMPAIGN_START, -LOOKBACK_DAYS),
            "period_end": slot_jdt,
        },
        {
            "downloader": "HK.FCP",
            "period_start": CAMPAIGN_START,
            "period_end": slot_jdt,
        },
    ]
