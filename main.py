"""
main.py - the persistent scheduling process.

Thread structure:
  - tick.tick(), its own background thread, every ~2s, sequential (never
    overlapping). Each tick itself spawns one further thread PER due
    (reward, slot) - see core/reward_runner.py - so rewards run fully
    independently of each other and of the tick loop.
  - The dedicated sender thread (Senders/sender_thread.py), started once
    here - the only thread ever allowed to call Senders.payamresan.send().
  - Token health, its own thread, every 15 minutes, independent of tick speed.
  - The main thread runs the admin panel, a Flask app (see ui/__init__.py) -
    a browser tab instead of the cmd console, since cmd.exe/conhost cannot
    render Persian/RTL text reliably (user decision 1405/06/23; rebuilt as
    a multi-page Flask app with settings-write 1405/06/27).

Full detail always goes to logs/app.log (see core/logging_setup.py)
regardless of console mode.
"""

import os

os.environ["ROBOT_REWARD_QUIET_CONSOLE"] = "1"

import logging
import subprocess
import sys
import threading
import time
import webbrowser

import jdatetime

from ui import create_app
from tick import tick
from API_Downloader.token_health import check_all_tokens
from Senders import sender_thread

TICK_INTERVAL_SECONDS = 2
TOKEN_CHECK_INTERVAL_SECONDS = 15 * 60
DASHBOARD_PORT = 8765


_error_logger = logging.getLogger("main")
_PID_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "main.pid")


def _kill_previous_instance():
    """
    Reads main.pid (this script's own folder). If it names a still-
    running process, force-kills it before this instance does anything else
    - a previous main.py that was never closed silently keeps serving
    the OLD dashboard on port 8765 while a fresh start looks like it did
    nothing (bit the user once, see main.bat history 1405/06/24).
    Deliberately not the .bat's job - matching "which pythonw.exe is ours"
    by command-line text is fragile (Windows does not put the working
    directory into the command line for `start "" pythonw script.py`, so an
    earlier attempt at this silently never matched anything). A pidfile
    written by the process itself is exact.
    """
    if os.path.isfile(_PID_FILE):
        try:
            with open(_PID_FILE) as f:
                old_pid = int(f.read().strip())
            if old_pid != os.getpid():
                subprocess.run(
                    ["taskkill", "/F", "/PID", str(old_pid)],
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                )
        except (ValueError, OSError):
            pass
    with open(_PID_FILE, "w") as f:
        f.write(str(os.getpid()))


def _record_error(state, lock, exc):
    now_j = jdatetime.datetime.now()
    with lock:
        state["last_error"] = {"message": f"{type(exc).__name__}: {exc}", "at": now_j.strftime("%H:%M:%S")}
    # Full traceback goes to logs/errors.log via the logger, never straight
    # to stderr - when launched with pythonw.exe (no console, see
    # main.bat) there is no stderr to write to.
    _error_logger.exception("unhandled error in main loop")


def _worker_loop(state, lock):
    while True:
        try:
            tick_results = tick() or []
        except Exception as e:
            tick_results = []
            _record_error(state, lock, e)

        if tick_results:
            now_j = jdatetime.datetime.now()
            with lock:
                state["last_activity_at"] = now_j.strftime("%H:%M:%S")

        time.sleep(TICK_INTERVAL_SECONDS)


def _token_check_loop(state, lock):
    while True:
        try:
            status = check_all_tokens()
            with lock:
                state["token_status"] = status
        except Exception as e:
            _record_error(state, lock, e)

        with lock:
            state["next_token_check_at"] = time.monotonic() + TOKEN_CHECK_INTERVAL_SECONDS
        time.sleep(TOKEN_CHECK_INTERVAL_SECONDS)


def main():
    _kill_previous_instance()

    state = {
        "token_status": {},
        "next_token_check_at": time.monotonic(),
        "last_activity_at": "-",
        "started_at": time.monotonic(),
        "last_error": None,
    }
    lock = threading.Lock()

    sender_thread.start()  # the ONLY thread allowed to call Senders.payamresan.send()
    threading.Thread(target=_worker_loop, args=(state, lock), daemon=True).start()
    threading.Thread(target=_token_check_loop, args=(state, lock), daemon=True).start()

    app = create_app(state, lock)
    url = f"http://127.0.0.1:{DASHBOARD_PORT}/"
    print(f"Robot Reward dashboard: {url}")
    webbrowser.open(url)
    app.run(host="127.0.0.1", port=DASHBOARD_PORT, threaded=True, use_reloader=False)  # blocks forever


if __name__ == "__main__":
    main()
