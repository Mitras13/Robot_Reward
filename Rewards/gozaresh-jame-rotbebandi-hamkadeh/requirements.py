"""
gozaresh-jame-rotbebandi-hamkadeh/requirements.py

Sibling of gozaresh-jame-rotbebandi-5040/requirements.py (company همکده
instead of 5040) - identical period logic, see that file's docstring for
the full reasoning.

    effective_date = slot_jdt - 1 day
    period_start   = 00:00:00 of day 1 of effective_date's (Jalali) month
    period_end     = 23:59:59 of effective_date
"""

from core import context as ctx


def period_for_slot(slot_jdt):
    effective_date = ctx.shift_days(slot_jdt, -1)
    period_start = effective_date.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    period_end = effective_date.replace(hour=23, minute=59, second=59, microsecond=0)
    return period_start, period_end


def get_requirements(slot_jdt):
    period_start, period_end = period_for_slot(slot_jdt)
    return [
        {
            "downloader": "SP.HK.SPK",
            "period_start": period_start,
            "period_end": period_end,
        },
    ]
