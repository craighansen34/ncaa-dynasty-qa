"""Unit tests that run the REAL verify.run_verifier against injected feature text,
so the enforcement rules (unique IDs, regression mapping, well-formed scenarios)
can't silently regress."""
import contextlib, io, os, sys, tempfile, unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import verify


class VerifierEnforcementTests(unittest.TestCase):
    def setUp(self):
        self._orig = (verify.RECRUITING, verify.COACH, verify.ROSTER)

    def tearDown(self):
        verify.RECRUITING, verify.COACH, verify.ROSTER = self._orig

    def run_with(self, recruiting=None, coach=None, roster=None, tests_dir=None):
        if recruiting is not None: verify.RECRUITING = recruiting
        if coach is not None: verify.COACH = coach
        if roster is not None: verify.ROSTER = roster
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            ok = verify.run_verifier(strict=False, tests_dir=tests_dir)
        return ok, buf.getvalue(), list(verify.LAST_RESULT['audit_errors'])

    def test_real_suite_is_clean(self):
        ok, out, errors = self.run_with()
        self.assertTrue(ok, out)
        self.assertEqual(errors, [])

    def test_duplicate_scenario_id_is_rejected(self):
        dup = self._orig[1].replace("Scenario: TR-50", "Scenario: TR-49", 1)
        ok, out, errors = self.run_with(coach=dup)
        self.assertFalse(ok)
        self.assertTrue(any("DUPLICATE" in e and "TR-49" in e for e in errors), errors)
        self.assertIn("HALTING BEFORE EXECUTION", out)

    def test_duplicate_across_feature_files_is_rejected(self):
        dup = self._orig[1].replace("Scenario: TR-22", "Scenario: TR-01", 1)
        ok, _, errors = self.run_with(coach=dup)
        self.assertFalse(ok)
        self.assertTrue(any("DUPLICATE" in e and "TR-01" in e for e in errors), errors)

    def test_missing_regression_mapping_is_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            with open(os.path.join(d, "test_only_some.py"), "w") as f:
                f.write('"""covers TR-43 TR-44 TR-45 TR-46 TR-47 TR-48 TR-50"""\n')
            ok, _, errors = self.run_with(tests_dir=d)
        self.assertFalse(ok)
        missing = [e for e in errors if "MISSING REGRESSION TESTS" in e]
        self.assertEqual(len(missing), 1, errors)
        self.assertIn("TR-49", missing[0])
        self.assertNotIn("TR-43", missing[0])

    def test_baseline_scenarios_do_not_need_mapping(self):
        with tempfile.TemporaryDirectory() as d:
            with open(os.path.join(d, "test_x.py"), "w") as f:
                f.write(" ".join(f"TR-{i}" for i in range(43, 109)))
            ok, out, errors = self.run_with(tests_dir=d)
        self.assertTrue(ok, errors)

    def test_scenario_without_id_is_rejected(self):
        bad = self._orig[1] + "\n  Scenario: coach does something undocumented\n    Given coach remains Level 1\n"
        ok, _, errors = self.run_with(coach=bad)
        self.assertFalse(ok)
        self.assertTrue(any("MISSING TR ID" in e for e in errors), errors)

    def test_scenario_without_steps_is_rejected(self):
        import re
        bad = re.sub(r"(Scenario: TR-50[^\n]*\n)((?:[ \t]*(?:Given|When|Then|And|But) [^\n]*\n?)+)", r"\1", self._orig[1])
        ok, _, errors = self.run_with(coach=bad)
        self.assertFalse(ok)
        self.assertTrue(any("no steps" in e and "TR-50" in e for e in errors), errors)

    def test_undefined_step_phrase_is_rejected(self):
        import re
        bad = re.sub(r"(Scenario: TR-50[^\n]*\n)", r"\1    Given the coach performs an undefined action\n", self._orig[1], count=1)
        ok, out, errors = self.run_with(coach=bad)
        self.assertFalse(ok)
        self.assertTrue(any("UNMATCHED" in e for e in errors), errors)
        self.assertIn("MISMATCH [TR-50]", out)


    def test_duplicate_id_used_by_exactly_two_scenarios(self):
        """Added via the surviving-mutant advisor: kills the duplicate-ID off-by-one mutant
        (count > 1 -> count > 2) even without the other duplicate-ID tests."""
        import re

        texts = list(self._orig)
        heading = re.compile(
            r"(?m)^[^\n]*\bScenario(?: Outline)?:[^\n]*\b(TR-\d+)\b"
        )
        scenarios = [
            (index, match)
            for index, text in enumerate(texts)
            for match in heading.finditer(text)
        ]
        self.assertGreaterEqual(len(scenarios), 2)
        original_ids = [match.group(1) for _, match in scenarios]
        self.assertEqual(len(original_ids), len(set(original_ids)))

        duplicate_id = original_ids[0]
        index, second = scenarios[1]
        start, end = second.span(1)
        texts[index] = texts[index][:start] + duplicate_id + texts[index][end:]

        mutated_ids = [
            match.group(1)
            for text in texts
            for match in heading.finditer(text)
        ]
        self.assertEqual(mutated_ids.count(duplicate_id), 2)

        ok, _, errors = self.run_with(recruiting=texts[0], coach=texts[1])

        self.assertFalse(ok)
        self.assertTrue(
            any("DUPLICATE TRACEABILITY IDs" in error for error in errors),
            errors,
        )


    def test_regression_mapping_ignores_non_test_python_files(self):
        """Advisor-generated: kills mutant 'test file prefix loosened to any .py'."""
        import os
        import re
        import tempfile

        ids = sorted(set(re.findall(r"TR-\d+", "\n".join(self._orig))))
        self.assertTrue(any(int(tr_id[3:]) > 42 for tr_id in ids))

        with tempfile.TemporaryDirectory() as tests_dir:
            helper_path = os.path.join(tests_dir, "coverage_helper.py")
            with open(helper_path, "w", encoding="utf-8") as handle:
                handle.write("# " + " ".join(ids) + "\n")

            _, _, errors = self.run_with(
                recruiting=self._orig[0],
                coach=self._orig[1],
                tests_dir=tests_dir,
            )
            self.assertTrue(
                any("MISSING REGRESSION TESTS" in error for error in errors),
                "IDs in coverage_helper.py must not count as regression tests",
            )

            # The same content should count once the filename is eligible.
            os.rename(helper_path, os.path.join(tests_dir, "test_coverage.py"))
            _, _, errors = self.run_with(
                recruiting=self._orig[0],
                coach=self._orig[1],
                tests_dir=tests_dir,
            )
            self.assertFalse(
                any("MISSING REGRESSION TESTS" in error for error in errors),
                errors,
            )

    def test_regression_mapping_does_not_accept_longer_id_prefix(self):
        """Advisor-generated: kills mutant 'ID match truncated to prefix'."""
        import os
        import re
        import tempfile

        recruiting, coach, roster = self._orig
        ids = set(re.findall(r"TR-\d+", recruiting + "\n" + coach + "\n" + roster))
        target = "TR-43"
        self.assertIn(target, ids)

        # Cover every existing ID except TR-43; name TR-430 instead.
        references = (ids - {target}) | {target + "0"}
        with tempfile.TemporaryDirectory() as tests_dir:
            path = os.path.join(tests_dir, "test_mapping.py")
            with open(path, "w", encoding="utf-8") as handle:
                handle.write("# " + " ".join(sorted(references)) + "\n")

            ok, stdout, errors = self.run_with(
                recruiting=recruiting,
                coach=coach,
                tests_dir=tests_dir,
            )

        self.assertFalse(ok, stdout)
        self.assertTrue(
            any(
                "MISSING REGRESSION TESTS" in error
                and re.search(r"\bTR-43\b", error)
                for error in errors
            ),
            errors,
        )

    def test_but_only_scenarios_are_not_malformed(self):
        """Advisor-generated: kills mutant 'But-steps not counted as steps'."""
        import re

        # Preserve existing scenario IDs and step phrases; change only keywords.
        step_keyword = re.compile(
            r"^([ \t]*(?:[-*][ \t]+)?)(?:Given|When|Then|And)(?=[ \t])",
            re.MULTILINE,
        )
        recruiting, recruiting_count = step_keyword.subn(
            r"\1But", self._orig[0]
        )
        coach, coach_count = step_keyword.subn(
            r"\1But", self._orig[1]
        )
        self.assertGreater(
            recruiting_count + coach_count, 0,
            "Fixture must contain step keywords to replace",
        )

        _, stdout, audit_errors = self.run_with(
            recruiting=recruiting, coach=coach
        )

        # Isolate the no-steps audit from execution or other audit failures.
        malformed = [
            error for error in audit_errors
            if "MALFORMED SCENARIOS" in error
        ]
        self.assertEqual(malformed, [], stdout)

    def test_exactly_two_step_handlers_are_ambiguous(self):
        """Advisor-generated: kills mutant 'ambiguity threshold raised'."""
        import re

        # Manual fix: use phrases the verifier actually parses (raw text also has non-scenario lines).
        phrases = [t for text in self._orig for sc in verify.parse_feature(text) for _, t in sc["steps"]]
        phrase = next(
            (p for p in phrases if len(verify.find_handlers(p)) == 1),
            None,
        )
        self.assertIsNotNone(phrase, "Fixture needs a uniquely matched step")
        handler = verify.find_handlers(phrase)[0][0]

        saved = list(verify.REGISTRY)
        try:
            verify.REGISTRY.append(
                (re.compile(re.escape(phrase) + r"\Z"), handler)
            )
            self.assertEqual(len(verify.find_handlers(phrase)), 2)

            _, _, errors = self.run_with(
                recruiting=self._orig[0],
                coach=self._orig[1],
            )
            self.assertTrue(
                any("AMBIGUOUS STEP HANDLERS" in error for error in errors),
                errors,
            )
        finally:
            verify.REGISTRY[:] = saved

    def test_ambiguous_step_handlers_are_rejected(self):
        """Advisor-generated: kills mutant 'ambiguity check disabled'."""
        import re

        # Manual fix: use phrases the verifier actually parses (raw text also has non-scenario lines).
        phrase = [t for text in self._orig for sc in verify.parse_feature(text) for _, t in sc["steps"]][0]
        self.assertEqual(len(verify.find_handlers(phrase)), 1)

        def extra_handler(*args, **kwargs):
            pass

        saved = list(verify.REGISTRY)
        try:
            verify.REGISTRY.append(
                (re.compile(re.escape(phrase) + r"\Z"), extra_handler)
            )
            self.assertEqual(len(verify.find_handlers(phrase)), 2)

            ok, stdout, audit_errors = self.run_with(
                recruiting=self._orig[0], coach=self._orig[1]
            )
            self.assertTrue(
                any("AMBIGUOUS STEP HANDLERS" in error
                    for error in audit_errors),
                (stdout, audit_errors),
            )
            self.assertFalse(ok)
        finally:
            verify.REGISTRY[:] = saved

    # ---- Advisor-generated tests for orphaned-rule, orphaned-scenario and
    # scenario-execution mutants (reviewed before adding) ----
    def _drop_scenario(self, text, tr):
        import re
        out, n = re.subn(rf"^[ \t]*Scenario: {tr}\b.*?(?=^[ \t]*Scenario:|\Z)", "", text,
                         count=1, flags=re.MULTILINE | re.DOTALL)
        self.assertEqual(n, 1, f"Fixture must remove the {tr} scenario")
        return out

    def test_deleted_scenario_is_reported_as_orphaned_rule(self):
        ok, stdout, audit_errors = self.run_with(roster=self._drop_scenario(self._orig[2], "TR-51"))
        self.assertFalse(ok, stdout)
        self.assertIn("TR-51", "\n".join(e for e in audit_errors if "ORPHANED RULES" in e), audit_errors)

    def test_missing_rule_above_baseline_is_rejected(self):
        ok, _, audit_errors = self.run_with(roster=self._drop_scenario(self._orig[2], "TR-72"))
        self.assertFalse(ok)
        self.assertTrue(any("ORPHANED RULES" in e and "TR-72" in e for e in audit_errors), audit_errors)

    def test_out_of_range_scenario_reports_orphaned_scenario(self):
        import re
        recruiting = re.sub(r"(Scenario: *)TR-\d+\b", r"\g<1>TR-199", self._orig[0], count=1)
        self.assertNotEqual(recruiting, self._orig[0])
        ok, _, audit_errors = self.run_with(recruiting=recruiting)
        self.assertFalse(ok)
        self.assertIn("TR-199", "\n".join(e for e in audit_errors if "ORPHANED SCENARIOS" in e))

    def test_three_digit_id_is_reported_as_orphaned_scenario(self):
        roster = self._orig[2].replace("Scenario: TR-51 ", "Scenario: TR-150 ", 1)
        self.assertNotEqual(roster, self._orig[2])
        ok, _, audit_errors = self.run_with(roster=roster)
        self.assertFalse(ok)
        self.assertIn("TR-150", "\n".join(e for e in audit_errors if "ORPHANED SCENARIOS" in e))

    def test_failing_scenario_fails_run(self):
        roster = self._orig[2].replace("roster size evaluates to 84", "roster size evaluates to 83", 1)
        self.assertNotEqual(roster, self._orig[2], "Fixture must change a Then value")
        ok, stdout, audit_errors = self.run_with(roster=roster)
        self.assertEqual(audit_errors, [], stdout)
        self.assertFalse(ok, "A scenario assertion failure must fail the run")

    def test_scenario_assertion_failure_is_reported(self):
        roster = self._orig[2].replace("roster size evaluates to 84", "roster size evaluates to 83", 1)
        ok, stdout, audit_errors = self.run_with(roster=roster)
        self.assertEqual(audit_errors, [], stdout)
        self.assertEqual([f["tr"] for f in verify.LAST_RESULT["failed"]], ["TR-51"], stdout)
        self.assertEqual(verify.LAST_RESULT["passed"], verify.LAST_RESULT["scenarios"] - 1)


if __name__ == "__main__":
    unittest.main()
