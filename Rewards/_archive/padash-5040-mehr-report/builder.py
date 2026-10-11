"""
padash-5040-mehr-report/builder.py

Two-phase build, distinguished purely by slot_jdt.hour/minute (see
requirements.py docstring):

  00:00 -> "build" phase: runs padash-karshenasan-5040's real pipeline
    (its own requirements.get_requirements + builder.build), anchored to
    the fixed campaign-end instant (1405/06/31 23:59 - matches that
    reward's own management_image.is_final_slot check exactly, so its
    existing management-report code path fires exactly as it does when the
    real campaign reward reaches its own final slot - nothing duplicated).
    Copies the resulting PNG to this reward's own outputs/ under a FIXED
    filename (not slot-labeled) so the 08:30 phase can find it - the two
    phases run as separate core.reward_runner invocations (different
    threads, no shared memory).
  08:30 -> "send" phase: just points at that fixed-name cached PNG (built
    3.5 hours earlier) - never recomputes, so late data entry after
    midnight can't change the numbers already frozen and reviewed.

If the 00:00 phase was ever missed (catch-up-once skipped it - see
core/scheduling.py), the cached file won't exist yet and render.py simply
sends nothing rather than guessing/recomputing at the wrong instant.
"""

import importlib
import os
import shutil

import jdatetime

_OUTPUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "outputs")
_CACHE_PATH = os.path.join(_OUTPUT_DIR, "final_management_report.png")

# دقیقاً همون FINAL_SLOT که padash-karshenasan-5040/management_image.py
# خودش چک می‌کنه (day=31, hour=23, minute=59) - عمداً اینجا هم هاردکد شده
# چون این پاداش کاملاً مستقل از اون شماره‌گذاری اسلاته، نه بخشی از همون
# schedule.csv.
_CAMPAIGN_END_SLOT = jdatetime.datetime(1405, 6, 31, 23, 59)


def _is_build_phase(slot_jdt):
    return slot_jdt.hour == 0 and slot_jdt.minute == 0


def build(raw_paths, slot_jdt):
    if _is_build_phase(slot_jdt):
        req_mod = importlib.import_module("Rewards.padash-karshenasan-5040.requirements")
        builder_mod = importlib.import_module("Rewards.padash-karshenasan-5040.builder")

        sibling_raw_paths = {}
        for req in req_mod.get_requirements(_CAMPAIGN_END_SLOT):
            downloader_module = importlib.import_module(f"API_Downloader.{req['downloader']}")
            sibling_raw_paths[req["downloader"]] = downloader_module.fetch(
                None, req["period_start"], req["period_end"]
            )

        sibling_report = builder_mod.build(sibling_raw_paths, _CAMPAIGN_END_SLOT)
        image_path = sibling_report.get("management_image_path")

        os.makedirs(_OUTPUT_DIR, exist_ok=True)
        if image_path:
            shutil.copy(image_path, _CACHE_PATH)

        return {"slot_jdt": slot_jdt, "phase": "build"}

    image_path = _CACHE_PATH if os.path.exists(_CACHE_PATH) else None
    return {"slot_jdt": slot_jdt, "phase": "send", "image_path": image_path}
