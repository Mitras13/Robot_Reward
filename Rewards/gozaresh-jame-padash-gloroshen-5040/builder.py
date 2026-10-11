"""
gozaresh-jame-padash-gloroshen-5040/builder.py

Runs the SAME builder as padash-gloroshen-5040-15mehr-10aban, so this report
can never disagree with what the کارشناسان were told. The builder is loaded
as a PRIVATE module copy whose _OUTPUT_DIR points into this reward's own
outputs/ (same pattern as gozaresh-jame-padash-hamkadeh-mehr) - the live
reward's per-slot CSVs, which its render reads for rank-change lines, are
never touched.
"""

import importlib
import importlib.util
import os

from .requirements import SOURCE_REWARD

_HERE = os.path.dirname(os.path.abspath(__file__))
_REWARDS_DIR = os.path.dirname(_HERE)
_WORK_DIR = os.path.join(_HERE, "outputs", "_tables")


def _private_builder():
    package = f"Rewards.{SOURCE_REWARD}"
    importlib.import_module(package)
    spec = importlib.util.spec_from_file_location(
        f"{package}._jame_builder_copy", os.path.join(_REWARDS_DIR, SOURCE_REWARD, "builder.py"),
    )
    module = importlib.util.module_from_spec(spec)
    module.__package__ = package
    spec.loader.exec_module(module)
    module._OUTPUT_DIR = _WORK_DIR
    return module


def build(raw_paths, slot_jdt):
    builder = _private_builder()
    report = builder.build(raw_paths, slot_jdt)
    report["tiers"] = builder.TIERS
    return report
