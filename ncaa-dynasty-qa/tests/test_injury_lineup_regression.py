"""Regression tests for injury status, recovery timelines, and lineup
adjustments (TR-83..TR-92)."""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import verify


def roster_with(*names):
    r = verify.Roster()
    for n in names:
        r.add(verify.Player(n))
    return r


class InjuryStatusTests(unittest.TestCase):
    """TR-83: injury status categories track the recovery timeline."""

    def test_healthy_by_default(self):
        r = roster_with("P1")
        self.assertEqual(r.injury_status("P1"), "healthy")

    def test_out_with_more_than_one_week(self):
        r = roster_with("P1")
        r.set_injury("P1", 3)
        self.assertEqual(r.injury_status("P1"), "out")

    def test_questionable_with_one_week(self):
        r = roster_with("P1")
        r.set_injury("P1", 1)
        self.assertEqual(r.injury_status("P1"), "questionable")

    def test_healthy_after_clear(self):
        r = roster_with("P1")
        r.set_injury("P1", 3)
        r.set_injury("P1", 0)
        self.assertEqual(r.injury_status("P1"), "healthy")


class RecoveryTimelineTests(unittest.TestCase):
    """TR-84: a player recovers exactly on schedule."""

    def test_countdown_week_by_week(self):
        r = roster_with("P1")
        r.set_injury("P1", 3)
        for remaining in (2, 1, 0):
            r.advance_week()
            self.assertEqual(r.players["P1"].injury_weeks, remaining)
        self.assertEqual(r.injury_status("P1"), "healthy")

    def test_questionable_one_week_before_return(self):
        r = roster_with("P1")
        r.set_injury("P1", 2)
        r.advance_week()
        self.assertEqual(r.injury_status("P1"), "questionable")


class InjuryReportTests(unittest.TestCase):
    """TR-85 and TR-92: the injury report lists injured players only."""

    def test_report_lists_each_injured_player_with_weeks(self):
        r = roster_with("P1", "P2", "P3")
        r.set_injury("P1", 4)
        r.set_injury("P3", 1)
        self.assertEqual(r.injury_report(), {"P1": 4, "P3": 1})

    def test_report_empty_when_all_healthy(self):
        r = roster_with("P1", "P2", "P3")
        self.assertEqual(r.injury_report(), {})

    def test_report_empties_when_injury_cleared(self):
        r = roster_with("P1", "P2")
        r.set_injury("P2", 2)
        self.assertEqual(len(r.injury_report()), 1)
        r.set_injury("P2", 0)
        self.assertEqual(r.injury_report(), {})


class LineupAdjustmentTests(unittest.TestCase):
    """TR-86, TR-87, TR-88 and TR-89: elevating backups, returning
    players to the lineup, and demotions."""

    def test_healthy_backup_elevated_for_injured_starter(self):
        r = roster_with("P1", "P2")
        r.promote("P1")
        r.set_injury("P1", 2)
        self.assertTrue(r.elevate_backup("P1", "P2"))
        self.assertTrue(r.players["P2"].starter)
        self.assertFalse(r.players["P1"].starter)

    def test_injured_backup_cannot_be_elevated(self):
        r = roster_with("P1", "P2")
        r.promote("P1")
        r.set_injury("P1", 2)
        r.set_injury("P2", 1)
        self.assertFalse(r.elevate_backup("P1", "P2"))
        self.assertEqual(r.error, "PLAYER_INJURED")
        self.assertFalse(r.players["P2"].starter)

    def test_elevating_unknown_players_is_rejected(self):
        r = roster_with("P1")
        self.assertFalse(r.elevate_backup("P1", "Ghost"))
        self.assertEqual(r.error, "UNKNOWN_PLAYER")

    def test_recovered_player_returns_to_lineup(self):
        r = roster_with("P1")
        r.promote("P1")
        r.set_injury("P1", 2)
        self.assertFalse(r.players["P1"].starter)
        r.advance_week()
        r.advance_week()
        self.assertEqual(r.injury_status("P1"), "healthy")
        self.assertTrue(r.promote("P1"))
        self.assertTrue(r.players["P1"].starter)

    def test_demote_moves_starter_to_bench(self):
        r = roster_with("P1")
        r.promote("P1")
        r.demote("P1")
        self.assertFalse(r.players["P1"].starter)
        self.assertIn("P1", r.players)


class InjuryTimelineEdgeTests(unittest.TestCase):
    """TR-90 and TR-91: idempotent recording and offseason healing."""

    def test_recording_same_length_preserves_timeline(self):
        r = roster_with("P1")
        r.set_injury("P1", 3)
        r.advance_week()
        self.assertEqual(r.players["P1"].injury_weeks, 2)
        self.assertTrue(r.set_injury("P1", 2))
        self.assertEqual(r.players["P1"].injury_weeks, 2)

    def test_late_season_injury_heals_at_rollover(self):
        r = roster_with("P1")
        r.week = 11
        r.set_injury("P1", 3)
        r.advance_week()
        self.assertEqual(r.week, 12)
        self.assertEqual(r.players["P1"].injury_weeks, 2)
        self.assertTrue(r.rollover_season())
        self.assertEqual(r.players["P1"].injury_weeks, 0)
        self.assertEqual(r.injury_status("P1"), "healthy")


if __name__ == "__main__":
    unittest.main()
