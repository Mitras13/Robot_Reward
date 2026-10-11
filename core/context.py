import datetime
import jdatetime

# ---------------------------------------------------------------------------
# Jalali is the primary time representation used throughout this project -
# for computation, not just for display/logs. Gregorian only appears at the
# very last moment, when a downloader must hand a date to an external API
# that requires it (see API_Downloader/downloader_core.py: api_datetime_str).
#
# Ported from Robot_Analytics/context.py. Keep the two in sync conceptually;
# this project adds parse_jalali_date() and days_between(), which the reward
# campaign window logic in core/scheduling.py needs.
# ---------------------------------------------------------------------------


def now_jalali():
    """Current time as a Jalali datetime - the starting point for every tick."""
    return jdatetime.datetime.now()


def start_of_day(jdt):
    return jdt.replace(hour=0, minute=0, second=0, microsecond=0)


def end_of_day(jdt):
    return jdt.replace(hour=23, minute=59, second=59, microsecond=0)


def shift_days(jdt, n):
    """Move n days forward (or backward if n is negative)."""
    return jdt + datetime.timedelta(days=n)


def start_of_week(jdt):
    """Start of week (Saturday) at 00:00:00.
    jdatetime's weekday(): Saturday=0 ... Friday=6, so this is a direct offset."""
    return start_of_day(shift_days(jdt, -jdt.weekday()))


def start_of_month(jdt):
    """Start of the current Jalali month at 00:00:00."""
    return jdt.replace(day=1, hour=0, minute=0, second=0, microsecond=0)


def parse_jalali_date(text):
    """
    Parse a Jalali date written in config as "1405/07/01" (or "1405-07-01")
    into a jdatetime.datetime at 00:00:00.

    Used for campaign valid_from / valid_to. Raises ValueError on anything
    malformed - a campaign with an unreadable window must fail loudly at load
    time, never be silently treated as "always active".
    """
    cleaned = (text or "").strip().replace("-", "/")
    if not cleaned:
        raise ValueError("empty Jalali date")
    parts = cleaned.split("/")
    if len(parts) != 3:
        raise ValueError(f"bad Jalali date: {text!r} (expected YYYY/MM/DD)")
    year, month, day = (int(p) for p in parts)
    return jdatetime.datetime(year, month, day, 0, 0, 0)


def days_between(from_jdt, to_jdt):
    """
    Whole days from from_jdt to to_jdt, counted on day boundaries so the time
    of day cannot shift the answer. Same day -> 0, tomorrow -> 1.
    """
    a = start_of_day(from_jdt).togregorian().date()
    b = start_of_day(to_jdt).togregorian().date()
    return (b - a).days


# build_context() removed (1405/06/24, user decision): each reward folder
# now builds its own period/context locally using the helpers above - there
# is no shared "context row" shape anymore. If a reward needs a run_key or
# similar identity string, it builds it itself from its own reward_id + slot.
