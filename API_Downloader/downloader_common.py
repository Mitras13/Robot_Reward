import time
from .downloader_core import AuthExpiredError


def download_with_retry(fetch_func, max_retries=3, delay_seconds=30, label="download"):
    """
    Shared retry wrapper for all API Downloaders.

    AuthExpiredError is NEVER retried (same token = same failure every time).
    It's raised immediately so tick.py can log it as a credential issue
    (per project rule: logged only, no admin alert, no retry).

    Any other exception is retried up to max_retries times. If all attempts
    fail, the last exception is raised so tick.py can log it and alert
    the admin group.
    """
    last_error = None

    for attempt in range(1, max_retries + 1):
        try:
            print(f"📡 {label}: attempt {attempt}/{max_retries}")
            result = fetch_func()
            print(f"✅ {label}: success on attempt {attempt}")
            return result

        except AuthExpiredError as e:
            print(f"🔑 {label}: credential issue, not retrying -> {e}")
            raise

        except Exception as e:
            last_error = e
            print(f"⚠️  {label}: attempt {attempt} failed -> {e}")
            if attempt < max_retries:
                time.sleep(delay_seconds)

    print(f"❌ {label}: all {max_retries} attempts failed")
    raise last_error
