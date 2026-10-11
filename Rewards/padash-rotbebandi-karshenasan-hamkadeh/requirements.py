"""
padash-rotbebandi-karshenasan-hamkadeh/requirements.py

Reward: "گزارش رتبه‌بندی کارشناسان" - company همکده (HK), level کارشناس.
(Renamed ratebandi -> rotbebandi 2026-09-22, user decision - id/folder name
only, no behavior change.)
Recurring MONTHLY report (not a fixed campaign like the tamdid/karshenasan-
5040 rewards) - config/rewards.csv valid_from/valid_to here only bounds how
long this reward folder stays wired up at all (confirmed by the user
2026-09-20: از 1405/06/29 تا 1405/12/29), NOT the per-month reporting window,
which is computed fresh every slot below.

Runs weekly, Saturdays at 00:00 (see schedule.csv, days=شنبه - changed from
daily 2026-09-22, user decision). Because 00:00 is the START of a new day,
the window reported at that moment must cover through the day that JUST
ended (the Friday just finished, not the new Saturday) - confirmed by the
user 2026-09-20 with the month-boundary example (00:00 of 1 مهر -> reports
all of شهریور, from 00:00 1 شهریور to 23:59:59 آخرین روز شهریور):

    effective_date = slot_jdt - 1 day
    period_start   = 00:00:00 of day 1 of effective_date's (Jalali) month
    period_end     = 23:59:59 of effective_date

This same period_for_slot() - unchanged since it only ever ran daily before
2026-09-22 - already produces exactly the weekly behavior the user described
2026-09-22 without any code change: period_start stays pinned to day 1 of
the month every Saturday (cumulative within-month report), and once a
Saturday's "yesterday" (effective_date) rolls into a new month, period_start
automatically follows it too - which is what naturally produces a
full-month closing report on the Saturday right after a month's last Friday,
and a fresh small report the Saturday after that. Nothing here needed to
change for the move to weekly; only schedule.csv did.

SP.HK.SPK's per-کارشناس summary already scopes itself to [period_start,
period_end] server-side (see API_Downloader/SP/HK/SPK.py build_json_body) -
builder.py never re-filters the raw file by date.
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
