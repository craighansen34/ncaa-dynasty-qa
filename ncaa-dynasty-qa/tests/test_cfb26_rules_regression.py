"""Regression tests for EA College Football 26 rules: recruiting hours,
scholarship offers, half-star prestige and SEC standings (TR-93..TR-102).
Run: cd tests && python3 -m unittest test_cfb26_rules_regression
"""
import os, sys, unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from verify import (RecruitingHours, Conference, Roster, Player, WEEKLY_HOURS,
                    PRESEASON_HOURS, PROSPECT_WEEKLY_HOUR_CAP, OFFER_HOUR_COST,
                    SCHOLARSHIP_OFFERS_PER_SEASON, MIN_PRESTIGE, MAX_PRESTIGE)


def week(prestige):
    h = RecruitingHours(prestige); h.start_week(); return h


class TestRecruitingHours(unittest.TestCase):
    def test_hours_table_every_half_star(self):
        """TR-93: every half-star level from 0.5 to 5 has preseason and weekly hours."""
        levels = [x / 2 for x in range(1, 11)]
        self.assertEqual(sorted(WEEKLY_HOURS), levels)
        self.assertEqual(sorted(PRESEASON_HOURS), levels)
        self.assertEqual((WEEKLY_HOURS[5], WEEKLY_HOURS[3], WEEKLY_HOURS[0.5]), (1000, 600, 300))
        for s in levels:
            self.assertGreater(PRESEASON_HOURS[s], WEEKLY_HOURS[s])

    def test_preseason_then_weekly(self):
        """TR-93: preseason bonus first, then the weekly amount."""
        h = RecruitingHours(5); self.assertEqual(h.hours, 1250)
        h.start_week(); self.assertEqual(h.hours, 1000)

    def test_unused_hours_do_not_carry(self):
        """TR-94: leftover hours are lost when the next week starts."""
        h = week(3); h.spend("Smith", 50); self.assertEqual(h.hours, 550)
        h.start_week(); self.assertEqual(h.hours, 600)

    def test_prospect_cap(self):
        """TR-95: over 50 hours on one prospect in a week is rejected and changes nothing."""
        h = week(3); self.assertTrue(h.spend("Smith", 40))
        self.assertFalse(h.spend("Smith", 20)); self.assertEqual(h.error, "PROSPECT_HOUR_CAP")
        self.assertEqual((h.hours, h.spent["Smith"]), (560, 40))
        self.assertTrue(h.spend("Smith", 10))  # exactly the cap is fine
        self.assertEqual(h.spent["Smith"], PROSPECT_WEEKLY_HOUR_CAP)
        h.start_week(); self.assertTrue(h.spend("Smith", 50))

    def test_not_enough_hours(self):
        """TR-96: spending more than remains is rejected; zero or negative too."""
        h = week(0.5); h.hours = 5
        self.assertFalse(h.spend("A", 10)); self.assertEqual(h.error, "NOT_ENOUGH_HOURS")
        self.assertEqual(h.hours, 5)
        self.assertFalse(h.spend("A", 0)); self.assertEqual(h.error, "INVALID_HOURS")
        self.assertTrue(h.spend("A", 5)); self.assertEqual(h.hours, 0)


class TestScholarshipOffers(unittest.TestCase):
    def test_offer_costs_hours_and_one_offer(self):
        """TR-97: an offer costs 5 hours and one of 35; offering twice is rejected."""
        h = week(3); self.assertTrue(h.offer("Smith"))
        self.assertEqual((h.hours, h.offers_left), (600 - OFFER_HOUR_COST, SCHOLARSHIP_OFFERS_PER_SEASON - 1))
        self.assertFalse(h.offer("Smith")); self.assertEqual(h.error, "ALREADY_OFFERED")
        self.assertEqual(h.offers_left, 34)

    def test_offer_needs_hours(self):
        """TR-97: an offer with fewer than 5 hours left is rejected and keeps the offer."""
        h = week(3); h.hours = 4
        self.assertFalse(h.offer("Smith")); self.assertEqual(h.error, "NOT_ENOUGH_HOURS")
        self.assertEqual(h.offers_left, 35)

    def test_36th_offer_rejected_and_season_resets(self):
        """TR-98: 35 offers per season; a new season restores all 35."""
        h = RecruitingHours(5)
        for i in range(35): self.assertTrue(h.offer(f"P{i}"))
        self.assertFalse(h.offer("Extra")); self.assertEqual(h.error, "NO_OFFERS_LEFT")
        h.new_season()
        self.assertEqual((h.offers_left, h.hours, h.week), (35, 1250, 0))
        self.assertTrue(h.offer("P0"))  # last season's offers don't block this season


