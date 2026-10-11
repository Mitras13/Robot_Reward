from ..downloader_common import download_with_retry
from ..downloader_core import fetch_generic_excel, api_datetime_str

URL = "https://api.5040.me/api/call/incoming-calls"
METHOD = "GET"
COMPANY_CODE = "54"
REPORT_CODE = "INCALL"


def build_params(period_start, period_end):
    """Only the parameters specific to THIS report/endpoint - captured from
    a real request (see docs), report=1 is a fixed value the endpoint expects."""
    return {
        "report": 1,
        "startDate": api_datetime_str(period_start),
        "endDate": api_datetime_str(period_end),
    }


def fetch(context, period_start, period_end):
    """Standard contract every downloader implements.

    Bearer auth (token54.txt), like 54.FCR/54.VPR - but GET with query
    params, and the response is an actual .xlsx file, not raw CSV, so this
    goes through fetch_generic_excel instead of fetch_generic.
    """

    def attempt():
        return fetch_generic_excel(
            url=URL,
            method=METHOD,
            company_code=COMPANY_CODE,
            report_code=REPORT_CODE,
            period_start=period_start,
            period_end=period_end,
            build_params=build_params,
            auth_mode="bearer",
        )

    label = f"{REPORT_CODE}_{COMPANY_CODE}"
    return download_with_retry(attempt, max_retries=3, delay_seconds=30, label=label)
