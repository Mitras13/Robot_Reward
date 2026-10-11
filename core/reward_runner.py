"""
Runs one reward folder's full pipeline (context -> download -> build ->
render), independently of every other reward. This is the generic engine -
adding a reward means adding a `Rewards/{id}/` folder, never touching this
file (user decision 1405/06/24).

Each due reward runs in its OWN thread (see main.tick()), so one reward's
slow download or bug can never delay or crash another reward's slot. The
rendered output is handed to Senders.sender_thread.submit() - NOT sent
directly - because the sender's underlying engine (a single Playwright
browser session, see Senders/send_message.py) may only ever be driven from
one specific thread; a dedicated thread there drains a shared queue instead.

Reward folder contract (`Rewards/{reward_id}/`):
    schedule.csv    - columns: days,times (see core/scheduling.py for the
                       mini-language). No reward_id column - the folder
                       itself is the scope.
    requirements.py - get_requirements(slot_jdt) -> [
                           {"downloader": "HK.SCL", "period_start": jdt, "period_end": jdt},
                           ...
                       ]
                       downloader is a dotted API_Downloader path.
    builder.py       - build(raw_paths, slot_jdt) -> report
                       raw_paths: {downloader_name: csv_path, ...}, one
                       entry per requirement. `report` is this reward's own
                       business - the runner never looks inside it.
    render.py        - render(report, reward_id, slot) -> list[Senders.message.OutboundMessage]

See Rewards/TEMPLATE/ for a fully-commented starting point.
"""

import csv
import importlib
import logging
import os

from core import scheduling, slot_log, live_state
from core.errors import RewardConfigError
from Senders import sender_thread

logger = logging.getLogger("core.reward_runner")

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REWARDS_ROOT = os.path.join(_PROJECT_ROOT, "Rewards")


def _write_message_audit(reward_id, slot_jdt, messages):
    """Persists every OutboundMessage's full 7 fields (see Senders/message.py)
    to Rewards/{reward_id}/outputs/messages_{slot label}.csv, right after
    render() produces them - before sender_thread.submit() hands them off,
    which only keeps contact/image/caption (see sender_thread._to_rendered)
    and discards reward_id/slot/panel_user_id/chat_user_id forever. Pure
    audit trail: nothing reads this file today (the sender still gets the
    in-memory list unchanged, right below); this only exists so those 4
    fields aren't lost irrecoverably if the process crashes before/during
    sending. Naming mirrors builder.py's own outputs/{slot label}.csv
    convention, with a "messages_" prefix so the two never collide."""
    if not messages:
        return
    output_dir = os.path.join(REWARDS_ROOT, reward_id, "outputs")
    os.makedirs(output_dir, exist_ok=True)
    slot_label = slot_jdt.strftime("%Y_%m_%d_%H%M")
    path = os.path.join(output_dir, f"messages_{slot_label}.csv")
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["reward_id", "slot", "panel_user_id", "chat_user_id", "contact", "text", "image"])
        for m in messages:
            writer.writerow([m.reward_id, m.slot, m.panel_user_id, m.chat_user_id, m.contact, m.text, m.image])


def load_schedule(reward_id):
    """Renamed from _load_schedule (1405/06/26) - now also called by
    ui/services/dashboard_state.py to build the dashboard's "upcoming slots" list across
    all active rewards, not just internally by due_reward_ids() below."""
    path = os.path.join(REWARDS_ROOT, reward_id, "schedule.csv")
    if not os.path.exists(path):
        raise RewardConfigError(f"schedule.csv not found for reward '{reward_id}' (expected {path})")
    with open(path, encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))
    for row in rows:
        row["reward_id"] = reward_id  # core.scheduling filters rows by this key
    return rows


def due_reward_ids(reward_rows, now_j):
    """
    reward_rows: active (enabled=1) rows from config/rewards.csv - each
    needs "id", "valid_from", "valid_to".

    Returns [(reward_id, slot), ...] due right now. Every slot that was
    missed (catch-up-once) is recorded as "skipped" here, never replayed.
    A reward with a missing/broken schedule.csv is logged loudly and
    skipped for this tick - never crashes the loop.
    """
    already_run = slot_log.load_today(now_j)
    due = []
    for row in reward_rows:
        reward_id = row["id"]
        campaign = {**row, "reward_id": reward_id}
        try:
            if not scheduling.is_campaign_active(campaign, now_j):
                continue
            schedule_rows = load_schedule(reward_id)
            slot, missed = scheduling.due_slot_and_missed(
                campaign, schedule_rows, now_j, already_run.get(reward_id, set())
            )
        except RewardConfigError as e:
            logger.error("'%s': %s", reward_id, e)
            continue

        for missed_slot in missed:
            slot_log.record(reward_id, missed_slot, now_j, "skipped", "missed - catch-up-once")

        if slot:
            due.append((reward_id, slot))
    return due


def run_reward(reward_id, slot, now_j):
    """
    Runs reward_id's full pipeline for `slot`. Must never raise - a bug in
    one reward's folder must never take down the tick loop or any other
    reward's thread (call this inside its own threading.Thread, see
    main.tick()).
    """
    slot_jdt = scheduling.slot_to_jdatetime(now_j, slot)
    slot_log.record(reward_id, slot, now_j, "running")
    live_state.start_reward(reward_id)
    logger.info("'%s' slot %s: starting", reward_id, slot)

    try:
        requirements_mod = importlib.import_module(f"Rewards.{reward_id}.requirements")
        builder_mod = importlib.import_module(f"Rewards.{reward_id}.builder")
        render_mod = importlib.import_module(f"Rewards.{reward_id}.render")

        requirements = requirements_mod.get_requirements(slot_jdt)

        raw_paths = {}
        for req in requirements:
            downloader_name = req["downloader"]
            live_state.start_download(downloader_name, reward_id)
            try:
                downloader_module = importlib.import_module(f"API_Downloader.{downloader_name}")
                raw_paths[downloader_name] = downloader_module.fetch(
                    None, req["period_start"], req["period_end"]
                )
            finally:
                live_state.finish_download(downloader_name)

        report = builder_mod.build(raw_paths, slot_jdt)
        messages = render_mod.render(report, reward_id, slot)
        _write_message_audit(reward_id, slot_jdt, messages)

    except Exception as e:
        logger.exception("'%s' slot %s: failed", reward_id, slot)
        slot_log.record(reward_id, slot, now_j, "failed", f"{type(e).__name__}: {e}")
        return
    finally:
        live_state.finish_reward(reward_id)

    slot_log.record(reward_id, slot, now_j, "done", f"{len(messages)} message(s)")
    logger.info("'%s' slot %s: done, %d message(s) queued for sending", reward_id, slot, len(messages))
    sender_thread.submit(messages)
