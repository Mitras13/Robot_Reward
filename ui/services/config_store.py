"""
Read/write access to config/rewards.csv and config/sender_version.txt for
the settings page (`ui/blueprints/settings.py`) - the one place in the
panel allowed to mutate project config, so validation and atomic-write
safety live in exactly one spot.

No restart is ever needed after a save: tick.load_rewards() already
re-reads config/rewards.csv fresh every tick, and
Senders/payamresan.current_sender_version() already re-reads
config/sender_version.txt on every send call (both pre-existing,
unchanged conventions) - the next tick/next batch simply sees the new
file.
"""

import csv
import io
import os
import threading

import tick as tick_module
from core.context import parse_jalali_date

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
REWARDS_ROOT = os.path.join(_PROJECT_ROOT, "Rewards")
_REWARDS_CSV_PATH = tick_module.REWARDS_CONFIG_PATH
_SENDER_VERSION_PATH = os.path.join(_PROJECT_ROOT, "config", "sender_version.txt")

_write_lock = threading.Lock()


class ConfigValidationError(ValueError):
    pass


def _atomic_write_text(path, text, encoding="utf-8-sig"):
    """Write to a sibling .tmp file then os.replace() over the real path -
    never leaves a half-written config file behind if the process dies
    mid-write. encoding must match whatever the file's own readers expect -
    utf-8-sig for rewards.csv (main.load_rewards() reads it that way), but
    plain utf-8 for sender_version.txt (payamresan.current_sender_version()
    reads it that way - a BOM there would make every value compare unequal
    to "1"/"2" and silently fall back to v1)."""
    tmp_path = path + ".tmp"
    with open(tmp_path, "w", encoding=encoding, newline="") as f:
        f.write(text)
    os.replace(tmp_path, path)


def list_rewards_with_meta():
    """Every config/rewards.csv row, each annotated with folder_exists
    (whether Rewards/{id}/ actually exists on disk) for the settings
    page's warning chip."""
    rows = tick_module.load_rewards()
    for row in rows:
        row["folder_exists"] = os.path.isdir(os.path.join(REWARDS_ROOT, row.get("id", "")))
    return rows


def current_sender_version():
    try:
        with open(_SENDER_VERSION_PATH, encoding="utf-8") as f:
            return f.read().strip()
    except OSError:
        return "1"


def _validate_rows(rows):
    if not rows:
        raise ConfigValidationError("حداقل باید یک ردیف پاداش وجود داشته باشد")

    seen_ids = set()
    for i, row in enumerate(rows, start=1):
        missing = [c for c in tick_module.REQUIRED_COLUMNS if not str(row.get(c, "")).strip() and c != "enabled"]
        # enabled is checked separately below (its valid empty-ish value is "0")
        if missing:
            raise ConfigValidationError(f"ردیف {i}: مقدار {', '.join(missing)} خالی است")

        reward_id = row["id"].strip()
        if reward_id in seen_ids:
            raise ConfigValidationError(f"ردیف {i}: شناسه‌ی «{reward_id}» تکراری است")
        seen_ids.add(reward_id)
        if any(ch in reward_id for ch in ("/", "\\")) or ".." in reward_id:
            raise ConfigValidationError(f"ردیف {i}: شناسه‌ی «{reward_id}» نامعتبر است")

        if str(row.get("enabled", "")).strip() not in ("0", "1"):
            raise ConfigValidationError(f"ردیف {i}: enabled باید 0 یا 1 باشد")

        for field in ("valid_from", "valid_to"):
            try:
                parse_jalali_date(row[field])
            except ValueError:
                raise ConfigValidationError(f"ردیف {i}: تاریخ {field} نامعتبر است ({row[field]!r})")


def save_rewards(rows):
    """rows: [{"id", "name", "company", "level", "enabled", "valid_from",
    "valid_to"}, ...] straight from the settings page's POST body.
    Raises ConfigValidationError (caller turns this into a 400) on any
    problem, without touching the file. Never touches folder_exists -
    that's request-time-only metadata, not a CSV column."""
    _validate_rows(rows)

    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=tick_module.REQUIRED_COLUMNS)
    writer.writeheader()
    for row in rows:
        writer.writerow({c: row[c] for c in tick_module.REQUIRED_COLUMNS})

    with _write_lock:
        _atomic_write_text(_REWARDS_CSV_PATH, buf.getvalue())


def save_sender_version(version):
    version = str(version).strip()
    if version not in ("1", "2"):
        raise ConfigValidationError(f"نسخه‌ی سندر نامعتبر است: {version!r}")
    with _write_lock:
        _atomic_write_text(_SENDER_VERSION_PATH, version, encoding="utf-8")
