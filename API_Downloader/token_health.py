"""
token_health.py - periodic, cheap liveness probe for each company's token.

⚠️ Why this exists: token refresh is manual (needs SMS OTP, see
refresh_token.py) and deliberately outside the automated pipeline. Without
this, the FIRST sign of an expired token was a real report's send time
arriving and failing - too late to do anything about it. Checking every
~15 minutes (see main.py) means an expired token gets noticed and can
be refreshed by hand well before the next real report cycle needs it.

Reuses each existing downloader's own URL/METHOD/build_params (HK.SCL for
HK, 54.FCR for 54) - single source of truth, no separately-maintained
endpoint config. Calls downloader_core.call_api() directly (bypassing
fetch_generic) with a zero-width period, so nothing is saved to raw_data/.

Loaded via importlib rather than a plain `from .54 import FCR` because "54"
isn't a valid Python identifier - a literal import statement naming it
would be a SyntaxError. importlib.import_module works fine since it takes
the dotted path as a string, not source-level syntax.
"""
import base64
import importlib
import json
import time

import jdatetime

from .downloader_core import call_api, load_token, load_smart_panel_token, AuthExpiredError

_SCL_HK = importlib.import_module(".HK.SCL", package=__package__)
_FCR_54 = importlib.import_module(".54.FCR", package=__package__)

# (downloader module to reuse URL/METHOD/build_params from, auth_mode)
_PROBES = {
    "HK": (_SCL_HK, "cookie"),
    "54": (_FCR_54, "bearer"),
}


def check_token(company_code):
    """
    Returns True if the token still authenticates, False if it's expired/
    invalid (AuthExpiredError specifically). Any OTHER exception (network
    hiccup, unrelated server error) is treated as inconclusive -> True, to
    avoid false alarms from something that isn't actually a token problem.
    """
    module, auth_mode = _PROBES[company_code]
    now = jdatetime.datetime.now()
    token = load_token(company_code)
    params = module.build_params(now, now)

    try:
        call_api(
            module.URL, module.METHOD, params, token,
            auth_mode=auth_mode, json_body={} if auth_mode == "bearer" else None,
        )
        return True
    except AuthExpiredError:
        return False
    except Exception:
        return True


def check_smart_panel_token(company_code):
    """
    Smart-panel tokens (SP.HK.*, SP.54.* - SPK alone feeds 12 rewards) were
    never probed before 1405/07/19. They are JWTs, so expiry is read from
    the token's own "exp" claim - no network call at all, so this can never
    add to the panel's HTTP 429 rate limit. Missing/empty file or an "exp"
    in the past -> False. A token without a readable "exp" -> True
    (inconclusive, same rule as check_token: no false alarms).
    """
    try:
        token = load_smart_panel_token(company_code)
    except AuthExpiredError:
        return False
    try:
        payload_b64 = token.split(".")[1]
        payload_b64 += "=" * (-len(payload_b64) % 4)
        exp = json.loads(base64.urlsafe_b64decode(payload_b64)).get("exp")
    except (IndexError, ValueError):
        return True
    if not isinstance(exp, (int, float)):
        return True
    return exp > time.time()


def check_all_tokens():
    """Checks every known company's token, prints a loud alert for any that
    have expired. Returns {"HK", "54", "SP-HK", "SP-54": True/False} - consumed by
    main.py's dashboard as well as printed here."""
    status = {}
    for company_code in _PROBES:
        ok = check_token(company_code)
        status[company_code] = ok
        if ok:
            print(f"🔑 token check: {company_code} OK")
        else:
            print(
                f"🚨🚨🚨 TOKEN EXPIRED for company '{company_code}' - reports for this "
                f"company will fail until refreshed. Run: python API_Downloader/refresh_token.py {company_code}"
            )
    for company_code in ("HK", "54"):
        key = f"SP-{company_code}"
        ok = check_smart_panel_token(company_code)
        status[key] = ok
        if not ok:
            print(f"🚨 smart panel token EXPIRED ({key}) - run: python API_Downloader/login_smart_panel.py 54")
    return status
