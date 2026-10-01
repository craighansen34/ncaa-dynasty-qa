"""The test suite and the Play dynasty page read the same rules.json."""
import json, os, sys, unittest
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import verify  # noqa: E402

RULES = json.load(open(os.path.join(ROOT, "rules.json")))
SCALARS = ["MAX_ROSTER", "TRANSFER_DEADLINE_WEEK", "SEASON_WEEKS", "MIN_PRESTIGE", "MAX_PRESTIGE", "PRESTIGE_STEP",
           "GRADE_SCALE", "SCHOOL_GRADES", "GRADE_SEASON_CHANGES", "PROSPECT_WEEKLY_HOUR_CAP", "OFFER_HOUR_COST",
           "SCHOLARSHIP_OFFERS_PER_SEASON"]


class SharedRules(unittest.TestCase):
    def test_verifier_numbers_come_from_rules_file(self):
        for k in SCALARS:
            self.assertEqual(getattr(verify, k), RULES[k], k)
        for k in ("WEEKLY_HOURS", "PRESEASON_HOURS"):
            self.assertEqual({str(s): h for s, h in getattr(verify, k).items()}, RULES[k], k)

    def test_every_prestige_level_has_hours(self):
        p = RULES["MIN_PRESTIGE"]
        while p <= RULES["MAX_PRESTIGE"]:
            self.assertIn(str(int(p) if p == int(p) else p), RULES["WEEKLY_HOURS"])
            p += RULES["PRESTIGE_STEP"]

    @unittest.skipUnless(os.path.exists(os.path.join(ROOT, "..", "src")), "web app not present")
    def test_web_game_reads_the_same_file(self):
        for f in ("src/lib/dynasty/engine.ts", "src/lib/ai/dynasty-advisor.server.ts"):
            src = open(os.path.join(ROOT, "..", f)).read()
            self.assertIn("ncaa-dynasty-qa/rules.json", src, f)


if __name__ == "__main__":
    unittest.main()
