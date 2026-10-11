"""
Campaign scheduling: a validity window (valid_from/valid_to columns of
config/rewards.csv) plus a send pattern (each reward's own
Rewards/{id}/schedule.csv, loaded by core/reward_runner.load_schedule),
instead of the sibling project's eternal explicit rows.

Ported unchanged from Robot_Analytics/main.py: catch-up-once semantics
(only the most recent unmarked past slot runs; older missed ones are
recorded as skipped, never replayed), zero-padded "HH:MM" string comparison,
and slot_to_jdatetime() anchoring a reward's period to the labeled slot
rather than wall-clock execution time.

Every function here is pure (no file I/O, no clock reads other than the
now_j passed in) so it can be tested without touching the filesystem.
"""

import datetime
import re

from core.errors import RewardConfigError
from core import context as ctx

WEEKDAY_FA = ["شنبه", "یکشنبه", "دوشنبه", "سه‌شنبه", "چهارشنبه", "پنج‌شنبه", "جمعه"]

_TIME_RE = re.compile(r"^\d{2}:\d{2}$")
_EVERY_RE = re.compile(r"^every:(\d+)(h|m)@(\d{2}:\d{2})-(\d{2}:\d{2})$")


# (load_campaigns()/load_schedule() for the old config/campaigns.csv +
# config/schedule.csv layout were removed 1405/07/19 - unused since the
# per-reward-folder rewrite; this module stays file-I/O free.)

def is_enabled(campaign):
    return str(campaign.get("enabled", "1")).strip() in ("1", "true", "True")


def is_campaign_active(campaign, now_j):
    """
    True when today's date falls inside [valid_from, valid_to] (both
    inclusive) and the campaign is enabled. Uses whole-day comparison so the
    time of day never matters - a campaign is active all day on its last day.
    """
    if not is_enabled(campaign):
        return False
    valid_from = ctx.parse_jalali_date(campaign["valid_from"])
    valid_to = ctx.parse_jalali_date(campaign["valid_to"])
    today = ctx.start_of_day(now_j)
    return ctx.start_of_day(valid_from) <= today <= ctx.start_of_day(valid_to)


# ---------------------------------------------------------------------------
# "days" field: weekday name, "month:N", "last:N", "first:N", or a wildcard
# meaning every day, "|"-separated, any-match. last:N / first:N are relative
# to the CAMPAIGN's own validity window, not the calendar - e.g. "last:3"
# means the final 3 days of THIS campaign's run, whatever its valid_to is.
# ---------------------------------------------------------------------------

_ALL_DAYS_TOKENS = ("all", "*")
_ALL_DAYS_FA = "همه"  # همه


def _single_day_matches(day_entry, now_j, campaign):
    entry = day_entry.strip()
    if entry == _ALL_DAYS_FA or entry in _ALL_DAYS_TOKENS:
        return True
    if entry.startswith("month:"):
        return now_j.day == int(entry.split(":", 1)[1])
    if entry.startswith("last:"):
        n = int(entry.split(":", 1)[1])
        valid_to = ctx.parse_jalali_date(campaign["valid_to"])
        days_left = ctx.days_between(now_j, valid_to)
        return 0 <= days_left < n
    if entry.startswith("first:"):
        n = int(entry.split(":", 1)[1])
        valid_from = ctx.parse_jalali_date(campaign["valid_from"])
        days_in = ctx.days_between(valid_from, now_j)
        return 0 <= days_in < n
    return entry == WEEKDAY_FA[now_j.weekday()]


def day_matches(days_field, now_j, campaign):
    entries = [d for d in days_field.split("|") if d.strip()]
    if not entries:
        raise RewardConfigError(f"empty 'days' field for reward '{campaign.get('reward_id')}'")
    return any(_single_day_matches(d, now_j, campaign) for d in entries)


# ---------------------------------------------------------------------------
# "times" field: "09:00|13:00|17:00" and/or "every:<N>h@HH:MM-HH:MM" /
# "every:<N>m@HH:MM-HH:MM", "|"-separated, unioned.
# ---------------------------------------------------------------------------

