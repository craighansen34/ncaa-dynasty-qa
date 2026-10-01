"""Regression tests for the roster-move deadline, injuries and dynasty
progression (TR-62..TR-72). Stdlib only.
Run: cd tests && python3 -m unittest test_deadline_injury_dynasty_regression
"""
import os, sys, unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from verify import (Roster, Player, TRANSFER_DEADLINE_WEEK, SEASON_WEEKS,
                    MAX_ROSTER, MIN_PRESTIGE, MAX_PRESTIGE)


def roster(n):
    r = Roster()
    for i in range(1, n + 1):
        r.add(Player(f"P{i}"))
    return r


class TestTransferDeadline(unittest.TestCase):
    def test_deadline_week_accepted(self):
        """TR-62: a transfer in the deadline week itself is accepted."""
        r = roster(70); r.week = TRANSFER_DEADLINE_WEEK
        self.assertTrue(r.transfer_in(Player("Portal1")))
        self.assertIn("Portal1", r.players); self.assertEqual(r.count, 71)

    def test_after_deadline_blocked(self):
        """TR-63: one week after the deadline the transfer is blocked and nothing changes."""
        r = roster(70); r.week = TRANSFER_DEADLINE_WEEK + 1
        self.assertFalse(r.transfer_in(Player("Portal1")))
        self.assertEqual(r.error, "DEADLINE_PASSED")
        self.assertNotIn("Portal1", r.players); self.assertEqual(r.count, 70)

    def test_deadline_checked_before_roster_cap(self):
        """TR-63: at a full roster after the deadline, the deadline error wins."""
        r = roster(MAX_ROSTER); r.week = TRANSFER_DEADLINE_WEEK + 1
        r.transfer_in(Player("Portal1"))
        self.assertEqual(r.error, "DEADLINE_PASSED")

    def test_cap_still_applies_before_deadline(self):
        """TR-62: before the deadline the 85-man cap still blocks a transfer."""
        r = roster(MAX_ROSTER); r.week = 1
        self.assertFalse(r.transfer_in(Player("Portal1")))
        self.assertEqual(r.error, "ROSTER_FULL")

    def test_rollover_reopens_window(self):
        """TR-64: rollover resets to week 1 so transfers are accepted again."""
        r = roster(70); r.week = SEASON_WEEKS
        r.rollover_season()
        self.assertEqual(r.week, 1)
        self.assertTrue(r.transfer_in(Player("Portal1")))


class TestInjuries(unittest.TestCase):
    def test_injured_starter_benched(self):
        """TR-65: injuring a starter removes starter status."""
        r = roster(60); r.promote("P1")
        r.set_injury("P1", 3)
        self.assertFalse(r.players["P1"].starter)
        self.assertEqual(r.players["P1"].injury_weeks, 3)

    def test_clearing_injury_does_not_restore_starter(self):
        """TR-65: clearing an injury does not silently re-promote the player."""
        r = roster(60); r.promote("P1"); r.set_injury("P1", 3); r.set_injury("P1", 0)
        self.assertFalse(r.players["P1"].starter)

    def test_injured_cannot_be_promoted_until_healed(self):
        """TR-66: promotion is blocked while injured, allowed once healed."""
        r = roster(60); r.set_injury("P1", 2)
        self.assertFalse(r.promote("P1")); self.assertEqual(r.error, "PLAYER_INJURED")
        r.advance_week()
        self.assertFalse(r.promote("P1"))
        r.advance_week()
        self.assertTrue(r.promote("P1")); self.assertTrue(r.players["P1"].starter)

    def test_revision_replaces_timeline(self):
        """TR-67: a revised injury replaces the remaining weeks rather than adding."""
        r = roster(60); r.set_injury("P1", 6); r.set_injury("P1", 2); r.advance_week()
        self.assertEqual(r.players["P1"].injury_weeks, 1)
        r.set_injury("P1", 4)
        self.assertEqual(r.players["P1"].injury_weeks, 4)

    def test_negative_injury_rejected(self):
        """TR-67: a negative injury length is rejected and leaves the injury unchanged."""
        r = roster(60); r.set_injury("P1", 3)
        self.assertFalse(r.set_injury("P1", -1))
        self.assertEqual(r.error, "INVALID_INJURY")
        self.assertEqual(r.players["P1"].injury_weeks, 3)

    def test_healing_floors_at_zero(self):
        """TR-68: healing never goes negative and healthy players are unaffected."""
        r = roster(60); r.set_injury("P1", 1)
        for _ in range(3): r.advance_week()
        self.assertEqual(r.players["P1"].injury_weeks, 0)
        self.assertEqual(r.players["P2"].injury_weeks, 0)
        self.assertEqual(r.week, 4)

    def test_unknown_player_rejected(self):
        """TR-69: injuring a player not on the roster errors and adds nobody."""
        r = roster(60)
        self.assertFalse(r.set_injury("Ghost", 2))
        self.assertEqual(r.error, "UNKNOWN_PLAYER")
        self.assertNotIn("Ghost", r.players); self.assertEqual(r.count, 60)

    def test_cannot_advance_past_final_week(self):
        """TR-72: advancing from week 12 errors, keeps the week, and does not heal injuries."""
        r = roster(60); r.week = SEASON_WEEKS; r.set_injury("P1", 2)
        self.assertFalse(r.advance_week())
        self.assertEqual(r.error, "SEASON_OVER")
        self.assertEqual(r.week, SEASON_WEEKS)
        self.assertEqual(r.players["P1"].injury_weeks, 2)

    def test_full_season_has_twelve_weeks(self):
        """TR-72: from week 1 exactly 11 advances reach the final week."""
        r = roster(1)
        self.assertEqual(sum(r.advance_week() for _ in range(20)), SEASON_WEEKS - 1)


