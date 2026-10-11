from ...downloader_common import download_with_retry
from ...downloader_core import fetch_smart_panel_json, smart_panel_datetime_str

URL = "https://5040-product.5040.me/api/voip/call-log/288"
COMPANY_CODE = "54"
REPORT_CODE = "SPH"  # Support, Per-Hour

# Fixed id assigned by the smart panel to this specific output-generator
# ("ساعتی پشتیبانی") - not a company/queue selector, just how the server
# identifies which saved export config to run. Same mechanism as
# SP/HK/SPH.py's id=278, but 5040's smart panel instance lives on a
# different domain (5040-product.5040.me, not 5040.5040.me) - confirmed
# from a real captured request, not assumed from the HK pattern.
OUTPUT_GENERATOR_ID = "288"


def build_json_body(period_start, period_end):
    return {
        "start": smart_panel_datetime_str(period_start),
        "end": smart_panel_datetime_str(period_end),
        "id": OUTPUT_GENERATOR_ID,
    }


def fetch(context, period_start, period_end):
    """Standard contract every downloader implements."""

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
