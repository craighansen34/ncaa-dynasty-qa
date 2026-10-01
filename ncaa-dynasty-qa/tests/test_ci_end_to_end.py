"""End-to-end tests of the CI entry point (ci_summary.py).

Each test runs ci_summary.py as a subprocess on a throwaway copy of the suite
and checks the exit code plus the job-summary Markdown a maintainer would see:
  exit 0 = all green, exit 1 = a test/verifier/coverage/parity/mutation failure,
  exit 2 = an invalid threshold setting (nothing was run).
Nested runs set QA_E2E_NESTED=1 so these tests don't recurse into themselves.

Runtime: the expensive part of CI (regression suite + mutation run) happens at
most twice per test run - once for a green copy of the suite and once for a
"weak" copy with the duplicate-ID enforcement tests disabled. Every other case
replays that cached result via QA_RESULTS_CACHE with its own thresholds/gate,
so ci_summary.py still re-runs the verifier and re-evaluates every threshold,
gate, artifact, schema check, history entry and summary line for real.
Malformed thresholds exit before anything runs, so they need no cache."""
import os, shutil, subprocess, sys, tempfile, unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NESTED = os.environ.get("QA_E2E_NESTED") == "1"
THRESHOLD_VARS = ["MIN_COVERAGE", "MIN_PARITY", "MIN_MUTATION_SCORE", "MIN_RULE_MUTATION_SCORE"]


def copy_suite():
    d = tempfile.mkdtemp()
    for name in ("verify.py", "ci_summary.py", "thresholds.py", "validate_artifact.py", "mutation_history.py",
                 "mutation-results.schema.json", "rules.json"):
        shutil.copy(os.path.join(ROOT, name), d)
    shutil.copytree(os.path.join(ROOT, "features"), os.path.join(d, "features"))
    shutil.copytree(os.path.join(ROOT, "tests"), os.path.join(d, "tests"),
                    ignore=shutil.ignore_patterns("__pycache__"))
    return d


DUPLICATE_ID_TESTS = ("test_duplicate_scenario_id_is_rejected",
                      "test_duplicate_across_feature_files_is_rejected",
                      "test_duplicate_id_used_by_exactly_two_scenarios")


def disable_duplicate_id_tests(d):
    p = os.path.join(d, "tests", "test_verifier_enforcement.py")
    src = open(p).read()
    for name in DUPLICATE_ID_TESTS:
        assert f"def {name}(" in src, name
        src = src.replace(f"def {name}(", f"def _disabled_{name}(")
    open(p, "w").write(src)


_SHARED = {}  # kind -> (suite_dir, cache_path); built lazily, removed in tearDownModule


def shared_suite(kind):
    """A suite copy plus the cache file of its one real (expensive) CI run.
    kind: "green" (unmodified) or "weak" (duplicate-ID enforcement tests disabled)."""
    if kind not in _SHARED:
        d = copy_suite()
        if kind == "weak":
            disable_duplicate_id_tests(d)
        cache = os.path.join(d, "results-cache.json")
        _SHARED[kind] = (d, cache)
        # Prime the cache with one real run. The nested unit suite reads the mutation
        # minimums too, so prime at 0% - the most lenient setting any replay uses -
        # and let each replay's ci_summary apply its own (stricter) thresholds.
        run_ci(d, QA_RESULTS_CACHE=cache, MIN_MUTATION_SCORE="0", MIN_RULE_MUTATION_SCORE="0",
               MIN_COVERAGE="0", MIN_PARITY="0")
        assert os.path.exists(cache), f"{kind} priming run did not write its cache"
    return _SHARED[kind]


def replay(kind, **env):
    d, cache = shared_suite(kind)
    return run_ci(d, QA_RESULTS_CACHE=cache, **env)


def tearDownModule():
    for d, _ in _SHARED.values():
        shutil.rmtree(d, ignore_errors=True)
    _SHARED.clear()


