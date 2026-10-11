"""
gozaresh-jame-padash-hamkadeh-mehr/requirements.py

Daily comprehensive report of the 4 همکده Mehr rewards, sent only to
عرفان زمانی (مدیر ارشد فروش) - user 2026-10-04: today 17:00, then every day
09:00. Moved to 08:30 on 2026-10-07 (user request) to stop clustering with
the other three 09:00 hamkadeh slots (padash-zaribvosoli-hamkadeh,
padash-supervisor-hamkadeh-goroh1/2), whose simultaneous API calls are the
likely cause of the one-off HTTP 429 on 1405/07/15's 09:00 run.

Same raw data the 4 rewards use, cumulative from 1405/07/11 00:00 to the
slot (clamped to the end of the longest campaign, 1405/07/30 23:59:59):
  - SP.HK.SPK  -> کارشناسان + both سوپروایزر groups
  - HK.FCP     -> سرپرستان
The کارشناس campaign ends earlier (1405/07/25); builder.py fetches its own
window for it once the slot is past that date.
"""

from core import context as ctx

CAMPAIGN_START = ctx.parse_jalali_date("1405/07/11").replace(hour=0, minute=0, second=0)
CAMPAIGN_END = ctx.parse_jalali_date("1405/07/30").replace(hour=23, minute=59, second=59)


def period_for_slot(slot_jdt):
    period_end = min(slot_jdt, CAMPAIGN_END)
    if period_end.hour == 23 and period_end.minute == 59:
        period_end = period_end.replace(second=59)
    return CAMPAIGN_START, period_end


def get_requirements(slot_jdt):
    period_start, period_end = period_for_slot(slot_jdt)
    return [
        {"downloader": "SP.HK.SPK", "period_start": period_start, "period_end": period_end},
        {"downloader": "HK.FCP", "period_start": period_start, "period_end": period_end},
    ]
