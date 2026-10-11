from ..downloader_common import download_with_retry
from ..downloader_core import fetch_generic, api_datetime_str

URL = "https://api.5040.me/api/v1/extraction"
METHOD = "POST"
COMPANY_CODE = "54"
REPORT_CODE = "EXT"


def build_params(period_start, period_end):
    return {}


def build_json_body(period_start, period_end):
    """Optimized query per the user's own real captured request - instead of
    the legacy EXT_54 script's approach (resolve every product code to
    include via products_54.json, which doesn't exist in this project),
    this uses reverseProducts+withoutProducts to EXCLUDE just the one listed
    product, which the user confirmed is the lighter/faster query. All other
    fields are copied from that captured request unchanged, only the two
    date fields are computed dynamically."""
    return {
        "mobile": None,
        "clientMobileId": None,
        "products": ["668e32ef345cfb0325061dd3"],
        "withoutProducts": 1,
        "reverseProducts": 1,
        "agencies": [],
        "references": ["Landing", "Sms"],
        "startEntryDate": api_datetime_str(period_start),
        "endEntryDate": api_datetime_str(period_end),
        "numberStatuses": [],
        "callStatuses": [],
        "justDeletedEntries": False,
        "containDeletedEntries": True,
        "minCallNumber": None,
        "maxCallNumber": None,
        "minSuccessCallNumber": None,
        "maxSuccessCallNumber": None,
        "factorSerial": None,
        "factorStatuses": [],
        "withoutFactorEntries": False,
    }


def fetch(context, period_start, period_end):
    """Standard contract every downloader implements. Bearer auth, like 54.FCR."""

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
            auth_mode="bearer",
        )

    label = f"{REPORT_CODE}_{COMPANY_CODE}"
    return download_with_retry(attempt, max_retries=3, delay_seconds=30, label=label)
