"""
Shared error types for the whole pipeline.

The download-layer trichotomy (AuthExpiredError/InvalidContentError/
ServerError) is defined HERE, canonically (moved from
API_Downloader/downloader_core.py 1405/07/19, user decision - it used to be
the other way round, which made core <-> API_Downloader a package-level
import cycle). downloader_core.py imports these same classes back from here,
so `downloader_core.AuthExpiredError` and `core.errors.AuthExpiredError` are
still one and the same class - an `except` on either catches both.

  AuthExpiredError  -> NEVER retried. The same token produces the same failure
                       every time; retrying just burns time and hides the
                       real problem (a human has to refresh the token).
  InvalidContentError -> HTTP 200 but the body is not data (a login page, an
                       error page, a truncated body). Retried, because it is
                       often a transient server-side state.
  ServerError       -> 5xx / timeout. Retried, then escalated.
"""


class AuthExpiredError(Exception):
    """Token is invalid/expired/missing. Needs a manual re-login.
    Per project rule: logged only, no admin alert, no retry."""
    pass


class InvalidContentError(Exception):
    """Server responded 200 but content doesn't look like valid data
    (e.g. a login/welcome page instead of a CSV)."""
    pass


class ServerError(Exception):
    """Server-side failure unrelated to auth (5xx, timeout, etc).
    Per project rule: retried 3x, then alert to admin group."""
    pass


class RewardConfigError(Exception):
    """
    A campaign/schedule/params/roster file is missing, malformed, or
    self-contradictory. Raised at load time and always loud - a reward with an
    unreadable config must never silently behave as if it had a default.
    """
