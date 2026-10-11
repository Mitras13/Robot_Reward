"""
Live "what is happening right now" state, for the dashboard only.

Ported from Robot_Analytics/live_state.py, with reward-shaped names.

Deliberately lock-free. Writers are the pipeline thread and the download
worker pool; the only reader is the dashboard render loop. set.add/discard and
dict item assignment are atomic enough under the GIL that the worst possible
outcome is a display that is one frame stale. Never make a decision from this
module - the durable truth is logs/outbox/ and logs/slot_runs.csv.

current_downloads is {downloader_name: reward_id} (reshaped 1405/06/26 - was
a bare set) so the dashboard can say *which reward* a downloader belongs to,
not just its bare name; safe, since nothing outside this module and
core/reward_runner.py reads it.

Actual send progress (started 1405/06/25) now lives in core/runlog.py's
snapshot() - this module's own earlier send_progress/begin_send/
record_send_result were never wired to anything and are removed rather than
kept as dead, duplicate tracking.
"""

current_downloads = {}
current_rewards = set()


def start_download(name, reward_id):
    current_downloads[name] = reward_id


def finish_download(name):
    current_downloads.pop(name, None)


def start_reward(reward_id):
    current_rewards.add(reward_id)


def finish_reward(reward_id):
    current_rewards.discard(reward_id)


def snapshot():
    """A shallow copy safe to render from."""
    return {
        "downloads": [{"downloader": name, "reward_id": rid} for name, rid in current_downloads.items()],
        "rewards": sorted(current_rewards),
    }
