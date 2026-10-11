"""
padash-supervisor-hamkadeh-goroh1-11-30mehr/builder.py

Team ranking for supervisors (rules given by the user 2026-10-03):

Baseline roster (user 2026-10-03) - on 11 مهر itself, every run uses the
کارشناسان listed under each supervisor in THAT run's own SP.HK.SPK output,
and saves that list to roster_1405_07_11.csv (overwriting - so the file
always holds the LAST 11 مهر output). From 12 مهر on, that saved list is the
frozen baseline: later team transfers have no effect, and the SAME baseline
people are used in both numerator and denominator ("جامعه کارشناسان مورد
محاسبه در صورت و مخرج یکسان"). Only if no run at all happened on 11 مهر is
the full 11 مهر day fetched as a fallback.

Group - by baseline team size: GROUP_MIN_SIZE <= size <= GROUP_MAX_SIZE.
  group 1: 15+, group 2: under 15.

Ranking metric - average وصولی کل per baseline کارشناس:
  sum(paid of baseline members, cumulative from 11 مهر) / baseline size.
  paid comes from the panel in میلیون تومان -> converted to تومان.

ضریب وصولی condition - the panel defines paid_coe exactly as
  cartable_paid (وصولی کارتابلی, میلیون تومان) * 1000 / answered_count
(verified on every row of two real SPK files, 2026-10-03), so team ضریب =
sum(cartable_paid) * 1000 / sum(answered_count) over its baseline members.
Compared to the overall ضریب of all supervisors = the panel's company-total
row ("همکده") for the same window (same formula, whole company). A team is eligible only if
its ضریب >= overall * (1 - COE_TOLERANCE_PCT/100). An ineligible team is
dropped from the ranking and the next eligible team takes its place.

Prizes - PRIZES_MILLION_TOMAN[rank-1] for the top len(PRIZES) eligible teams.
Ties on average are broken by higher team ضریب, then by supervisor name.
"""

import importlib
import os
import time

import pandas as pd

GROUP_LABEL = "گروه اول"
GROUP_DESC = "تیم‌های ۱۵ نفر و بیشتر"
GROUP_MIN_SIZE = 15
GROUP_MAX_SIZE = 10_000

# rank 1..14, میلیون تومان - total 170
PRIZES_MILLION_TOMAN = [40, 28, 20, 16, 12, 10, 9, 8, 7, 6, 5, 4, 3, 2]

COE_TOLERANCE_PCT = 6

MONEY_TO_TOMAN = 1_000_000

_HERE = os.path.dirname(os.path.abspath(__file__))
_OUTPUT_DIR = os.path.join(_HERE, "outputs")
_ROSTER_PATH = os.path.join(_HERE, "roster_1405_07_11.csv")
# Manual baseline (user 2026-10-03): the user's own export of کارشناسان with
# their supervisor; base_count = how many times each supervisor's name
# repeats in it. When this file exists it overrides the SPK-derived roster.
_BASELINE_PATH = os.path.join(_HERE, "baseline_counts.csv")
_COMPANY_TOTAL_ROW_NAME = "همکده"
_NUM_COLS = ["paid", "cartable_paid", "paid_coe", "answered_count"]


def prize_for_rank(rank):
    if rank is None or rank > len(PRIZES_MILLION_TOMAN):
        return 0
    return PRIZES_MILLION_TOMAN[rank - 1]


def _read_spk(path):
    # Both supervisor groups run at the same minute and SP.HK.SPK names its
    # file by the second - one reward can read the file while the other is
    # still rewriting it (EmptyDataError, 1405/07/11 18:00). Re-read briefly.
    for attempt in range(6):
        try:
            df = pd.read_csv(path, encoding="utf-8-sig")
            break
        except (pd.errors.EmptyDataError, pd.errors.ParserError):
            if attempt == 5:
                raise
            time.sleep(3)
    for col in _NUM_COLS:
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0.0)
    df["AAName"] = df["AAName"].astype(str).str.strip()
    df["supervisor__name"] = df["supervisor__name"].fillna("").astype(str).str.strip()
    return df


def _roster_from(df):
    r = df[(df["AAName"] != _COMPANY_TOTAL_ROW_NAME) & (df["AAName"] != "")]
    r = r[(r["supervisor__name"] != "") & (r["supervisor__name"] != "0")]
    return r[["AAName", "supervisor__name"]].drop_duplicates("AAName").rename(
        columns={"AAName": "کارشناس", "supervisor__name": "supervisor"}
    )


