"""Run the verifier and regression suite, then write a Markdown report to
$GITHUB_STEP_SUMMARY (or stdout locally). Exits 1 if anything fails."""
import io, os, sys, unittest, contextlib, platform

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
VERIFY_PY = os.path.join(HERE, 'verify.py')
from thresholds import load_thresholds, THRESHOLDS

_values, _threshold_errors = load_thresholds(os.environ)
if _threshold_errors:
    md = "\n".join(["## NCAA Dynasty QA — Invalid CI threshold", "",
                    "CI stopped before running anything because a threshold setting is invalid:", ""]
                   + [f"- {e}" for e in _threshold_errors]
                   + ["", "Each threshold is a percentage from 0 to 100, set under `env:` in `.github/workflows/qa.yml`:", ""]
                   + [f"- `{n}` — {d} (default {v:g})" for n, (v, d) in THRESHOLDS.items()] + [""])
    print(md, file=sys.stderr)
    if os.environ.get('GITHUB_STEP_SUMMARY'):
        with open(os.environ['GITHUB_STEP_SUMMARY'], 'a') as f: f.write(md + "\n")
    sys.exit(2)
MIN_COVERAGE = _values['MIN_COVERAGE']
MIN_PARITY = _values['MIN_PARITY']
MIN_MUTATION_SCORE = _values['MIN_MUTATION_SCORE']
MIN_RULE_MUTATION_SCORE = _values['MIN_RULE_MUTATION_SCORE']

import json
sys.path.insert(0, os.path.join(HERE, 'tests'))
from test_verifier_mutations import run_mutants, artifact


class _Problem:
    """A failed/errored regression test, in a form that survives a JSON round trip."""
    def __init__(self, test_id): self._id = test_id
    def id(self): return self._id


class _TestRun:
    def __init__(self, tests_run, skipped, problems, ok):
        self.testsRun, self.skipped, self.problems, self.ok = tests_run, skipped, problems, ok


def _collect():
    """The expensive part of CI: regression suite under coverage + mutation run."""
    try:
        import coverage
        cov = coverage.Coverage(include=[VERIFY_PY])
        cov.start()
    except ImportError:
        cov = None
    suite = unittest.defaultTestLoader.discover(os.path.join(HERE, 'tests'), pattern='test_*.py',
                                                top_level_dir=os.path.join(HERE, 'tests'))
    tres = unittest.TextTestRunner(verbosity=2, stream=sys.stdout).run(suite)
    cov_pct, cov_missing = None, []
    if cov is not None:
        cov.stop()
        _, stmts, _, missing, _ = cov.analysis2(VERIFY_PY)
        cov_pct = 100.0 * (len(stmts) - len(missing)) / max(1, len(stmts))
        cov_missing = list(missing)
    return {"tests_run": tres.testsRun, "skipped": len(tres.skipped), "ok": tres.wasSuccessful(),
            "problems": [[t.id(), tb] for t, tb in tres.failures + tres.errors],
            "cov_pct": cov_pct, "cov_missing": cov_missing, "mut": run_mutants()}


# QA_RESULTS_CACHE (test-only): reuse one expensive run across several threshold/gate
# settings. Everything after this point - verifier, thresholds, gate, artifact, schema,
# history, summary - is still recomputed on every invocation.
_CACHE = os.environ.get('QA_RESULTS_CACHE')
if _CACHE and os.path.exists(_CACHE):
    with open(_CACHE) as f:
        raw = json.load(f)
    print(f"Reusing regression + mutation results from {_CACHE}")
else:
    raw = _collect()
    if _CACHE:
        with open(_CACHE, 'w') as f:
            json.dump(raw, f, default=lambda o: sorted(o) if isinstance(o, (set, frozenset)) else str(o))
        with open(_CACHE) as f:
            raw = json.load(f)  # same shape on first and later runs

import verify
problems = [(_Problem(i), tb) for i, tb in raw["problems"]]
tres = _TestRun(raw["tests_run"], [None] * raw["skipped"], problems, raw["ok"])
ok_t = raw["ok"]
cov_pct, cov_missing = raw["cov_pct"], raw["cov_missing"]
ok_c = cov_pct is not None and cov_pct >= MIN_COVERAGE
if cov_pct is not None:
    print(f"Regression-suite coverage of verify.py: {cov_pct:.1f}% (minimum {MIN_COVERAGE:g}%)")
else:
    print("coverage package not installed - run: pip install coverage")
