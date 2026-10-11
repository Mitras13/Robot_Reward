"""
padash-sarparast-hamkadeh-11-30mehr/builder.py

Growth race between the 6 همکده سرپرستان (user 2026-10-04: "فقط 6 سرپرست
همکده"; 5040's سرپرستان are NOT part of this reward).

Money: HK.FCP "مبلغ فاکتور" is in ریال -> /1e7 = میلیون تومان (matches the
user's manual workbook, sheet "پنل", to the unit). Owner = the invoice's
"سرپرستان ثبت کننده فاکتور"; time = the invoice's COLLECTION time by
payment type (user 2026-10-10, applies to every reward): آنلاین -> "تاریخ
پرداخت", کارت به کارت -> "زمان ثبت اطلاعات واریزی". The acceptance time
("زمان بررسی اطلاعات واریزی", what HK.FCP filters on server-side) is NOT a
limit - finance may accept in a later window; it is only the fallback for
any other payment type. Both windows are filtered on collection time here.

Growth formula (user 2026-10-04, replaces the earlier weekday-average
method): compare the current window with the SAME number of days - down to
the same clock time - taken from the start of the reference window:

  elapsed   = slot - 1405/07/11 00:00
  previous  = وصولی from 1405/06/21 00:00 to 1405/06/21 00:00 + elapsed
  growth    = (current - previous) / previous

Both windows start on a Saturday (21 شهریور and 11 مهر), so the compared
days are also the same weekdays; the reference has 21 days, enough for the
whole 20-day campaign.
Ranking: highest growth first; when nobody grows, the smallest drop ranks
higher (same ordering). Ties: higher actual وصولی, then name. Prizes for
ranks 1..5.

The reference HK.FCP export is frozen in this folder so every slot compares
against the same data; it is fetched once if missing. Since HK.FCP filters
on acceptance time, it is downloaded over a wider acceptance window
(REFERENCE_START -> REFERENCE_FETCH_END) and then cut to collection time
REFERENCE_START -> REFERENCE_END, so invoices paid on the last reference
days but accepted later are not lost (reference_fcp_1405_06_21_to_07_15.csv,
replaces the earlier acceptance-time file reference_fcp_1405_06_21_to_07_10.csv).
"""

import importlib
import os

import pandas as pd

PRIZES_MILLION_TOMAN = [80, 60, 40, 20, 10]

MONEY_TO_MILLION = 10_000_000  # ریال -> میلیون تومان

_HERE = os.path.dirname(os.path.abspath(__file__))
_OUTPUT_DIR = os.path.join(_HERE, "outputs")
_REFERENCE_PATH = os.path.join(_HERE, "reference_fcp_1405_06_21_to_07_15.csv")

_OWNER_COL = "سرپرستان ثبت کننده فاکتور"
_ACCEPT_COL = "زمان بررسی اطلاعات واریزی"
_AMOUNT_COL = "مبلغ فاکتور"


def prize_for_rank(rank):
    if rank is None or rank > len(PRIZES_MILLION_TOMAN):
        return 0
    return PRIZES_MILLION_TOMAN[rank - 1]


def _norm(name):
    return " ".join(str(name).split())


def _collection_time(df):
    kind = df["نوع پرداخت"].astype(str).str.strip()
    out = df[_ACCEPT_COL].astype(str)
    out = out.mask(kind == "آنلاین", df["تاریخ پرداخت"].astype(str))
    return out.mask(kind == "کارت به کارت", df["زمان ثبت اطلاعات واریزی"].astype(str))


def _load_fcp(path):
    df = pd.read_csv(path, encoding="utf-8-sig")
    out = pd.DataFrame({
        "sarparast": df[_OWNER_COL],
        "ts": _collection_time(df).str.strip().str.replace("/", "-", regex=False),
        "amount": pd.to_numeric(df[_AMOUNT_COL], errors="coerce").fillna(0.0) / MONEY_TO_MILLION,
    })
    out = out[out["sarparast"].notna()].copy()
    out["sarparast"] = out["sarparast"].map(_norm)
    out["date"] = out["ts"].str[:10]
    return out


def _reference(req):
    if not os.path.exists(_REFERENCE_PATH):
        fcp = importlib.import_module("API_Downloader.HK.FCP")
        path = fcp.fetch(None, req.REFERENCE_START, req.REFERENCE_FETCH_END)
        pd.read_csv(path, encoding="utf-8-sig").to_csv(_REFERENCE_PATH, index=False, encoding="utf-8-sig")
    ref = _load_fcp(_REFERENCE_PATH)
    return ref[_in_window(ref, req.REFERENCE_START, req.REFERENCE_END)]


def _in_window(fcp, start, end):
    fmt = "%Y-%m-%d %H:%M:%S"
    return (fcp["ts"] >= start.strftime(fmt)) & (fcp["ts"] <= end.strftime(fmt))


def _expected(ref, req, slot_jdt):
    """({sarparast: previous-window میلیون تومان}, cutoff) - the reference
    from its start through the same elapsed time as the current window."""
    _, period_end = req.period_for_slot(slot_jdt)
    cutoff = req.REFERENCE_START + (period_end - req.CAMPAIGN_START)
    cutoff_str = cutoff.strftime("%Y-%m-%d %H:%M:%S")
    previous = ref[ref["ts"] <= cutoff_str].groupby("sarparast")["amount"].sum()
    return {s: float(previous.get(s, 0.0)) for s in sorted(ref["sarparast"].unique())}, cutoff

def build(raw_paths, slot_jdt):
    from . import requirements as req

    ref = _reference(req)
    cur = _load_fcp(raw_paths["HK.FCP"])
    cur = cur[_in_window(cur, *req.period_for_slot(slot_jdt))]
    expected, reference_cutoff = _expected(ref, req, slot_jdt)
    actual = cur.groupby("sarparast")["amount"].sum()

    teams = pd.DataFrame({
        "sarparast": list(expected),
        "reference_total_million": [float(ref.loc[ref["sarparast"] == s, "amount"].sum()) for s in expected],
        "expected_million": [expected[s] for s in expected],
        "actual_million": [float(actual.get(s, 0.0)) for s in expected],
    })
    teams["growth_pct"] = teams.apply(
        lambda r: (r["actual_million"] / r["expected_million"] - 1) * 100 if r["expected_million"] > 0 else 0.0,
        axis=1,
    )
    teams = teams.sort_values(
        ["growth_pct", "actual_million", "sarparast"], ascending=[False, False, True], kind="mergesort",
    ).reset_index(drop=True)
    teams["rank"] = range(1, len(teams) + 1)
    teams["prize_million"] = teams["rank"].map(prize_for_rank)

    total_expected = teams["expected_million"].sum()
    overall_growth_pct = (teams["actual_million"].sum() / total_expected - 1) * 100 if total_expected else 0.0

    os.makedirs(_OUTPUT_DIR, exist_ok=True)
    teams.to_csv(os.path.join(_OUTPUT_DIR, f"{slot_jdt.strftime('%Y_%m_%d_%H%M')}.csv"),
                 index=False, encoding="utf-8-sig")

    return {
        "slot_jdt": slot_jdt,
        "teams": teams,
        "overall_growth_pct": overall_growth_pct,
        "reference_cutoff": reference_cutoff,
    }