def have_coverage():
    try:
        import coverage  # noqa: F401
        return True
    except ImportError:
        return False


def run_ci(suite_dir, **env):
    summary = os.path.join(suite_dir, "summary.md")
    if os.path.exists(summary):
        os.remove(summary)  # shared suite dirs: each run gets its own job summary
    e = {k: v for k, v in os.environ.items() if k not in THRESHOLD_VARS}
    env.setdefault("MUTATION_GATE", "off")  # threshold tests opt into the strict gate explicitly
    e.update(env, GITHUB_STEP_SUMMARY=summary, QA_E2E_NESTED="1")
    res = subprocess.run([sys.executable, "ci_summary.py"], cwd=suite_dir, env=e,
                         capture_output=True, text=True, timeout=600)
    md = open(summary).read() if os.path.exists(summary) else ""
    return res.returncode, res.stdout + res.stderr, md


@unittest.skipIf(NESTED, "nested CI run")
class MalformedThresholdEndToEnd(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dir = copy_suite()

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.dir, ignore_errors=True)

    def assert_rejected(self, var, raw, phrase):
        code, out, md = run_ci(self.dir, **{var: raw})
        self.assertEqual(code, 2, f"{var}={raw!r} should exit 2\n{out[-1500:]}")
        self.assertIn("Invalid CI threshold", md)
        self.assertIn(f"{var}={raw!r}", md)
        self.assertIn(phrase, md)
        # Actionable: points at the workflow file and lists every setting with its default.
        self.assertIn(".github/workflows/qa.yml", md)
        for name in THRESHOLD_VARS:
            self.assertIn(f"`{name}`", md)
        # Nothing ran: no results table.
        self.assertNotIn("| Gherkin scenarios |", md)

    def test_unparseable_value_for_each_threshold(self):
        for var in THRESHOLD_VARS:
            with self.subTest(var=var):
                self.assert_rejected(var, "eighty", "is not a number")

    def test_out_of_range_value_for_each_threshold(self):
        for var, raw in zip(THRESHOLD_VARS, ["101", "-5", "150%", "1000"]):
            with self.subTest(var=var):
                self.assert_rejected(var, raw, "outside the allowed range 0-100")

    def test_non_finite_value(self):
        self.assert_rejected("MIN_PARITY", "nan", "not a finite number")

    def test_every_bad_threshold_is_reported_at_once(self):
        code, _, md = run_ci(self.dir, MIN_COVERAGE="x", MIN_PARITY="200")
        self.assertEqual(code, 2)
        self.assertIn("MIN_COVERAGE='x' is not a number", md)
        self.assertIn("MIN_PARITY='200' is outside the allowed range 0-100", md)


@unittest.skipIf(NESTED, "nested CI run")
class SurvivingMutationEndToEnd(unittest.TestCase):
    """Duplicate-ID enforcement tests disabled, so that rule's mutants survive."""

    @classmethod
    def setUpClass(cls):
        # Thresholds low enough that only the per-rule check can fail.
        cls.code, cls.out, cls.md = replay("weak", MIN_MUTATION_SCORE="50", MIN_COVERAGE="0", MIN_PARITY="0")

    def test_exits_1(self):
        self.assertEqual(self.code, 1, self.out[-2000:])

    def test_overall_score_passes_but_rule_fails(self):
        self.assertIn("| Mutation detection | ❌ fail |", self.md)
        self.assertRegex(self.md, r"\| `duplicate-id` \| [0-9]+/4 \| [0-9.]+% \| ❌ below minimum \|")
        self.assertIn("rule(s) below the per-rule minimum:** `duplicate-id`", self.md)
        for rule in ("regression-mapping", "missing-id", "no-steps", "unknown-step", "ambiguous-step",
                     "orphaned-rule", "orphaned-scenario", "scenario-execution"):
            self.assertRegex(self.md, rf"\| `{rule}` \| (\d+)/\1 \| 100.0% \| ✅ \|")

    def test_surviving_mutants_listed_with_code_change(self):
        self.assertIn("### Surviving mutations", self.md)
        self.assertIn("| duplicate-ID detection off-by-one | `tr_ids.count(t) > 1` | `tr_ids.count(t) > 2` |", self.md)
        self.assertIn("Add a unit test that fails for it", self.md)