class TestDynastyProgression(unittest.TestCase):
    def season(self, prestige, wins, losses):
        r = roster(60); r.prestige = prestige
        for _ in range(wins): r.play_game(won=True)
        for _ in range(losses): r.play_game(won=False)
        r.rollover_season()
        return r

    def test_ten_wins_raises_prestige(self):
        """TR-70: a 10-win season lifts two school grades, but one season alone keeps 3 stars."""
        r = self.season(3, 10, 2)
        self.assertEqual((r.grades["championship_contender"], r.grades["brand_exposure"]), (7, 7))
        self.assertEqual(r.prestige, 3)

    def test_prestige_capped_at_max(self):
        """TR-70: prestige never exceeds 5 stars; the record is still archived."""
        r = self.season(MAX_PRESTIGE, 12, 0)
        self.assertEqual(r.prestige, MAX_PRESTIGE)
        self.assertIn({"season": 1, "wins": 12, "losses": 0, "games_played": 12}, r.history)

    def test_middling_season_keeps_prestige(self):
        """TR-70/TR-71: middling seasons leave prestige unchanged."""
        self.assertEqual(self.season(3, 9, 3).prestige, 3)
        self.assertEqual(self.season(3, 4, 8).prestige, 3)

    def test_three_wins_lowers_prestige(self):
        """TR-71: a 3-win season lowers Championship Contender and Brand Exposure only."""
        r = self.season(3, 3, 9)
        self.assertEqual((r.grades["championship_contender"], r.grades["brand_exposure"], r.grades["program_tradition"]), (5, 5, 6))
        self.assertEqual(r.prestige, 3)

    def test_prestige_floored_at_min(self):
        """TR-71: prestige never drops below half a star."""
        self.assertEqual(self.season(MIN_PRESTIGE, 0, 12).prestige, MIN_PRESTIGE)

    def test_offseason_heals_injuries(self):
        """TR-71: rollover clears every injury, even ones longer than the offseason."""
        r = roster(60); r.set_injury("P2", 5); r.set_injury("P3", 40)
        r.rollover_season()
        self.assertEqual(r.players["P2"].injury_weeks, 0)
        self.assertEqual(r.players["P3"].injury_weeks, 0)
        self.assertEqual(r.season, 2)

    def test_retry_does_not_change_prestige_twice(self):
        """TR-70: retrying an already-archived season does not bump grades again."""
        r = roster(60); r.prestige = 2
        for _ in range(10): r.play_game(won=True)
        r.rollover_season(season=1); r.rollover_season(season=1)
        self.assertEqual(r.grades["championship_contender"], 5)
        self.assertEqual(r.prestige, 2)

    def test_interrupted_rollover_keeps_prestige_week_and_injuries(self):
        """TR-71: a failed rollover leaves prestige, week and injuries unchanged."""
        r = roster(60); r.prestige = 2; r.week = 12; r.set_injury("P1", 3)
        for _ in range(10): r.play_game(won=True)
        def boom(): raise RuntimeError("crash")
        r._before_commit = boom
        with self.assertRaises(RuntimeError):
            r.rollover_season()
        self.assertEqual((r.prestige, r.week, r.players["P1"].injury_weeks), (2, 12, 3))

    def test_multi_season_dynasty_climb(self):
        """TR-70/TR-71: prestige tracks each season across a four-season dynasty."""
        r = roster(60); r.prestige = 2
        for wins in (11, 10, 2, 10):
            for _ in range(wins): r.play_game(won=True)
            for _ in range(12 - wins): r.play_game(won=False)
            r.rollover_season()
        # grade total 44 -> 47 -> 49 -> 46 -> 48 (11 grades): stays 2 stars; contender D+.. ends B-
        self.assertEqual(sum(r.grades.values()), 48)
        self.assertEqual(r.prestige, 2)
        self.assertEqual([h["wins"] for h in r.history], [11, 10, 2, 10])
        self.assertEqual(r.season, 5)


if __name__ == "__main__":
    unittest.main()
