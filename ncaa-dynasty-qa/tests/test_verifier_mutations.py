"""Mutation tests: deliberately break each enforcement rule in a copy of
verify.py and confirm tests/test_verifier_enforcement.py notices (fails).
A mutant that "survives" (the unit suite still passes) means the unit
tests no longer protect that rule."""
import ast, json, os, shutil, subprocess, sys, tempfile, unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# (verifier rule, mutant name, original snippet in verify.py, mutated snippet)
MUTANTS = [
    ("duplicate-id",       "duplicate-ID check disabled",       "    if dupes:\n",                               "    if False:\n"),
    ("duplicate-id",       "duplicate-ID detection off-by-one", "tr_ids.count(t) > 1",                           "tr_ids.count(t) > 2"),
    ("regression-mapping", "regression-mapping check disabled", "    if uncovered:\n",                           "    if False:\n"),
    ("regression-mapping", "mapping baseline widened",          "int(t[3:]) > COVERAGE_BASELINE",                "int(t[3:]) > COVERAGE_BASELINE + 10"),
    ("regression-mapping", "mapping ignores test references",   "uncovered = [t for t in new_ids if t not in covered]", "uncovered = []"),
    ("missing-id",         "missing-ID check disabled",         "    if malformed:\n",                           "    if False:\n"),
    ("no-steps",           "no-steps check disabled",           "    if empty:\n",                               "    if False:\n"),
    ("unknown-step",       "unknown-step check disabled",       "    if unmatched:\n",                           "    if False:\n"),
    # Deliberate breaks added with the surviving-mutant advisor
    ('duplicate-id', 'duplicate IDs collapsed before audit', "    tr_ids = [s['tr'] for s in scenarios]\n", "    tr_ids = list(dict.fromkeys(s['tr'] for s in scenarios))\n"),
    ('duplicate-id', 'duplicates only checked in first feature file', '    dupes = sorted({t for t in tr_ids if tr_ids.count(t) > 1})', '    dupes = sorted({t for t in tr_ids[:len(parse_feature(RECRUITING))] if tr_ids[:len(parse_feature(RECRUITING))].count(t) > 1})'),
    ('regression-mapping', 'only last test file counted', '                ids |= set(re.findall(', '                ids = set(re.findall('),
    ('regression-mapping', 'test file prefix loosened to any .py', "            if fn.startswith('test_') and fn.endswith('.py'):", "            if fn.endswith('.py'):"),
    ('regression-mapping', 'ID match truncated to prefix', "re.findall(r'TR-\\d+',", "re.findall(r'TR-\\d\\d?',"),
    ('missing-id', 'malformed scenarios silently skipped', "    malformed = [s['name'] for s in scenarios if s['tr'] == 'UNKNOWN']", "    malformed = [s['name'] for s in scenarios if s['tr'] == 'UNKNOWN' and s['steps'] == []]"),
    ('missing-id', 'lowercase/garbled IDs accepted', "            m = re.match(r'Scenario:\\s*(TR-\\d+)\\s*(.*)', line)", "            m = re.match(r'Scenario:\\s*(\\S+)\\s*(.*)', line)"),
    ('no-steps', 'no-steps check only for UNKNOWN IDs', "{s['tr'] for s in scenarios if not s['steps']}", "{s['tr'] for s in scenarios if not s['steps'] and s['tr'] == 'UNKNOWN'}"),
    ('no-steps', 'But-steps not counted as steps', 'for k in ["Given", "When", "Then", "And", "But"]', 'for k in ["Given", "When", "Then", "And"]'),
    ('unknown-step', 'unmatched phrases treated as ambiguous', '        if len(hits) == 0:\n            unmatched.append((tr, txt))', '        if len(hits) == 0:\n            ambiguous.append((tr, txt, 0))'),
    ('ambiguous-step', 'ambiguity threshold raised', '        elif len(hits) > 1:', '        elif len(hits) > 2:'),
    ('ambiguous-step', 'ambiguity check disabled', '    if ambiguous:\n', '    if False:\n'),
    # Real-world breaks for rules that previously had no mutants
    ('orphaned-rule', 'orphaned-rule check disabled', '    if missing:\n', '    if False:\n'),
    ('orphaned-rule', 'orphaned rules only checked up to baseline', '    missing = sorted(expected - set(tr_ids))', '    missing = sorted(t for t in expected - set(tr_ids) if int(t[3:]) <= COVERAGE_BASELINE)'),
    ('orphaned-scenario', 'orphaned-scenario check disabled', '    if extra:\n', '    if False:\n'),
    ('orphaned-scenario', 'orphaned scenarios only flagged for two-digit IDs', '    extra = sorted(set(tr_ids) - expected)', '    extra = sorted(t for t in set(tr_ids) - expected if len(t) == 5)'),
    ('scenario-execution', 'failing scenarios do not fail the run', '    if failed:\n', '    if False:\n'),
    ('scenario-execution', 'assertion failures counted as passes', "            failed.append((s['tr'], s['name'], str(e)))", "            passed += 1"),
]


