"""Regression tests for EA CFB 26 report-card prestige (TR-103..TR-108).
Team Prestige is the composite of the My School grades; only Championship
Contender, Brand Exposure and Program Tradition move with results.
Run: cd tests && python3 -m unittest test_report_card_prestige_regression
"""
import os, sys, unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from verify import (Roster, Player, GRADE_SCALE, SCHOOL_GRADES, GRADE_SEASON_CHANGES,
                    GRADE_MAX, prestige_from_grades, season_grades, MIN_PRESTIGE)

B = GRADE_SCALE.index("B")


def card(value=B, **over):
    g = {k: value for k in SCHOOL_GRADES}; g.update(over); return g


def play(r, wins):
    for i in range(12): r.play_game(won=i < wins)
    return r.rollover_season()


def team(value=B, **over):
    r = Roster()
    for i in range(60): r.add(Player(f"P{i}"))
    r.grades = card(value, **over); return r


class TestComposite(unittest.TestCase):
    def test_uniform_card_maps_to_stars(self):
        """TR-103: a report card of all one grade gives that grade's star level."""
        for i in range(1, GRADE_MAX + 1):
            self.assertEqual(prestige_from_grades(card(i)), i / 2)

    def test_average_rounds_to_nearest_half_star(self):
        """TR-103: two A+ grades on a B card lift the average over 6.5; one does not."""
        self.assertEqual(prestige_from_grades(card(academic_prestige=10)), 3)
        self.assertEqual(prestige_from_grades(card(academic_prestige=10, athletic_facilities=10)), 3.5)

    def test_setting_prestige_sets_uniform_card(self):
        """TR-103: 'program prestige is N stars' means every grade at that level."""
        r = Roster(); r.prestige = 4.5
        self.assertEqual(set(r.grades.values()), {9})
        self.assertEqual(sorted(r.grades), sorted(SCHOOL_GRADES))


class TestSeasonChanges(unittest.TestCase):
    def test_ten_wins_moves_contender_and_brand(self):
        """TR-104: 10 wins reaches the contender and brand thresholds, not tradition's."""
        r = team(); play(r, 10)
        self.assertEqual((r.grades["championship_contender"], r.grades["brand_exposure"],
                          r.grades["program_tradition"]), (B + 1, B + 1, B))
        self.assertEqual(r.prestige, 3)

    def test_threshold_boundaries(self):
        """TR-104/TR-105: each grade moves exactly at its up/down threshold, not one short."""
        for g, t in GRADE_SEASON_CHANGES.items():
            self.assertEqual(season_grades(card(), t["up_wins"])[g], B + 1, g)
            self.assertEqual(season_grades(card(), t["up_wins"] - 1)[g], B, g)
            self.assertEqual(season_grades(card(), t["down_wins"])[g], B - 1, g)
            self.assertEqual(season_grades(card(), t["down_wins"] + 1)[g], B, g)

    def test_losing_and_middling_seasons(self):
        """TR-105: 2 wins lowers all three; 6 wins changes none."""
        r = team(); play(r, 2)
        for g in GRADE_SEASON_CHANGES: self.assertEqual(r.grades[g], B - 1)
        before = dict(r.grades); play(r, 6)
        self.assertEqual(r.grades, before)

    def test_grades_and_prestige_are_bounded(self):
        """TR-106: grades stay within F..A+; an all-F card is still half a star."""
        self.assertEqual(prestige_from_grades(card(0)), MIN_PRESTIGE)
        r = team(0, championship_contender=GRADE_MAX); play(r, 12)
        self.assertEqual(r.grades["championship_contender"], GRADE_MAX)
        play(r, 0)
        self.assertEqual(r.grades["brand_exposure"], 0)
        self.assertEqual(r.prestige, MIN_PRESTIGE)

    def test_static_grades_never_move(self):
        """TR-107: only the result-driven grades change, even after a perfect season."""
        r = team(); play(r, 12)
        for g in SCHOOL_GRADES:
            self.assertEqual(r.grades[g], B + 1 if g in GRADE_SEASON_CHANGES else B, g)

    def test_retry_is_idempotent(self):
        """TR-108: a repeated rollover applies grade changes once."""
        r = team(); play(r, 10)
        self.assertFalse(r.rollover_season(season=1))
        self.assertEqual(r.grades["championship_contender"], B + 1)
        self.assertEqual(r.season, 2)

    def test_failed_rollover_keeps_grades(self):
        """TR-108: a rollover that fails before commit leaves the report card unchanged."""
        r = team()
        for _ in range(12): r.play_game(won=True)
        def boom(): raise RuntimeError("crash")
        r._before_commit = boom
        with self.assertRaises(RuntimeError): r.rollover_season()
        self.assertEqual(r.grades, card())


if __name__ == "__main__":
    unittest.main()
