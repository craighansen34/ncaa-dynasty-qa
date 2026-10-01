"""CI history for mutation outcomes: append each run's per-rule outcome
counts to a JSON history file and compare against the previous run.

A *regression* is any rule whose killed count dropped, or whose count of
survived / unreached / ineffective / target_not_found mutants grew.
Stdlib only. Usage: python3 mutation_history.py [history.json]  (prints the latest comparison)"""
import json, os, sys

BAD = ("survived", "unreached", "ineffective", "target_not_found")
MAX_RUNS = 50


def rule_outcomes(artifact):
    """{rule: {outcome: count}} from a mutation-results.json document."""
    out = {}
    for m in artifact.get("mutants", []):
        d = out.setdefault(m["rule"], {})
        d[m["outcome"]] = d.get(m["outcome"], 0) + 1
    return dict(sorted(out.items()))


def load(path):
    if not path or not os.path.exists(path):
        return []
    try:
        data = json.load(open(path))
    except ValueError:
        return []
    return data.get("runs", []) if isinstance(data, dict) else []


def compare(prev, cur):
    """Return (rows, regressions). Each row: rule, previous counts, current counts, status."""
    rows, regressions = [], []
    p_rules, c_rules = (prev or {}).get("rules", {}), cur["rules"]
    for rule in sorted(set(p_rules) | set(c_rules)):
        p, c = p_rules.get(rule, {}), c_rules.get(rule, {})
        why = []
        if prev is not None:
            if rule not in c_rules:
                why.append("rule no longer has mutants")
            if c.get("killed", 0) < p.get("killed", 0):
                why.append(f"killed {p.get('killed', 0)} → {c.get('killed', 0)}")
            for o in BAD:
                if c.get(o, 0) > p.get(o, 0):
                    why.append(f"{o} {p.get(o, 0)} → {c.get(o, 0)}")
        if prev is None or rule not in p_rules:
            status = "new"
        elif why:
            status = "regressed"
        elif c != p:
            status = "improved" if c.get("killed", 0) > p.get("killed", 0) else "changed"
        else:
            status = "unchanged"
        row = {"rule": rule, "previous": p, "current": c, "status": status, "details": why}
        rows.append(row)
        if status == "regressed":
            regressions.append(row)
    return rows, regressions


def record(path, artifact, run_id=None):
    """Append this run to the history file; return (previous_run_or_None, current_run, rows, regressions)."""
    runs = load(path)
    cur = {"run_id": run_id or os.environ.get("GITHUB_RUN_ID") or f"local-{len(runs) + 1}",
           "python": artifact.get("reproduce", {}).get("python"),
           "rules": rule_outcomes(artifact)}
    prev = next((r for r in reversed(runs) if r.get("python") == cur["python"]), None)
    rows, regressions = compare(prev, cur)
    runs = (runs + [cur])[-MAX_RUNS:]
    if path:
        with open(path, "w") as f:
            json.dump({"schema_version": 1, "runs": runs}, f, indent=2)
    return prev, cur, rows, regressions


def fmt(counts):
    return ", ".join(f"{n} {o}" for o, n in sorted(counts.items())) or "—"


def markdown(prev, rows, regressions):
    L = ["### Mutation history (vs previous run)", ""]
    if prev is None:
        L += ["No previous run on this Python version — this run is the new baseline.", ""]
    else:
        L += [f"Compared with run `{prev['run_id']}`.", ""]
    L += ["| Rule | Previous | Current | Status |", "|---|---|---|---|"]
    icon = {"regressed": "❌ regressed", "improved": "✅ improved", "new": "🆕 new",
            "unchanged": "unchanged", "changed": "changed"}
    L += [f"| `{r['rule']}` | {fmt(r['previous'])} | {fmt(r['current'])} | {icon[r['status']]}"
          + (f" ({'; '.join(r['details'])})" if r['details'] else "") + " |" for r in rows] + [""]
    if regressions:
        L += [f"**{len(regressions)} rule(s) regressed since the previous run:** "
              + ", ".join(f"`{r['rule']}`" for r in regressions), ""]
    return L


if __name__ == "__main__":
    runs = load(sys.argv[1] if len(sys.argv) > 1 else "mutation-history.json")
    if not runs:
        print("No history."); sys.exit(0)
    prev = runs[-2] if len(runs) > 1 else None
    rows, regs = compare(prev, runs[-1])
    print("\n".join(markdown(prev, rows, regs)))
    sys.exit(1 if regs else 0)
