"""Browser test: plays the /game page and the verifier's Roster side by side and
checks they agree on prestige, recruiting hours, roster limit, transfer
deadline and season length. Needs Playwright and a running app (not part of the
stdlib CI suite).

    python3 web/test_game_parity.py [--url http://localhost:8080]
"""
import json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
import verify as v  # noqa: E402
from playwright.sync_api import sync_playwright  # noqa: E402

URL = sys.argv[sys.argv.index("--url") + 1] if "--url" in sys.argv else "http://localhost:8080"
KEY = "ncaa-dynasty-game-v1"
failures = []
checks = []
OUT = sys.argv[sys.argv.index("--out") + 1] if "--out" in sys.argv else os.path.join(HERE, "..", "..", "src", "data", "game-parity.json")


def check(label, web, py):
    ok = web == py
    print(("PASS" if ok else "FAIL"), f"{label}: web={web!r} rules={py!r}")
    checks.append({"check": label, "web": web, "rules": py, "ok": ok})
    if not ok:
        failures.append(label)


def state(prestige=3, players=12, week=1, games=0, wins=0):
    ps = [{"name": f"P{i}", "year": 1, "redshirted": False, "starter": False, "injuryWeeks": 0} for i in range(players)]
    return {"players": ps, "wins": wins, "losses": games - wins, "gamesPlayed": games, "season": 1,
            "week": week, "prestige": prestige, "history": [], "auditLog": []}


def load(page, s):
    page.evaluate(f"localStorage.setItem({json.dumps(KEY)}, {json.dumps(json.dumps(s))})")
    page.goto(URL + "/game")
    page.locator("main[data-loaded=true]").wait_for()


def num(page, tid):
    return float(page.get_by_test_id(tid).inner_text())


def alert(page):
    a = page.get_by_role("alert")
    return a.inner_text() if a.count() else None


with sync_playwright() as pw:
    page = pw.chromium.launch(headless=True).new_page(viewport={"width": 1280, "height": 1800})
    page.set_default_timeout(90_000)  # first dev-server load can be slow
    page.goto(URL + "/game")
    page.once("dialog", lambda d: d.accept())

    # Recruiting hours at every prestige level
    for p, hours in v.WEEKLY_HOURS.items():
        load(page, state(prestige=p))
        check(f"hours at {p} stars", num(page, "hours"), hours)

    # Report-card prestige: win totals at and around every grade threshold, the limits,
    # and two 11-win seasons (the first one alone does not move prestige).
    wins_set = sorted({w for t in v.GRADE_SEASON_CHANGES.values()
                       for w in (t["up_wins"], t["up_wins"] - 1, t["down_wins"], t["down_wins"] + 1)})
    cases = [(3, (w,)) for w in wins_set] + [(v.MAX_PRESTIGE, (v.SEASON_WEEKS,)), (v.MIN_PRESTIGE, (0,)), (3, (11, 11))]
    for start, seasons in cases:
        r = v.Roster(); r.prestige = start
        load(page, state(prestige=start))
        for n, wins in enumerate(seasons, 1):
            for g in range(v.SEASON_WEEKS):
                r.play_game(g < wins)
                page.get_by_role("button", name="Win" if g < wins else "Loss", exact=True).click()
            r.rollover_season()
            page.get_by_role("button", name=f"End season {n}").click()
        tag = f"{start}★ after {'-'.join(map(str, seasons))} wins"
        check(f"prestige {tag}", num(page, "prestige"), r.prestige)
        check(f"hours {tag}", num(page, "hours"), v.WEEKLY_HOURS[r.prestige])
        page.get_by_test_id("report-card").locator("summary").click()
        web_card = {g: page.get_by_test_id(f"grade-{g}").inner_text() for g in v.SCHOOL_GRADES}
        check(f"report card {tag}", web_card, {g: v.GRADE_SCALE[i] for g, i in r.grades.items()})

    # Roster limit: signing one past the cap
    r = v.Roster()
    for i in range(v.MAX_ROSTER):
        r.add(v.Player(f"P{i}"))
    py_ok = r.add(v.Player("Extra"))
    load(page, state(players=v.MAX_ROSTER))
    page.get_by_label("Player name").fill("Extra")
    page.get_by_role("button", name="Sign player").click()
    check("roster count at cap", page.get_by_test_id("roster").inner_text(), f"{r.count} / {v.MAX_ROSTER}")
    check("signing past cap blocked", alert(page) is not None, not py_ok)

    # Transfer deadline: last allowed week and first blocked week
    for week in (v.TRANSFER_DEADLINE_WEEK, v.TRANSFER_DEADLINE_WEEK + 1):
        r = v.Roster(); r.week = week
        py_ok = r.transfer_in(v.Player("T"))
        load(page, state(week=week, games=week - 1))
        page.get_by_label("Player name").fill("T")
        page.get_by_role("button", name="Add as transfer").click()
        check(f"transfer in week {week} allowed", alert(page) is None, py_ok)

    # Season length: the game stops after SEASON_WEEKS games
    load(page, state())
    for _ in range(v.SEASON_WEEKS):
        page.get_by_role("button", name="Win", exact=True).click()
    check("record after full season", page.get_by_test_id("record").inner_text(), f"{v.SEASON_WEEKS}–0")
    check("no games after last week", page.get_by_role("button", name="Win", exact=True).is_disabled(), True)

import datetime
with open(OUT, "w") as f:
    json.dump({"generated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(), "url": URL,
               "passed": len(checks) - len(failures), "total": len(checks), "checks": checks}, f, indent=1)
print("Wrote", os.path.abspath(OUT))
print(f"\n{len(failures)} mismatch(es)" if failures else "\nWeb game matches the test suite's rules.")
sys.exit(1 if failures else 0)
