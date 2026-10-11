"""
gozaresh-jame-rotbebandi-5040/requirements.py

Reward: "گزارش هفتگی رتبه‌بندی جامع ( عملکرد )" - company 5040, sent as a PDF
FILE (not an image) to a fixed set of management/report groups - see
render.py's docstring for the recipient list and why it's a file, not a
photo.

Schedule (2026-09-30, user decision): daily except پنج‌شنبه/جمعه
(schedule.csv), at 12:00. period_for_slot is IDENTICAL to the sibling
padash-rotbebandi-karshenasan-5040 reward's own period_for_slot (confirmed
by the user 2026-09-30 - "از 1م هرماه ساعت 00:00 تا همون روزی که ارسال
میشه"), duplicated here rather than imported, per this project's
one-reward-per-folder isolation convention:

    effective_date = slot_jdt - 1 day
    period_start   = 00:00:00 of day 1 of effective_date's (Jalali) month
    period_end     = 23:59:59 of effective_date

SP.54.SPK's per-کارشناس summary already scopes itself to [period_start,
period_end] server-side - builder.py never re-filters the raw file by date.
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
