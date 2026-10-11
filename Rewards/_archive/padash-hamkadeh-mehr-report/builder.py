"""
padash-hamkadeh-mehr-report/builder.py

Twin of padash-5040-mehr-report/builder.py - see that file's docstring for
the full two-phase rationale. Drives padash-tamdid-karshenasan-hamkadeh's
own requirements.py/builder.py directly (nothing duplicated).
"""

import importlib
import os
import shutil

import jdatetime

_OUTPUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "outputs")
_CACHE_PATH = os.path.join(_OUTPUT_DIR, "final_management_report.png")

# دقیقاً همون FINAL_SLOT که padash-tamdid-karshenasan-hamkadeh/management_image.py
# خودش چک می‌کنه (day=31, hour=23, minute=59).
_CAMPAIGN_END_SLOT = jdatetime.datetime(1405, 6, 31, 23, 59)


def _is_build_phase(slot_jdt):
    return slot_jdt.hour == 0 and slot_jdt.minute == 0


def build(raw_paths, slot_jdt):
    if _is_build_phase(slot_jdt):
        req_mod = importlib.import_module("Rewards.padash-tamdid-karshenasan-hamkadeh.requirements")
        builder_mod = importlib.import_module("Rewards.padash-tamdid-karshenasan-hamkadeh.builder")

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
