"""Season-rollover regression tests: archived records stay unchanged, ineligible
players do not advance, and season-specific roster state resets correctly."""
import copy
import os, sys, unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from verify import Roster, Player, MAX_ROSTER


def play(r, wins, losses):
    for _ in range(wins):
        r.play_game(True)
    for _ in range(losses):
        r.play_game(False)


class ArchivedRecordsStayUnchanged(unittest.TestCase):
    def test_later_seasons_do_not_alter_earlier_archives(self):
        r = Roster()
        r.add(Player("QB", 1))
        play(r, 9, 3)
        r.rollover_season()
        first = copy.deepcopy(r.history[0])
        for w, l in ((11, 1), (2, 10), (6, 6)):
            play(r, w, l)
            r.rollover_season()
        self.assertEqual(r.history[0], first)
        self.assertEqual(first, {"season": 1, "wins": 9, "losses": 3, "games_played": 12})
        self.assertEqual([h["season"] for h in r.history], [1, 2, 3, 4])

    def test_new_season_games_do_not_touch_archive(self):
        r = Roster()
        play(r, 7, 5)
        r.rollover_season()
        play(r, 4, 0)
        self.assertEqual(r.history, [{"season": 1, "wins": 7, "losses": 5, "games_played": 12}])

    def test_retry_and_stale_requests_leave_archive_identical(self):
        r = Roster()
        play(r, 10, 2)
        r.rollover_season()
        before = copy.deepcopy(r.history)
        play(r, 3, 1)
        self.assertFalse(r.rollover_season(1))   # retry of an archived season
        self.assertFalse(r.rollover_season(5))   # season that isn't current
        self.assertEqual(r.history, before)
        self.assertEqual((r.wins, r.losses), (3, 1))  # current season untouched too

    def test_audit_log_record_matches_archive(self):
        r = Roster()
        play(r, 8, 4)
        r.rollover_season()
        play(r, 5, 7)
        r.rollover_season()
        self.assertEqual([e["archived_record"] for e in r.audit_log], r.history)


class IneligiblePlayersDoNotAdvance(unittest.TestCase):
    def test_graduated_senior_is_not_carried_to_year_five(self):
        r = Roster()
        r.add(Player("SR", 4))
        r.rollover_season()
        self.assertNotIn("SR", r.players)
        self.assertTrue(all(p.year <= 4 for p in r.players.values()))

    def test_redshirted_player_keeps_year_then_advances_next_season(self):
        r = Roster()
        rs = Player("RS", 2)
        rs.redshirted = True
        r.add(rs)
        r.rollover_season()
        self.assertEqual(r.players["RS"].year, 2)
        self.assertFalse(r.players["RS"].redshirted)  # redshirt used up
        r.rollover_season()
        self.assertEqual(r.players["RS"].year, 3)

    def test_only_eligible_players_move_up_in_mixed_roster(self):
        r = Roster()
        for name, year, red in (("FR", 1, False), ("RSFR", 1, True),
                                ("SR", 4, False), ("RSSR", 4, True)):
            p = Player(name, year)
            p.redshirted = red
            r.add(p)
        r.rollover_season()
        self.assertEqual({n: p.year for n, p in r.players.items()},
                         {"FR": 2, "RSFR": 1, "RSSR": 4})
        actions = {t["player"]: t["action"] for t in r.audit_log[0]["transitions"]}
        self.assertEqual(actions, {"FR": "advanced", "RSFR": "redshirt_hold",
                                   "SR": "graduated", "RSSR": "redshirt_hold"})

    def test_retry_does_not_advance_anyone_twice(self):
        r = Roster()
        r.add(Player("SO", 2))
        r.rollover_season()
        r.rollover_season(1)
        self.assertEqual(r.players["SO"].year, 3)


class SeasonStateResets(unittest.TestCase):
    def setUp(self):
        self.r = Roster()
        for i in range(MAX_ROSTER):
            self.r.add(Player(f"P{i}", 1 + i % 3))
        self.r.add(Player("extra", 1))          # blocked -> roster-full error set
        self.assertIsNotNone(self.r.error)
        self.r.promote("P0")
        self.r.set_injury("P1", 4)
        play(self.r, 6, 5)
        for _ in range(5):
            self.r.advance_week()
        self.r.rollover_season()

    def test_record_and_week_reset(self):
        r = self.r
        self.assertEqual((r.wins, r.losses, r.games_played, r.week, r.season), (0, 0, 0, 1, 2))

    def test_lineup_injuries_and_error_reset(self):
        r = self.r
        self.assertIsNone(r.error)
        self.assertFalse(any(p.starter for p in r.players.values()))
        self.assertTrue(all(p.injury_weeks == 0 for p in r.players.values()))

    def test_players_are_not_reset(self):
        # career state (roster membership, class year) carries over; only season state resets
        self.assertEqual(self.r.count, MAX_ROSTER)
        self.assertEqual(self.r.players["P0"].year, 2)


if __name__ == "__main__":
    unittest.main()
