"""
padash-vosol-bastei-karshenasan-hamkadeh-19mehr/builder.py

Per-package bonus on collected کارتابلی invoices (user 2026-10-11). Prize per
package (تومان), keyed by (main sessions, bonus sessions):
  3 -> 500k, 4 -> 700k, 5 -> 900k, 7+1 -> 1.2M, 8+1 -> 1.4M, 10+2 -> 1.8M,
  11+2 -> 2M, 12+3 -> 2.1M, 14+4 -> 2.5M, 15+5 -> 2.7M
The 2-session package and every package not in this table (e.g. the
WhatsApp packages "5+1جلسه رایگان واتساپی", "3جلسه واتساپی") earn nothing.

"نام پکیج به همراه تعداد" looks like
  "پکیج 5+15 جلسه ای مشاوره روانشناسی 18,920,000 با تعداد - 2,پکیج 4 جلسه ای ..."
The panel writes the bonus first ("1+7" = the 7+1 package), so the pair is
normalised to (larger, smaller). Every package counts separately - quantity
2 = two prizes, two packages in one invoice = both prizes (user 2026-10-11).

An invoice counts only if:
  - "تاریخ وصول" (آنلاین -> تاریخ پرداخت, کارت به کارت -> زمان ثبت اطلاعات
    واریزی) inside 1405/07/19 10:30:00 -> min(slot, 23:59:59)
  - "نوع ثبت فاکتور" == کارتابلی
  - "وضعیت مالی" == تایید شده (HK.FCP already only returns accepted ones);
    the acceptance date itself is not restricted (see requirements.py)
  - not cancelled / not returned
Owner = "ثبت کننده", kept only if it ends with a Latin team suffix (drops
"سایت" and other non-کارشناس owners - same rule as the other همکده rewards)
and is not a test account.
"""

import os
import re

import pandas as pd

PRIZES_TOMAN = {
    (3, 0): 500_000,
    (4, 0): 700_000,
    (5, 0): 900_000,
    (7, 1): 1_200_000,
    (8, 1): 1_400_000,
    (10, 2): 1_800_000,
    (11, 2): 2_000_000,
    (12, 3): 2_100_000,
    (14, 4): 2_500_000,
    (15, 5): 2_700_000,
}

_OWNER_COL = "ثبت کننده"
_PKG_COL = "نام پکیج به همراه تعداد"

_PKG_RE = re.compile(r"پکیج\s*(\d+)\s*(?:\+\s*(\d+))?\s*جلسه\s*ای.*?با\s*تعداد\s*-\s*(\d+)")
_ENGLISH_SUFFIX_RE = re.compile(r"[A-Za-z]\)?\s*$")

_HERE = os.path.dirname(os.path.abspath(__file__))
_OUTPUT_DIR = os.path.join(_HERE, "outputs")

_TS_FMT = "%Y-%m-%d %H:%M:%S"


def package_label(key):
    main, bonus = key
    return f"{main}+{bonus}" if bonus else str(main)


def _packages(text):
    """{(main, bonus): count} of the prize-eligible packages in one invoice."""
    out = {}
    for a, b, qty in _PKG_RE.findall(str(text)):
        a, b = int(a), int(b or 0)
        key = (max(a, b), min(a, b))
        if key in PRIZES_TOMAN:
            out[key] = out.get(key, 0) + int(qty)
    return out


def build(raw_paths, slot_jdt):
    from . import requirements as req

    start = req.CAMPAIGN_START.strftime(_TS_FMT)
    end = req.collection_end_for_slot(slot_jdt).strftime(_TS_FMT)

    df = pd.read_csv(raw_paths["HK.FCP"], encoding="utf-8-sig", dtype=str).fillna("")
    pay_type = df["نوع پرداخت"].str.strip()
    df["تاریخ وصول"] = ""
    df.loc[pay_type == "آنلاین", "تاریخ وصول"] = df["تاریخ پرداخت"].str.strip()
    df.loc[pay_type == "کارت به کارت", "تاریخ وصول"] = df["زمان ثبت اطلاعات واریزی"].str.strip()

    owner = df[_OWNER_COL].str.strip()
    df = df[
        (df["تاریخ وصول"] >= start) & (df["تاریخ وصول"] <= end)
        & (df["نوع ثبت فاکتور"].str.strip() == "کارتابلی")
        & (df["وضعیت مالی"].str.strip() == "تایید شده")
        & (df["وضعیت فاکتور"].str.strip() != "لغو شده")
        & (df.get("فاکتور برگشتی", pd.Series("", index=df.index)).str.strip() != "1")
        & owner.map(lambda n: bool(_ENGLISH_SUFFIX_RE.search(n)))
        & (~owner.str.contains("(تست)", regex=False))
    ].copy()

    rows = []
    for _, inv in df.iterrows():
        for key, qty in _packages(inv[_PKG_COL]).items():
            rows.append({"کارشناس": inv[_OWNER_COL].strip(), "key": key, "qty": qty,
                         "invoice": inv["سریال فاکتور"],
                         "supervisor": inv["سوپروایزران ثبت کننده فاکتور"].strip(),
                         "sarparast": inv["سرپرستان ثبت کننده فاکتور"].strip()})
    items = pd.DataFrame(rows, columns=["کارشناس", "key", "qty", "invoice", "supervisor", "sarparast"])

    people = []
    for name, g in items.groupby("کارشناس"):
        counts = g.groupby("key")["qty"].sum().to_dict()
        prize = sum(PRIZES_TOMAN[k] * q for k, q in counts.items())
        people.append({
            "کارشناس": name,
            "packages": dict(sorted(counts.items())),
            "package_count": int(sum(counts.values())),
            "invoices": int(g["invoice"].nunique()),
            "supervisor": g["supervisor"].mode().iat[0] if g["supervisor"].ne("").any() else "",
            "sarparast": g["sarparast"].mode().iat[0] if g["sarparast"].ne("").any() else "",
            "prize_toman": int(prize),
        })
    table = pd.DataFrame(people, columns=["کارشناس", "packages", "package_count", "invoices",
                                          "supervisor", "sarparast", "prize_toman"])
    table = table.sort_values(["prize_toman", "کارشناس"], ascending=[False, True]).reset_index(drop=True)

    os.makedirs(_OUTPUT_DIR, exist_ok=True)
    out = table.copy()
    out["packages"] = out["packages"].map(
        lambda d: " | ".join(f"{package_label(k)}×{q}" for k, q in d.items()))
    out.to_csv(os.path.join(_OUTPUT_DIR, f"{slot_jdt.strftime('%Y_%m_%d_%H%M')}.csv"),
               index=False, encoding="utf-8-sig")

    package_totals = {key: int(items.loc[items["key"] == key, "qty"].sum()) for key in PRIZES_TOMAN}

    return {
        "slot_jdt": slot_jdt,
        "period_start": req.CAMPAIGN_START,
        "period_end": req.collection_end_for_slot(slot_jdt),
        "package_totals": package_totals,
        "is_final": slot_jdt >= req.CAMPAIGN_END.replace(second=0),
        "table": table,
    }
