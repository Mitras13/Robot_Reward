"""
padash-supervisor-hamkadeh-goroh1-11-30mehr/requirements.py

Reward: "پاداش ویژه سوپروایزرهای فروش همکده - گروه اول" (teams with 15 or
more baseline کارشناسان) - company همکده (HK), level سوپروایزر.
Campaign window (user 2026-10-03): 1405/07/11 00:00 -> 1405/07/30 23:59:59.

Cumulative: every slot pulls SP.HK.SPK (per-کارشناس smart-panel report,
includes supervisor__name) from campaign start through the slot. The
baseline team roster (who belongs to which supervisor on 11 مهر) is a
separate, frozen snapshot - see builder.py's _load_roster().
"""

from core import context as ctx

CAMPAIGN_START = ctx.parse_jalali_date("1405/07/11").replace(hour=0, minute=0, second=0)
CAMPAIGN_END = ctx.parse_jalali_date("1405/07/30").replace(hour=23, minute=59, second=59)

# baseline roster day (user 2026-10-03: "تعداد کارشناسان مبنا در روز ۱۱ مهر")
ROSTER_START = CAMPAIGN_START
ROSTER_END = ctx.parse_jalali_date("1405/07/11").replace(hour=23, minute=59, second=59)


def period_for_slot(slot_jdt):
    period_end = min(slot_jdt, CAMPAIGN_END)
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
