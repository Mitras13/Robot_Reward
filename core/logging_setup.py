"""
This project's own logging system.

Why this is not a copy of Robot_Analytics' approach: that project replaces
builtins.print with a function that tees into a log file. It works, but it has
two real costs we do not want to inherit -

  1. Full tracebacks never reach the log file. Only main.py prints them,
     and only to stderr, so the one thing you actually need at 2am is the one
     thing that is missing.
  2. Every line looks the same. There is no way to tell which reward, which
     downloader, or which layer produced a message.

So here we use real named loggers, and keep the print-capturing trick only
where it is genuinely needed: around the vendored Senders/send_message.py,
which prints and which we do not want to modify.

Entry points call setup() exactly once, before anything else.
"""

import builtins
import contextlib
import logging
import os
import sys
from logging.handlers import TimedRotatingFileHandler

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOG_DIR = os.path.join(_PROJECT_ROOT, "logs")

APP_LOG = os.path.join(LOG_DIR, "app.log")
ERROR_LOG = os.path.join(LOG_DIR, "errors.log")

# Console/log output is English (or short emoji) by project convention: the
# execution machine's conhost does not reliably render RTL Persian mixed with
# LTR text, and that caused real garbling in the dashboard. Persian belongs in
# message content, not in logs.
_FORMAT = "%(asctime)s %(levelname)-7s %(name)-28s %(message)s"
_DATEFMT = "%Y-%m-%d %H:%M:%S"

_configured = False


def setup(quiet_console=False, level=logging.INFO):
    """
    Configure the root logger. Idempotent - calling it twice is a no-op, so a
    tool that imports tick.py cannot accidentally double every log line.

    quiet_console: True when the live dashboard owns the terminal.
    """
    global _configured
    if _configured:
        return

    os.makedirs(LOG_DIR, exist_ok=True)

    # Entry points must be able to write Persian report text to stdout.
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")
        except (AttributeError, ValueError):
            pass

    formatter = logging.Formatter(_FORMAT, datefmt=_DATEFMT)
    root = logging.getLogger()
    root.setLevel(level)

    app_handler = TimedRotatingFileHandler(
        APP_LOG, when="midnight", backupCount=30, encoding="utf-8"
    )
    app_handler.setFormatter(formatter)
    app_handler.setLevel(level)
    root.addHandler(app_handler)

    # Everything worth waking up for, with the traceback attached. Kept in its
    # own file so "did anything go wrong today" is one short read, not a grep
    # through a day of INFO lines.
    error_handler = TimedRotatingFileHandler(
        ERROR_LOG, when="midnight", backupCount=90, encoding="utf-8"
    )
    error_handler.setFormatter(formatter)
    error_handler.setLevel(logging.WARNING)
    root.addHandler(error_handler)

    if not quiet_console:
        console = logging.StreamHandler(sys.stdout)
        console.setFormatter(formatter)
        console.setLevel(level)
        root.addHandler(console)

    _configured = True


def get_logger(name):
    """
    Naming convention, so a log line says which layer spoke:
      core.dispatch, core.outbox, core.scheduling
      reward.hk-padash-saati-forosh
      downloader.HK.STF
      sender.payamresan
    """
    return logging.getLogger(name)


@contextlib.contextmanager
def capture_prints(logger, level=logging.INFO):
    """
    Route bare print() calls made inside this block into `logger`.

    Used for exactly one thing: wrapping the call into the vendored
    Senders/send_message.py, which prints its progress and which we keep
    byte-identical to its source project (see tests/test_vendored_sender.py).
    Do not reach for this anywhere else - write a real logger call instead.
    """
    original_print = builtins.print

    def _captured(*args, sep=" ", end="\n", file=None, flush=False):
        # A print() aimed at a real file object is a deliberate write, not a
        # log line - let it through untouched.
        if file is not None and file not in (sys.stdout, sys.stderr):
            return original_print(*args, sep=sep, end=end, file=file, flush=flush)
        text = sep.join(str(a) for a in args).rstrip()
        if text:
            logger.log(level, text)

    builtins.print = _captured
    try:
        yield
    finally:
        builtins.print = original_print
