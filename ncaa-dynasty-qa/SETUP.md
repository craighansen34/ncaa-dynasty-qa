# NCAA Dynasty QA Suite — Setup Guide

Requires Python 3.10–3.14 (see **Supported Python versions**). The verifier and tests use the standard library only; the optional coverage report needs `pip install coverage`.

## Layout

```
verify.py                              # 3-stage verifier (audit + execution)
features/
  recruiting_budget_and_visits.feature.md   # TR-01..TR-21, TR-43..TR-47, TR-73..TR-82
  coach_progression_and_perks.feature.md    # TR-22..TR-42, TR-48..TR-50
  player_roster_and_season.feature.md       # TR-51..TR-72
tests/
  test_xp_regression.py                # XP curve / TR-24 invariant tests
  test_verifier_fault_injection.py     # verifier self-tests (must fail loudly)
  test_edge_case_regression.py         # TR-43..TR-50 edge-case tests
  test_player_roster_regression.py   # TR-51..TR-72 roster/season tests
  test_recruiting_class_regression.py # TR-73..TR-82 prospects, offers, signing classes
.github/workflows/qa.yml               # CI: runs everything on push and PR
```

## Commands

Run from the folder containing `verify.py`:

```bash
# 1. Scenario verifier — all 92 scenarios
python3 verify.py

# 2. Regression tests
python3 -m unittest discover -s tests -p "test_*.py"

# 3. Full CI command (what GitHub Actions runs)
python3 verify.py && python3 -m unittest discover -s . -p "test_*.py"
```

## Expected results

- `verify.py` prints three sections and exits `0`:
  - **Section 1** — 92 scenarios parsed, no duplicate TR IDs, no orphaned rules or scenarios.
  - **Section 2** — 0 unmatched phrases, 0 ambiguous phrases.
  - **Section 3** — `Passed: 50/50   Failed: 0`.
- Regression tests: `Ran 65 tests ... OK`.
- Any audit or scenario failure exits with status `1` and names the offending TR ID or phrase.

## Adding a new scenario

1. **Pick the next TR ID** (e.g. `TR-109`). IDs must be unique and contiguous — the verifier expects exactly `TR-01..TR-102` today, so also bump the expected range in `verify.py` (`range(1, 103)` → `range(1, 104)`) and the count string (`expected: 102`).
2. **Write the scenario** in the appropriate `features/*.feature.md` file:
   ```gherkin
   Scenario: TR-51 Short descriptive title
     Given some setup step
     When the action happens
     Then the outcome evaluates to 42
   ```
3. **Add step definitions** in `verify.py` for any new phrasing:
   ```python
   @step(r'the outcome evaluates to (?P<n>\d+)')
   def _(c, n): assert c['b'].some_value == int(n)
   ```
   Rules:
   - Patterns are anchored to the full phrase (`\Z` is appended automatically) — make them specific enough that no two patterns match the same phrase, or Section 2 fails with an ambiguity error.
   - Steps receive the context dict `c` with `c['b']` (a `Budget`) and `c['c']` (a `Coach`); add fields to those classes if the scenario needs new state.
4. **Add a regression test** in `tests/` mirroring the scenario's core invariant.
5. **Run the full CI command** — the verifier halts before execution if any audit fails, so fix Section 1/2 errors first.

## Continuous integration

`.github/workflows/qa.yml` runs the verifier and all regression tests on every
push and pull request, on every supported Python version. A red build means either
an audit failure (traceability/phrasing) or a scenario/test failure — the log
names the offending item.

## CI report and coverage rules

