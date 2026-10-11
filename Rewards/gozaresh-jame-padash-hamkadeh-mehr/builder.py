"""
gozaresh-jame-padash-hamkadeh-mehr/builder.py

Runs the SAME calculation code as the 4 live rewards, so this report can
never disagree with what their people were told:
  padash-zaribvosoli-hamkadeh-11-25mehr        (کارشناسان)
  padash-supervisor-hamkadeh-goroh1-11-30mehr  (سوپروایزر گروه اول)
  padash-supervisor-hamkadeh-goroh2-11-30mehr  (سوپروایزر گروه دوم)
  padash-sarparast-hamkadeh-11-30mehr          (سرپرستان)

Each of those builders writes its slot table to its own outputs/ folder,
which its render.py later reads as "the previous report" for rank-change
lines. To keep this report from touching those files, every builder is
loaded here as a PRIVATE module copy (its own module object, same package
so its relative imports still work) whose _OUTPUT_DIR points into this
reward's own outputs/. The live reward modules are never modified.
"""

import importlib
import importlib.util
import os

_HERE = os.path.dirname(os.path.abspath(__file__))
_REWARDS_DIR = os.path.dirname(_HERE)
_WORK_DIR = os.path.join(_HERE, "outputs", "_tables")

KARSHENAS = "padash-zaribvosoli-hamkadeh-11-25mehr"
GROUP1 = "padash-supervisor-hamkadeh-goroh1-11-30mehr"
GROUP2 = "padash-supervisor-hamkadeh-goroh2-11-30mehr"
SARPARAST = "padash-sarparast-hamkadeh-11-30mehr"


def _private_builder(reward_id):
    package = f"Rewards.{reward_id}"
    importlib.import_module(package)
    spec = importlib.util.spec_from_file_location(
        f"{package}._jame_builder_copy", os.path.join(_REWARDS_DIR, reward_id, "builder.py"),
    )
    module = importlib.util.module_from_spec(spec)
    module.__package__ = package
    spec.loader.exec_module(module)
    module._OUTPUT_DIR = os.path.join(_WORK_DIR, reward_id)
    return module


def _karshenas_spk(raw_paths, slot_jdt):
    """SP.HK.SPK for the کارشناس window - the shared file while that
    campaign is running, its own (11..25 مهر) download after it ended."""
    k_req = importlib.import_module(f"Rewards.{KARSHENAS}.requirements")
    if slot_jdt <= k_req.CAMPAIGN_END:
        return raw_paths["SP.HK.SPK"]
    start, end = k_req.period_for_slot(slot_jdt)
    return importlib.import_module("API_Downloader.SP.HK.SPK").fetch(None, start, end)


def build(raw_paths, slot_jdt):
    from . import requirements as req

    kb = _private_builder(KARSHENAS)
    g1b = _private_builder(GROUP1)
    g2b = _private_builder(GROUP2)
    sb = _private_builder(SARPARAST)

    spk = {"SP.HK.SPK": raw_paths["SP.HK.SPK"]}
    _, period_end = req.period_for_slot(slot_jdt)
    return {
        "slot_jdt": slot_jdt,
        "period_end": period_end,
        "karshenas": kb.build({"SP.HK.SPK": _karshenas_spk(raw_paths, slot_jdt)}, slot_jdt),
        "group1": g1b.build(spk, slot_jdt),
        "group2": g2b.build(spk, slot_jdt),
        "sarparast": sb.build({"HK.FCP": raw_paths["HK.FCP"]}, slot_jdt),
        "modules": {"karshenas": kb, "group1": g1b, "group2": g2b, "sarparast": sb},
    }
