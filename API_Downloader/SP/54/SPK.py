from ...downloader_common import download_with_retry
from ...downloader_core import fetch_smart_panel_json

URL = "https://5040-product.5040.me/api/report/smart/calculate/1172"
COMPANY_CODE = "54"
REPORT_CODE = "SPK"  # Smart panel, per-کارشناس Kartabeli calculate report

# Fixed id assigned by the smart panel to this specific output-generator -
# same mechanism as SP/54/SPH.py's id=288, but a completely different
# request-body shape (see build_json_body) - confirmed from a real captured
# request (2026-09-13), not assumed from the SPH/SPI pattern. Gives a
# per-کارشناس SUMMARY table directly (answered_count, CPC, ...), unlike
# 54.VPS's raw per-call rows.
OUTPUT_GENERATOR_ID = "1172"

# Full column list of this endpoint's per-کارشناس response row, given
# directly by the user (2026-09-15) so every Rewards/{id}/builder.py reading
# this downloader's CSV can pick the right column without re-asking. Money
# columns (paid, cartable_paid, manual_paid, registered_factor, ...) follow
# the same میلیون تومان convention already confirmed for cartable_paid in
# SahmieShomareVorodiKarshenasan54 (Robot_Analytics) - multiply by
# 1,000,000 for a real تومان figure; not independently re-verified per
# column here, only cartable_paid was.
#   AAName                              کارشناس
#   supervisor__name                    سوپروایزر
#   CPC                                 قیمت هر تماس
#   answered_count                      تعداد پاسخ داد
#   answered_percent                    درصد پاسخ داد
#   bought_percent_cartable             درصد خرید کارتابلی
#   bought_percent_total                درصد خرید کل
#   call_duration                       مدت مکالمه
#   calls_count                         تعداد تماس
#   cartable_paid                       وصولی کارتابلی
#   cartable_registered_factor          ثبت کارتابلی
#   entries_count                       تعداد شماره دریافتی
#   manual_paid                         مبلغ وصولی دستی
#   manual_registered_factor            مبلغ ثبت دستی
#   money_coe                           ضریب پولی
#   number_cartable_paid                تعداد وصولی کارتابلی
#   number_cartable_registered_factor   تعداد فاکتور ثبت شده کارتابلی
#   number_manual_paid                  تعداد ثبت وصول کارتابلی
#   number_manual_registered_factor     تعداد ثبت دستی
#   number_paid                         تعداد وصولی کل
#   number_registered_factor            تعداد ثبت کلی
#   paid                                وصولی کل
#   paid_coe                            ضریب وصولی
#   paid_percent                        درصد وصولی
#   past_registered_paid                وصولی با ثبت گذشته
#   registered_factor                   مبلغ ثبت کلی
#   registered_paid                     ثبت و وصول


def build_json_body(period_start, period_end):
    """
    ⚠️ Different shape from SPH/SPI/SPC's {"start","end","id"} -
    report/smart/calculate/{id} wants the period wrapped in a "date" list of
    one object, with BOTH a "start"/"end" (Gregorian, "YYYY-MM-DD HH:MM") and
    a same-value "startHelp"/"endHelp" + "startj"/"endj" (also Gregorian in
    the real captured request, despite the "j" suffix - not Jalali, copied
    exactly as observed rather than assumed), plus "av_date_ls": [] and
    startTime/EndTime: null. Do not simplify this shape without re-capturing
    a real request - every field was present in the one actually seen working.
    """
    start_dt = period_start.togregorian()
    end_dt = period_end.togregorian()
    start_str = start_dt.strftime("%Y-%m-%d %H:%M")
    end_str = end_dt.strftime("%Y-%m-%d %H:%M")
    start_date = start_dt.strftime("%Y-%m-%d")
    end_date = end_dt.strftime("%Y-%m-%d")

    return {
        "av_date_ls": [],
        "date": [
            {
                "start": start_str,
                "startHelp": start_date,
                "startj": start_date,
                "end": end_str,
                "endHelp": end_date,
                "endj": end_date,
                "startTime": None,
                "EndTime": None,
            }
        ],
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
