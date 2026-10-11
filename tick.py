"""
tick.py - one tick.

config/rewards.csv is the central index: which rewards exist, their
company/level/enabled flag, and their campaign validity window
(valid_from/valid_to). Everything about HOW a reward computes or sends
lives entirely inside its own `Rewards/{id}/` folder (schedule.csv,
requirements.py, builder.py, render.py) - tick.py and core/reward_runner.py
never change when a reward is added (user decision 1405/06/24).

config/rewards.csv columns:
    id         - matches the Rewards/{id}/ folder name exactly
    name       - Persian display name of the reward
    company    - which company it belongs to (e.g. 5040, همکده)
    level      - who it targets: کارشناس / سوپروایزر / سرپرست / مدیر
    enabled    - 1/0
    valid_from / valid_to - campaign window, Jalali "YYYY/MM/DD", inclusive

Each due reward runs in its OWN thread (core/reward_runner.run_reward) so
one reward's slow download or bug can never delay or crash another's slot -
see core/reward_runner.py's module docstring for the full pipeline and why.
"""

import csv
import logging
import os
import threading

import jdatetime

from core import logging_setup, reward_runner

logging_setup.setup(quiet_console=os.environ.get("ROBOT_REWARD_QUIET_CONSOLE") == "1")
logger = logging.getLogger("tick")

_PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
REWARDS_CONFIG_PATH = os.path.join(_PROJECT_ROOT, "config", "rewards.csv")

REQUIRED_COLUMNS = ["id", "name", "company", "level", "enabled", "valid_from", "valid_to"]


def load_rewards(path=None):
    """
    Reads config/rewards.csv fresh every call - no caching - so an edit
    takes effect on the very next tick without a restart. Returns []
    (logging why) on anything wrong with the file, never raises - a bad
    config file must not crash the process.
    """
    path = path or REWARDS_CONFIG_PATH
    if not os.path.exists(path):
        logger.error("rewards config not found: %s", path)
        return []

    with open(path, encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))

    if rows:
        missing = [c for c in REQUIRED_COLUMNS if c not in rows[0]]
        if missing:
            logger.error("rewards config missing column(s) %s: %s", missing, path)
            return []

    return rows


def is_enabled(row):
    return str(row.get("enabled", "0")).strip() in ("1", "true", "True")


def tick():
    """
    Called every ~2s by main.py's worker thread; standalone via
    `python tick.py` for manual testing.

    Returns the list of currently ACTIVE (enabled=1) reward rows (used by
    the dashboard) - as a side effect, spawns one thread per (reward, slot)
    that is due right now, per core.reward_runner.due_reward_ids().
    """
    now_j = jdatetime.datetime.now()
    rewards = load_rewards()
    active = [r for r in rewards if is_enabled(r)]

    for reward_id, slot in reward_runner.due_reward_ids(active, now_j):
        threading.Thread(
            target=reward_runner.run_reward,
            args=(reward_id, slot, now_j),
            daemon=True,
            name=f"reward-{reward_id}-{slot}",
        ).start()

    return active


if __name__ == "__main__":
    active = tick()
    print(f"{len(active)} active reward(s):")
    for r in active:
        print(f"  - {r['id']} | {r['name']} | {r['company']} | {r['level']}")
