"""Tests for CI threshold parsing and CI's behaviour on invalid values."""
import os, subprocess, sys, tempfile, unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from thresholds import parse_threshold, load_thresholds


class ParseThresholdTests(unittest.TestCase):
    def test_valid_values(self):
        for raw, want in [("0", 0), ("100", 100), ("80", 80), ("42.5", 42.5), (" 75 ", 75), ("90%", 90)]:
            with self.subTest(raw=raw):
                self.assertEqual(parse_threshold("MIN_PARITY", raw, 20), (want, None))

    def test_unset_or_blank_uses_default(self):
        for raw in (None, "", "   "):
            self.assertEqual(parse_threshold("MIN_COVERAGE", raw, 80), (80, None))

    def test_unparseable_values_rejected(self):
        for raw in ("abc", "eighty", "80..5", "1e", "--5", "80 %%"):
            for name in ("MIN_PARITY", "MIN_COVERAGE"):
                with self.subTest(name=name, raw=raw):
                    v, err = parse_threshold(name, raw, 50)
                    self.assertIsNone(v)
                    self.assertIn(name, err)
                    self.assertIn("not a number", err)

    def test_non_finite_values_rejected(self):
        for raw in ("nan", "inf", "-inf"):
            v, err = parse_threshold("MIN_COVERAGE", raw, 80)
            self.assertIsNone(v); self.assertIn("finite", err)

    def test_out_of_range_values_rejected(self):
        for raw in ("-1", "-0.01", "100.01", "150", "1000"):
            for name in ("MIN_PARITY", "MIN_COVERAGE"):
                with self.subTest(name=name, raw=raw):
                    v, err = parse_threshold(name, raw, 50)
                    self.assertIsNone(v)
                    self.assertIn("outside the allowed range 0-100", err)

    def test_load_reports_every_bad_threshold(self):
        values, errors = load_thresholds({"MIN_PARITY": "x", "MIN_COVERAGE": "200"})
        self.assertEqual(len(errors), 2)
        self.assertEqual(set(values), {"MIN_MUTATION_SCORE", "MIN_RULE_MUTATION_SCORE"})


class CiRejectsInvalidThresholdsTests(unittest.TestCase):
    def run_ci(self, **env):
        with tempfile.NamedTemporaryFile("r", suffix=".md", delete=False) as f:
            summary = f.name
        try:
            e = dict(os.environ, GITHUB_STEP_SUMMARY=summary, **env)
            res = subprocess.run([sys.executable, os.path.join(ROOT, "ci_summary.py")],
                                 env=e, capture_output=True, text=True)
            with open(summary) as f:
                return res.returncode, res.stdout + res.stderr, f.read()
        finally:
            os.remove(summary)

    def test_bad_parity_fails_ci_with_guidance(self):
        code, out, md = self.run_ci(MIN_PARITY="lots")
        self.assertEqual(code, 2)
        self.assertIn("Invalid CI threshold", md)
        self.assertIn("MIN_PARITY='lots' is not a number", md)

    def test_out_of_range_coverage_fails_ci_with_guidance(self):
        code, out, md = self.run_ci(MIN_COVERAGE="120")
        self.assertEqual(code, 2)
        self.assertIn("MIN_COVERAGE='120' is outside the allowed range 0-100", md)


if __name__ == "__main__":
    unittest.main()