@unittest.skipIf(NESTED, "nested CI run")
class PerRuleThresholdEndToEnd(unittest.TestCase):
    """MIN_RULE_MUTATION_SCORE: defaults, valid overrides, and actionable failures,
    on the weak suite where duplicate-id scores 0/4 = 0% and every other rule 100%."""

    def test_strict_gate_fails_on_survivors_despite_overrides(self):
        """The strict gate fails CI on any surviving mutant even when thresholds allow it."""
        code, out, md = replay("weak", MIN_RULE_MUTATION_SCORE="0", MIN_MUTATION_SCORE="0",
                               MIN_COVERAGE="0", MIN_PARITY="0", MUTATION_GATE="strict")
        self.assertEqual(code, 1, out[-2000:])
        self.assertIn("### Mutation gate failed", md)
        self.assertIn("| `duplicate-id` | duplicate-ID check disabled | survived |", md)
        self.assertIn("rule duplicate-id: 4 survived", out)

    def test_valid_override_below_weak_rule_passes(self):
        """A valid override of 0% lets the 0% duplicate-id rule pass."""
        if not have_coverage():
            self.skipTest("coverage not installed; a clean run requires it")
        code, out, md = replay("weak", MIN_RULE_MUTATION_SCORE="0", MIN_MUTATION_SCORE="50",
                               MIN_COVERAGE="0", MIN_PARITY="0")
        self.assertEqual(code, 0, out[-2000:])
        self.assertIn("Every rule must reach **0%**", md)
        self.assertRegex(md, r"\| `duplicate-id` \| 0/4 \| 0.0% \| ✅ \|")
        self.assertNotIn("below the per-rule minimum", md)

    def test_default_style_100_fails_with_actionable_detail(self):
        """At 100% the same results fail and name the weak rule and its survivors."""
        code, out, md = replay("weak", MIN_RULE_MUTATION_SCORE="100", MIN_MUTATION_SCORE="50",
                               MIN_COVERAGE="0", MIN_PARITY="0")
        self.assertEqual(code, 1, out[-2000:])
        self.assertIn("Every rule must reach **100%**", md)
        self.assertIn("rule(s) below the per-rule minimum:** `duplicate-id` (0.0%)", md)
        self.assertIn("### Surviving mutations", md)
        self.assertIn("Add a unit test that fails for it", md)


@unittest.skipIf(NESTED, "nested CI run")
class CleanRunEndToEnd(unittest.TestCase):
    def setUp(self):
        if not have_coverage():
            self.skipTest("coverage not installed; a clean run requires it")

    def test_green_suite_exits_0(self):
        code, out, md = replay("green")
        self.assertEqual(code, 0, out[-2000:])
        self.assertIn("| Gherkin scenarios | ✅ pass | 108/108 passed |", md)
        self.assertIn("### Mutant report", md)
        self.assertIn("effective 26/26 · executed 26/26 · killed 26", md)
        self.assertIn("| `duplicate-id` | duplicate-ID check disabled | ✅ | ✅ ", md)
        self.assertNotIn("❌", md)
        # Per-rule minimum defaults to 100% when MIN_RULE_MUTATION_SCORE is unset.
        self.assertIn("Every rule must reach **100%**", md)

    def test_green_suite_passes_strict_gate(self):
        code, out, md = replay("green", MUTATION_GATE="strict")
        self.assertEqual(code, 0, out[-2000:])
        self.assertIn("| Mutation gate (strict) | ✅ pass | 0 unkilled", md)

    def test_valid_per_rule_override_on_green_suite(self):
        """A valid MIN_RULE_MUTATION_SCORE override is accepted and shown in the summary."""
        code, out, md = replay("green", MIN_RULE_MUTATION_SCORE="80")
        self.assertEqual(code, 0, out[-2000:])
        self.assertIn("Every rule must reach **80%**", md)


