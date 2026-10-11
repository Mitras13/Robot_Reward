"""
Manual login tool for the "smart panel" (panel-e-hooshmand) - a separate
auth system from the existing hamkadeh.com/5040.me token flow, NOT part of
the automated pipeline.

Login here uses an image captcha (no SMS OTP), so it requires a human to
read the captcha and type the code - same reason refresh_token.py can't be
called from tick.py.

The login response actually carries two independent credential sets
("mahsul" and "hamkadeh"), and - confirmed against a real login response,
2026-08-16 - they use DIFFERENT field names for the JWT itself:
data["hamkadeh"]["access"] but data["mahsul"]["token"] (mahsul's dict has
no "access" key at all). Requests to HK's smart-panel host (5040.5040.me)
use the "hamkadeh" JWT (confirmed against a real /api/user/profile/
request); requests to 5040's OWN smart-panel host (5040-product.5040.me,
same host this login itself runs against) use "mahsul" instead - confirmed
once 54's own downloaders (API_Downloader/SP/54/*.py) got a 403 using the
"hamkadeh" token. Both are saved from the same single login.

Run by hand:
    python login_smart_panel.py 54

Saves "hamkadeh" -> tokenSmartPanel.txt and "mahsul" -> tokenSmartPanel54.txt,
both next to this file.
"""
import sys
import os
import base64
import requests

CONFIG = {
    "54": {
        "captcha_url": "https://5040-product.5040.me/api/user/generate-captcha/",
        "login_url": "https://5040-product.5040.me/api/user/login",
        "username": "gozareshat",
        # One login, two credential sets to extract - see module docstring.
        # Each set uses its own field name for the JWT (not both "access").
        "token_files": {
            "hamkadeh": {"filename": "tokenSmartPanel.txt", "field": "access"},
            "mahsul": {"filename": "tokenSmartPanel54.txt", "field": "token"},
        },
    },
}

CAPTCHA_IMAGE_PATH = os.path.join(os.path.dirname(__file__), "_captcha_preview.jpg")


def login(company_code):
    cfg = CONFIG.get(company_code)
    if not cfg:
        print(f"Unknown company code: {company_code}")
        return

    print("Fetching captcha...")
    r1 = requests.get(cfg["captcha_url"])
    if r1.status_code != 200:
        print(f"Failed to fetch captcha: HTTP {r1.status_code}")
        return

    captcha_data = r1.json()["data"]
    captcha_token = captcha_data["token"]
    image_b64 = captcha_data["image"]

    with open(CAPTCHA_IMAGE_PATH, "wb") as f:
        f.write(base64.b64decode(image_b64))
    print(f"Captcha image saved to: {CAPTCHA_IMAGE_PATH}")
    print("Open that file and read the code.")

    password = input("Password (for user 'gozareshat'): ").strip()
    code = input("Captcha code: ").strip()

    print("Logging in...")
    r2 = requests.post(cfg["login_url"], json={
        "username": cfg["username"],
        "password": password,
        "code": code,
        "token": captcha_token,
    })

    if r2.status_code != 200:
        print(f"\nLogin request failed: HTTP {r2.status_code}")
        print(r2.text)
        return

    data = r2.json()
    for credential_key, spec in cfg["token_files"].items():
        filename, field = spec["filename"], spec["field"]
        try:
            token = data[credential_key][field]
        except KeyError:
            # Don't print r2.text here - it contains the OTHER credential's
            # real JWT (already succeeded), which shouldn't get pasted into
            # chat/logs. Print structure only: top-level keys, and one level
            # deeper for any nested dict, so the actual key names are
            # visible without leaking any token value.
            print(f"\nUnexpected response shape - couldn't find data['{credential_key}']['{field}']. "
                  f"Top-level keys: {list(data.keys())}")
            for k, v in data.items():
                if isinstance(v, dict):
                    print(f"  data['{k}'] keys: {list(v.keys())}")
            continue

        token_path = os.path.join(os.path.dirname(__file__), filename)
        with open(token_path, "w", encoding="utf-8") as f:
            f.write(token)
        print(f"\nToken ({credential_key}) saved to {filename}")


if __name__ == "__main__":
    if len(sys.argv) != 2 or sys.argv[1] not in CONFIG:
        print("Usage: python login_smart_panel.py [54]")
        sys.exit(1)
    login(sys.argv[1])
