from ..downloader_common import download_with_retry
from ..downloader_core import fetch_generic, api_datetime_str

URL = "https://api.hamkadeh.com/api/v1.1/factor/index"
METHOD = "GET"
COMPANY_CODE = "HK"
REPORT_CODE = "FCP"


def build_params(period_start, period_end):
    """Same endpoint as HK.FCR (factor/index), but scoped to paid+accepted
    invoices only. ⚠️ Despite sharing the endpoint with HK.FCR, the date
    filter params are DIFFERENT here - start_accept_action_date/
    end_accept_action_date (payment-acceptance date), not start_created_at/
    end_created_at - confirmed from an actual captured request. Same class of
    bug as 54.FCP's startPayAcceptDate/endPayAcceptDate mixup, see
    Report_Builders/KharidMojaddad54.py / CLAUDE.md."""
    return {
        "export_data": 1,
        "start_accept_action_date": api_datetime_str(period_start),
        "end_accept_action_date": api_datetime_str(period_end),
        "status": "paid",
        "receipt_status": "accepted",
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
        )

    label = f"{REPORT_CODE}_{COMPANY_CODE}"
    return download_with_retry(attempt, max_retries=3, delay_seconds=30, label=label)