mut = raw["mut"]
ARTIFACT = os.environ.get('MUTATION_ARTIFACT', os.path.join(HERE, 'mutation-results.json'))
with open(ARTIFACT, 'w') as f:
    json.dump(artifact(mut), f, indent=2)
print(f"Per-mutant results written to {ARTIFACT}")
# Schema check: a malformed artifact (missing fields, bad outcome) fails CI.
from validate_artifact import validate
with open(ARTIFACT) as f:
    schema_errors = validate(json.load(f))
ok_schema = not schema_errors
# Keep validation diagnostics next to the artifact so they survive a failing job.
VALIDATION = os.path.splitext(ARTIFACT)[0] + '.validation.txt'
with open(VALIDATION, 'w') as f:
    f.write(("INVALID" if schema_errors else "VALID") + f" {os.path.basename(ARTIFACT)}\n"
            + "".join(f"  - {e}\n" for e in schema_errors))
if schema_errors:
    print(f"ARTIFACT SCHEMA INVALID ({len(schema_errors)} error(s)):")
    for e in schema_errors: print(f"  - {e}")
mut_total, mut_killed = len(mut['results']), sum(1 for m in mut['results'] if m['killed'])
mut_score = 100.0 * mut_killed / max(1, mut_total)
weak_rules = {k: v for k, v in mut['rules'].items() if v['score'] < MIN_RULE_MUTATION_SCORE}
ok_m = (mut['baseline_ok'] and not mut['missing_targets'] and not mut['ineffective']
        and not mut['not_executed'] and mut_score >= MIN_MUTATION_SCORE and not weak_rules)
# Mutation gate: every mutant must be reached, effective, and killed.
GATE = (os.environ.get('MUTATION_GATE') or 'strict').strip().lower()
if GATE not in ('strict', 'off'):
    print(f"MUTATION_GATE must be 'strict' or 'off', got {GATE!r}", file=sys.stderr); sys.exit(2)
gate_bad = [m for m in artifact(mut)['mutants'] if m['outcome'] != 'killed']
ok_gate = GATE == 'off' or not gate_bad
by_rule = {}
for m in artifact(mut)['mutants']:
    d = by_rule.setdefault(m['rule'], {})
    d[m['outcome']] = d.get(m['outcome'], 0) + 1
print(f"Mutation gate ({GATE}): {'PASS' if ok_gate else 'FAIL'}")
for k in sorted(by_rule):
    print(f"  rule {k}: " + ", ".join(f"{n} {o}" for o, n in sorted(by_rule[k].items())))
for m in gate_bad:
    print(f"  {m['outcome'].upper()}: [{m['rule']}] {m['name']}")
# CI history: compare per-rule outcomes with the previous run on this Python version.
import mutation_history
HISTORY = os.environ.get('MUTATION_HISTORY', os.path.join(HERE, 'mutation-history.json'))
with open(ARTIFACT) as f:
    h_prev, _, h_rows, h_regressions = mutation_history.record(HISTORY, json.load(f))
print(f"Mutation history: {len(h_regressions)} rule regression(s) vs previous run"
      + (f" ({', '.join(r['rule'] for r in h_regressions)})" if h_regressions else ""))
print(f"Mutation score: {mut_score:.1f}% ({mut_killed}/{mut_total} detected, minimum {MIN_MUTATION_SCORE:g}%)")

buf = io.StringIO()
with contextlib.redirect_stdout(buf):
    try:
        ok_v = verify.run_verifier(strict=False)
    except Exception as e:  # never let the summary crash silently
        ok_v = False
        verify.LAST_RESULT.setdefault('audit_errors', []).append(f"verifier crashed: {e!r}")
print(buf.getvalue())
r = verify.LAST_RESULT
mapped, unmapped = r.get('mapped', []), r.get('unmapped', [])
total_ids = len(mapped) + len(unmapped)
parity = 100.0 * len(mapped) / max(1, total_ids)
ok_p = parity >= MIN_PARITY
print(f"Scenario-to-regression-test parity: {parity:.1f}% ({len(mapped)}/{total_ids}, minimum {MIN_PARITY:g}%)")
if not ok_p:
    print("Unmapped scenario IDs: " + ", ".join(unmapped))

def ranges(lines):
    out, start, prev = [], None, None
    for n in lines:
        if start is None: start = prev = n
        elif n == prev + 1: prev = n
        else: out.append(f"{start}-{prev}" if start != prev else str(start)); start = prev = n
    if start is not None: out.append(f"{start}-{prev}" if start != prev else str(start))
    return ", ".join(out)

