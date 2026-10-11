from ..downloader_common import download_with_retry
from ..downloader_core import fetch_generic, api_datetime_str

URL = "https://api.5040.me/api/v1/factor-extraction"
METHOD = "POST"
COMPANY_CODE = "54"
REPORT_CODE = "FCP"


def build_params(period_start, period_end):
    """Only the parameters specific to THIS report/endpoint.

    Same endpoint as 54.FCR (factor-extraction), but scoped to paid invoices
    only via payStatus=paid. ⚠️ Despite sharing the endpoint with 54.FCR,
    the date filter params are DIFFERENT here - startPayAcceptDate/
    endPayAcceptDate (payment-acceptance date), not startInvoiceDate/
    endInvoiceDate - confirmed from an actual captured request.
    """
    return {
        "report": 1,
        "filter": 1,
        "startPayAcceptDate": api_datetime_str(period_start),
        "endPayAcceptDate": api_datetime_str(period_end),
        "payStatus": "paid",
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
            auth_mode="bearer",
            json_body={},
        )

    label = f"{REPORT_CODE}_{COMPANY_CODE}"
    return download_with_retry(attempt, max_retries=3, delay_seconds=30, label=label)
