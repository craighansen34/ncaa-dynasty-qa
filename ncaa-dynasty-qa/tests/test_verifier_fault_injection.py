"""
Dependency-free regression tests for the NCAA Dynasty QA Verifier.
Validates that the verifier fails (exit code 1) and reports offending items when:
  1. Duplicate traceability IDs are present
  2. Orphaned rules (missing scenarios) or orphaned scenarios (unmapped IDs) exist
  3. Unmatched step phrases exist in features
  4. Ambiguous step handlers match a single phrase
"""

import sys
import unittest
import subprocess
import tempfile
import os

class TestVerifierAuditFaultInjections(unittest.TestCase):

    def run_verifier_subprocess(self, script_content):
        with tempfile.NamedTemporaryFile('w', suffix='.py', delete=False) as f:
            f.write(script_content)
            temp_path = f.name
        try:
            res = subprocess.run([sys.executable, temp_path], capture_output=True, text=True)
            return res.returncode, res.stdout + res.stderr
        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)

    def get_base_script(self):
        return """
import sys
import re

REGISTRY = [
    (re.compile(r'base recruiting budget is (?P<h>\\d+) hours\\Z'), lambda ctx, h: None),
    (re.compile(r'total available hours evaluate to (?P<h>\\d+)\\Z'), lambda ctx, h: None),
]

def find_handlers(phrase):
    matches = []
    for rx, fn in REGISTRY:
        m = rx.match(phrase)
        if m: matches.append((fn, m))
    return matches

def audit_and_run(scenarios, strict=True):
    audit_errors = []
    tr_ids = [s['tr'] for s in scenarios]
    expected = {f"TR-{i:02d}" for i in range(1, len(scenarios) + 1)}
    
    dupes = sorted({t for t in tr_ids if tr_ids.count(t) > 1})
    missing = sorted(expected - set(tr_ids))
    extra = sorted(set(tr_ids) - expected)
    
    if dupes:
        audit_errors.append(f"DUPLICATE TRACEABILITY IDs: {dupes}")
        print(f"ERROR: DUPLICATE TRACEABILITY IDs: {dupes}")
    if missing:
        audit_errors.append(f"ORPHANED RULES: {missing}")
        print(f"ERROR: ORPHANED RULES: {missing}")
    if extra:
        audit_errors.append(f"ORPHANED SCENARIOS: {extra}")
        print(f"ERROR: ORPHANED SCENARIOS: {extra}")

    unmatched, ambiguous = [], []
    for s in scenarios:
        for txt in s['steps']:
            hits = find_handlers(txt)
            if len(hits) == 0:
                unmatched.append((s['tr'], txt))
            elif len(hits) > 1:
                ambiguous.append((s['tr'], txt, len(hits)))

    if unmatched:
        audit_errors.append(f"UNMATCHED STEP PHRASES: {unmatched}")
        for tr, txt in unmatched:
            print(f"ERROR: UNMATCHED [{tr}]: {txt}")
    if ambiguous:
        audit_errors.append(f"AMBIGUOUS STEP HANDLERS: {ambiguous}")
        for tr, txt, n in ambiguous:
            print(f"ERROR: AMBIGUOUS [{tr}] matched by {n} patterns: {txt}")

    if audit_errors:
        if strict:
            sys.exit(1)
        return False
    print("ALL CHECKS PASSED")
    return True
"""

    def test_duplicate_traceability_id_injection(self):
        """Inject duplicate TR-01 ID; assert exit code 1 and offending ID in report."""
        script = self.get_base_script() + """
scenarios = [
    {'tr': 'TR-01', 'steps': ['base recruiting budget is 500 hours']},
    {'tr': 'TR-01', 'steps': ['total available hours evaluate to 500']}
]
audit_and_run(scenarios, strict=True)
"""
        code, output = self.run_verifier_subprocess(script)
        self.assertEqual(code, 1, "Must exit with status 1 on duplicate traceability ID")
        self.assertIn("DUPLICATE TRACEABILITY IDs", output)
        self.assertIn("TR-01", output, "Report must identify offending duplicate ID TR-01")

    def test_orphaned_rule_and_scenario_injection(self):
        """Inject missing expected rule and unexpected ID; assert exit code 1 and offending items."""
        script = self.get_base_script() + """
scenarios = [
    {'tr': 'TR-99', 'steps': ['base recruiting budget is 500 hours']}
]
audit_and_run(scenarios, strict=True)
"""
        code, output = self.run_verifier_subprocess(script)
        self.assertEqual(code, 1, "Must exit with status 1 on orphaned rule / scenario")
        self.assertIn("ORPHANED RULES", output)
        self.assertIn("TR-01", output, "Report must identify missing required rule TR-01")
        self.assertIn("ORPHANED SCENARIOS", output)
        self.assertIn("TR-99", output, "Report must identify unmapped scenario TR-99")

    def test_unmatched_step_phrase_injection(self):
        """Inject undefined step phrase; assert exit code 1 and offending phrase text."""
        script = self.get_base_script() + """
scenarios = [
    {'tr': 'TR-01', 'steps': ['completely undefined and unmapped recruiting action']}
]
audit_and_run(scenarios, strict=True)
"""
        code, output = self.run_verifier_subprocess(script)
        self.assertEqual(code, 1, "Must exit with status 1 on unmatched step phrase")
        self.assertIn("UNMATCHED", output)
        self.assertIn("completely undefined and unmapped recruiting action", output,
                      "Report must print the offending unmatched step phrase")
        self.assertIn("TR-01", output)

    def test_ambiguous_step_handler_injection(self):
        """Inject overlapping regex patterns matching the same phrase; assert exit code 1."""
        script = self.get_base_script() + """
REGISTRY.append((re.compile(r'base recruiting budget is (?P<h>\\d+) hours\\Z'), lambda ctx, h: None))
scenarios = [
    {'tr': 'TR-01', 'steps': ['base recruiting budget is 500 hours']}
]
audit_and_run(scenarios, strict=True)
"""
        code, output = self.run_verifier_subprocess(script)
        self.assertEqual(code, 1, "Must exit with status 1 on ambiguous step handlers")
        self.assertIn("AMBIGUOUS", output)
        self.assertIn("base recruiting budget is 500 hours", output,
                      "Report must print the offending phrase matched by multiple patterns")
        self.assertIn("matched by 2 patterns", output)

if __name__ == '__main__':
    unittest.main(verbosity=2)
