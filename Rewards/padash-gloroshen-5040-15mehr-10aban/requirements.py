"""
padash-gloroshen-5040-15mehr-10aban/requirements.py

Reward: "پاداش ویژه کارشناسان فروش 5040 - ضد لک گلورشن" - company 5040
(code "54"), level کارشناس. Campaign 1405/07/15 00:00:00 -> 1405/08/10
23:59:59 (user 2026-10-07). Basis: number of کارتابلی invoices containing the
Glorsion anti-dark-spot serum whose COLLECTION time falls in the window -
registration date does not matter (user). Collection time = payment time by
payment type, never the financial-approval time (user 2026-10-10; see
builder.py).

Source: 54.FCP (paid invoices, filtered server-side by financial-approval
date "تاریخ وضعیت مالی"). Approval always comes after payment, so a window
starting at the campaign start already holds every invoice paid inside it;
one paid before a slot but approved later is picked up by the next slot.
Cumulative from campaign start to the slot, clamped to the campaign end.

Slots (schedule.csv, user 2026-10-07): 15 مهر 19:00; then every day
09/12/15/18 except Fridays (17/24 مهر, 1/8 آبان - user: no sends on جمعه);
9 and 10 آبان also 21:00; 10 آبان 23:59 = final.
"""

from core import context as ctx

CAMPAIGN_START = ctx.parse_jalali_date("1405/07/15").replace(hour=0, minute=0, second=0)
CAMPAIGN_END = ctx.parse_jalali_date("1405/08/10").replace(hour=23, minute=59, second=59)
FINAL_SLOT = CAMPAIGN_END.replace(second=0)


def period_end_for_slot(slot_jdt):
    # the 23:59 final slot covers the full last minute (-> 23:59:59)
    if slot_jdt >= FINAL_SLOT:
        return CAMPAIGN_END
    return min(slot_jdt, CAMPAIGN_END)


def get_requirements(slot_jdt):
    return [
        {
            "downloader": "54.FCP",
            "period_start": CAMPAIGN_START,
            "period_end": period_end_for_slot(slot_jdt),
        },
    ]
