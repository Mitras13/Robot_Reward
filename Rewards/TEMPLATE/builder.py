"""
TEMPLATE/builder.py - turn raw downloaded data into this reward's own
report. This is entirely this reward's business - core/reward_runner.py
never looks inside whatever `report` you return, it just hands it straight
to render.py in this same folder.

Contract: build(raw_paths, slot_jdt) -> report
    raw_paths: {downloader_name: csv_path, ...} - one entry per requirement
        declared in requirements.py, already downloaded and saved to disk.
        Read with pandas.read_csv(path, encoding="utf-8-sig") - every
        downloader saves CSV/parquet-string convention (see project
        convention: every column comes back as a string, convert what you
        actually need with pd.to_numeric/pd.to_datetime yourself).
    slot_jdt: the labeled slot time this run is anchored to.

    `report` can be anything - a DataFrame, a dict of per-person totals, a
    dataclass - whatever render.py in this folder needs to build text.

If this reward has a fixed name list / parameter table / caps (mentioned in
the original project intent), load it here from a file inside this same
folder (e.g. Rewards/{id}/roster.csv, Rewards/{id}/params.csv) - keep it
local to the reward, do not add it to config/ or core/.

Shared helpers - use these instead of copying another reward's private copy
(core/reward_helpers.py):
    collection_time(df, fallback_col=None)  - "تاریخ وصول" of FCP invoices by
        payment type (the 2026-10-10 rule). Decide explicitly what other
        payment types do: None drops them, ACCEPTANCE_COL falls back.
    norm_name(name), to_fa_digits(value)
    render_html_to_png(...), render_html_to_pdf(...)  - for render.py
"""

import pandas as pd


def build(raw_paths, slot_jdt):
    raise NotImplementedError("copy this folder and implement build()")