def cell(t): return t.replace('|', '\\|').replace('\n', '<br>')
L = [f"## NCAA Dynasty QA — Python {platform.python_version()}", "",
     "| Check | Result | Count |", "|---|---|---|",
     f"| Gherkin scenarios | {'✅ pass' if ok_v else '❌ fail'} | {r.get('passed',0)}/{r.get('scenarios',0)} passed |",
     f"| Regression tests | {'✅ pass' if ok_t else '❌ fail'} | {tres.testsRun - len(problems) - len(tres.skipped)}/{tres.testsRun} passed |",
     (f"| Regression coverage (verify.py) | {'✅ pass' if ok_c else '❌ below minimum'} | {cov_pct:.1f}% (min {MIN_COVERAGE:g}%) |"
      if cov_pct is not None else "| Regression coverage (verify.py) | ❌ not measured | install `coverage` |"),
     f"| Mutation detection | {'✅ pass' if ok_m else '❌ fail'} | {mut_killed}/{mut_total} detected — {mut_score:.1f}% (min {MIN_MUTATION_SCORE:g}%) |",
     f"| Mutation gate ({GATE}) | {'✅ pass' if ok_gate else '❌ fail'} | {len(gate_bad)} unkilled (unreached/survived/ineffective) |",
     f"| Artifact schema | {'✅ pass' if ok_schema else '❌ invalid'} | {len(schema_errors)} error(s) |",
     f"| Scenario-to-test parity | {'✅ pass' if ok_p else '❌ below minimum'} | {parity:.1f}% — {len(mapped)}/{total_ids} mapped (min {MIN_PARITY:g}%) |", ""]
L += ["### Mutation detection by verifier rule", "",
      f"Every rule must reach **{MIN_RULE_MUTATION_SCORE:g}%** on its own, so a strong overall score can't hide a weak rule.", "",
      "| Verifier rule | Detected | Score | Result | Surviving mutants |", "|---|---|---|---|---|"]
L += [f"| `{k}` | {v['killed']}/{v['total']} | {v['score']:.1f}% | {'✅' if v['score'] >= MIN_RULE_MUTATION_SCORE else '❌ below minimum'} | {cell(', '.join(v['survivors'])) or '—'} |"
      for k, v in mut['rules'].items()] + [""]
# Per-mutant report: effectiveness, execution evidence, and outcome in one table.
_ms = artifact(mut)['mutants']
_n = len(_ms)
_eff = sum(1 for m in _ms if m.get('effective'))
_exe = sum(1 for m in _ms if m.get('executed'))
_oc = {}
for m in _ms: _oc[m['outcome']] = _oc.get(m['outcome'], 0) + 1
def _lines(m):
    ex, mu = m.get('executed_lines') or [], m.get('mutated_lines') or []
    return (f"{ranges(ex)} of {ranges(mu)}" if mu else "—")
L += ["### Mutant report", "",
      f"**{_n} mutants** — effective {_eff}/{_n} · executed {_exe}/{_n} · "
      + " · ".join(f"{o} {c}" for o, c in sorted(_oc.items())), "",
      "<details><summary>Per-mutant details</summary>", "",
      "| Rule | Mutant | Effective | Executed (lines run of changed) | Outcome |", "|---|---|---|---|---|"]
L += [f"| `{m['rule']}` | {cell(m['name'])} | {'✅' if m.get('effective') else '❌'} | "
      f"{'✅' if m.get('executed') else '❌'} {_lines(m)} | {'✅ killed' if m['outcome'] == 'killed' else '❌ ' + m['outcome']} |"
      for m in sorted(_ms, key=lambda m: (m['outcome'] == 'killed', m['rule'], m['name']))]
L += ["", "</details>", ""]
print(f"Mutant report: {_n} mutants, effective {_eff}/{_n}, executed {_exe}/{_n}, "
      + ", ".join(f"{o} {c}" for o, c in sorted(_oc.items())))
if gate_bad and GATE == 'strict':
    L += ["### Mutation gate failed", "",
          "Every mutant must be reached by `test_verifier_enforcement.py`, change the verifier, and be killed:", "",
          "| Rule | Mutant | Outcome |", "|---|---|---|"] + [f"| `{m['rule']}` | {cell(m['name'])} | {m['outcome']} |" for m in gate_bad] + [
          "", "Set `MUTATION_GATE: off` to rely on the score thresholds alone.", ""]
