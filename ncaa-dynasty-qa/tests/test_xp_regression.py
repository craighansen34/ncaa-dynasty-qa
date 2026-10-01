"""Dependency-free regression tests for Coach XP progression.
Protects TR-24's 550 XP result and the threshold formula 1000 + (level - 1) * 200.
Run: python3 -m unittest test_xp_regression.py  (from the folder containing verify.py)
"""
import unittest
from verify import Coach, threshold, MAX_LEVEL, START_SP

class TestCoachXPProgressionRegression(unittest.TestCase):
    def test_tr24_multi_level_overflow_preserves_550_xp(self):
        """Level 4 coach with 950 XP gains 3,000 XP -> Level 6, exactly 550 XP remaining."""
        coach = Coach()
        coach.level = 4
        coach.current_xp = 950
        coach.unspent_sp = START_SP + (coach.level - 1) * 10
        coach.spent_sp = 0
        coach.gain_xp(3000)
        self.assertEqual(coach.level, 6)
        self.assertEqual(coach.current_xp, 550)
        self.assertNotEqual(coach.current_xp, 1500, "Stale 1500 XP math regression")
        self.assertNotEqual(coach.current_xp, 750, "Static-threshold regression")
        self.assertEqual(coach.xp_to_next_level, 2000)
        self.assertEqual(coach.unspent_sp, 65)
        self.assertEqual(coach.total_earned_sp, 65)

    def test_threshold_formula_progression(self):
        for lvl in range(1, 50):
            self.assertEqual(threshold(lvl), 1000 + (lvl - 1) * 200)
        self.assertIsNone(threshold(50))

    def test_catches_static_threshold_bug(self):
        coach = Coach()
        coach.gain_xp(2100)  # 1000 (L1) + 1100 of L2's 1200
        self.assertEqual(coach.level, 2)
        self.assertEqual(coach.current_xp, 1100)

    def test_exact_threshold_boundary_crossing(self):
        c1 = Coach(); c1.gain_xp(999); self.assertEqual((c1.level, c1.current_xp), (1, 999))
        c2 = Coach(); c2.gain_xp(1000); self.assertEqual((c2.level, c2.current_xp), (2, 0))
        c3 = Coach(); c3.gain_xp(1001); self.assertEqual((c3.level, c3.current_xp), (2, 1))

    def test_level_50_cap_and_overflow_discard(self):
        c = Coach(); c.level = 49
        c.gain_xp(threshold(49) + 50000)
        self.assertEqual(c.level, 50)
        self.assertEqual(c.current_xp, 0)
        self.assertIsNone(c.xp_to_next_level)
        c.gain_xp(5000)  # no-op at cap
        self.assertEqual(c.level, 50); self.assertEqual(c.current_xp, 0)

    def test_sp_accounting_invariant_on_multi_level(self):
        c = Coach(); c.gain_xp(16200)  # exact sum of L1..L9 thresholds
        self.assertEqual(c.level, 10); self.assertEqual(c.current_xp, 0)
        self.assertEqual(c.unspent_sp + c.spent_sp, 15 + 9 * 10)

if __name__ == '__main__':
    unittest.main(verbosity=2)
