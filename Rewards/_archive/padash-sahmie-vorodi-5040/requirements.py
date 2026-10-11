"""
padash-sahmie-vorodi-5040/requirements.py

Reward: "سهمیه تماس‌های ورودی" - company 5040 (SP company code "54"), level
کارشناس. Announcement text (given by the user 2026-09-21): هر کارشناسی که
در شهریورماه بیش از ۳۵۰ میلیون تومان "وصولی کارتابلی" ثبت کند، در مهرماه از
سهمیه‌ی تماس‌های ورودی ماهانه بهره‌مند می‌شود. Single run, confirmed by the
user 2026-09-21: ساعت 08:00 صبح 1 مهر (schedule.csv: month:1,08:00) - NOT
end of شهریور, so the query window below is a FIXED [CAMPAIGN_START,
CAMPAIGN_END] pair rather than [CAMPAIGN_START, slot_jdt] (slot_jdt on the
actual run day is 1 مهر, past the شهریور window this reward measures).

config/rewards.csv valid_from/valid_to for this reward is 1405/06/02 ->
1405/07/01 (not 06/01) specifically so the campaign is NOT active on
1405/06/01 itself - scheduling.day_matches's "month:1" token matches ANY
month's 1st day, so an active window starting on 06/01 would wrongly fire
this once on 06/01 too, before شهریور's data even exists.
"""

from core import context as ctx

CAMPAIGN_START = ctx.parse_jalali_date("1405/06/01")
CAMPAIGN_END = ctx.parse_jalali_date("1405/06/31").replace(hour=23, minute=59, second=59)


def get_requirements(slot_jdt):
    return [
        {
            "downloader": "SP.54.SPK",
            "period_start": CAMPAIGN_START,
            "period_end": CAMPAIGN_END,
        },
    ]