def stage_suite(d, verify_source, extra_tests=None):
    shutil.copytree(os.path.join(ROOT, "features"), os.path.join(d, "features"))
    shutil.copy(os.path.join(ROOT, "rules.json"), d)
    os.mkdir(os.path.join(d, "tests"))
    for fn in os.listdir(os.path.join(ROOT, "tests")):
        if fn.startswith("test_") and fn.endswith(".py") and fn != "test_verifier_mutations.py":
            shutil.copy(os.path.join(ROOT, "tests", fn), os.path.join(d, "tests", fn))
    for fn, text in (extra_tests or {}).items():
        with open(os.path.join(d, "tests", fn), "w") as f:
            f.write(text)
    with open(os.path.join(d, "verify.py"), "w") as f:
        f.write(verify_source)


# Stdlib-only tracer: runs the enforcement suite (the tests that decide
# kill/survive) under `trace`, recording which lines of the staged verify.py
# THAT suite executes. Lines reached only by unrelated tests don't count.
_TRACER = r'''
import sys, os, trace, io, json, unittest
target = os.path.realpath(os.path.join("..", "verify.py"))
tr = trace.Trace(count=1, trace=0, ignoredirs=[sys.prefix, sys.exec_prefix])
out = io.StringIO()
def run():
    suite = unittest.defaultTestLoader.loadTestsFromNames(["test_verifier_enforcement"])
    return unittest.TextTestRunner(stream=out, verbosity=1).run(suite).wasSuccessful()
ok = tr.runfunc(run)
lines = sorted(ln for (fn, ln), c in tr.results().counts.items()
               if c > 0 and os.path.realpath(fn) == target)
with open("trace_result.json", "w") as f:
    json.dump({"ok": ok, "lines": lines, "output": out.getvalue()}, f)
'''


def run_enforcement_suite(verify_source, extra_tests=None):
    """Run tests/test_verifier_enforcement.py against this verifier source.
    Returns (exit_code, output, executed_lines_of_verify_py)."""
    d = tempfile.mkdtemp()
    try:
        stage_suite(d, verify_source, extra_tests)
        tdir = os.path.join(d, "tests")
        env = dict(os.environ, PYTHONHASHSEED=str(SEED), QA_SEED=str(SEED))
        res = subprocess.run([sys.executable, "-c", _TRACER], cwd=tdir, env=env,
                             capture_output=True, text=True, timeout=600)
        path = os.path.join(tdir, "trace_result.json")
        if not os.path.exists(path):  # crashed before finishing (e.g. syntax error)
            return 1, res.stdout + res.stderr, set()
        data = json.load(open(path))
        return (0 if data["ok"] else 1), data["output"] + res.stderr, set(data["lines"])
    finally:
        shutil.rmtree(d, ignore_errors=True)


def same_ast(a, b):
    """True when two sources compile to the same AST (comment/whitespace-only change)."""
    try:
        return ast.dump(ast.parse(a)) == ast.dump(ast.parse(b))
    except SyntaxError:
        return False


def rule_scores(results):
    """Per-verifier-rule detection: {rule: {"killed": n, "total": n, "score": pct, "survivors": [names]}}."""
    out = {}
    for m in results:
        r = out.setdefault(m["rule"], {"killed": 0, "total": 0, "survivors": []})
        r["total"] += 1
        if m["killed"]:
            r["killed"] += 1
        else:
            r["survivors"].append(m["name"])
    for r in out.values():
        r["score"] = 100.0 * r["killed"] / r["total"]
    return dict(sorted(out.items()))


