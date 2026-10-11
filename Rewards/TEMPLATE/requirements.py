"""
TEMPLATE/requirements.py - what to download for one slot.

This folder is never run by anything (no "TEMPLATE" row exists in
config/rewards.csv) - copy this whole folder to Rewards/{your-reward-id}/
and fill in the three files + schedule.csv to build a real reward.

Contract: get_requirements(slot_jdt) -> list[dict]
    Each dict: {"downloader": "<dotted API_Downloader path>",
                "period_start": jdatetime.datetime,
                "period_end":   jdatetime.datetime}

    "downloader" is a dotted path under API_Downloader/, e.g. "HK.SCL" for
    API_Downloader/HK/SCL.py, or "SP.54.SPK" for API_Downloader/SP/54/SPK.py.
    Every downloader module exposes fetch(context, period_start, period_end)
    - core/reward_runner.py calls it directly; context is unused by every
    existing downloader today, always passed as None.

    slot_jdt is the LABELED slot time (see core/scheduling.slot_to_jdatetime)
    - anchor your period to this, never to jdatetime.datetime.now(), so a
    late-running tick still produces a reward matching its labeled slot.

Example - "give me the last 24 hours, ending at this slot":

    from core import context as ctx

    def get_requirements(slot_jdt):
        period_end = slot_jdt
        period_start = ctx.shift_days(slot_jdt, -1)
        return [{
            "downloader": "HK.SCL",
            "period_start": period_start,
            "period_end": period_end,
        }]

A reward needing more than one source just returns more than one dict -
core/reward_runner.py downloads each one and hands builder.build() a
{downloader_name: raw_csv_path} dict with one entry per requirement.
"""


def get_requirements(slot_jdt):
    raise NotImplementedError("copy this folder and implement get_requirements()")
