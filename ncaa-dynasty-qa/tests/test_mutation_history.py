"""Unit tests for the CI mutation-history report (mutation_history.py)."""
import json, os, sys, tempfile, unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import mutation_history as mh


def art(outcomes, python="3.12.0"):
    """outcomes: {rule: [outcome, ...]} -> minimal mutation-results document."""
    return {"reproduce": {"python": python},
            "mutants": [{"rule": r, "outcome": o} for r, os_ in outcomes.items() for o in os_]}


class MutationHistoryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = os.path.join(self.tmp.name, "h.json")

    def tearDown(self):
        self.tmp.cleanup()

    def test_first_run_is_baseline(self):
        prev, _, rows, regs = mh.record(self.path, art({"a": ["killed"]}), run_id="r1")
        self.assertIsNone(prev)
        self.assertEqual([r["status"] for r in rows], ["new"])
        self.assertEqual(regs, [])
        self.assertIn("new baseline", "\n".join(mh.markdown(prev, rows, regs)))

    def test_survivor_increase_is_regression(self):
        mh.record(self.path, art({"a": ["killed", "killed"], "b": ["killed"]}), run_id="r1")
        prev, _, rows, regs = mh.record(self.path, art({"a": ["killed", "survived"], "b": ["killed"]}), run_id="r2")
        self.assertEqual(prev["run_id"], "r1")
        self.assertEqual([r["rule"] for r in regs], ["a"])
        self.assertIn("killed 2 → 1", regs[0]["details"])
        self.assertIn("survived 0 → 1", regs[0]["details"])
        md = "\n".join(mh.markdown(prev, rows, regs))
        self.assertIn("| `a` | 2 killed | 1 killed, 1 survived | ❌ regressed", md)
        self.assertIn("| `b` | 1 killed | 1 killed | unchanged |", md)
        self.assertIn("**1 rule(s) regressed since the previous run:** `a`", md)

    def test_unreached_and_ineffective_are_regressions(self):
        mh.record(self.path, art({"a": ["killed"], "b": ["killed"]}), run_id="r1")
        _, _, _, regs = mh.record(self.path, art({"a": ["unreached"], "b": ["ineffective"]}), run_id="r2")
        self.assertEqual(sorted(r["rule"] for r in regs), ["a", "b"])

    def test_removed_rule_is_regression(self):
        mh.record(self.path, art({"a": ["killed"], "b": ["killed"]}), run_id="r1")
        _, _, _, regs = mh.record(self.path, art({"a": ["killed"]}), run_id="r2")
        self.assertEqual(regs[0]["rule"], "b")
        self.assertIn("rule no longer has mutants", regs[0]["details"])

    def test_improvement_not_flagged(self):
        mh.record(self.path, art({"a": ["survived"]}), run_id="r1")
        _, _, rows, regs = mh.record(self.path, art({"a": ["killed"]}), run_id="r2")
        self.assertEqual(regs, [])
        self.assertEqual(rows[0]["status"], "improved")

    def test_compares_same_python_version_only(self):
        mh.record(self.path, art({"a": ["killed"]}, "3.12.0"), run_id="r1")
        mh.record(self.path, art({"a": ["survived"]}, "3.13.0"), run_id="r2")
        prev, _, _, regs = mh.record(self.path, art({"a": ["killed"]}, "3.12.0"), run_id="r3")
        self.assertEqual(prev["run_id"], "r1")
        self.assertEqual(regs, [])

    def test_history_is_capped_and_corrupt_file_resets(self):
        for i in range(mh.MAX_RUNS + 5):
            mh.record(self.path, art({"a": ["killed"]}), run_id=f"r{i}")
        self.assertEqual(len(json.load(open(self.path))["runs"]), mh.MAX_RUNS)
        open(self.path, "w").write("{broken")
        prev, _, _, _ = mh.record(self.path, art({"a": ["killed"]}))
        self.assertIsNone(prev)


if __name__ == "__main__":
    unittest.main()
