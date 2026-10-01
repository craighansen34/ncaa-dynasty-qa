"""Dependency-free regression tests for player management, roster changes,
and season progression (TR-51..TR-61).
Protects the 85-man roster cap, cut/transfer departures, redshirt eligibility
preservation, senior graduation, year advancement, depth-chart promotion,
and season record tracking.
Run: python3 -m unittest discover -s tests -p "test_*.py"  (from the folder containing verify.py)
"""
import unittest
from verify import Roster, Player, MAX_ROSTER


def populated_roster(n):
    r = Roster()
    for i in range(1, n + 1):
        r.add(Player(f"P{i}"))
    return r


class TestRosterCap(unittest.TestCase):
    def test_cut_frees_roster_slot(self):
        """TR-51: cutting a player from a full 85-man roster drops the count to 84."""
        r = populated_roster(MAX_ROSTER)
        r.cut("P1")
        self.assertEqual(r.count, 84)
        self.assertNotIn("P1", r.players)

    def test_signing_at_cap_blocked(self):
        """TR-52: signing at the 85-man cap fails with ROSTER_FULL and changes nothing."""
        r = populated_roster(MAX_ROSTER)
        self.assertFalse(r.add(Player("NewGuy")))
        self.assertEqual(r.error, "ROSTER_FULL")
        self.assertEqual(r.count, MAX_ROSTER)
        self.assertNotIn("NewGuy", r.players)


class TestRosterDepartures(unittest.TestCase):
    def test_transfer_portal_removes_player(self):
        """TR-53: a transfer-portal departure removes the player and decrements the count."""
        r = populated_roster(70)
        r.transfer_out("P1")
        self.assertEqual(r.count, 69)
        self.assertNotIn("P1", r.players)


class TestSeasonProgression(unittest.TestCase):
    def test_redshirt_preserves_eligibility(self):
        """TR-54: a redshirted freshman stays at year 1 after the offseason advance."""
        r = populated_roster(60)
        r.redshirt("P1")
        r.advance_season()
        self.assertIn("P1", r.players)
        self.assertEqual(r.players["P1"].year, 1)
        self.assertFalse(r.players["P1"].redshirted, "Redshirt is consumed after one season")

    def test_seniors_graduate(self):
        """TR-55: seniors are removed from the roster at the offseason advance."""
        r = populated_roster(60)
        r.players["P1"].year = 4
        r.advance_season()
        self.assertNotIn("P1", r.players)
        self.assertEqual(r.count, 59)

    def test_returning_players_advance_a_year(self):
        """TR-56: a returning freshman advances to year 2 at the offseason advance."""
        r = populated_roster(60)
        r.advance_season()
        self.assertEqual(r.players["P1"].year, 2)

    def test_promotion_to_starter(self):
        """TR-57: promoting a bench player sets starter status."""
        r = populated_roster(60)
        self.assertFalse(r.players["P1"].starter)
        r.promote("P1")
        self.assertTrue(r.players["P1"].starter)

    def test_season_record_tracking(self):
        """TR-58: a 9-3 season records 9 wins, 3 losses, 12 games played."""
        r = populated_roster(60)
        for _ in range(9):
            r.play_game(won=True)
        for _ in range(3):
            r.play_game(won=False)
        self.assertEqual((r.wins, r.losses, r.games_played), (9, 3, 12))


class TestSeasonRollover(unittest.TestCase):
    def test_rollover_archives_record_and_resets(self):
        """TR-59: rollover archives 9-3 as season 1, zeroes the record, moves to season 2."""
        r = populated_roster(60)
        for w in [True] * 9 + [False] * 3:
            r.play_game(won=w)
        r.rollover_season()
        self.assertEqual(r.history, [{"season": 1, "wins": 9, "losses": 3, "games_played": 12}])
        self.assertEqual((r.wins, r.losses, r.games_played, r.season), (0, 0, 0, 2))

    def test_rollover_advances_eligible_players(self):
        """TR-60: rollover graduates seniors, advances returners, keeps redshirts at their year."""
        r = populated_roster(60)
        r.players["P1"].year = 4
        r.redshirt("P3")
        r.rollover_season()
        self.assertNotIn("P1", r.players)
        self.assertEqual(r.players["P2"].year, 2)
        self.assertEqual(r.players["P3"].year, 1)
        self.assertEqual(r.count, 59)

    def test_rollover_resets_season_state(self):
        """TR-61: starters and the roster-full error are season-specific and reset."""
        r = populated_roster(MAX_ROSTER)
        r.promote("P2")
        self.assertFalse(r.add(Player("NewGuy")))
        r.rollover_season()
        self.assertFalse(r.players["P2"].starter)
        self.assertIsNone(r.error)

    def test_multiple_rollovers_keep_full_history(self):
        """TR-59 companion: each rollover appends; earlier seasons are never overwritten."""
        r = populated_roster(10)
        r.play_game(won=True); r.rollover_season()
        r.play_game(won=False); r.rollover_season()
        self.assertEqual([h["season"] for h in r.history], [1, 2])
        self.assertEqual((r.history[0]["wins"], r.history[1]["losses"]), (1, 1))


if __name__ == '__main__':
    unittest.main()
