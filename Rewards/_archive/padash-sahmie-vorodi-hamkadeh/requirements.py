"""
padash-sahmie-vorodi-hamkadeh/requirements.py

Reward: "سهمیه تماس‌های ورودی" - company همکده (SP company code "HK"), level
کارشناس. Twin of padash-sahmie-vorodi-5040, same announcement shape (given
by the user 2026-09-21) but company همکده and threshold ۲۵۰ میلیون تومان
(vs. 5040's ۳۵۰ میلیون): هر کارشناسی که در شهریورماه بیش از ۲۵۰ میلیون
تومان "وصولی کارتابلی" ثبت کند، در مهرماه از سهمیه‌ی تماس‌های ورودی ماهانه
بهره‌مند می‌شود. Single run, confirmed by the user 2026-09-21: ساعت 08:00
صبح 1 مهر (schedule.csv: month:1,08:00) - NOT end of شهریور, so the query
window below is a FIXED [CAMPAIGN_START, CAMPAIGN_END] pair rather than
[CAMPAIGN_START, slot_jdt] (slot_jdt on the actual run day is 1 مهر, past
the شهریور window this reward measures).

config/rewards.csv valid_from/valid_to for this reward is 1405/06/02 ->
1405/07/01 (not 06/01) - see the 5040 twin's requirements.py docstring for
why (avoids scheduling.day_matches's "month:1" token also firing this on
1405/06/01).
"""

from core import context as ctx

CAMPAIGN_START = ctx.parse_jalali_date("1405/06/01")
CAMPAIGN_END = ctx.parse_jalali_date("1405/06/31").replace(hour=23, minute=59, second=59)


def get_requirements(slot_jdt):
    return [
        {
            "downloader": "SP.HK.SPK",
            "period_start": CAMPAIGN_START,
            "period_end": CAMPAIGN_END,
        },
    ]
