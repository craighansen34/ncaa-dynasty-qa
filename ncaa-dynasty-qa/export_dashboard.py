"""Export mutation results, mutation history and a season-rollover audit log
into one JSON snapshot for the web dashboard (src/data/qa-snapshot.json).
Stdlib only. Run after `python3 ci_summary.py`:
    python3 export_dashboard.py [--out PATH]
"""
import argparse, datetime, json, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from verify import Roster, Player  # noqa: E402


def load(name):
    p = os.path.join(HERE, name)
    return json.load(open(p)) if os.path.exists(p) else None


def demo_audit_log():
    """Plays a four-season demo dynasty through the real rollover code."""
    r = Roster()
    for i, year in enumerate([1, 1, 2, 3, 4, 4], 1):
        r.add(Player(f"P{i}", year))
    r.redshirt("P5")
    for wins in (11, 7, 3, 10):
        for g in range(12):
            r.play_game(won=g < wins)
        r.rollover_season()
        r.add(Player(f"Frosh{r.season}", 1))
    return r.audit_log


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=os.path.join(HERE, "..", "src", "data", "qa-snapshot.json"))
    args = ap.parse_args()
    snap = {
        "generated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "results": load("mutation-results.json"),
        "history": (load("mutation-history.json") or {}).get("runs", []),
        "audit_log": demo_audit_log(),
        "audit_log_source": "demo four-season dynasty played through Roster.rollover_season",
    }
    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    json.dump(snap, open(args.out, "w"), indent=1)
    print(f"Wrote {os.path.abspath(args.out)}")


if __name__ == "__main__":
    main()
