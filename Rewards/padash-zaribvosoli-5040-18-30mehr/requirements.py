"""
padash-zaribvosoli-5040-18-30mehr/requirements.py

Reward: رقابت افزایش ضریب وصولی کارشناسان 5040 - an exact repeat of
padash-karshenasan-5040 (23 -> 31 شهریور: same ranking, same 7 commission
tiers, same message), user 2026-10-10. Announced to every 5040 کارشناس the
same day by elan-padash-zaribvosoli-5040-18mehr.

Campaign window: 1405/07/18 00:00 -> 1405/07/30 23:59:59, cumulative from
campaign start through the current slot (SP.54.SPK's request is already
scoped to this window, so builder.py never re-filters by date).

Slots (user 2026-10-10, chosen to avoid every other reward's slot):
10:00 / 14:00 / 18:30 daily (Friday 24 مهر: 14:00 only), + 21:00 from 25 مهر,
+ 23:59 final on 30 مهر. No per-slot manager messages (no xlsx to شیرازی/
کاظمی) and no management image - user 2026-10-10: managers get the 08:40
comprehensive report; management images come later for all rewards.
"""

from core import context as ctx

CAMPAIGN_START = ctx.parse_jalali_date("1405/07/18").replace(hour=0, minute=0, second=0)
CAMPAIGN_END = ctx.parse_jalali_date("1405/07/30").replace(hour=23, minute=59, second=59)


def period_end_for_slot(slot_jdt):
    period_end = min(slot_jdt, CAMPAIGN_END)
    if period_end.hour == 23 and period_end.minute == 59:
        period_end = period_end.replace(second=59)
    return period_end


def get_requirements(slot_jdt):
    return [
        {
            "downloader": "SP.54.SPK",
            "period_start": CAMPAIGN_START,
            "period_end": period_end_for_slot(slot_jdt),
        },
    ]
