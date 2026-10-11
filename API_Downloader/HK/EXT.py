from ..downloader_common import download_with_retry
from ..downloader_core import fetch_generic, api_datetime_str

URL = "https://api.hamkadeh.com/api/entry/extract-numbers-new"
METHOD = "POST"
COMPANY_CODE = "HK"
REPORT_CODE = "EXT"


def build_params(period_start, period_end):
    return {}


def build_json_body(period_start, period_end):
    """This endpoint takes its period in the JSON body, not query params -
    ported from the legacy تمدیدی/HK.EXT.py reference script."""
    return {
        "product_id": 3,
        "reference": ["landing", "sms"],
        "entry_date_start": api_datetime_str(period_start),
        "entry_date_end": api_datetime_str(period_end),
    }


def fetch(context, period_start, period_end):
    """Standard contract every downloader implements. Cookie auth, like HK.FCR."""

    def attempt():
        return fetch_generic(
            url=URL,
            method=METHOD,
            company_code=COMPANY_CODE,
            report_code=REPORT_CODE,
            period_start=period_start,
            period_end=period_end,
            build_params=build_params,
            build_json_body=build_json_body,
        )

    label = f"{REPORT_CODE}_{COMPANY_CODE}"
    return download_with_retry(attempt, max_retries=3, delay_seconds=30, label=label)
