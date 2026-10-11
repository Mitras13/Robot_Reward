"""
Tests for core/scheduling.py - the schedule mini-language and catch-up-once.

Pure functions only (no files, no clock), so these run anywhere:
    python -m unittest discover -s tests
"""

import os
import sys
import unittest

import jdatetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core import scheduling  # noqa: E402
from core.errors import RewardConfigError  # noqa: E402


def jdt(y, m, d, hh=0, mm=0):
    return jdatetime.datetime(y, m, d, hh, mm)


CAMPAIGN = {"reward_id": "r1", "enabled": "1", "valid_from": "1405/07/11", "valid_to": "1405/07/30"}


def rows(days, times):
    return [{"reward_id": "r1", "days": days, "times": times}]


class ExpandTimesTest(unittest.TestCase):
    def test_explicit_times_sorted_and_deduped(self):
        self.assertEqual(scheduling.expand_times("13:00|09:00|13:00"), ["09:00", "13:00"])

    def test_every_hours_inclusive_range(self):
        self.assertEqual(scheduling.expand_times("every:2h@08:00-12:00"), ["08:00", "10:00", "12:00"])

    def test_every_minutes_unioned_with_explicit(self):
        self.assertEqual(scheduling.expand_times("every:30m@09:00-10:00|20:00"),
                         ["09:00", "09:30", "10:00", "20:00"])

    def test_bad_tokens_raise(self):
        for bad in ("", "9:00", "every:2x@08:00-10:00", "every:1h@12:00-08:00"):
            with self.subTest(bad=bad), self.assertRaises(RewardConfigError):
                scheduling.expand_times(bad)


class DayMatchesTest(unittest.TestCase):
    def test_wildcards(self):
        for token in ("همه", "all", "*"):
            self.assertTrue(scheduling.day_matches(token, jdt(1405, 7, 15), CAMPAIGN))

    def test_weekday_name(self):
        now = jdt(1405, 7, 19)
        today = scheduling.WEEKDAY_FA[now.weekday()]
        self.assertTrue(scheduling.day_matches(today, now, CAMPAIGN))
        other = scheduling.WEEKDAY_FA[(now.weekday() + 1) % 7]
        self.assertFalse(scheduling.day_matches(other, now, CAMPAIGN))

    def test_month_day(self):
        self.assertTrue(scheduling.day_matches("month:15", jdt(1405, 7, 15), CAMPAIGN))
        self.assertFalse(scheduling.day_matches("month:15", jdt(1405, 7, 16), CAMPAIGN))

    def test_last_and_first_are_relative_to_campaign_window(self):
        self.assertTrue(scheduling.day_matches("last:1", jdt(1405, 7, 30), CAMPAIGN))
        self.assertFalse(scheduling.day_matches("last:1", jdt(1405, 7, 29), CAMPAIGN))
        self.assertTrue(scheduling.day_matches("first:2", jdt(1405, 7, 12), CAMPAIGN))
        self.assertFalse(scheduling.day_matches("first:2", jdt(1405, 7, 13), CAMPAIGN))

    def test_pipe_is_any_match(self):
        self.assertTrue(scheduling.day_matches("month:1|month:15", jdt(1405, 7, 15), CAMPAIGN))

    def test_empty_days_raises(self):
        with self.assertRaises(RewardConfigError):
            scheduling.day_matches(" | ", jdt(1405, 7, 15), CAMPAIGN)


class CampaignWindowTest(unittest.TestCase):
    def test_inclusive_both_ends_whole_day(self):
        self.assertTrue(scheduling.is_campaign_active(CAMPAIGN, jdt(1405, 7, 11, 0, 0)))
        self.assertTrue(scheduling.is_campaign_active(CAMPAIGN, jdt(1405, 7, 30, 23, 59)))
        self.assertFalse(scheduling.is_campaign_active(CAMPAIGN, jdt(1405, 7, 10, 23, 59)))
        self.assertFalse(scheduling.is_campaign_active(CAMPAIGN, jdt(1405, 8, 1)))

    def test_disabled_is_never_active(self):
        self.assertFalse(scheduling.is_campaign_active({**CAMPAIGN, "enabled": "0"}, jdt(1405, 7, 15)))


class CatchUpOnceTest(unittest.TestCase):
    SCHEDULE = rows("همه", "09:00|13:00|17:00")

    def test_nothing_due_before_first_slot(self):
        self.assertEqual(scheduling.due_slot_and_missed(CAMPAIGN, self.SCHEDULE, jdt(1405, 7, 15, 8, 59), set()),
                         (None, []))

    def test_exact_slot_time_is_due(self):
        self.assertEqual(scheduling.due_slot_and_missed(CAMPAIGN, self.SCHEDULE, jdt(1405, 7, 15, 9, 0), set()),
                         ("09:00", []))

    def test_only_latest_missed_runs_older_are_skipped(self):
        slot, missed = scheduling.due_slot_and_missed(CAMPAIGN, self.SCHEDULE, jdt(1405, 7, 15, 17, 30), set())
        self.assertEqual(slot, "17:00")
        self.assertEqual(missed, ["13:00", "09:00"])

    def test_already_attempted_slots_never_rerun(self):
        done = {"09:00", "13:00", "17:00"}
        self.assertEqual(scheduling.due_slot_and_missed(CAMPAIGN, self.SCHEDULE, jdt(1405, 7, 15, 18, 0), done),
                         (None, []))

    def test_slot_jdatetime_anchors_to_label_not_wall_clock(self):
        anchored = scheduling.slot_to_jdatetime(jdt(1405, 7, 15, 17, 42), "17:00")
        self.assertEqual((anchored.hour, anchored.minute, anchored.second), (17, 0, 0))

    def test_other_rewards_rows_are_ignored(self):
        schedule = [{"reward_id": "other", "days": "همه", "times": "10:00"}]
        self.assertEqual(scheduling.slots_for_day(CAMPAIGN, schedule, jdt(1405, 7, 15)), [])


if __name__ == "__main__":
    unittest.main()
