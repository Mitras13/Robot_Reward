"""
padash-sarparast-hamkadeh-11-30mehr/requirements.py

Reward: "پاداش ویژه سرپرستان فروش همکده" - company همکده (HK), level سرپرست.
Campaign window (user 2026-10-04): 1405/07/11 00:00 -> 1405/07/30 23:59:59.

Cumulative: every slot pulls HK.FCP (paid + financially accepted invoices,
has the "سرپرستان ثبت کننده فاکتور" column) from campaign start through the
slot. HK.FCP filters server-side by acceptance date; builder.py re-filters
on collection time (user 2026-10-10). The reference window (1405/06/21 ->
1405/07/10) is fixed and frozen in this folder - see builder.py.
"""

from core import context as ctx

CAMPAIGN_START = ctx.parse_jalali_date("1405/07/11").replace(hour=0, minute=0, second=0)
CAMPAIGN_END = ctx.parse_jalali_date("1405/07/30").replace(hour=23, minute=59, second=59)

REFERENCE_START = ctx.parse_jalali_date("1405/06/21").replace(hour=0, minute=0, second=0)
REFERENCE_END = ctx.parse_jalali_date("1405/07/10").replace(hour=23, minute=59, second=59)
# HK.FCP filters on acceptance time; the reference is downloaded up to here so
# invoices PAID by REFERENCE_END but accepted a few days later are included
# (builder.py cuts it back to REFERENCE_END on collection time).
REFERENCE_FETCH_END = ctx.parse_jalali_date("1405/07/15").replace(hour=23, minute=59, second=59)


def period_for_slot(slot_jdt):
    period_end = min(slot_jdt, CAMPAIGN_END)
    if period_end.hour == 23 and period_end.minute == 59:
        period_end = period_end.replace(second=59)
    return CAMPAIGN_START, period_end


def get_requirements(slot_jdt):
    period_start, period_end = period_for_slot(slot_jdt)
    return [
        {
            "downloader": "HK.FCP",
            "period_start": period_start,
            "period_end": period_end,
        },
    ]