- `python3 ci_summary.py` runs both suites and prints a Markdown report (in GitHub Actions it's written to the job summary with counts plus failing scenario IDs, errors, and test tracebacks). Exits 1 on any failure.
- The verifier now fails if a scenario ID is duplicated or missing, or if any scenario after TR-42 isn't mentioned (e.g. `"TR-51: ..."` in a docstring) in some `tests/test_*.py` file. So every new scenario needs a matching regression test.
- The job summary also reports how much of `verify.py` the regression tests exercise. The job fails if that falls below `MIN_COVERAGE` (default 80%, set in `.github/workflows/qa.yml`), and the summary lists the uncovered line numbers. Locally: `pip install coverage`, then `MIN_COVERAGE=90 python3 ci_summary.py`.
- `tests/test_verifier_enforcement.py` runs the real verifier against broken inputs (duplicate IDs, missing test mappings, scenarios with no ID, no steps, or unknown steps) to keep these rules enforced.
- The summary reports scenario-to-test parity: the share of scenario IDs mentioned in at least one regression test. The job fails below `MIN_PARITY` (default 20%, set in the workflow) and lists every unmapped scenario ID. Locally: `MIN_PARITY=50 python3 ci_summary.py`.
- `tests/test_verifier_mutations.py` breaks each rule in a temporary copy of `verify.py` (duplicate IDs, test mapping, missing ID, no steps, unknown or ambiguous steps, orphaned rules, orphaned scenarios, failing scenarios) and fails if `test_verifier_enforcement.py` doesn't catch it. If you rewrite one of those checks, update its entry in `MUTANTS`.

- **Mutation score:** the summary shows how many verifier mutants the unit suite detected, e.g. 8/8. The job fails below `MIN_MUTATION_SCORE` (default 100%), and every surviving mutant is listed with the code it changed.
- **Threshold settings:** `MIN_COVERAGE`, `MIN_PARITY` and `MIN_MUTATION_SCORE` must each be a number from 0 to 100 (a trailing `%` is allowed; leave blank to use the default). If a value can't be read as a number, or is out of range, CI stops before running anything, exits with code 2, and the summary explains how to fix it.

- **Per-rule mutation score:** every mutant is tagged with the verifier rule it breaks (`duplicate-id`, `regression-mapping`, `missing-id`, `no-steps`, `unknown-step`, `ambiguous-step`, `orphaned-rule`, `orphaned-scenario`, `scenario-execution`). The summary shows a score for each rule, and CI fails if any single rule is below `MIN_RULE_MUTATION_SCORE` (default 100%), even when the overall score passes. Tag new mutants with their rule as the first field in `MUTANTS`.
- **Surviving-mutant advisor:** the QA web app's home page takes a surviving mutant's code change and test output and uses Lovable AI to draft one focused test for `test_verifier_enforcement.py`. Review the suggestion before adding it.

## CI threshold settings

`ci_summary.py` reads four thresholds from environment variables. In CI they're set under `env:` in `.github/workflows/qa.yml`.

| Variable | Default | What it measures | Fails when |
|---|---|---|---|
| `MIN_COVERAGE` | `80` | % of `verify.py` lines run by the regression tests (needs `pip install coverage`) | coverage is below the value, or the coverage tool isn't installed |
| `MIN_PARITY` | `20` | % of scenario IDs (TR-xx) named in at least one `tests/test_*.py` file | parity is below the value; every unmapped ID is listed |
| `MIN_MUTATION_SCORE` | `100` | % of all verifier mutants the enforcement tests detect | the overall score is below the value; surviving mutants are listed |
| `MIN_RULE_MUTATION_SCORE` | `100` | % of mutants detected for **each** verifier rule, checked separately | any single rule is below the value, even if the overall score passes |

**Accepted formats.** A number from 0 to 100 inclusive. Decimals (`87.5`), surrounding spaces and a trailing `%` (`90%`) are allowed, and a blank or unset value uses the default. The following are rejected: text (`eighty`), `nan`/`inf`, negative numbers, and anything above 100. Fractions aren't converted, so `0.8` means 0.8%, not 80%.

**Exit codes.**

| Code | Meaning |
|---|---|
| `0` | everything passed |
| `1` | a scenario, regression test, coverage, parity or mutation check failed; the job summary shows the details |
| `2` | a threshold setting is invalid. Nothing was run, and the summary names each bad variable, what's wrong with it, and the allowed range, plus every variable's default |

**Example CI configuration:**

```yaml
jobs:
  verify:
    runs-on: ubuntu-latest
    env:
      MIN_COVERAGE: "85"
      MIN_PARITY: "25"
      MIN_MUTATION_SCORE: "100"
      MIN_RULE_MUTATION_SCORE: "100"
    strategy:
      fail-fast: false
      matrix:
        python-version: ["3.10", "3.11", "3.12", "3.13", "3.14"]
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: ${{ matrix.python-version }}
      - run: python -m pip install coverage
      - run: python ci_summary.py
```

**Locally:** `MIN_PARITY=50 MIN_COVERAGE=90 python3 ci_summary.py`. Without `GITHUB_STEP_SUMMARY` set, the report prints to the terminal.

`tests/test_ci_end_to_end.py` runs `ci_summary.py` on a temporary copy of the suite to check these rules. It confirms every variable rejects bad values with exit code 2 and clear guidance, that a clean run exits 0, and that with the duplicate-ID tests removed the run exits 1, shows `duplicate-id` below its per-rule minimum, and lists the surviving mutants with their code changes.

To keep this fast, the slow part of CI (regression suite plus mutation run) runs for real only twice: once on a clean copy and once on a copy with the duplicate-ID tests removed. Every other case reuses that result through the test-only `QA_RESULTS_CACHE` setting, and `ci_summary.py` still re-runs the verifier and re-checks every threshold, the gate, the results file, its schema, the history and the job summary. Invalid thresholds stop CI before anything runs, so they need no reuse. Never set `QA_RESULTS_CACHE` in the workflow.

## Supported Python versions

**Supported: CPython 3.10, 3.11, 3.12, 3.13, 3.14.**

Policy: we support every CPython release that is still maintained upstream (bugfix or security phase; see python.org/downloads). CI tests each one in `.github/workflows/qa.yml`, and that matrix is the definitive list. When a release reaches end of life it's removed from the matrix and this list; when a new one comes out, it's added once `actions/setup-python` offers it. Other versions may work, but they aren't tested or supported.

## Mutation-target validation

CI also validates the mutation suite itself, so a 100% score can't come from
skipped or ineffective mutants. Each entry in `MUTANTS` (in
`tests/test_verifier_mutations.py`) must:

- match `verify.py` exactly once (missing targets are listed in the summary),
- actually change the source — a no-op mutant is reported under
  **Ineffective mutation targets** and fails the run,
- sit on a code path that really executes during a green verifier pass —
  mutants on dead code are reported under **Mutated code never executed**.

`MIN_RULE_MUTATION_SCORE` (default 100) sets the per-rule minimum; every rule
must meet it on its own. End-to-end tests in `tests/test_ci_end_to_end.py`
cover the default, valid overrides, and the failure report when a rule misses
its minimum.

## Per-mutant CI artifact

Each CI run writes `mutation-results.json` (uploaded as `mutation-results-py<version>`). One record per mutant:
`rule`, `name`, `original`, `mutated`, `effective` (false when the text or AST is unchanged), `mutated_lines`,
`executed_lines` (mutated lines actually run by `test_verifier_enforcement.py` — lines reached only by other tests don't count),
`executed`, `killed`, and `outcome` (`killed`, `survived`, `ineffective`, or `target_not_found`).
Behaviour-preserving mutants that do change the AST are reported as `survived`, never as detected.

### Mutant report in the job summary

The job summary has a **Mutant report** section: one line with totals (how many mutants are effective, how many had their changed lines executed, and the count per outcome), then a collapsible table with one row per mutant — rule, name, effective ✅/❌, executed ✅/❌ with "lines run of changed lines", and outcome. Unkilled mutants are listed first. The same totals are printed in the job log as `Mutant report: ...`.

### Schema, strict gate, and reproducing a run

- `mutation-results.schema.json` defines the artifact (schema_version 2). CI validates it with the stdlib-only
  `validate_artifact.py` and fails with each bad field and mutant named. Run it yourself: `python3 validate_artifact.py mutation-results.json`.
- `outcome` is one of `killed`, `survived`, `unreached` (changed lines never run by the enforcement suite), `ineffective`, `target_not_found`.
- **Mutation gate** (`MUTATION_GATE`, default `strict`): CI fails if any mutant is not `killed`, regardless of the score
  thresholds. Set it to `off` to rely on `MIN_MUTATION_SCORE` / `MIN_RULE_MUTATION_SCORE` alone. The job log prints
  one line per rule with its outcome counts.
- Each artifact's `reproduce` block holds the seed (`QA_SEED`, default 0, also used as `PYTHONHASHSEED`), the Python
  version, the enforcement tests run, the mutants applied, and the exact command to repeat the run locally.

## Season rollover

`Roster.rollover_season(season=None)` is all-or-nothing and safe to retry: changes are staged on a copy and committed
together, and a season that is already archived (or isn't the current one) is a no-op returning `False`.
Tests: `tests/test_season_rollover.py`.

## Mutation history report

`mutation_history.py` appends each run's per-rule outcome counts to `mutation-history.json` (kept between CI runs
with `actions/cache`, one history per Python version, last 50 runs) and compares against the previous run on the
same Python version. The job summary shows a per-rule table; a rule is flagged **regressed** if its killed count
drops, its survived / unreached / ineffective / target-not-found count grows, or it loses all its mutants.
The history report only flags regressions; failing CI is left to the strict gate.
View it locally with `python3 mutation_history.py mutation-history.json`.

CI always uploads `mutation-results.json`, `mutation-results.validation.txt` (schema diagnostics) and
`mutation-history.json`, even when the gate or schema check fails.

## Rollover audit log

Each committed rollover appends to `Roster.audit_log`: `season_id`, `archived_record`, `completed_at` (UTC ISO-8601;
override `Roster.clock` in tests), and `transitions` — one per player with `from_year`, `to_year` (null if graduated)
and `action` (`advanced`, `redshirt_hold`, `graduated`). Failed or repeated rollovers add no entry.

## Web dashboard

The app's `/dashboard` page shows per-rule mutation scores, the mutation history and a season-rollover audit log. After `python3 ci_summary.py`, run `python3 export_dashboard.py` to refresh the bundled snapshot (`src/data/qa-snapshot.json`). To view a GitHub run, download its `mutation-results.json` / `mutation-history.json` artifacts and use the page's "Load files" button.

## Web game

The `/game` page plays a dynasty with the same rules. Rule numbers (roster limit, deadline, season length, prestige, recruiting hours, offers) live in `rules.json`; edit them there and both the suite and the game use the new value. Rule logic changes also need the matching edit in `src/lib/dynasty/engine.ts`.

Two checks keep them in step:
- `tests/test_shared_rules.py` (runs in CI) checks `verify.py` and the game both read `rules.json`.
- `web/test_game_parity.py` (needs Playwright and the running app) plays `/game` and `verify.Roster` side by side: hours at every prestige level, prestige after seasons at each win threshold and at 0.5/5 stars, the roster cap, the transfer deadline and season length. Run `python3 web/test_game_parity.py --url http://localhost:8080`; exit 1 lists every mismatch.

### Dashboard: results from GitHub Actions

On `/dashboard`, type the repository (`owner/repo`) and press **Load from GitHub**. It lists recent QA workflow runs; **Show results** downloads that run's `mutation-results-py*` files and shows one button per Python version. When the whole app is the repository, the root `.github/workflows/qa.yml` runs the suite from `ncaa-dynasty-qa/`; keep it in step with this folder's copy.

The script also writes `src/data/game-parity.json`; the QA dashboard shows it under "Play dynasty vs. test suite rules". Rerun the script to refresh it.

## Prestige (report card)

Team Prestige is the average of 11 school grades (`SCHOOL_GRADES` in rules.json, scale F..A+ = 0-10 = half stars), rounded to the nearest half star (0.5-5). Only Championship Contender, Brand Exposure and Program Tradition change after a season, one step at the win thresholds in `GRADE_SEASON_CHANGES`. EA does not publish those step sizes, so they are estimates; edit rules.json to change them. Scenarios TR-103..TR-108.
