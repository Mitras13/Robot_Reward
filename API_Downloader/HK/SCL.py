from ..downloader_common import download_with_retry
from ..downloader_core import fetch_generic, api_datetime_str

URL = "https://api.hamkadeh.com/api/accounting/call-log/index"
METHOD = "POST"
COMPANY_CODE = "HK"
REPORT_CODE = "SCL"


def build_params(period_start, period_end):
    """Only the parameters specific to THIS report/endpoint."""
    return {
        "export_data": 1,
        "call_type[]": 4,
        "start_at": api_datetime_str(period_start),
        "end_at": api_datetime_str(period_end),
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
        )

    label = f"{REPORT_CODE}_{COMPANY_CODE}"
    return download_with_retry(attempt, max_retries=3, delay_seconds=30, label=label)
