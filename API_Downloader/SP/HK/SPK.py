from ...downloader_common import download_with_retry
from ...downloader_core import fetch_smart_panel_json

URL = "https://5040.5040.me/api/report/smart/calculate/1247"
COMPANY_CODE = "HK"
REPORT_CODE = "SPK"  # Smart panel, per-کارشناس Kartabeli calculate report

# Fixed id assigned by the smart panel to this specific output-generator -
# same mechanism as SP.54.SPK's id=1172, but HK's own id (1247) and its own
# host (5040.5040.me, "hamkadeh" credential set) per project-structure's
# HK/54 smart-panel host split - confirmed from a real captured request
# (2026-09-13).
OUTPUT_GENERATOR_ID = "1247"


def build_json_body(period_start, period_end):
    """
    Same body shape as SP.54.SPK.build_json_body - report/smart/calculate/{id}
    wants the period wrapped in a "date" list of one object, with BOTH a
    "start"/"end" (Gregorian, "YYYY-MM-DD HH:MM") and a same-value
    "startHelp"/"endHelp" + "startj"/"endj" (also Gregorian despite the "j"
    suffix, confirmed from the real captured HK request), plus
    "av_date_ls": [] and startTime/EndTime: null.
    """
    start_dt = period_start.togregorian()
    end_dt = period_end.togregorian()
    start_str = start_dt.strftime("%Y-%m-%d %H:%M")
    end_str = end_dt.strftime("%Y-%m-%d %H:%M")
    start_date = start_dt.strftime("%Y-%m-%d")
    end_date = end_dt.strftime("%Y-%m-%d")

    return {
        "av_date_ls": [],
        "date": [
            {
                "start": start_str,
                "startHelp": start_date,
                "startj": start_date,
                "end": end_str,
                "endHelp": end_date,
                "endj": end_date,
                "startTime": None,
                "EndTime": None,
            }
        ],
        "id": OUTPUT_GENERATOR_ID,
    }


def fetch(context, period_start, period_end):
    """Standard contract every downloader implements. Returns the raw
    per-کارشناس panel data as-is (JSON->CSV, see fetch_smart_panel_json) -
    no unit conversion or business logic here; see
    Report_Builders/SahmieShomareVorodiKarshenasanHK.py for how
    cartable_paid/answered_count are interpreted and scaled."""

    def attempt():
        return fetch_smart_panel_json(
            url=URL,
            company_code=COMPANY_CODE,
            report_code=REPORT_CODE,
            period_start=period_start,
            period_end=period_end,
            build_json_body=build_json_body,
        )

    label = f"{REPORT_CODE}_{COMPANY_CODE}"
    return download_with_retry(attempt, max_retries=3, delay_seconds=30, label=label)
