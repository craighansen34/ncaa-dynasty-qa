# NCAA Football Dynasty QA Specification & Verifier

Dependency-free QA suite, executable Gherkin feature specifications, and regression tests for NCAA Football Dynasty Mode front-office and coaching simulation mechanics.

## Quick Start (Zero Dependencies)

Runs on Python 3.10–3.14 using only the standard library; no pytest or other test runner needed. See SETUP.md for the version support policy and CI thresholds.

### 1. Run Scenario Verifier (All 50 Scenarios)
```bash
python3 verify.py
```
Runs the strict 3-stage pipeline:
- **Section 1: Traceability Audit** (detects duplicate TR IDs, missing rules, unmapped scenarios).
- **Section 2: Phrase Coverage & Ambiguity Audit** (detects unmatched phrases and overlapping step patterns).
- **Section 3: Deterministic Execution** (runs all 92 scenarios against domain models).
Exits with status `0` on success, or `1` on any audit or scenario failure.

### 2. Run Regression Tests
```bash
python3 -m unittest test_verifier_fault_injection.py test_xp_regression.py
```
- `test_xp_regression.py`: Protects TR-24's 550 XP calculation, dynamic threshold curve (`1000 + (L-1)*200`), static-threshold prevention, boundary crossings, and Level 50 cap behavior.
- `test_verifier_fault_injection.py`: Subprocess tests confirming the verifier halts with exit code 1 and identifies the offending item for duplicate IDs, orphaned scenarios, missing phrases, and pattern ambiguity.

### 3. CI / Pipeline Command
```bash
python3 verify.py && python3 -m unittest discover -s . -p "test_*.py"
```

---

## Traceability Summary (TR-01 through TR-82)

- **TR-01 to TR-07**: Recruiting hour staging, live reservations, drawer dismissals, edits, and target removal refunds.
- **TR-08 to TR-12**: Official visit bookings, 50h deposits, same-week refund (50h), post-advance cancellation (0h refund), and rival commitment / lockout relief credits (+25h).
- **TR-13 to TR-16**: Relief credit stacking, over-cap capacity, and strict week rollover expiration.
- **TR-17 to TR-21**: Weekly auto-renewal, ineligible recruit purging, budget cut priority trimming, and 4-visitor weekly capacity limits.
- **TR-22 to TR-26**: Coach XP progression curve (`1000 + (L-1)*200`), single & multi-level XP cascade math (TR-24 550 XP invariant), and SP accounting (`15 + (L-1)*10`).
- **TR-27 to TR-31**: Archetype discount (20%), perk tier gating (20 SP Tier 2, 50 SP Tier 3), and unspent SP balance enforcement.
- **TR-32 to TR-35**: Coordinator synergy, poaching fallout, mandatory retirement (age 70 / 50 seasons), and gameday advance blockers.
- **TR-36 to TR-42**: Visitor home game capacity, cross-module state isolation, 50-year career tracking, contract buyouts, Level 50 cap arrival (`current_xp = 0`, `xp_to_next_level = null`), cap freeze, and massive XP overflow truncation.
- **TR-43 to TR-50**: Relief-credit overdraft ceilings, zero-hour staging no-ops, exact 4-visit capacity boundary, same-week refund floor at zero, rollover discard of unconfirmed staged hours, retirement boundaries (50 seasons exact, age 69 / 49 seasons negative case), and zero-XP gain no-ops.
- **TR-51 to TR-58**: Player management and roster changes (85-man cap enforcement, cuts, transfer portal departures, redshirt eligibility preservation, senior graduation, year advancement, depth-chart promotion) and season record tracking.
- **TR-59 to TR-61**: Season rollover — archives the final record, advances eligible players, and resets season-specific state (record, starters, roster-full error).
- **TR-62 to TR-64**: Roster-move deadline — incoming transfers allowed through week 8, blocked after, window reopens at rollover (college football has no trades, so this is the deadline).
- **TR-65 to TR-69, TR-72**: Injuries — injured starters leave the lineup, cannot be promoted until healed, revisions replace the timeline, healing stops at zero, unknown players rejected, no advancing past week 12.
- **TR-70 to TR-71**: Dynasty progression — program prestige runs 0.5–5 stars in half-star steps (EA College Football 26); 10+ wins raises it half a star, 3 or fewer lowers it half a star (the game doesn't publish its formula, so these thresholds are approximate); the offseason heals injuries.
- **TR-93 to TR-102**: EA College Football 26 rules — weekly recruiting hours by prestige (300–1000, with a preseason bonus), unused hours don't carry over, 50 hours per prospect per week, a scholarship offer costs 5 hours, 35 offers per season; SEC standings by conference win percentage, then head-to-head, then record vs common opponents. The older 85-scholarship roster rules are kept as legacy.
- **TR-73 to TR-82**: Recruiting — a 35-prospect board (1-5 star ratings, no duplicates), scholarship offers that can be rescinded, a 25-player signing class that must fit within the 85 scholarships, and enrollment of signees as freshmen.
