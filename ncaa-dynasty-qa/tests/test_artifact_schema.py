"""Schema validation for mutation-results.json: required fields, outcome
values, and CLI diagnostics that name the bad field and mutant."""
import copy, json, os, subprocess, sys, tempfile, unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from validate_artifact import validate


def good():
    m = {"rule": "duplicate-id", "name": "check disabled", "original": "a", "mutated": "b",
         "effective": True, "mutated_lines": [10], "executed_lines": [10], "executed": True,
         "killed": True, "outcome": "killed"}
    return {"schema_version": 2, "baseline_ok": True,
            "rules": {"duplicate-id": {"killed": 1, "total": 1, "score": 100.0, "survivors": []}},
            "mutants": [m],
            "reproduce": {"seed": 0, "python": "3.12.0", "test_selection": ["test_verifier_enforcement"],
                          "mutant_selection": ["check disabled"], "command": "QA_SEED=0 python3 ci_summary.py"}}


class ArtifactSchemaTests(unittest.TestCase):
    def test_valid_artifact(self):
        self.assertEqual(validate(good()), [])

    def test_every_outcome_value_accepted(self):
        for o in ("killed", "survived", "unreached", "ineffective", "target_not_found"):
            d = good(); d["mutants"][0]["outcome"] = o
            self.assertEqual(validate(d), [], o)

    def test_invalid_outcome_named_with_mutant(self):
        d = good(); d["mutants"][0]["outcome"] = "maybe"
        [e] = validate(d)
        self.assertIn("$.mutants[0].outcome (mutant 'check disabled')", e)
        self.assertIn('invalid value "maybe"', e)
        self.assertIn('"unreached"', e)

    def test_missing_mutant_field(self):
        d = good(); del d["mutants"][0]["executed_lines"]
        self.assertEqual(validate(d), ["$.mutants[0]: missing required field 'executed_lines'"])

    def test_missing_reproduce_block(self):
        d = good(); del d["reproduce"]
        self.assertEqual(validate(d), ["$: missing required field 'reproduce'"])

    def test_wrong_types(self):
        d = good(); d["mutants"][0]["killed"] = "yes"; d["reproduce"]["seed"] = True
        errs = validate(d)
        self.assertEqual(len(errs), 2, errs)
        self.assertTrue(any("killed" in e and "expected boolean" in e for e in errs))
        self.assertTrue(any("seed" in e and "expected integer" in e for e in errs))

    def test_cli_exit_codes_and_diagnostics(self):
        with tempfile.TemporaryDirectory() as t:
            ok, bad, broken = (os.path.join(t, n) for n in ("ok.json", "bad.json", "broken.json"))
            json.dump(good(), open(ok, "w"))
            d = good(); d["mutants"][0]["outcome"] = "maybe"; del d["mutants"][0]["rule"]
            json.dump(d, open(bad, "w"))
            open(broken, "w").write("{not json")
            run = lambda p: subprocess.run([sys.executable, os.path.join(ROOT, "validate_artifact.py"), p],
                                           capture_output=True, text=True)
            self.assertEqual(run(ok).returncode, 0)
            r = run(bad)
            self.assertEqual(r.returncode, 1)
            self.assertIn("2 schema error(s)", r.stdout)
            self.assertIn("missing required field 'rule'", r.stdout)
            self.assertEqual(run(broken).returncode, 1)
            self.assertIn("cannot read JSON", run(broken).stdout)


if __name__ == "__main__":
    unittest.main()
