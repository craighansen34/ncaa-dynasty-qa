"""Season rollover tests (TR-59..TR-61): end-to-end dynasty runs through the
Gherkin step definitions, plus focused edge cases - empty rosters, players at
eligibility limits, retries, and interrupted (failed mid-way) rollovers.
Run: python3 -m unittest discover -s tests -p "test_*.py"  (from the folder containing verify.py)
"""
import os, sys, unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import verify
from verify import Roster, Player, MAX_ROSTER


def roster(n):
    r = Roster()
    for i in range(1, n + 1):
        r.add(Player(f"P{i}"))
    return r


def snapshot(r):
    return (r.season, list(r.history), r.wins, r.losses, r.games_played, r.error,
            {n: (p.year, p.redshirted, p.starter) for n, p in r.players.items()})


def run_steps(*phrases):
    """Execute Gherkin step phrases through the real verifier registry."""
    ctx = {'r': Roster()}
    for phrase in phrases:
        hits = verify.find_handlers(phrase)
        assert len(hits) == 1, f"{phrase!r} matched {len(hits)} step definitions"
        fn, m = hits[0]
        fn(ctx, **m.groupdict())
    return ctx['r']


class SeasonRolloverEndToEnd(unittest.TestCase):
    def test_full_season_through_steps(self):
        """TR-59/TR-60/TR-61: a season driven by Gherkin steps archives, graduates, advances and resets."""
        r = run_steps("the roster holds 85 players", "player P1 is a senior", "player P2 is a freshman",
                      "player P3 is promoted to starter", "the user attempts to sign player NewGuy to a full roster",
                      "the team wins 10 games and loses 2", "the season rollover executes",
                      "season 1 is archived with 10 wins and 2 losses", "the season record resets to 0 wins and 0 losses",
                      "the current season evaluates to 2", "player P1 is no longer on the roster",
                      "player P2 eligibility year evaluates to 2", "player P3 starter status evaluates to false",
                      "the roster full error is cleared", "roster size evaluates to 84")
        self.assertEqual(len(r.history), 1)

    def test_four_season_dynasty_class_progression(self):
        """TR-60: a recruiting class advances FR->SO->JR->SR, then graduates after the fourth rollover."""
        r = roster(20)
        for season in range(1, 5):
            for won in (True, True, False):
                r.play_game(won=won)
            self.assertTrue(r.rollover_season())
            if season < 4:
                self.assertEqual({p.year for p in r.players.values()}, {season + 1})
        self.assertEqual(r.count, 0)
        self.assertEqual([h["season"] for h in r.history], [1, 2, 3, 4])
        self.assertTrue(all((h["wins"], h["losses"]) == (2, 1) for h in r.history))
        self.assertEqual(r.season, 5)

    def test_mixed_classes_and_redshirt(self):
        """TR-60: mixed classes - seniors leave, redshirts hold their year, everyone else moves up."""
        r = roster(8)
        for i, year in enumerate([1, 2, 3, 4, 1, 2, 3, 4], start=1):
            r.players[f"P{i}"].year = year
        r.redshirt("P5")
        r.rollover_season()
        self.assertEqual({n: p.year for n, p in r.players.items()},
                         {"P1": 2, "P2": 3, "P3": 4, "P5": 1, "P6": 3, "P7": 4})
        self.assertFalse(r.players["P5"].redshirted)

    def test_reset_state_allows_new_season_signings(self):
        """TR-61: after rollover the roster-full error is cleared and graduations free signing slots."""
        r = roster(MAX_ROSTER)
        r.players["P1"].year = 4
        self.assertFalse(r.add(Player("Blocked")))
        r.rollover_season()
        self.assertIsNone(r.error)
        self.assertTrue(r.add(Player("Recruit")))
        self.assertEqual(r.count, MAX_ROSTER)


class SeasonRolloverIdempotency(unittest.TestCase):
    def test_retry_does_not_duplicate_archive_or_advance_twice(self):
        """TR-59: retrying the same season is a no-op - one archive entry, one year of advancement."""
        r = roster(5)
        r.play_game(won=True)
        self.assertTrue(r.rollover_season(season=1))
        after = snapshot(r)
        self.assertFalse(r.rollover_season(season=1))
        self.assertFalse(r.rollover_season(season=1))
        self.assertEqual(snapshot(r), after)
        self.assertEqual(len(r.history), 1)
        self.assertEqual(r.players["P1"].year, 2)

    def test_stale_season_request_is_rejected(self):
        """TR-59: a request for a season that isn't current changes nothing."""
        r = roster(3)
        before = snapshot(r)
        self.assertFalse(r.rollover_season(season=7))
        self.assertEqual(snapshot(r), before)


