"""
padash-karshenasan-5040/requirements.py

Reward: رتبه‌بندی/پورسانت پله‌ای کارشناسان 5040 - company 5040 (SP company
code "54"), level کارشناس.
Campaign window: 1405/06/23 14:00 -> end of day 1405/06/31 (see
config/rewards.csv valid_from/valid_to, which is whole-day inclusive; the
14:00 start-of-day-23 precision lives only here, not at the campaign-level
window).

Cumulative from campaign start through the current slot (running totals
over the whole campaign, not a rolling per-slot window) - matches builder.py's
"مبلغ پورسانت بر آوردی تا این لحظه" column, confirmed by the user 2026-09-15:
  - SP.54.SPK window: [CAMPAIGN_START, this slot] - the request itself is
    already scoped to this window (see API_Downloader/SP/54/SPK.py's
    build_json_body), so builder.py never re-filters the raw file by date.

STILL PENDING from the user (do not guess):
  - message text(s) (render.py not built yet - user asked for builder only
    for now)
"""

from core import context as ctx

CAMPAIGN_START = ctx.parse_jalali_date("1405/06/23").replace(hour=14, minute=0, second=0)


def get_requirements(slot_jdt):
    return [
        {
            "downloader": "SP.54.SPK",
            "period_start": CAMPAIGN_START,
            "period_end": slot_jdt,
        },
    ]
