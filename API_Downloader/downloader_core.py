import io
import os
import pandas as pd
import requests

from core.context import now_jalali
# Canonical definitions live in core/errors.py (moved there 1405/07/19 to
# break the core <-> API_Downloader import cycle); re-exported here so every
# existing `from ..downloader_core import AuthExpiredError` keeps working.
from core.errors import AuthExpiredError, InvalidContentError, ServerError  # noqa: F401

RAW_DATA_ROOT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "raw_data")

# Keep existing token filenames as-is - no need to re-authenticate.
TOKEN_FILES = {
    "HK": os.path.join(os.path.dirname(__file__), "tokenHK.txt"),
    "54": os.path.join(os.path.dirname(__file__), "token54.txt"),
    # PT (Pezeshket) removed entirely on 1405/06/23 (user decision) - not
    # needed for this project.
}


# ---------------------------------------------------------------------------
# Credentials
# ---------------------------------------------------------------------------

def load_token(company_code):
    path = TOKEN_FILES.get(company_code)
    if not path or not os.path.exists(path):
        raise AuthExpiredError(f"No token file found for company '{company_code}'")
    with open(path, encoding="utf-8") as f:
        token = f.read().strip()
    if not token:
        raise AuthExpiredError(f"Token file for '{company_code}' is empty")
    return token


# ---------------------------------------------------------------------------
# "Smart panel" (panel-e-hooshmand) - a separate system from the
# hamkadeh.com/5040.me APIs above. Different login flow (image captcha,
# see login_smart_panel.py), different token file(s), and its endpoints
# return JSON directly instead of CSV. Kept in this same core module rather
# than a parallel one so there's a single place downloaders import from.
#
# One login (against 5040-product.5040.me) returns TWO independent
# credential sets - "hamkadeh" (used for HK's smart-panel requests, which
# go through the 5040.5040.me host) and "mahsul" (5040's own company,
# requests go directly against 5040-product.5040.me) - confirmed once 54's
# own smart-panel downloaders (SP/54/*.py) got a 403 using the "hamkadeh"
# token: different token per company/host, not one shared token.
# ---------------------------------------------------------------------------

SMART_PANEL_TOKEN_FILES = {
    "HK": os.path.join(os.path.dirname(__file__), "tokenSmartPanel.txt"),
    "54": os.path.join(os.path.dirname(__file__), "tokenSmartPanel54.txt"),
}


def load_smart_panel_token(company_code):
    path = SMART_PANEL_TOKEN_FILES.get(company_code)
    if not path:
        raise AuthExpiredError(f"No smart panel token file configured for company '{company_code}'")
    if not os.path.exists(path):
        raise AuthExpiredError(f"No smart panel token file found for '{company_code}' - run login_smart_panel.py")
    with open(path, encoding="utf-8") as f:
        token = f.read().strip()
    if not token:
        raise AuthExpiredError(f"Smart panel token file for '{company_code}' is empty")
    return token


def smart_panel_datetime_str(jdt):
    """Smart panel endpoints want 'YYYY-MM-DD HH:MM' (no seconds) - different
    from api_datetime_str's format used by the other downloaders."""
    return jdt.togregorian().strftime("%Y-%m-%d %H:%M")


# ---------------------------------------------------------------------------
# Date handling - Jalali everywhere, Gregorian ONLY at this one boundary.
# ---------------------------------------------------------------------------

def api_datetime_str(jdt):
    """
    Convert a Jalali datetime -> Gregorian string, in the exact format the
    external APIs expect. This is the ONLY place in the whole downloader
    layer where a Gregorian representation gets created.
    """
    return jdt.togregorian().strftime("%Y-%m-%d %H:%M:%S")


def build_raw_filename(company_code, report_code, period_start, period_end, download_time):
    """period_start/period_end/download_time are Jalali datetimes - format directly, no conversion needed.
    download_time must be the actual wall-clock moment the request was sent
    (see fetch_generic) - NOT the report's scheduled slot time, which can
    differ from real execution time on a late-running tick."""
    start_str = period_start.strftime("%Y%m%d%H%M")
    end_str = period_end.strftime("%Y%m%d%H%M")
    download_str = download_time.strftime("%Y%m%d%H%M%S")
    return f"{company_code}_{report_code}_{start_str}_{end_str}_{download_str}.csv"


def build_raw_path(company_code, report_code, filename):
    folder = os.path.join(RAW_DATA_ROOT, report_code, company_code)
    os.makedirs(folder, exist_ok=True)
    return os.path.join(folder, filename)


# ---------------------------------------------------------------------------
# HTTP call + save
# ---------------------------------------------------------------------------

