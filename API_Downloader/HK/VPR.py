from ..downloader_common import download_with_retry
from ..downloader_core import fetch_generic, api_datetime_str

URL = "https://api.hamkadeh.com/api/call-log/exports"
METHOD = "GET"
COMPANY_CODE = "HK"
REPORT_CODE = "VPR"


def build_params(period_start, period_end):
    """Only the parameters specific to THIS report/endpoint."""
    return {
        "start_call_from": api_datetime_str(period_start),
        "start_call_to": api_datetime_str(period_end),
        "location": "factor",
    }


def fetch(context, period_start, period_end):
    """Standard contract every downloader implements."""

    def attempt():
        return fetch_generic(
            url=URL,
            method=METHOD,
            company_code=COMPANY_CODE,
            report_code=REPORT_CODE,
            period_start=period_start,
            period_end=period_end,
            build_params=build_params,
            json_body={},
        )

    label = f"{REPORT_CODE}_{COMPANY_CODE}"
    return download_with_retry(attempt, max_retries=3, delay_seconds=30, label=label)
