from ...downloader_common import download_with_retry
from ...downloader_core import fetch_smart_panel_excel, smart_panel_datetime_str

URL = "https://5040-product.5040.me/api/voip/call-log-excel/290"
COMPANY_CODE = "54"
REPORT_CODE = "SPC"  # Support, incoming Calls ("تماس ورودی") - .xlsx response, not JSON

# Fixed id assigned by the smart panel to this specific output-generator -
# same mechanism as SP/54/SPH.py's id=288 and SP/54/SPI.py's id=289.
OUTPUT_GENERATOR_ID = "290"


def build_json_body(period_start, period_end):
    return {
        "start": smart_panel_datetime_str(period_start),
        "end": smart_panel_datetime_str(period_end),
        "id": OUTPUT_GENERATOR_ID,
    }


def fetch(context, period_start, period_end):
    """Standard contract every downloader implements."""

    def attempt():
        return fetch_smart_panel_excel(
            url=URL,
            company_code=COMPANY_CODE,
            report_code=REPORT_CODE,
            period_start=period_start,
            period_end=period_end,
            build_json_body=build_json_body,
        )

    label = f"{REPORT_CODE}_{COMPANY_CODE}"
    return download_with_retry(attempt, max_retries=3, delay_seconds=30, label=label)