class TestHalfStarPrestige(unittest.TestCase):
    def season(self, prestige, wins):
        r = Roster(); r.add(Player("P1")); r.prestige = prestige
        for i in range(12): r.play_game(won=i < wins)
        r.rollover_season(); return r

    def test_half_star_steps_and_limits(self):
        """TR-99: prestige moves half a star, between 0.5 and 5."""
        self.assertEqual(self.season(3, 10).prestige, 3)   # one season: grade total 66 -> 68
        self.assertEqual(self.season(3, 3).prestige, 3)    # 66 -> 64
        self.assertEqual(self.season(3.5, 11).prestige, 3.5)  # 77 -> 80, average 7.27 rounds to 7

        self.assertEqual(self.season(4.5, 12).prestige, 4.5)  # 99 -> 102: one season is not enough
        self.assertEqual(self.season(MAX_PRESTIGE, 12).prestige, MAX_PRESTIGE)
        self.assertEqual(self.season(1, 0).prestige, 1)  # 22 -> 19 still rounds to 1 star
        self.assertEqual(self.season(MIN_PRESTIGE, 0).prestige, 0.5)

    def test_new_prestige_sets_recruiting_hours(self):
        """TR-99: next season's hours come from the updated prestige."""
        r = self.season(3, 11)
        for i in range(12): r.play_game(won=i < 11)
        r.rollover_season()
        self.assertEqual(r.prestige, 3.5)
        self.assertEqual(week(r.prestige).hours, 700)


class TestSecStandings(unittest.TestCase):
    def conf(self, *games):
        c = Conference()
        for w, l in games: c.record(w, l)
        return c

    def test_by_win_percentage(self):
        """TR-100: best conference winning percentage ranks first."""
        c = self.conf(("Georgia", "Alabama"), ("Georgia", "Texas"), ("Alabama", "Texas"))
        self.assertEqual(c.standings(), ["Georgia", "Alabama", "Texas"])
        self.assertEqual(c.conf_record("Alabama"), (1, 1))

    def test_percentage_not_raw_wins(self):
        """TR-100: 2-0 ranks above 2-1 (percentage, not total wins)."""
        c = self.conf(("A", "X"), ("A", "Y"), ("B", "X"), ("B", "Y"), ("Z", "B"))
        self.assertLess(c.standings().index("A"), c.standings().index("B"))

    def test_head_to_head(self):
        """TR-101: tied teams are ordered by their head-to-head result."""
        c = self.conf(("Texas", "Georgia"), ("Georgia", "Auburn"), ("Texas", "Auburn"),
                      ("Georgia", "Florida"), ("Florida", "Texas"))
        self.assertEqual(c.standings(), ["Texas", "Georgia", "Florida", "Auburn"])
        flipped = self.conf(("Georgia", "Texas"), ("Georgia", "Auburn"), ("Texas", "Auburn"),
                            ("Texas", "Florida"), ("Florida", "Georgia"))
        self.assertEqual(flipped.standings()[:2], ["Georgia", "Texas"])

    def test_common_opponents(self):
        """TR-102: teams that did not meet are split by record vs common opponents."""
        c = self.conf(("Alabama", "Auburn"), ("Alabama", "LSU"), ("Missouri", "Alabama"),
                      ("Georgia", "Auburn"), ("LSU", "Georgia"), ("Georgia", "Kentucky"))
        self.assertEqual(c.standings(), ["Missouri", "Alabama", "Georgia", "LSU", "Auburn", "Kentucky"])

    def test_common_opponents_ignores_non_common_games(self):
        """TR-102: a win over a team only one side played doesn't count in the tiebreak."""
        c = self.conf(("Georgia", "Auburn"), ("Georgia", "LSU"), ("Kentucky", "Georgia"),
                      ("Alabama", "Auburn"), ("LSU", "Alabama"), ("Alabama", "Vanderbilt"))
        order = c.standings()
        self.assertLess(order.index("Georgia"), order.index("Alabama"))


if __name__ == "__main__":
    unittest.main()
