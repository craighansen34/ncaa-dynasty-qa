"""Browser test: opens the Rules test suite page (/rule-tests) with a fresh team,
plays seasons at several win totals and records every rule's result.
Needs Playwright and a running app (runs in the GitHub game-parity job).

    python3 web/test_rule_checks.py [--url http://localhost:8080] [--out file.json]
"""
import json, os, sys
from datetime import datetime, timezone
from playwright.sync_api import sync_playwright

HERE = os.path.dirname(os.path.abspath(__file__))
URL = sys.argv[sys.argv.index("--url") + 1] if "--url" in sys.argv else "http://localhost:8080"
OUT = sys.argv[sys.argv.index("--out") + 1] if "--out" in sys.argv else os.path.join(HERE, "..", "..", "src", "data", "rule-checks.json")
WINS = [0, 3, 6, 9, 12]

checks = []
with sync_playwright() as p:
    b = p.chromium.launch(headless=True)
    page = b.new_page()
    page.goto(URL + "/rule-tests")
    page.evaluate("localStorage.clear()")
    page.reload()
    page.locator("main[data-loaded=true]").wait_for()
    for w in WINS:
        page.get_by_label("Season wins").fill(str(w))
        page.wait_for_function(f"[...document.querySelectorAll('tr[data-check]')].every(r => JSON.parse(r.dataset.check).wins === {w})")
        for raw in page.locator("tr[data-check]").evaluate_all("rs => rs.map(r => r.dataset.check)"):
            checks.append(json.loads(raw))
    b.close()

failed = [c for c in checks if not c["pass"]]
for c in failed:
    print(f"FAIL {c['group']} · {c['rule']} (wins={c['wins']}): expected {c['expected']}, got {c['actual']}")
out = {"generated_at": datetime.now(timezone.utc).isoformat(), "passed": len(checks) - len(failed), "total": len(checks), "checks": checks}
with open(OUT, "w") as f:
    json.dump(out, f, indent=1)
print(f"{out['passed']}/{out['total']} rule checks pass")
sys.exit(1 if failed else 0)