@unittest.skipIf(NESTED, "nested CI run")
class ArtifactRetainedOnGateFailure(unittest.TestCase):
    """When the strict gate fails (surviving duplicate-ID mutants) AND the artifact
    has an invalid outcome value, CI must still leave mutation-results.json and its
    validation diagnostics on disk for upload. Reuses the weak suite's cached results
    with the 4 survivors' outcome corrupted to "survivd"."""

    @classmethod
    def setUpClass(cls):
        import json
        _, weak_cache = shared_suite("weak")
        cls.dir = copy_suite()
        disable_duplicate_id_tests(cls.dir)
        # Same results as the weak run, but with an outcome value the schema rejects.
        raw = json.load(open(weak_cache))
        bad = [m for m in raw["mut"]["results"] if m.get("outcome") == "survived"]
        assert len(bad) == 4, len(bad)
        for m in bad:
            m["outcome"] = "survivd"
        cache = os.path.join(cls.dir, "results-cache.json")
        json.dump(raw, open(cache, "w"))
        cls.code, cls.out, cls.md = run_ci(cls.dir, QA_RESULTS_CACHE=cache, MIN_MUTATION_SCORE="0",
                                           MIN_RULE_MUTATION_SCORE="0", MIN_COVERAGE="0", MIN_PARITY="0",
                                           MUTATION_GATE="strict")
        cls.artifact = os.path.join(cls.dir, "mutation-results.json")
        cls.validation = os.path.join(cls.dir, "mutation-results.validation.txt")

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.dir, ignore_errors=True)

    def test_ci_fails(self):
        self.assertEqual(self.code, 1, self.out[-2000:])
        self.assertIn("### Mutation gate failed", self.md)

    def test_artifact_retained_with_every_mutant(self):
        import json
        self.assertTrue(os.path.exists(self.artifact))
        doc = json.load(open(self.artifact))
        self.assertEqual(len(doc["mutants"]), 26)
        self.assertEqual(sum(m["outcome"] == "survivd" for m in doc["mutants"]), 4)
        self.assertIn("reproduce", doc)

    def test_validation_diagnostics_retained(self):
        self.assertTrue(os.path.exists(self.validation))
        text = open(self.validation).read()
        self.assertTrue(text.startswith("INVALID mutation-results.json"), text)
        self.assertEqual(text.count('invalid value "survivd"'), 4, text)
        self.assertIn("(mutant 'duplicate-ID check disabled')", text)
        self.assertIn("### mutation-results.json failed schema validation", self.md)

    def test_history_recorded_despite_failure(self):
        self.assertTrue(os.path.exists(os.path.join(self.dir, "mutation-history.json")))
        self.assertIn("### Mutation history", self.md)


@unittest.skipIf(NESTED, "nested CI run")
class ResultsCacheIsReplayOnly(unittest.TestCase):
    """Guard the speed-up itself: a replay must not re-run the expensive work,
    and must not reuse anything threshold-dependent from the priming run."""

    def test_replay_skips_regression_and_mutation_runs(self):
        code, out, md = replay("weak", MIN_COVERAGE="0", MIN_PARITY="0", MIN_MUTATION_SCORE="0",
                               MIN_RULE_MUTATION_SCORE="0")
        self.assertIn("Reusing regression + mutation results", out)
        self.assertNotIn("test_real_suite_is_clean", out)  # the unit suite did not run again
        self.assertIn("| Regression tests | ✅ pass |", md)

    def test_replay_reevaluates_coverage_threshold(self):
        if not have_coverage():
            self.skipTest("coverage not installed")
        code, _, md = replay("green", MIN_COVERAGE="100")
        self.assertEqual(code, 1)
        self.assertIn("### Coverage below minimum", md)


if __name__ == "__main__":
    unittest.main()
