"""
padash-ghahve-sashe-5040-13mehr/requirements.py

Reward: "پاداش ویژه قهوه لاغری حاوی اینولین ساشه‌ای" - company 5040 (code
"54"), level کارشناس. One day only: 1405/07/13, 09:00 -> 15:00 (user
2026-10-05). Basis: ثبت و وصول کارتابلی - an invoice counts only if BOTH its
registration time ("تاریخ ثبت") AND its payment-acceptance time ("تاریخ وضعیت
مالی") fall inside 09:00-15:00 on 13 مهر, and "نوع ثبت فاکتور" is کارتابلی.

Source: 54.FCP (paid invoices, filtered server-side by payment-acceptance
date - verified against a real export: its window bounds match "تاریخ وضعیت
مالی", not "تاریخ پرداخت"/"تاریخ ثبت اطلاعات پرداختی"). The registration-
time and کارتابلی filters are applied in builder.py.

Slots 11:00 / 13:00 / 14:00 (progress) and 15:00 (final), user 2026-10-05.
"""

from core import context as ctx

CAMPAIGN_DAY = ctx.parse_jalali_date("1405/07/13")
CAMPAIGN_START = CAMPAIGN_DAY.replace(hour=9, minute=0, second=0)
CAMPAIGN_END = CAMPAIGN_DAY.replace(hour=15, minute=0, second=0)


def period_end_for_slot(slot_jdt):
    return min(slot_jdt, CAMPAIGN_END)


def get_requirements(slot_jdt):
    return [
        {
            "downloader": "54.FCP",
            "period_start": CAMPAIGN_START,
            "period_end": period_end_for_slot(slot_jdt),
        },
    ]
