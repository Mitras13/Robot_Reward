import pandas as pd

from ..downloader_common import download_with_retry
from ..downloader_core import (
    InvalidContentError,
    api_datetime_str,
    build_raw_filename,
    build_raw_path,
    call_api,
    load_token,
)
from core.context import now_jalali

URL = "https://api.5040.me/api/agents/agent-statistic"
METHOD = "GET"
COMPANY_CODE = "54"
REPORT_CODE = "AST"

# Fixed output schema - always present, even on a genuinely empty (zero
# agents/zero activity) result, so a Report_Builder's pd.read_csv never hits
# EmptyDataError on a day/period with no data (review finding AST-01).
COLUMNS = [
    "agent_id", "agent_name", "city_id", "state", "city", "DU24H",
    "total_count", "total_price", "status_key", "status_name",
    "status_count", "status_price",
]


def build_params(period_start, period_end):
    """The real captured request sends both bounds as ONE comma-joined
    `date` param (not two separate start/end params like FCR/VPS) -
    confirmed from a real browser network capture, not guessed."""
    return {
        "filter": 1,
        "date": f"{api_datetime_str(period_start)},{api_datetime_str(period_end)}",
    }


def _flatten(payload):
    """agent-statistic returns nested JSON (agent -> city -> status), not a
    flat table - unlike every other 54/HK endpoint in this project. The
    page's own "دریافت خروجی" button builds its CSV client-side (no separate
    network request), and its exact status->column mapping (e.g. which
    status is "تعویق شده") isn't confirmed from a real response yet - some
    status keys seen in a live capture (e.g. "Submit") don't even appear in
    that button's column list. Rather than guess a mapping here, this keeps
    every (agent, city, status) row intact in long format; the report
    builder decides the final column mapping once that's confirmed with the
    user, per project convention (Report_Builders must not receive raw data
    already opinionated about business meaning it hasn't been told).

    Raises InvalidContentError unless the envelope is explicitly a success:
    `status` must be the boolean True (not truthy - not 1, not "true", not
    missing) AND `statistics` must be present as a dict. A malformed or
    incomplete envelope ({}, {"status": null}, {"status": true} with no
    `statistics` key, etc.) must fail and retry, not silently produce a
    "successful" empty report - a schema change or a truncated server
    response must never look the same as a genuine zero-activity period
    (review finding AST-01, tightened to close the fail-open gap in AST-05:
    only `status is False` was rejected before, so every other malformed
    shape fell through as if it were a valid empty result). A real empty
    result looks like `{"status": true, "statistics": {}}` and is still
    accepted."""
    if payload.get("status") is not True:
        raise InvalidContentError(f"agent-statistic API returned an invalid/unexpected envelope: {payload}")
    if not isinstance(payload.get("statistics"), dict):
        raise InvalidContentError(f"agent-statistic API response is missing a valid 'statistics' object: {payload}")

    rows = []
    for agent_id, agent in payload.get("statistics", {}).items():
        for city_id, city in agent.get("cities", {}).items():
            base = {
                "agent_id": agent_id,
                "agent_name": agent.get("name"),
                "city_id": city_id,
                "state": city.get("state"),
                "city": city.get("city"),
                "DU24H": city.get("DU24H"),
                "total_count": city.get("factors", {}).get("totalCount"),
                "total_price": city.get("factors", {}).get("totalPrice"),
            }
            statuses = city.get("statuses") or {}
            if not statuses:
                rows.append({**base, "status_key": "", "status_name": "", "status_count": 0, "status_price": 0})
                continue
            for status_key, status in statuses.items():
                rows.append({
                    **base,
                    "status_key": status_key,
                    "status_name": status.get("name"),
                    "status_count": status.get("totalCount"),
                    "status_price": status.get("totalPrice"),
                })
    return pd.DataFrame(rows, columns=COLUMNS)


def fetch(context, period_start, period_end):
    """Standard contract every downloader implements. Bearer auth, like
    54.FCR/54.VPS. Response is JSON (agent-statistic), not CSV, so this
    doesn't go through fetch_generic - it flattens to a DataFrame and saves
    that as CSV instead, same end result as every other downloader in the
    project (on-disk file is always CSV, utf-8-sig)."""

    def attempt():
        token = load_token(COMPANY_CODE)
        params = build_params(period_start, period_end)

        download_time = now_jalali()
        response = call_api(URL, METHOD, params, token, auth_mode="bearer")
        df = _flatten(response.json())

        filename = build_raw_filename(COMPANY_CODE, REPORT_CODE, period_start, period_end, download_time)
        save_path = build_raw_path(COMPANY_CODE, REPORT_CODE, filename)
        df.to_csv(save_path, index=False, encoding="utf-8-sig")
        return save_path

    label = f"{REPORT_CODE}_{COMPANY_CODE}"
    return download_with_retry(attempt, max_retries=3, delay_seconds=30, label=label)