def run_mutants(mutants=MUTANTS, source=None, extra_tests=None):
    """Apply each mutant and run the enforcement suite. A mutant is 'killed'
    (detected) when the suite fails. Returns a dict for reporting; each entry
    in "results" doubles as the machine-readable CI artifact record."""
    if source is None:
        with open(os.path.join(ROOT, "verify.py")) as f:
            source = f.read()
    base_code, base_out, _ = run_enforcement_suite(source, extra_tests)
    results, missing, ineffective, not_executed, skipped = [], [], [], [], []
    for rule, name, original, mutated in mutants:
        rec = {"rule": rule, "name": name, "original": original, "mutated": mutated,
               "mutated_lines": [], "executed_lines": [], "executed": False, "killed": False}
        if source.count(original) != 1:
            missing.append(name); skipped.append(dict(rec, effective=None, outcome="target_not_found")); continue
        new_source = source.replace(original, mutated)
        if new_source == source or same_ast(source, new_source):
            # No-op mutant (identical text or identical AST): it cannot prove
            # anything, so it must not count toward the score at all.
            ineffective.append(name); skipped.append(dict(rec, effective=False, outcome="ineffective")); continue
        idx = new_source.index(mutated)
        start = new_source[:idx].count("\n") + 1
        span = sorted(range(start, start + mutated.rstrip("\n").count("\n") + 1))
        code, out, lines = run_enforcement_suite(new_source, extra_tests)
        hit = sorted(set(span) & lines)
        killed, executed = code != 0, bool(hit)
        results.append({"rule": rule, "name": name, "original": original, "mutated": mutated,
                        "effective": True, "mutated_lines": span, "executed_lines": hit,
                        "executed": executed, "killed": killed,
                        "outcome": "killed" if killed else ("survived" if executed else "unreached"),
                        "output": out})
        if not executed:
            not_executed.append(name)
    return {"rules": rule_scores(results), "baseline_ok": base_code == 0, "baseline_output": base_out,
            "missing_targets": missing, "ineffective": ineffective,
            "not_executed": not_executed, "results": results, "skipped": skipped}


SEED = int(os.environ.get("QA_SEED", "0"))
ENFORCEMENT_TESTS = ["test_verifier_enforcement"]


def artifact(r, seed=SEED, mutants=MUTANTS):
    """Machine-readable per-mutant report (written by ci_summary.py as mutation-results.json)."""
    muts = [{k: m[k] for k in ("rule", "name", "original", "mutated", "effective", "mutated_lines",
                               "executed_lines", "executed", "killed", "outcome")} for m in r["results"]]
    muts += r["skipped"]
    import platform
    names = [m[1] for m in mutants]
    return {"schema_version": 2, "baseline_ok": r["baseline_ok"], "rules": r["rules"], "mutants": muts,
            "reproduce": {"seed": seed, "python": platform.python_version(),
                          "test_selection": list(ENFORCEMENT_TESTS), "mutant_selection": names,
                          "command": f"QA_SEED={seed} PYTHONHASHSEED={seed} python{sys.version_info[0]}.{sys.version_info[1]} ci_summary.py"}}