if schema_errors:
    L += ["### mutation-results.json failed schema validation", ""] + [f"- {cell(e)}" for e in schema_errors] + [
          "", "See `mutation-results.schema.json` for required fields and allowed `outcome` values.", ""]
L += mutation_history.markdown(h_prev, h_rows, h_regressions)
if weak_rules:
    L += [f"**{len(weak_rules)} rule(s) below the per-rule minimum:** " + ", ".join(f"`{k}` ({v['score']:.1f}%)" for k, v in weak_rules.items()), ""]
if not mut['baseline_ok']:
    L += ["### Mutation testing invalid", "", "The enforcement suite fails on the *unmutated* verifier, so mutation results are meaningless. Fix it first:", "", "```", mut['baseline_output'][-3000:], "```", ""]
if mut['missing_targets']:
    L += ["### Mutation targets not found", "", "These mutants couldn't be applied because their code isn't in `verify.py` exactly once (update `MUTANTS` in `tests/test_verifier_mutations.py`):", ""] + [f"- {n}" for n in mut['missing_targets']] + [""]
if mut['ineffective']:
    L += ["### Ineffective mutation targets", "",
          "These mutants don't change the verifier at all (original and mutated code are identical), "
          "so they can't prove the tests detect anything. Fix or remove them in `MUTANTS`:", ""] + [f"- {n}" for n in mut['ineffective']] + [""]
if mut['not_executed']:
    L += ["### Mutated code never executed", "",
          "These mutants changed code that never runs during a green verifier pass, so a 'detected' "
          "result would be meaningless. Pick targets on live code paths:", ""] + [f"- {n}" for n in mut['not_executed']] + [""]
survivors = [m for m in mut['results'] if not m['killed']]
if survivors:
    L += [f"### Surviving mutations ({len(survivors)})" + ("" if ok_m else " — below minimum"), "",
          "Each of these breaks the verifier, but `tests/test_verifier_enforcement.py` still passed. Add a unit test that fails for it.", "",
          "| Mutant | Original | Mutated |", "|---|---|---|"]
    L += [f"| {m['name']} | `{cell(m['original'].strip())}` | `{cell(m['mutated'].strip())}` |" for m in survivors] + [""]
if not ok_p:
    L += ["### Scenario-to-test parity below minimum", "",
          f"Parity is **{parity:.1f}%**, short of the **{MIN_PARITY:g}%** minimum. "
          f"{len(unmapped)} scenario(s) have no regression test referencing their ID:", "",
          ", ".join(f"`{t}`" for t in unmapped), "",
          "Add a regression test whose docstring names each ID (e.g. `\"\"\"TR-07: ...\"\"\"`), or lower `MIN_PARITY` in the workflow.", ""]
if cov_pct is not None and not ok_c:
    L += ["### Coverage below minimum", "",
          f"Coverage is **{cov_pct:.1f}%**, short of the **{MIN_COVERAGE:g}%** minimum by {MIN_COVERAGE - cov_pct:.1f} points.", "",
          f"Uncovered lines in `verify.py`: {ranges(cov_missing)}", "",
          "Add regression tests that exercise these lines, or lower `MIN_COVERAGE` in the workflow if intentional.", ""]
elif cov_pct is None:
    L += ["### Coverage not measured", "", "The `coverage` package is not installed (`pip install coverage`).", ""]
if r.get('audit_errors'):
    L += ["### Verifier audit errors (execution halted)", ""] + [f"- {cell(e)}" for e in r['audit_errors']] + [""]
if r.get('failed'):
    L += ["### Failed scenarios", "", "| ID | Scenario | Error |", "|---|---|---|"]
    L += [f"| {f['tr']} | {cell(f['name'])} | {cell(f['error'])} |" for f in r['failed']] + [""]
if problems:
    L += ["### Failed regression tests", ""]
    for test, tb in problems:
        L += [f"<details><summary><code>{test.id()}</code></summary>", "", "```", tb.strip()[-3000:], "```", "</details>", ""]
md = "\n".join(L)
out = os.environ.get('GITHUB_STEP_SUMMARY')
if out:
    with open(out, 'a') as f: f.write(md + "\n")
else:
    print(md)
sys.exit(0 if ok_v and ok_t and ok_c and ok_p and ok_m and ok_schema and ok_gate else 1)