class SeasonRolloverEdgeCases(unittest.TestCase):
    def test_empty_roster(self):
        """TR-59: an empty roster still archives a record and moves to the next season."""
        r = Roster()
        self.assertTrue(r.rollover_season())
        self.assertEqual(r.history, [{"season": 1, "wins": 0, "losses": 0, "games_played": 0}])
        self.assertEqual((r.count, r.season), (0, 2))
        self.assertFalse(r.rollover_season(season=1))

    def test_all_seniors_leave_empty_roster(self):
        """TR-60: a roster made only of seniors is empty after rollover."""
        r = roster(4)
        for p in r.players.values():
            p.year = 4
        r.rollover_season()
        self.assertEqual(r.count, 0)

    def test_junior_becomes_senior_not_graduate(self):
        """TR-60: a year-3 player is at the limit's edge - advances to 4 and stays."""
        r = roster(1)
        r.players["P1"].year = 3
        r.rollover_season()
        self.assertEqual(r.players["P1"].year, 4)

    def test_redshirted_senior_stays_one_more_season(self):
        """TR-60: a redshirted senior keeps year 4 for one season, then graduates."""
        r = roster(1)
        r.players["P1"].year = 4
        r.redshirt("P1")
        r.rollover_season()
        self.assertEqual(r.players["P1"].year, 4)
        self.assertFalse(r.players["P1"].redshirted)
        r.rollover_season()
        self.assertNotIn("P1", r.players)


class InterruptedRollover(unittest.TestCase):
    def interrupt(self, r):
        def boom():
            raise RuntimeError("simulated crash mid-rollover")
        r._before_commit = boom

    def test_interrupted_rollover_leaves_roster_untouched(self):
        """TR-61: a failure before commit leaves record, players, starters and season unchanged."""
        r = roster(MAX_ROSTER)
        r.players["P1"].year = 4
        r.promote("P2")
        r.add(Player("Blocked"))
        r.play_game(won=True)
        before = snapshot(r)
        self.interrupt(r)
        with self.assertRaises(RuntimeError):
            r.rollover_season()
        self.assertEqual(snapshot(r), before)

    def test_retry_after_interruption_applies_exactly_once(self):
        """TR-59: after a crash, the retry succeeds once and a further retry is a no-op."""
        r = roster(3)
        r.play_game(won=False)
        self.interrupt(r)
        with self.assertRaises(RuntimeError):
            r.rollover_season(season=1)
        del r._before_commit
        self.assertTrue(r.rollover_season(season=1))
        self.assertFalse(r.rollover_season(season=1))
        self.assertEqual(len(r.history), 1)
        self.assertEqual(r.history[0]["losses"], 1)
        self.assertEqual(r.players["P1"].year, 2)


if __name__ == "__main__":
    unittest.main()


class RolloverAuditLog(unittest.TestCase):
    def fixed_clock(self, r, *stamps):
        import datetime
        it = iter(stamps)
        r.clock = lambda: datetime.datetime.fromisoformat(next(it))

    def test_entry_records_season_transitions_and_timestamp(self):
        """TR-59/TR-60: the audit entry has the archived season ID, record, each player's transition, and a UTC completion time."""
        r = roster(4)
        r.players["P1"].year = 4
        r.players["P2"].year = 2
        r.redshirt("P3")
        r.play_game(won=True)
        self.fixed_clock(r, "2026-12-01T18:00:00+00:00")
        r.rollover_season()
        [e] = r.audit_log
        self.assertEqual(e["season_id"], 1)
        self.assertEqual(e["archived_record"], {"season": 1, "wins": 1, "losses": 0, "games_played": 1})
        self.assertEqual(e["completed_at"], "2026-12-01T18:00:00+00:00")
        self.assertEqual(e["transitions"], [
            {"player": "P1", "from_year": 4, "to_year": None, "action": "graduated"},
            {"player": "P2", "from_year": 2, "to_year": 3, "action": "advanced"},
            {"player": "P3", "from_year": 1, "to_year": 1, "action": "redshirt_hold"},
            {"player": "P4", "from_year": 1, "to_year": 2, "action": "advanced"}])

    def test_default_clock_is_utc(self):
        """TR-59: without an injected clock the completion time is timezone-aware UTC."""
        r = roster(1)
        r.rollover_season()
        self.assertTrue(r.audit_log[0]["completed_at"].endswith("+00:00"))

    def test_one_entry_per_season_in_order(self):
        """TR-59: consecutive rollovers log seasons 1, 2, 3 with increasing timestamps."""
        r = roster(2)
        self.fixed_clock(r, "2026-01-01T00:00:00+00:00", "2027-01-01T00:00:00+00:00", "2028-01-01T00:00:00+00:00")
        for _ in range(3):
            r.rollover_season()
        self.assertEqual([e["season_id"] for e in r.audit_log], [1, 2, 3])
        stamps = [e["completed_at"] for e in r.audit_log]
        self.assertEqual(stamps, sorted(stamps))

    def test_retry_and_interruption_add_no_entries(self):
        """TR-61: a failed rollover and a no-op retry never write audit entries."""
        r = roster(2)
        def boom():
            raise RuntimeError("crash")
        r._before_commit = boom
        with self.assertRaises(RuntimeError):
            r.rollover_season(season=1)
        self.assertEqual(r.audit_log, [])
        del r._before_commit
        r.rollover_season(season=1)
        r.rollover_season(season=1)
        self.assertEqual(len(r.audit_log), 1)

    def test_empty_roster_logs_no_transitions(self):
        """TR-59: an empty roster still logs its archived season with no transitions."""
        r = Roster()
        r.rollover_season()
        self.assertEqual(r.audit_log[0]["transitions"], [])
        self.assertEqual(r.audit_log[0]["season_id"], 1)
