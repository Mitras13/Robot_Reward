from ..downloader_common import download_with_retry
from ..downloader_core import fetch_generic, api_datetime_str

URL = "https://api.5040.me/api/v1/factor-extraction"
METHOD = "POST"
COMPANY_CODE = "54"
REPORT_CODE = "FCPD"


def build_params(period_start, period_end):
    """Only the parameters specific to THIS report/endpoint.

    Same endpoint + same paid-only filter as 54.FCP, but scoped further to
    delivered-to-customer invoices only via factorStatuses[]=Delivered -
    the new report builder that consumes this downloader only works with
    delivered factors, and this cuts a more focused dataset at the source
    instead of filtering it out client-side. Confirmed from an actual
    captured request:
    report=1&filter=1&startPayAcceptDate=...&endPayAcceptDate=...&payStatus=paid&factorStatuses[]=Delivered
    """
    return {
        "report": 1,
        "filter": 1,
        "startPayAcceptDate": api_datetime_str(period_start),
        "endPayAcceptDate": api_datetime_str(period_end),
        "payStatus": "paid",
        "factorStatuses[]": "Delivered",
    }


def fetch(context, period_start, period_end):
    """Standard contract every downloader implements. Bearer auth, like 54.FCP.

    period_start/period_end are expected to span from the start of the
    (Jalali) month to the report's period end - the cumulative window is
    the calling Report's responsibility (its own self-contained period
    computation), not this downloader's.
    """

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