def call_api(url, method, params, token, auth_mode="cookie", json_body=None):
    """
    auth_mode: "cookie" (default - token as a cookie, e.g. hamkadeh.com endpoints)
               "bearer" (token as an Authorization header, e.g. 5040.me's factor-extraction)
    """
    if auth_mode == "bearer":
        cookies = None
        # X-Requested-With (2026-10-10, user-approved): without it 5040.me's
        # Laravel API answers an EXPIRED token with an HTML "Server Error"
        # (HTTP 500 - it tries to redirect to a login route that doesn't
        # exist), so expiry looked like a server outage and token_health
        # reported the token as fine. With it, expiry is a clean 401 ->
        # AuthExpiredError. Verified: valid-token responses stay text/csv.
        headers = {"Authorization": f"Bearer {token}", "X-Requested-With": "XMLHttpRequest"}
    else:
        cookies = {"token": token}
        headers = None

    try:
        response = requests.request(
            method, url, params=params, cookies=cookies, headers=headers, json=json_body,
            timeout=(60, None), stream=True
        )
    except requests.exceptions.RequestException as e:
        raise ServerError(f"Connection failed: {e}")

    if response.status_code in (401, 403):
        raise AuthExpiredError(f"Auth failed (HTTP {response.status_code}) - token likely expired")
    if response.status_code != 200:
        raise ServerError(f"Server error (HTTP {response.status_code})")

    return response


def save_response_to_csv(response, save_path):
    total = int(response.headers.get("Content-Length", 0)) or None
    downloaded = 0
    is_first_chunk = True

    with open(save_path, "wb") as f:
        for chunk in response.iter_content(chunk_size=1024 * 1024):
            if not chunk:
                continue

            if is_first_chunk:
                is_first_chunk = False
                sample = chunk[:300].decode("utf-8", errors="ignore").strip()
                looks_invalid = (
                    len(chunk) < 100
                    or sample.upper().startswith("WELCOME")
                    or ("," not in sample and "\n" not in sample and ";" not in sample)
                )
                if looks_invalid:
                    f.close()
                    os.remove(save_path)
                    raise InvalidContentError(f"Invalid content received: {sample[:150]}")

            f.write(chunk)
            downloaded += len(chunk)

    return save_path


# ---------------------------------------------------------------------------
# The single entry point every downloader file calls.
# ---------------------------------------------------------------------------

def fetch_generic(url, method, company_code, report_code, period_start, period_end, build_params,
                   auth_mode="cookie", json_body=None, build_json_body=None):
    """
    period_start, period_end: Jalali datetimes (the report's requested/labeled
    period - may be anchored to a scheduled slot time, see main.slot_to_jdatetime).
    build_params(period_start, period_end) is responsible for converting to
    Gregorian internally (via api_datetime_str) ONLY when building the
    actual request parameters - not before.

    build_json_body(period_start, period_end): optional, same contract as
    build_params but for endpoints that take the period in a JSON body
    instead of query params (e.g. HK.EXT). If given, it takes precedence
    over the static `json_body` argument.

    The raw filename's download timestamp is captured here, right before the
    request is sent - independent of period_start/period_end and of any
    scheduled slot time - per the API contract that this segment records the
    actual moment of the request, not what period/report it's for.
    """
    token = load_token(company_code)
    params = build_params(period_start, period_end)
    if build_json_body is not None:
        json_body = build_json_body(period_start, period_end)

    download_time = now_jalali()
    response = call_api(url, method, params, token, auth_mode=auth_mode, json_body=json_body)

    filename = build_raw_filename(company_code, report_code, period_start, period_end, download_time)
    save_path = build_raw_path(company_code, report_code, filename)

    return save_response_to_csv(response, save_path)


def fetch_generic_excel(url, method, company_code, report_code, period_start, period_end, build_params,
                         auth_mode="bearer", json_body=None, build_json_body=None):
    """
    Same contract as fetch_generic, for endpoints that return an actual
    .xlsx file (Content-Type application/vnd.openxmlformats...spreadsheetml.sheet)
    instead of a raw CSV body - e.g. 5040.me's call/incoming-calls. The
    response can't go through save_response_to_csv's comma/semicolon sniff
    (xlsx is binary, would always look invalid), so it's parsed with
    pd.read_excel and re-saved as CSV, same end result as
    fetch_smart_panel_excel's JSON/XLSX->CSV conversion, so every downloader
    in the project still hands Report_Builders the same on-disk format.

    Uses the regular per-company TOKEN_FILES (load_token), not the smart
    panel token - this is a plain 5040.me/hamkadeh.com endpoint, just one
    that happens to respond with xlsx instead of csv.
    """
    token = load_token(company_code)
    params = build_params(period_start, period_end)
    if build_json_body is not None:
        json_body = build_json_body(period_start, period_end)

    download_time = now_jalali()
    response = call_api(url, method, params, token, auth_mode=auth_mode, json_body=json_body)
    # dtype=str - pandas' default numeric type inference silently mangles
    # text-like identifier columns (strips leading zeros off mobile numbers,
    # appends ".0" to any column that has a blank cell, loses precision past
    # int64 on long tracking/agency codes). Same real failure mode already
    # hit and fixed for Data_Bank_Core (see docs/data-bank-parquet-migration.md)
    # - every column comes through as the untouched string Excel displayed.
    df = pd.read_excel(io.BytesIO(response.content), dtype=str)

    filename = build_raw_filename(company_code, report_code, period_start, period_end, download_time)
    save_path = build_raw_path(company_code, report_code, filename)

    df.to_csv(save_path, index=False, encoding="utf-8-sig")
    return save_path


