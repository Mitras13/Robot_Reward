"""
Manual token refresh tool - NOT part of the automated pipeline.
Run this by hand whenever a company's token expires:
    python refresh_token.py HK
    python refresh_token.py 54

Requires interactive input (username/password, and an SMS code when the
company still uses one), which is why it can never be called automatically
from tick.py.

Login with OR without SMS (2026-10-10): 5040 dropped its SMS step - the
send-code call now returns {"status": true, "token": ...} directly, no code
needed. It may come back, so this tool handles both: if the send-code
response already carries a token it is saved as-is; otherwise it asks for
the SMS code and logs in as before. After saving, the token is checked with
the same probe the dashboard's token check uses.
"""
import getpass
import os
import sys

import requests

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(_HERE))  # project root, for API_Downloader.token_health

# JSON error bodies instead of HTML error pages (see downloader_core.call_api)
_HEADERS = {"Accept": "application/json"}

CONFIG = {
    "HK": {
        "send_code_url": "https://api.hamkadeh.com/api/auth/login/send-code",
        "login_url": "https://api.hamkadeh.com/api/auth/login",
        "send_method": "post",
        "token_file": "tokenHK.txt",
    },
    "54": {
        "send_code_url": "https://api.5040.me/api/auth/send-login-code",
        "login_url": "https://api.5040.me/api/auth/login",
        "send_method": "put",
        "token_file": "token54.txt",
    },
}


def _json(response):
    try:
        return response.json()
    except ValueError:
        return {}


def _fail(step, response):
    data = _json(response)
    print(f"❌ {step} failed: HTTP {response.status_code} {data.get('message', '')}".rstrip())


def refresh(company_code):
    cfg = CONFIG.get(company_code)
    if not cfg:
        print(f"❌ Unknown company code: {company_code}")
        return

    username = input("Username: ").strip()
    password = getpass.getpass("Password (hidden): ").strip()

    print("📲 Logging in...")
    send = getattr(requests, cfg["send_method"])
    r1 = send(cfg["send_code_url"], headers=_HEADERS,
              json={"type": "sms", "username": username, "password": password})
    data = _json(r1)
    if r1.status_code != 200 or data.get("status") is False:
        _fail("Login (send-code step)", r1)
        return

    token = data.get("token")
    if token:
        print("ℹ️  No SMS step - the server returned the token directly.")
    else:
        code = input("Enter SMS Code: ").strip()
        print("🔐 Verifying...")
        r2 = requests.post(cfg["login_url"], headers=_HEADERS,
                           json={"username": username, "password": password, "code": code})
        data = _json(r2)
        if r2.status_code != 200 or not data.get("status") or not data.get("token"):
            _fail("Login", r2)
            return
        token = data["token"]

    token_path = os.path.join(_HERE, cfg["token_file"])
    with open(token_path, "w", encoding="utf-8") as f:
        f.write(token)
    print(f"✅ Token saved to {cfg['token_file']}")

    from API_Downloader.token_health import check_token
    if check_token(company_code):
        print("✅ Token check passed - the robot can download again.")
    else:
        print("❌ Token check FAILED - the saved token is not accepted by the server.")


if __name__ == "__main__":
    if len(sys.argv) != 2 or sys.argv[1] not in CONFIG:
        print("Usage: python refresh_token.py [HK|54]")
        sys.exit(1)
    refresh(sys.argv[1])