def _expand_every(token):
    m = _EVERY_RE.match(token)
    if not m:
        raise RewardConfigError(f"bad time pattern: {token!r} (expected every:<N>h|m@HH:MM-HH:MM)")
    amount, unit, start_s, end_s = m.groups()
    step = datetime.timedelta(hours=int(amount)) if unit == "h" else datetime.timedelta(minutes=int(amount))
    if step.total_seconds() <= 0:
        raise RewardConfigError(f"non-positive interval in time pattern: {token!r}")

    anchor = datetime.date(2000, 1, 1)
    start_h, start_m = (int(p) for p in start_s.split(":"))
    end_h, end_m = (int(p) for p in end_s.split(":"))
    cursor = datetime.datetime.combine(anchor, datetime.time(start_h, start_m))
    end = datetime.datetime.combine(anchor, datetime.time(end_h, end_m))
    if cursor > end:
        raise RewardConfigError(f"time pattern start is after end: {token!r}")

    times = []
    while cursor <= end:
        times.append(cursor.strftime("%H:%M"))
        cursor += step
    return times


def expand_times(times_field):
    tokens = [t.strip() for t in times_field.split("|") if t.strip()]
    if not tokens:
        raise RewardConfigError("empty 'times' field")
    times = set()
    for token in tokens:
        if token.startswith("every:"):
            times.update(_expand_every(token))
        elif _TIME_RE.match(token):
            times.add(token)
        else:
            raise RewardConfigError(f"bad time token: {token!r}")
    return sorted(times)


def slots_for_day(campaign, schedule_rows, now_j):
    """Every "HH:MM" slot that applies to this campaign today, sorted, deduped."""
    reward_id = campaign["reward_id"]
    times = set()
    for row in schedule_rows:
        if row["reward_id"] != reward_id:
            continue
        if not day_matches(row["days"], now_j, campaign):
            continue
        times.update(expand_times(row["times"]))
    return sorted(times)


# ---------------------------------------------------------------------------
# catch-up-once due-slot detection - unchanged semantics from the sibling
# project's main.due_slot(), just fed by slots_for_day() instead of a single
# schedule.csv row.
# ---------------------------------------------------------------------------

def due_slot_and_missed(campaign, schedule_rows, now_j, already_run_slots):
    """
    already_run_slots: set of "HH:MM" strings already attempted TODAY for
    this reward_id (any outcome - running/done/skipped all count, see
    core/slot_log.py).

    Returns (due_slot_or_None, [missed_slot, ...]). The caller is expected to
    record every missed slot as "skipped" - they must never be replayed.
    """
    times = slots_for_day(campaign, schedule_rows, now_j)
    if not times:
        return None, []
    now_hm = now_j.strftime("%H:%M")
    passed = sorted((t for t in times if t <= now_hm), reverse=True)
    unmarked = [t for t in passed if t not in already_run_slots]
    if not unmarked:
        return None, []
    return unmarked[0], unmarked[1:]


def slot_to_jdatetime(now_j, slot):
    """
    Anchors a reward's computation to the LABELED slot time, not the actual
    (possibly late) wall-clock moment the tick runs. See module docstring.
    """
    hour, minute = (int(p) for p in slot.split(":"))
    return now_j.replace(hour=hour, minute=minute, second=0, microsecond=0)


def upcoming_slots(campaigns, schedule_rows, now_j, window_minutes=120):
    """
    For the dashboard's "next N minutes" panel: every (reward_id, slot) with
    slot in (now, now+window], across all active campaigns, today only.
    """
    now_hm = now_j.strftime("%H:%M")
    limit = now_j + datetime.timedelta(minutes=window_minutes)
    limit_hm = "24:00" if limit.day != now_j.day else limit.strftime("%H:%M")
    out = []
    for campaign in campaigns:
        if not is_campaign_active(campaign, now_j):
            continue
        for slot in slots_for_day(campaign, schedule_rows, now_j):
            if now_hm < slot <= limit_hm:
                out.append((campaign["reward_id"], slot))
    return sorted(out, key=lambda pair: pair[1])
