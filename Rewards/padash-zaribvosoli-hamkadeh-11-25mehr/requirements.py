"""
padash-zaribvosoli-hamkadeh-11-25mehr/requirements.py

Reward: "طرح رقابت ویژه ضریب وصولی کارشناسان همکده" - company همکده (HK),
level کارشناس. Campaign window (user 2026-10-03): 1405/07/11 00:00 ->
1405/07/25 23:59:59.

Cumulative: every slot reports ضریب وصولی (paid_coe) from campaign start
through the slot itself, via SP.HK.SPK (same per-کارشناس smart-panel report
the weekly رتبه‌بندی reward uses - already scoped server-side to the period,
so builder.py never re-filters by date).
"""

from core import context as ctx

CAMPAIGN_START = ctx.parse_jalali_date("1405/07/11").replace(hour=0, minute=0, second=0)
CAMPAIGN_END = ctx.parse_jalali_date("1405/07/25").replace(hour=23, minute=59, second=59)


def period_for_slot(slot_jdt):
    period_end = min(slot_jdt, CAMPAIGN_END)
    # the final 23:59 slot covers the whole last day (through 23:59:59)
    if period_end.hour == 23 and period_end.minute == 59:
        period_end = period_end.replace(second=59)
    return CAMPAIGN_START, period_end


def get_requirements(slot_jdt):
    period_start, period_end = period_for_slot(slot_jdt)
    return [
        {
            "downloader": "SP.HK.SPK",
            "period_start": period_start,
            "period_end": period_end,
        },
    ]