def fetch_smart_panel_json(url, company_code, report_code, period_start, period_end, build_json_body):
    """
    Smart panel equivalent of fetch_generic: synchronous POST, auth via
    load_smart_panel_token/auth_mode="bearer" instead of the per-company
    TOKEN_FILES.

    The panel's raw response is a JSON envelope, not a flat table
    ({"status", "message", "data": [...], "column": [...], ...}) - saved
    as CSV (see smart_panel_json_to_dataframe) so every downloader in the
    project hands Report_Builders the same on-disk format, per project
    convention (pd.read_csv, encoding="utf-8-sig").

    build_json_body(period_start, period_end) must return a dict already
    containing whatever the endpoint needs (e.g. the output-generator's
    fixed "id"), converting to Gregorian internally via
    smart_panel_datetime_str only when building the request body.
    """
    token = load_smart_panel_token(company_code)
    json_body = build_json_body(period_start, period_end)

    download_time = now_jalali()
    response = call_api(url, "POST", params=None, token=token, auth_mode="bearer", json_body=json_body)
    df = smart_panel_json_to_dataframe(response.json())

    start_str = period_start.strftime("%Y%m%d%H%M")
    end_str = period_end.strftime("%Y%m%d%H%M")
    download_str = download_time.strftime("%Y%m%d%H%M%S")
    filename = f"{company_code}_{report_code}_{start_str}_{end_str}_{download_str}.csv"
    save_path = build_raw_path(company_code, report_code, filename)

    df.to_csv(save_path, index=False, encoding="utf-8-sig")
    return save_path


def smart_panel_json_to_dataframe(payload):
    """
    Every smart-panel endpoint seen so far (voip/call-log/{id} at least)
    wraps its actual table in {"data": [{...row...}, ...], "column": [...]}
    alongside envelope fields (status/message/index_start_uniq) that aren't
    part of the data itself and are dropped here. If a future endpoint
    (e.g. the report/smart/calculate/{id} family) turns out to use a
    different shape, adapt per-downloader rather than assuming this generic
    parser covers it.

    A genuinely empty result (e.g. a Friday/holiday with zero support
    activity) is NOT a server malfunction - confirmed against a real
    response: HTTP 200, status=true, message="done", data=[], and "column"
    still present and correct. pd.DataFrame([]) has NO columns at all
    though, so indexing it by `columns` used to raise a bare KeyError here
    - which download_with_retry then retried 3 times against the exact
    same "no activity" result, spamming the log, before finally failing
    the whole tick (real bug, hit HK/54's SPH/SPI - the two smart-panel
    downloaders that go through this JSON parser; SPC is a separate Excel
    response, via fetch_smart_panel_excel, and never reaches this function).

    empty data is ONLY accepted as "legitimately zero rows" when status is
    exactly True - an HTTP 200 with status=false and data=[] is a real
    failure response, not "no activity today", and must NOT silently turn
    into a header-only CSV reported as a success; it raises
    InvalidContentError (carrying the payload's own "message") so
    download_with_retry retries it like any other failure.
    """
    data = payload.get("data", [])
    columns = payload.get("column")
    if not data:
        if payload.get("status") is not True:
            raise InvalidContentError(
                "smart panel response has empty data but status is not true "
                f"(status={payload.get('status')!r}, message={payload.get('message')!r}) - "
                "not treated as a legitimate 'no activity' result"
            )
        return pd.DataFrame(columns=columns or [])
    df = pd.DataFrame(data)
    if columns:
        df = df[columns]
    return df


def fetch_smart_panel_excel(url, company_code, report_code, period_start, period_end, build_json_body):
    """
    Some smart panel endpoints (e.g. voip/call-log-excel/{id}, vs. the plain
    voip/call-log/{id} JSON ones) return an actual .xlsx file instead of
    JSON - read via pandas.read_excel and saved as CSV, same end result as
    fetch_smart_panel_json's JSON->CSV conversion, so every downloader in
    the project hands Report_Builders the same on-disk format.

    Same request contract as fetch_smart_panel_json otherwise (auth via
    load_smart_panel_token/auth_mode="bearer", build_json_body(period_start,
    period_end) builds the POST body).
    """
    token = load_smart_panel_token(company_code)
    json_body = build_json_body(period_start, period_end)

    download_time = now_jalali()
    response = call_api(url, "POST", params=None, token=token, auth_mode="bearer", json_body=json_body)
    df = pd.read_excel(io.BytesIO(response.content))

    start_str = period_start.strftime("%Y%m%d%H%M")
    end_str = period_end.strftime("%Y%m%d%H%M")
    download_str = download_time.strftime("%Y%m%d%H%M%S")
    filename = f"{company_code}_{report_code}_{start_str}_{end_str}_{download_str}.csv"
    save_path = build_raw_path(company_code, report_code, filename)

    df.to_csv(save_path, index=False, encoding="utf-8-sig")
    return save_path
