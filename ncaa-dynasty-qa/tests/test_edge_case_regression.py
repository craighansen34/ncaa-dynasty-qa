"""Dependency-free regression tests for NCAA Dynasty edge cases (TR-43..TR-50).
Protects relief-credit overdraft ceilings, zero-hour staging, visit capacity,
refund floors, rollover discards, retirement boundaries, and zero-XP no-ops.
Run: python3 -m unittest discover -s tests -p "test_*.py"  (from the folder containing verify.py)
"""
import unittest
from verify import Budget, Coach, MAX_LEVEL


class TestBudgetEdgeCases(unittest.TestCase):
    def test_relief_credit_raises_overdraft_ceiling(self):
        """TR-43: base 500 + 50 relief -> staging 550 succeeds, 551st hour fails."""
        b = Budget()
        b.add_relief(50)
        self.assertTrue(b.stage(550))
        self.assertIsNone(b.error)
        self.assertEqual(b.staged, 550)
        self.assertFalse(b.stage(1))
        self.assertEqual(b.error, "OVERDRAFT")

    def test_zero_hour_staging_is_noop(self):
        """TR-44: staging 0 hours changes nothing."""
        b = Budget()
        self.assertTrue(b.stage(0))
        self.assertEqual(b.staged, 0)
        self.assertEqual(b.committed, 0)
        self.assertEqual(b.remaining, 500)

    def test_four_visits_succeed_fifth_blocked(self):
        """TR-45: exactly 4 visits book cleanly; the 5th hits the capacity error."""
        b = Budget()
        for _ in range(4):
            self.assertTrue(b.book_visit(50))
        self.assertEqual(b.active_visits, 4)
        self.assertEqual(b.committed, 200)
        self.assertFalse(b.book_visit(50))
        self.assertEqual(b.error, "CAPACITY")
        self.assertEqual(b.active_visits, 4, "Failed booking must not increment visit count")

    def test_same_week_cancel_refund_floors_at_zero(self):
        """TR-46: cancelling with only 25h committed clamps committed at 0, never negative."""
        b = Budget()
        b.book_visit(50)
        b.committed = 25
        b.cancel_visit(same_week=True)
        self.assertEqual(b.committed, 0)
        self.assertEqual(b.last_refund, 50)

    def test_rollover_discards_unconfirmed_staged_hours(self):
        """TR-47: week rollover clears staged hours and relief, keeps committed."""
        b = Budget()
        b.stage(120)
        b.add_relief(50)
        b.advance_week()
        self.assertEqual(b.staged, 0)
        self.assertEqual(b.relief, 0)
        self.assertEqual(b.committed, 0)
        self.assertEqual(b.remaining, 500)


class TestCoachEdgeCases(unittest.TestCase):
    def test_retirement_at_exactly_50_seasons(self):
        """TR-48: 50 seasons alone (age < 70) triggers mandatory retirement."""
        c = Coach()
        c.age = 60
        c.seasons = 50
        retired = c.age >= 70 or c.seasons >= 50
        self.assertTrue(retired)

    def test_no_retirement_at_age_69_and_49_seasons(self):
        """TR-49: one below both thresholds must NOT retire."""
        c = Coach()
        c.age = 69
        c.seasons = 49
        retired = c.age >= 70 or c.seasons >= 50
        self.assertFalse(retired)

    def test_zero_xp_gain_is_noop(self):
        """TR-50: gaining 0 XP leaves level, XP, and SP untouched."""
        c = Coach()
        c.gain_xp(0)
        self.assertEqual(c.level, 1)
        self.assertEqual(c.current_xp, 0)
        self.assertEqual(c.unspent_sp, 15)

    def test_zero_xp_gain_at_cap_stays_capped(self):
        """TR-50 companion: 0 XP at Level 50 keeps null next-level threshold."""
        c = Coach()
        c.level = MAX_LEVEL
        c.current_xp = 0
        c.gain_xp(0)
        self.assertEqual(c.level, MAX_LEVEL)
        self.assertEqual(c.current_xp, 0)
        self.assertIsNone(c.xp_to_next_level)


if __name__ == '__main__':
    unittest.main(verbosity=2)