class VerifierMutationTests(unittest.TestCase):
    def test_mutation_score_meets_minimum(self):
        sys.path.insert(0, ROOT)
        from thresholds import parse_threshold, THRESHOLDS
        minimum, err = parse_threshold("MIN_MUTATION_SCORE", os.environ.get("MIN_MUTATION_SCORE"),
                                       THRESHOLDS["MIN_MUTATION_SCORE"][0])
        self.assertIsNone(err, err)
        r = run_mutants()
        self.assertTrue(r["baseline_ok"], "Enforcement suite fails on unmutated verifier:\n" + r["baseline_output"][-2000:])
        self.assertEqual(r["missing_targets"], [], "Mutation targets not found in verify.py - update MUTANTS")
        self.assertEqual(r["ineffective"], [],
                         "No-op mutants (original == mutated) can't prove detection - fix MUTANTS")
        self.assertEqual(r["not_executed"], [],
                         "Mutated code never executed during a verifier run - pick live targets")
        killed = sum(m["killed"] for m in r["results"])
        score = 100.0 * killed / max(1, len(r["results"]))
        survivors = [m["name"] for m in r["results"] if not m["killed"]]
        self.assertGreaterEqual(score, minimum, f"Mutation score {score:.1f}% < {minimum:g}%; survivors: {survivors}")
        rule_min, err = parse_threshold("MIN_RULE_MUTATION_SCORE", os.environ.get("MIN_RULE_MUTATION_SCORE"),
                                        THRESHOLDS["MIN_RULE_MUTATION_SCORE"][0])
        self.assertIsNone(err, err)
        weak = {k: v for k, v in r["rules"].items() if v["score"] < rule_min}
        self.assertEqual(weak, {}, f"Verifier rules below {rule_min:g}% mutation detection: {weak}")

    def test_every_rule_has_mutants(self):
        """Each audit rule must be exercised by at least one mutant, so a rule can't be silently unguarded."""
        rules = {m[0] for m in MUTANTS}
        self.assertEqual(rules, {"duplicate-id", "regression-mapping", "missing-id", "no-steps", "unknown-step", "ambiguous-step",
                                 "orphaned-rule", "orphaned-scenario", "scenario-execution"})

    def test_rule_scores_isolate_weak_rule(self):
        """A perfect rule must not mask a weak one: per-rule scores are computed independently."""
        fake = [{"rule": "a", "name": f"a{i}", "killed": True} for i in range(9)] + [{"rule": "b", "name": "b1", "killed": False}]
        s = rule_scores(fake)
        self.assertEqual(s["a"]["score"], 100.0)
        self.assertEqual(s["b"]["score"], 0.0)
        self.assertEqual(s["b"]["survivors"], ["b1"])

    def test_noop_mutant_is_flagged_ineffective(self):
        """A no-op mutant (original == mutated) can't prove detection, so it is
        flagged as ineffective and excluded from the score instead of counted."""
        r = run_mutants([("duplicate-id", "no-op", "    if dupes:\n", "    if dupes:\n")])
        self.assertEqual(r["results"], [])
        self.assertEqual(r["ineffective"], ["no-op"])

    def test_mutant_on_dead_code_is_flagged_not_executed(self):
        """A mutant whose changed lines never run in the enforcement suite
        (here: a helper nothing calls) must be flagged as not executed."""
        with open(os.path.join(ROOT, "verify.py")) as f:
            src = f.read() + "\n\ndef _never_called():\n    return 'dead'\n"
        r = run_mutants([("unknown-step", "dead helper changed", "    return 'dead'\n", "    return 'alive'\n")],
                        source=src)
        self.assertEqual(r["not_executed"], ["dead helper changed"])
        self.assertEqual([m["executed"] for m in r["results"]], [False])

    def test_ast_identical_mutant_is_ineffective(self):
        """Text changes that leave the AST unchanged (comments, spacing) can't be counted."""
        r = run_mutants([("duplicate-id", "comment-only change",
                          "    if dupes:\n", "    if dupes:  # reformatted\n")])
        self.assertEqual(r["ineffective"], ["comment-only change"])
        self.assertEqual(r["results"], [])

    def test_ast_changing_behavior_preserving_mutant_survives(self):
        """An equivalent mutant (different AST, same behaviour) is effective and
        executed, but must be reported as surviving - never as detected."""
        r = run_mutants([("duplicate-id", "equivalent comparison",
                          "tr_ids.count(t) > 1", "tr_ids.count(t) >= 2")])
        self.assertEqual(r["ineffective"], [])
        self.assertEqual(r["not_executed"], [])
        [m] = r["results"]
        self.assertTrue(m["executed"] and m["executed_lines"])
        self.assertEqual(m["outcome"], "survived")
        self.assertEqual(r["rules"]["duplicate-id"]["survivors"], ["equivalent comparison"])

    def test_line_reached_only_by_unrelated_tests_is_not_executed(self):
        """A mutated line exercised only by some other test file (not the
        enforcement suite that decides kill/survive) gives no execution evidence."""
        with open(os.path.join(ROOT, "verify.py")) as f:
            src = f.read() + "\n\ndef _unrelated_helper():\n    return 1\n"
        extra = {"test_unrelated_helper.py":
                 "import os, sys, unittest\nsys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))\n"
                 "import verify\nclass T(unittest.TestCase):\n    def test_it(self):\n        self.assertEqual(verify._unrelated_helper(), 1)\n"}
        r = run_mutants([("unknown-step", "unrelated-only line", "    return 1\n", "    return 2\n")],
                        source=src, extra_tests=extra)
        self.assertEqual(r["not_executed"], ["unrelated-only line"])
        [m] = r["results"]
        self.assertEqual(m["executed_lines"], [])
        self.assertEqual(m["outcome"], "unreached")

    def test_artifact_records_every_mutant(self):
        """Artifact has one record per mutant with effectiveness, line evidence and outcome."""
        r = run_mutants([("ambiguous-step", "disabled", "    if ambiguous:\n", "    if False:\n"),
                         ("ambiguous-step", "noop", "    if ambiguous:\n", "    if ambiguous:\n")])
        a = json.loads(json.dumps(artifact(r)))
        by = {m["name"]: m for m in a["mutants"]}
        self.assertEqual(by["disabled"]["outcome"], "killed")
        self.assertTrue(by["disabled"]["executed_lines"])
        self.assertEqual(by["noop"]["outcome"], "ineffective")
        self.assertFalse(by["noop"]["effective"])
        sys.path.insert(0, ROOT)
        from validate_artifact import validate
        self.assertEqual(validate(a), [])
        rep = a["reproduce"]
        self.assertEqual(rep["seed"], SEED)
        self.assertEqual(rep["test_selection"], ["test_verifier_enforcement"])
        self.assertIn("QA_SEED=", rep["command"])


if __name__ == "__main__":
    unittest.main()
