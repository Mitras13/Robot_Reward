"""
padash-vosol-bastei-karshenasan-hamkadeh-19mehr/requirements.py

Reward: "پاداش ویژه کارشناسان فروش همکده - یکشنبه ۱۹ مهر" - company همکده
(HK), level کارشناس. One day only: 1405/07/19 10:30 -> 23:59:59 (user
2026-10-11). Basis: وصول فاکتورهای کارتابلی - only the collection time
("تاریخ وصول": آنلاین -> تاریخ پرداخت, کارت به کارت -> زمان ثبت اطلاعات
واریزی) must fall inside the window; registration time is NOT restricted.

Source: HK.FCP (paid + financially accepted invoices, filtered server-side
by the acceptance date). The acceptance date itself is NOT a constraint
(user 2026-10-11: an evening کارت به کارت may only be accepted the next
day) - the download starts at the start of the campaign day (acceptance is
never before collection) and runs up to the slot itself, so the final slot
(1405/07/20 00:05, after CAMPAIGN_END) still picks up invoices collected
inside the window but accepted after 23:59:59.

Slots (user 2026-10-11): 13:00 / 15:00 / 17:00 / 19:00 / 21:00 progress,
final at 1405/07/20 00:05 over the full 10:30 -> 23:59:59 window.
"""

from core import context as ctx

CAMPAIGN_DAY = ctx.parse_jalali_date("1405/07/19")
CAMPAIGN_START = CAMPAIGN_DAY.replace(hour=10, minute=30, second=0)
CAMPAIGN_END = CAMPAIGN_DAY.replace(hour=23, minute=59, second=59)


def collection_end_for_slot(slot_jdt):
    return min(slot_jdt.replace(second=59), CAMPAIGN_END)


def get_requirements(slot_jdt):
    return [
        {
            "downloader": "HK.FCP",
            "period_start": CAMPAIGN_DAY.replace(hour=0, minute=0, second=0),
            "period_end": slot_jdt,
        },
    ]
