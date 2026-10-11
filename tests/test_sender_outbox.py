"""
Tests for the durable outbox in Senders/sender_thread.py and the
config/chat_directory.csv lookup in Senders/payamresan.py. Never sends
anything: the outbox dirs and directory file are redirected to a temp dir,
and the sender thread is never started.
    python -m unittest discover -s tests
"""

import os
import queue
import sys
import tempfile
import unittest
from unittest import mock

import jdatetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from Senders import payamresan, sender_thread  # noqa: E402
from Senders.message import OutboundMessage  # noqa: E402


def msg(contact="علی", text="سلام", panel_user_id="p1"):
    return OutboundMessage(reward_id="r1", slot="09:00", panel_user_id=panel_user_id,
                           chat_user_id="", contact=contact, text=text)


class OutboxTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.pending = os.path.join(self.tmp.name, "pending")
        self.expired = os.path.join(self.tmp.name, "expired")
        self.patches = [
            mock.patch.object(sender_thread, "OUTBOX_PENDING_DIR", self.pending),
            mock.patch.object(sender_thread, "OUTBOX_EXPIRED_DIR", self.expired),
            mock.patch.object(sender_thread, "_queue", queue.Queue()),
        ]
        for p in self.patches:
            p.start()

    def tearDown(self):
        for p in self.patches:
            p.stop()
        self.tmp.cleanup()

    def test_submit_persists_then_enqueues(self):
        sender_thread.submit([msg()])
        messages, path = sender_thread._queue.get_nowait()
        self.assertEqual(messages, [msg()])
        self.assertTrue(os.path.isfile(path))
        self.assertTrue(os.path.basename(path).startswith(jdatetime.datetime.now().strftime("%Y%m%d") + "__r1__0900__"))

    def test_empty_submit_is_noop(self):
        sender_thread.submit([])
        self.assertTrue(sender_thread._queue.empty())
        self.assertFalse(os.path.isdir(self.pending))

    def test_recover_requeues_today_and_expires_older(self):
        sender_thread.submit([msg()])
        sender_thread._queue.get_nowait()  # simulate: process died before sending
        os.makedirs(self.pending, exist_ok=True)
        stale = os.path.join(self.pending, "14000101__r1__0900__abc.json")
        with open(stale, "w", encoding="utf-8") as f:
            f.write("[]")

        sender_thread._recover_pending()

        messages, path = sender_thread._queue.get_nowait()
        self.assertEqual(messages, [msg()])
        self.assertTrue(sender_thread._queue.empty())
        self.assertFalse(os.path.exists(stale))
        self.assertTrue(os.path.isfile(os.path.join(self.expired, "14000101__r1__0900__abc.json")))

    def test_recovered_batch_has_same_run_id_so_resume_skips_sent_items(self):
        sender_thread.submit([msg(), msg(contact="رضا")])
        original, path = sender_thread._queue.get_nowait()
        sender_thread._recover_pending()
        recovered, _ = sender_thread._queue.get_nowait()
        self.assertEqual(payamresan.compute_run_id(sender_thread._to_rendered(original)),
                         payamresan.compute_run_id(sender_thread._to_rendered(recovered)))


class ChatDirectoryTest(unittest.TestCase):
    def test_lookup_and_fallback(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "chat_directory.csv")
            with open(path, "w", encoding="utf-8-sig", newline="") as f:
                f.write("panel_user_id,chat_user_id\np1,ali_user\np2,\n")
            with mock.patch.object(payamresan, "_CHAT_DIRECTORY_FILE", path):
                rendered = [
                    {"contact": "علی", "panel_user_id": "p1", "chat_user_id": None},
                    {"contact": "رضا", "panel_user_id": "p2", "chat_user_id": None},
                    {"contact": "مینا", "panel_user_id": "p9", "chat_user_id": None},
                ]
                payamresan._enrich_with_chat_user_id(rendered)
        self.assertEqual([r["chat_user_id"] for r in rendered], ["ali_user", None, None])

    def test_missing_file_changes_nothing(self):
        with mock.patch.object(payamresan, "_CHAT_DIRECTORY_FILE", os.path.join(tempfile.gettempdir(), "nope.csv")):
            rendered = [{"contact": "علی", "panel_user_id": "p1", "chat_user_id": None}]
            payamresan._enrich_with_chat_user_id(rendered)
        self.assertIsNone(rendered[0]["chat_user_id"])


if __name__ == "__main__":
    unittest.main()
