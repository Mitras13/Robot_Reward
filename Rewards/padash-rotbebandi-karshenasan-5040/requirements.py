"""
padash-rotbebandi-karshenasan-5040/requirements.py

Reward: "گزارش رتبه‌بندی کارشناسان" - company 5040 (SP company code "54"),
level کارشناس. Sibling of padash-rotbebandi-karshenasan-hamkadeh (HK) - same
recurring weekly logic, only the downloader/company differ; see that
folder's requirements.py for the full reasoning behind the effective-date
window below (confirmed by the user 2026-09-20) and why moving to a weekly
schedule 2026-09-22 needed no change to period_for_slot() - only
schedule.csv.
(Renamed ratebandi -> rotbebandi 2026-09-22, user decision - id/folder name
only, no behavior change.)

Recurring report, driven entirely by schedule.csv (شنبه,00:00 - weekly,
changed from daily 2026-09-22) - config/rewards.csv valid_from/valid_to here
only bounds how long this reward folder stays wired up at all (1405/06/29 ->
1405/12/29), NOT the reporting window, which is computed fresh every slot:

    effective_date = slot_jdt - 1 day
    period_start   = 00:00:00 of day 1 of effective_date's (Jalali) month
    period_end     = 23:59:59 of effective_date

SP.54.SPK's per-کارشناس summary already scopes itself to [period_start,
period_end] server-side (see API_Downloader/SP/54/SPK.py build_json_body) -
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
            "downloader": "SP.54.SPK",
            "period_start": period_start,
            "period_end": period_end,
        },
    ]