def _load_roster(cumulative_df, slot_jdt, req):
    """(roster DataFrame [کارشناس, supervisor], is_final) - see module docstring."""
    if slot_jdt <= req.ROSTER_END:
        roster = _roster_from(cumulative_df)
        roster.to_csv(_ROSTER_PATH, index=False, encoding="utf-8-sig")
        return roster, False
    if os.path.exists(_ROSTER_PATH):
        return pd.read_csv(_ROSTER_PATH, encoding="utf-8-sig"), True
    spk = importlib.import_module("API_Downloader.SP.HK.SPK")
    path = spk.fetch(None, req.ROSTER_START, req.ROSTER_END)
    roster = _roster_from(_read_spk(path))
    roster.to_csv(_ROSTER_PATH, index=False, encoding="utf-8-sig")
    return roster, True


def _norm(name):
    return " ".join(str(name).split())


def _teams_from_baseline_counts(df):
    """Manual-baseline mode (matches the user's manual workbook): base_count
    from baseline_counts.csv; وصولی/ضریب summed over every SPK row whose
    supervisor__name is that supervisor (company row excluded)."""
    base = pd.read_csv(_BASELINE_PATH, encoding="utf-8-sig")
    base["supervisor"] = base["supervisor"].map(_norm)
    base = base[(base["base_count"] >= GROUP_MIN_SIZE) & (base["base_count"] <= GROUP_MAX_SIZE)]
    rows = df[df["AAName"] != _COMPANY_TOTAL_ROW_NAME].assign(supervisor=df["supervisor__name"].map(_norm))
    sums = rows.groupby("supervisor").agg(
        paid_million=("paid", "sum"),
        cartable_million=("cartable_paid", "sum"),
        answered=("answered_count", "sum"),
    ).reset_index()
    teams = base[["supervisor", "base_count"]].merge(sums, on="supervisor", how="left")
    return teams.fillna({"paid_million": 0.0, "cartable_million": 0.0, "answered": 0.0})


def build(raw_paths, slot_jdt):
    from . import requirements as req

    df = _read_spk(raw_paths["SP.HK.SPK"])

    company = df[df["AAName"] == _COMPANY_TOTAL_ROW_NAME]
    overall_coe = float(company["paid_coe"].iloc[0]) if len(company) else 0.0
    min_coe = overall_coe * (1 - COE_TOLERANCE_PCT / 100)

    if os.path.exists(_BASELINE_PATH):
        teams = _teams_from_baseline_counts(df)
        roster_final = True
    else:
        teams, roster_final = _teams_from_roster(df, slot_jdt, req)

    teams["paid_toman"] = (teams["paid_million"] * MONEY_TO_TOMAN).round().astype("int64")
    teams["avg_toman"] = (teams["paid_toman"] / teams["base_count"]).round().astype("int64")
    teams["team_coe"] = teams.apply(
        lambda r: r["cartable_million"] * 1000 / r["answered"] if r["answered"] > 0 else 0.0, axis=1
    )
    teams["coe_vs_overall_pct"] = (
        (teams["team_coe"] / overall_coe - 1) * 100 if overall_coe > 0 else 0.0
    )
    teams["eligible"] = teams["team_coe"] >= min_coe

    teams = teams.sort_values(
        ["eligible", "avg_toman", "team_coe", "supervisor"],
        ascending=[False, False, False, True], kind="mergesort",
    ).reset_index(drop=True)
    n_eligible = int(teams["eligible"].sum())
    teams["rank"] = [i + 1 if i < n_eligible else None for i in range(len(teams))]
    teams["prize_million"] = teams["rank"].apply(lambda r: prize_for_rank(int(r)) if pd.notna(r) else 0)
    teams = teams.drop(columns=["cartable_million", "answered", "paid_million"])

    os.makedirs(_OUTPUT_DIR, exist_ok=True)
    slot_label = slot_jdt.strftime("%Y_%m_%d_%H%M")
    teams.to_csv(os.path.join(_OUTPUT_DIR, f"{slot_label}.csv"), index=False, encoding="utf-8-sig")

    return {
        "slot_jdt": slot_jdt,
        "teams": teams,
        "overall_coe": overall_coe,
        "min_coe": min_coe,
        "roster_final": roster_final,
    }


def _teams_from_roster(df, slot_jdt, req):
    """SPK-roster mode (no baseline_counts.csv): see module docstring."""
    roster, roster_final = _load_roster(df, slot_jdt, req)
    sizes = roster.groupby("supervisor").size()
    group_sups = sizes[(sizes >= GROUP_MIN_SIZE) & (sizes <= GROUP_MAX_SIZE)].index
    members = roster[roster["supervisor"].isin(group_sups)].merge(
        df[["AAName"] + _NUM_COLS].rename(columns={"AAName": "کارشناس"}),
        on="کارشناس", how="left",
    ).fillna({c: 0.0 for c in _NUM_COLS})

    teams = members.groupby("supervisor").agg(
        base_count=("کارشناس", "size"),
        paid_million=("paid", "sum"),
        cartable_million=("cartable_paid", "sum"),
        answered=("answered_count", "sum"),
    ).reset_index()
    return teams, roster_final
