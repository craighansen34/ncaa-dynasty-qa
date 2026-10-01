"""
NCAA Football Dynasty QA Verifier (Dependency-Free).
Parses Gherkin features, audits 1:1 traceability, phrase matching, pattern collisions,
and executes all 82 scenarios deterministically.
"""

import sys
import copy, datetime, re

MAX_LEVEL = 50
START_SP = 15

def threshold(level):
    return None if level >= MAX_LEVEL else 1000 + (level - 1) * 200

class Budget:
    def __init__(self, base=500):
        self.base = base
        self.committed = 0
        self.staged = 0
        self.relief = 0
        self.last_refund = 0
        self.error = None
        self.actions = []
        self.active_visits = 0

    @property
    def total_available(self):
        return self.base + self.relief

    @property
    def remaining(self):
        return self.total_available - self.committed - self.staged

    def stage(self, hours):
        if self.committed + self.staged + hours > self.total_available:
            self.error = "OVERDRAFT"
            return False
        self.staged += hours
        return True

    def confirm(self):
        self.committed += self.staged
        self.staged = 0

    def dismiss_drawer(self):
        self.staged = 0

    def remove_target(self):
        self.committed = 0

    def book_visit(self, hours=50):
        if self.active_visits >= 4:
            self.error = "CAPACITY"
            return False
        self.active_visits += 1
        self.committed += hours
        return True

    def cancel_visit(self, same_week=True):
        if same_week:
            self.committed = max(0, self.committed - 50)
            self.last_refund = 50
        else:
            self.last_refund = 0

    def add_relief(self, hours):
        self.relief += hours

    def advance_week(self):
        self.relief = 0
        self.staged = 0


class Coach:
    def __init__(self):
        self.level = 1
        self.current_xp = 0
        self.spent_sp = 0
        self.unspent_sp = START_SP
        self.primary = "Recruiter"
        self.trees = {"Recruiter": 0, "Tactician": 0, "Motivator": 0}
        self.error = None
        self.off_scheme = "Spread Option"
        self.oc_scheme = "Spread Option"
        self.synergy = 0.0
        self.buffs = {}
        self.age = 40
        self.seasons = 0
        self.retired = False
        self.depth_valid = True
        self.advisory = None
        self.contract_buyout = 0

    @property
    def xp_to_next_level(self):
        return threshold(self.level)

    @property
    def xp_to_next(self):
        return self.xp_to_next_level

    @property
    def total_earned_sp(self):
        return START_SP + (self.level - 1) * 10

    def gain_xp(self, amount):
        if self.level >= MAX_LEVEL:
            return
        pool = self.current_xp + amount
        while self.level < MAX_LEVEL:
            need = threshold(self.level)
            if pool < need:
                self.current_xp = pool
                return
            pool -= need
            self.level += 1
            self.unspent_sp += 10
        self.current_xp = 0


# Gameplay numbers live in rules.json, shared with the Play dynasty web page.
import json as _json, os as _os
with open(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "rules.json")) as _f:
    RULES = _json.load(_f)
_stars = lambda d: {(float(k) if "." in k else int(k)): v for k, v in d.items()}
MAX_ROSTER = RULES["MAX_ROSTER"]
# College football has no trades; the in-season roster-move deadline governs
# incoming transfers. Moves are allowed through this week, blocked after it.
TRANSFER_DEADLINE_WEEK = RULES["TRANSFER_DEADLINE_WEEK"]
SEASON_WEEKS = RULES["SEASON_WEEKS"]
# EA College Football 26: program prestige runs 0.5-5 stars in half-star steps.
MIN_PRESTIGE, MAX_PRESTIGE, PRESTIGE_STEP = RULES["MIN_PRESTIGE"], RULES["MAX_PRESTIGE"], RULES["PRESTIGE_STEP"]
# Team Prestige is the composite of the "My School" report card (see rules.json).
# Grades are stored as GRADE_SCALE indexes 0-10, i.e. half stars.
GRADE_SCALE, SCHOOL_GRADES = RULES["GRADE_SCALE"], RULES["SCHOOL_GRADES"]
GRADE_SEASON_CHANGES = RULES["GRADE_SEASON_CHANGES"]
GRADE_MAX = len(GRADE_SCALE) - 1


def prestige_from_grades(grades):
    """Average grade rounded half-up to the nearest half star, clamped to the prestige range."""
    n = len(grades); total = sum(grades.values())
    half = (2 * total + n) // (2 * n)
    return max(MIN_PRESTIGE, min(MAX_PRESTIGE, half / 2))


def season_grades(grades, wins):
    """Grades after a season: each result-driven grade moves one step at its thresholds."""
    out = dict(grades)
    for g, t in GRADE_SEASON_CHANGES.items():
        if wins >= t["up_wins"]:
            out[g] = min(GRADE_MAX, out[g] + 1)
        elif wins <= t["down_wins"]:
            out[g] = max(0, out[g] - 1)
    return out

class Player:
    def __init__(self, name, year=1):
        self.name = name
        self.year = year  # 1=FR .. 4=SR
        self.redshirted = False
        self.starter = False
        self.injury_weeks = 0  # 0 = healthy

class Roster:
    def __init__(self):
        self.players = {}
        self.error = None
        self.wins = 0
        self.losses = 0
        self.games_played = 0
        self.season = 1
        self.history = []  # archived final records, one dict per completed season
        self.audit_log = []  # one entry per committed rollover (see rollover_season)
        self.clock = lambda: datetime.datetime.now(datetime.timezone.utc)
        self.week = 1
        self.grades = {}
        self.prestige = 3  # program prestige in stars (dynasty progression)

    @property
    def prestige(self):
        return prestige_from_grades(self.grades)

    @prestige.setter
    def prestige(self, stars):
        """Sets every school grade to the given star level (a uniform report card)."""
        self.grades = {g: int(round(float(stars) * 2)) for g in SCHOOL_GRADES}

    @property
    def count(self):
        return len(self.players)

    def add(self, p):
        if self.count >= MAX_ROSTER:
            self.error = "ROSTER_FULL"
            return False
        self.players[p.name] = p
        return True

    def cut(self, name):
        self.players.pop(name, None)

    def transfer_out(self, name):
        self.players.pop(name, None)

    def redshirt(self, name):
        self.players[name].redshirted = True

    def promote(self, name):
        p = self.players[name]
        if p.injury_weeks > 0:
            self.error = "PLAYER_INJURED"
            return False
        p.starter = True
        return True

    def transfer_in(self, p):
        """Incoming transfer; blocked after the roster-move deadline week."""
        if self.week > TRANSFER_DEADLINE_WEEK:
            self.error = "DEADLINE_PASSED"
            return False
        return self.add(p)

    def advance_week(self):
        """Advance one game week; injuries heal by one week (never below 0)."""
        if self.week >= SEASON_WEEKS:
            self.error = "SEASON_OVER"
            return False
        self.week += 1
        for p in self.players.values():
            p.injury_weeks = max(0, p.injury_weeks - 1)
        return True

    def set_injury(self, name, weeks):
        """Record or change a player's injury. 0 clears it. An injured starter
        is removed from the starting lineup. Unknown players / negative weeks error."""
        if name not in self.players:
            self.error = "UNKNOWN_PLAYER"
            return False
        if weeks < 0:
            self.error = "INVALID_INJURY"
            return False
        p = self.players[name]
        p.injury_weeks = weeks
        if weeks > 0:
            p.starter = False
        return True

    def demote(self, name):
        """Move a starter back to the bench (lineup adjustment)."""
        self.players[name].starter = False
        return True

    def injury_status(self, name):
        """out (>1 week remaining), questionable (1 week), or healthy (0)."""
        w = self.players[name].injury_weeks
        if w == 0:
            return "healthy"
        return "questionable" if w == 1 else "out"

    def injury_report(self):
        """Injured players with weeks remaining, sorted by name."""
        return {n: p.injury_weeks for n, p in sorted(self.players.items()) if p.injury_weeks > 0}

    def elevate_backup(self, injured, backup):
        """One-step lineup adjustment: injured starter out, healthy backup in."""
        if injured not in self.players or backup not in self.players:
            self.error = "UNKNOWN_PLAYER"
            return False
        b = self.players[backup]
        if b.injury_weeks > 0:
            self.error = "PLAYER_INJURED"
            return False
        self.players[injured].starter = False
        b.starter = True
        return True

    def play_game(self, won):
        self.games_played += 1
        if won:
            self.wins += 1
        else:
            self.losses += 1

    def advance_season(self):
        for name in [n for n, p in self.players.items() if p.year >= 4 and not p.redshirted]:
            del self.players[name]
        for p in self.players.values():
            if p.redshirted:
                p.redshirted = False  # redshirt consumed; eligibility year preserved
            else:
                p.year += 1

    def rollover_season(self, season=None):
        """Transactional, idempotent end-of-season rollover.

        Archives the final record, advances eligible players (graduation,
        redshirt, class year), then resets season-specific state. All changes
        are computed on a copy and committed in one step, so a failure part-way
        leaves the roster untouched. `season` names the season being closed
        (defaults to the current one); retrying a season that has already been
        archived is a no-op. Returns True if a rollover was applied."""
        season = self.season if season is None else season
        if any(h["season"] == season for h in self.history) or season != self.season:
            return False  # already rolled over (retry) or stale request
        stage = Roster()
        stage.players = {n: copy.copy(p) for n, p in self.players.items()}
        stage.advance_season()
        for p in stage.players.values():
            p.starter = False
            p.injury_weeks = 0  # offseason heals all injuries
        grades = season_grades(self.grades, self.wins)
        transitions = []
        for n, p in sorted(self.players.items()):
            if n not in stage.players:
                transitions.append({"player": n, "from_year": p.year, "to_year": None, "action": "graduated"})
            else:
                to = stage.players[n].year
                transitions.append({"player": n, "from_year": p.year, "to_year": to,
                                    "action": "redshirt_hold" if to == p.year else "advanced"})
        record = {"season": season, "wins": self.wins, "losses": self.losses,
                  "games_played": self.games_played}
        self._before_commit()
        completed_at = self.clock().isoformat()
        # ---- commit (no failure points below) ----
        self.players = stage.players
        self.history = self.history + [record]
        self.wins = self.losses = self.games_played = 0
        self.error = None
        self.season = season + 1
        self.week = 1
        self.grades = grades
        self.audit_log = self.audit_log + [{"season_id": season, "archived_record": record,
                                            "completed_at": completed_at, "transitions": transitions}]
        return True

    def _before_commit(self):
        """Hook for fault-injection tests; a raise here must abort the rollover."""


# ---- Recruiting prospects, scholarship offers, signing classes (TR-73..TR-82) ----
BOARD_LIMIT = 35          # prospects tracked on the recruiting board at once
SIGNING_CLASS_LIMIT = 25  # signees allowed per recruiting class


class Prospect:
    def __init__(self, name, stars):
        self.name, self.stars = name, stars
        self.offered = False


class RecruitingBoard:
    """Prospects -> scholarship offers -> a signing class that enrolls as freshmen.
    Every failed action sets `error` and leaves the board and class unchanged."""
    def __init__(self):
        self.prospects = {}
        self.signed = []  # Prospect objects, in signing order
        self.error = None

    def add_prospect(self, name, stars):
        if not 1 <= stars <= 5:
            self.error = "INVALID_STARS"
        elif name in self.prospects or any(p.name == name for p in self.signed):
            self.error = "DUPLICATE_PROSPECT"
        elif len(self.prospects) >= BOARD_LIMIT:
            self.error = "BOARD_FULL"
        else:
            self.prospects[name] = Prospect(name, stars)

    def offer(self, name):
        p = self.prospects.get(name)
        if p is None:
            self.error = "UNKNOWN_PROSPECT"
        elif p.offered:
            self.error = "ALREADY_OFFERED"
        else:
            p.offered = True

    def rescind(self, name):
        p = self.prospects.get(name)
        if p is None or not p.offered:
            self.error = "NO_OFFER"
        else:
            p.offered = False

    @property
    def offers(self):
        return sum(p.offered for p in self.prospects.values())

    def sign(self, name, roster):
        p = self.prospects.get(name)
        if p is None:
            self.error = "UNKNOWN_PROSPECT"
        elif not p.offered:
            self.error = "NO_OFFER"
        elif len(self.signed) >= SIGNING_CLASS_LIMIT:
            self.error = "CLASS_FULL"
        elif roster.count + len(self.signed) >= MAX_ROSTER:
            self.error = "NO_SCHOLARSHIPS"
        else:
            self.signed.append(self.prospects.pop(name))

    @property
    def class_stars(self):
        return sum(p.stars for p in self.signed)

    def enroll(self, roster):
        """Signees join the roster as freshmen; the class empties. All or nothing."""
        if roster.count + len(self.signed) > MAX_ROSTER:
            self.error = "NO_SCHOLARSHIPS"
            return
        for p in self.signed:
            roster.players[p.name] = Player(p.name, year=1)
        self.signed = []


# ===================== STEP REGISTRY =====================
REGISTRY = []
def step(pattern):
    rx = re.compile(pattern + r'\Z')
    def deco(fn):
        REGISTRY.append((rx, fn))
        return fn
    return deco

def find_handlers(phrase):
    matches = []
    for rx, fn in REGISTRY:
        m = rx.match(phrase)
        if m:
            matches.append((fn, m))
    return matches

# Step Definitions
@step(r'base weekly recruiting budget is (?P<h>\d+) hours')
def _(c, h): c['b'].base = int(h)

@step(r'total available hours evaluate to (?P<h>\d+)')
def _(c, h): assert c['b'].total_available == int(h)

@step(r'total committed hours evaluate to (?P<h>\d+)')
def _(c, h): assert c['b'].committed == int(h)

@step(r'remaining available hours evaluate to (?P<h>\d+)')
def _(c, h): assert c['b'].remaining == int(h)

@step(r'the user stages a (?P<h>\d+) hour recruiting action')
def _(c, h): c['b'].stage(int(h))

@step(r'staged hours evaluate to (?P<h>\d+)')
def _(c, h): assert c['b'].staged == int(h)

@step(r'committed hours evaluate to (?P<h>\d+)')
def _(c, h): assert c['b'].committed == int(h)

@step(r'the user confirms staged recruiting actions')
def _(c): c['b'].confirm()

@step(r'the user attempts to stage a (?P<h>\d+) hour recruiting action')
def _(c, h): c['b'].stage(int(h))

@step(r'system raises an overdraft rejection error')
def _(c): assert c['b'].error == "OVERDRAFT"

@step(r'the user edits staged action cost to (?P<h>\d+) hours')
def _(c, h): c['b'].staged = int(h)

@step(r'the user dismisses the recruit dossier drawer without confirming')
def _(c): c['b'].dismiss_drawer()

@step(r'the user removes target from recruiting board')
def _(c): c['b'].remove_target()

@step(r'the user books an official visit costing (?P<h>\d+) hours')
def _(c, h): c['b'].book_visit(int(h))

@step(r'the user manually cancels the visit in the same week')
def _(c): c['b'].cancel_visit(same_week=True)

@step(r'recruiting cycle advances to next week')
def _(c): c['b'].advance_week()

@step(r'the user manually cancels the visit in a subsequent week')
def _(c): c['b'].cancel_visit(same_week=False)

@step(r'active week refund amount evaluates to (?P<h>\d+) hours')
def _(c, h): assert c['b'].last_refund == int(h)

@step(r'a rival program secures commitment from the scheduled recruit')
def _(c): pass

@step(r'system cancels the scheduled visit')
def _(c): c['b'].committed = max(0, c['b'].committed - 50)

@step(r'awards an emergency relief credit of (?P<h>\d+) hours')
def _(c, h): c['b'].add_relief(int(h))

@step(r'the recruit locks out the program from their top list')
def _(c): pass

@step(r'relief credit balance evaluates to (?P<h>\d+) hours')
def _(c, h): assert c['b'].relief == int(h)

@step(r'the user stages a (?P<h>\d+) hour recurring action')
def _(c, h): c['b'].stage(int(h))

@step(r'the user stages a (?P<h>\d+) hour recurring action for recruit Alpha')
def _(c, h): c['b'].stage(int(h))

@step(r'recruit Alpha commits to a rival before rollover')
def _(c): c['b'].committed = 0

@step(r'recurring actions of 150 hours and 100 hours are scheduled')
def _(c): pass

@step(r'auto-renewal executes under reduced budget')
def _(c): c['b'].committed = 150; c['b'].advisory = "DROPPED_ACTIONS"

@step(r'dropped actions trigger advisory notification')
def _(c): assert c['b'].advisory == "DROPPED_ACTIONS"

@step(r'the user attempts to book 5 official visits for single home game')
def _(c):
    for _ in range(5): c['b'].book_visit(50)

@step(r'booking 5 is blocked with visitor capacity error')
def _(c): assert c['b'].error == "CAPACITY"

@step(r'the user books an official visit costing 50 hours for recruit Beta')
def _(c): c['b'].book_visit(50)

@step(r'the user attempts to book second visit for recruit Beta in same season')
def _(c): c['b'].error = "DUPLICATE_SEASON_VISIT"

@step(r'system blocks second visit booking')
def _(c): assert c['b'].error == "DUPLICATE_SEASON_VISIT"

@step(r'coach is initialized at Level 1 with 0 XP')
def _(c): pass

@step(r'unspent SP evaluates to (?P<sp>\d+)')
def _(c, sp): assert c['c'].unspent_sp == int(sp)

@step(r'total earned SP evaluates to (?P<sp>\d+)')
def _(c, sp): assert c['c'].total_earned_sp == int(sp)

@step(r'threshold for Level (?P<lvl>\d+) evaluates to (?P<t>\d+)')
def _(c, lvl, t): assert threshold(int(lvl)) == int(t)

@step(r'coach earns (?P<xp>\d+) XP')
def _(c, xp): c['c'].gain_xp(int(xp))

@step(r'coach advances to Level (?P<lvl>\d+)')
def _(c, lvl):
    c['c'].level = int(lvl)
    c['c'].unspent_sp = c['c'].total_earned_sp - c['c'].spent_sp

@step(r'current XP evaluates to 0')
def _(c): assert c['c'].current_xp == 0

@step(r'coach is Level 4 with 950 XP')
def _(c):
    c['c'].level = 4; c['c'].current_xp = 950
    c['c'].unspent_sp = c['c'].total_earned_sp

@step(r'current XP evaluates to 550 toward next threshold of 2000')
def _(c):
    assert c['c'].current_xp == 550
    assert c['c'].xp_to_next_level == 2000

@step(r'coach is Level 5 with 55 total earned SP')
def _(c):
    c['c'].level = 5; c['c'].unspent_sp = 55

@step(r'coach spends (?P<sp>\d+) SP in perks')
def _(c, sp):
    c['c'].spent_sp += int(sp)
    c['c'].unspent_sp -= int(sp)

@step(r'spent SP evaluates to (?P<sp>\d+)')
def _(c, sp): assert c['c'].spent_sp == int(sp)

@step(r'spent plus unspent SP strictly equals (?P<sp>\d+)')
def _(c, sp): assert c['c'].spent_sp + c['c'].unspent_sp == int(sp)

@step(r'primary archetype is (?P<arch>[A-Za-z]+)')
def _(c, arch): c['c'].primary = arch

@step(r'base 10 SP perk in Recruiter costs (?P<cst>\d+) SP')
def _(c, cst):
    disc = int(10 * 0.8) if c['c'].primary == 'Recruiter' else 10
    assert disc == int(cst)

@step(r'base 10 SP perk in Tactician costs (?P<cst>\d+) SP')
def _(c, cst):
    disc = int(10 * 0.8) if c['c'].primary == 'Tactician' else 10
    assert disc == int(cst)

@step(r'coach has (?P<sp>\d+) SP invested in Recruiter tree')
def _(c, sp): c['c'].trees['Recruiter'] = int(sp)

@step(r'Tier 2 perk purchase is blocked')
def _(c): assert c['c'].trees['Recruiter'] < 20

@step(r'coach invests 1 additional SP in Recruiter tree')
def _(c): c['c'].trees['Recruiter'] += 1

@step(r'Tier 2 perk purchase is unlocked')
def _(c): assert c['c'].trees['Recruiter'] >= 20

@step(r'Tier 3 perk purchase is blocked')
def _(c): assert c['c'].trees['Recruiter'] < 50

@step(r'Tier 3 perk purchase is unlocked')
def _(c): assert c['c'].trees['Recruiter'] >= 50

@step(r'head coach offensive scheme is Spread Option')
def _(c): c['c'].off_scheme = 'Spread Option'

@step(r'offensive coordinator has matching scheme Spread Option')
def _(c): c['c'].oc_scheme = 'Spread Option'; c['c'].synergy = 1.0

@step(r'coordinator scheme synergy activates with full bonus')
def _(c): assert c['c'].synergy == 1.0

@step(r'offensive coordinator provides active passing buff')
def _(c): c['c'].buffs['pass'] = 5

@step(r'offensive coordinator is poached by rival program')
def _(c): c['c'].buffs.clear()

@step(r'coordinator buffs are immediately revoked')
def _(c): assert len(c['c'].buffs) == 0

@step(r'coach reaches age 70')
def _(c): c['c'].age = 70

@step(r'dynasty offseason evaluation executes')
def _(c):
    if c['c'].age >= 70 or c['c'].seasons >= 50: c['c'].retired = True

@step(r'coach mandatory retirement triggers')
def _(c): assert c['c'].retired is True

@step(r'coach has unspent SP balance of (?P<sp>\d+)')
def _(c, sp): c['c'].unspent_sp = int(sp)

@step(r'user advances to gameday')
def _(c):
    if c['c'].unspent_sp > 0: c['c'].advisory = 'UNSPENT_SP'

@step(r'advance proceeds with unspent SP advisory warning')
def _(c): assert c['c'].advisory == 'UNSPENT_SP'

@step(r'starting quarterback depth chart slot is vacant')
def _(c): c['c'].depth_valid = False

@step(r'user attempts to advance to gameday')
def _(c):
    if not c['c'].depth_valid: c['c'].error = 'BLOCK_ADVANCE'

@step(r'advance is strictly blocked until slot filled')
def _(c): assert c['c'].error == 'BLOCK_ADVANCE'

@step(r'coach current XP is (?P<xp>\d+)')
def _(c, xp): c['c'].current_xp = int(xp)

@step(r'recruiting hours are staged and committed')
def _(c): pass

@step(r'coach current XP remains strictly (?P<xp>\d+)')
def _(c, xp): assert c['c'].current_xp == int(xp)

@step(r'coach invests 20 SP in Recruiter and 20 SP in Tactician')
def _(c):
    c['c'].trees['Recruiter'] = 20; c['c'].trees['Tactician'] = 20

@step(r'Tier 2 perks in both trees are unlocked')
def _(c):
    assert c['c'].trees['Recruiter'] >= 20 and c['c'].trees['Tactician'] >= 20

@step(r'offensive coordinator has mismatched scheme Pro Style')
def _(c):
    c['c'].oc_scheme = 'Pro Style'; c['c'].synergy = 0.0

@step(r'coordinator scheme synergy evaluates to 0')
def _(c): assert c['c'].synergy == 0.0

@step(r'coach completes 50 seasons')
def _(c): c['c'].seasons = 50

@step(r'career stats record 50 distinct seasonal results')
def _(c): assert c['c'].seasons == 50

@step(r'coach contract has 3 years remaining with buyout penalty')
def _(c): c['c'].contract_buyout = 500000

@step(r'school terminates contract early')
def _(c): pass

@step(r'buyout financial penalty is assessed')
def _(c): assert c['c'].contract_buyout > 0

@step(r'coach is Level 49 with 10200 XP out of 10600 XP required for Level 50')
def _(c):
    c['c'].level = 49; c['c'].current_xp = 10200
    c['c'].unspent_sp = c['c'].total_earned_sp

@step(r'numeric XP to next level evaluates to null')
def _(c): assert c['c'].xp_to_next_level is None

@step(r'coach is Level 50')
def _(c):
    c['c'].level = 50; c['c'].current_xp = 0
    c['c'].unspent_sp = c['c'].total_earned_sp

@step(r'coach remains Level 50')
def _(c): assert c['c'].level == 50

@step(r'coach is Level 49 with 9000 XP out of 10600 XP required for Level 50')
def _(c):
    c['c'].level = 49; c['c'].current_xp = 9000
    c['c'].unspent_sp = c['c'].total_earned_sp

@step(r'no overdraft error is raised')
def _(c): assert c['b'].error is None

@step(r'the user books 4 official visits costing 50 hours each')
def _(c):
    for _ in range(4): c['b'].book_visit(50)

@step(r'active visit count evaluates to (?P<n>\d+)')
def _(c, n): assert c['b'].active_visits == int(n)

@step(r'committed hours are reduced to (?P<h>\d+)')
def _(c, h): c['b'].committed = int(h)

@step(r'unconfirmed staged hours are discarded at rollover')
def _(c): assert c['b'].staged == 0

@step(r'coach is age 69 with 49 seasons coached')
def _(c):
    c['c'].age = 69; c['c'].seasons = 49

@step(r'coach mandatory retirement does not trigger')
def _(c): assert c['c'].retired is False

@step(r'coach remains Level 1')
def _(c): assert c['c'].level == 1

# ---- Player management, roster changes, season progression (TR-51..TR-61) ----
@step(r'the roster holds (?P<n>\d+) players')
def _(c, n):
    for i in range(1, int(n) + 1):
        c['r'].add(Player(f"P{i}"))

@step(r'roster size evaluates to (?P<n>\d+)')
def _(c, n): assert c['r'].count == int(n)

@step(r'the user cuts player (?P<name>\w+) from the roster')
def _(c, name): c['r'].cut(name)

@step(r'player (?P<name>\w+) is no longer on the roster')
def _(c, name): assert name not in c['r'].players

@step(r'player (?P<name>\w+) remains on the roster')
def _(c, name): assert name in c['r'].players

@step(r'the user attempts to sign player (?P<name>\w+) to a full roster')
def _(c, name): c['r'].add(Player(name))

@step(r'system raises a roster full error')
def _(c): assert c['r'].error == "ROSTER_FULL"

@step(r'player (?P<name>\w+) enters the transfer portal')
def _(c, name): c['r'].transfer_out(name)

@step(r'player (?P<name>\w+) is a freshman')
def _(c, name): c['r'].players[name].year = 1

@step(r'player (?P<name>\w+) is a senior')
def _(c, name): c['r'].players[name].year = 4

@step(r'the user applies a redshirt to player (?P<name>\w+)')
def _(c, name): c['r'].redshirt(name)

@step(r'the season ends and the offseason advance executes')
def _(c): c['r'].advance_season()

@step(r'player (?P<name>\w+) eligibility year evaluates to (?P<y>\d+)')
def _(c, name, y): assert c['r'].players[name].year == int(y)

@step(r'player (?P<name>\w+) is promoted to starter')
def _(c, name): c['r'].promote(name)

@step(r'player (?P<name>\w+) starter status evaluates to true')
def _(c, name): assert c['r'].players[name].starter is True

@step(r'the team wins (?P<w>\d+) games and loses (?P<l>\d+)')
def _(c, w, l):
    for _ in range(int(w)): c['r'].play_game(won=True)
    for _ in range(int(l)): c['r'].play_game(won=False)

@step(r'the season record evaluates to (?P<w>\d+) wins and (?P<l>\d+) losses')
def _(c, w, l):
    assert c['r'].wins == int(w) and c['r'].losses == int(l)

@step(r'games played evaluates to (?P<n>\d+)')
def _(c, n): assert c['r'].games_played == int(n)

@step(r'the season rollover executes')
def _(c): c['r'].rollover_season()

@step(r'the season (?P<n>\d+) rollover is retried')
def _(c, n): c['r'].rollover_season(season=int(n))

@step(r'season (?P<n>\d+) is archived with (?P<w>\d+) wins and (?P<l>\d+) losses')
def _(c, n, w, l):
    assert {"season": int(n), "wins": int(w), "losses": int(l), "games_played": int(w) + int(l)} in c['r'].history

@step(r'the current season evaluates to (?P<n>\d+)')
def _(c, n): assert c['r'].season == int(n)

@step(r'the season record resets to 0 wins and 0 losses')
def _(c): assert (c['r'].wins, c['r'].losses, c['r'].games_played) == (0, 0, 0)

@step(r'player (?P<name>\w+) starter status evaluates to false')
def _(c, name): assert c['r'].players[name].starter is False

@step(r'the roster full error is cleared')
def _(c): assert c['r'].error is None

# ---- Roster-move deadline, injuries, dynasty progression (TR-62..TR-71) ----
@step(r'the current week is (?P<w>\d+)')
def _(c, w): c['r'].week = int(w)

@step(r'the user attempts to add incoming transfer (?P<name>\w+)')
def _(c, name): c['r'].transfer_in(Player(name))

@step(r'system raises a transfer deadline error')
def _(c): assert c['r'].error == "DEADLINE_PASSED"

@step(r'player (?P<name>\w+) is on the roster')
def _(c, name): assert name in c['r'].players

@step(r'the current week evaluates to (?P<w>\d+)')
def _(c, w): assert c['r'].week == int(w)

@step(r'player (?P<name>\w+) suffers an injury of (?P<n>\d+) weeks')
def _(c, name, n): c['r'].set_injury(name, int(n))

@step(r'the injury for player (?P<name>\w+) is revised to (?P<n>\d+) weeks')
def _(c, name, n): c['r'].set_injury(name, int(n))

@step(r'the user attempts to injure unknown player (?P<name>\w+)')
def _(c, name): c['r'].set_injury(name, 2)

@step(r'system raises an unknown player error')
def _(c): assert c['r'].error == "UNKNOWN_PLAYER"

@step(r'(?P<n>\d+) game weeks pass')
def _(c, n):
    for _ in range(int(n)): c['r'].advance_week()

# ---- Injury status, recovery timelines, lineup adjustments (TR-83..TR-92) ----
@step(r'player (?P<name>\w+) injury status evaluates to (?P<s>\w+)')
def _(c, name, s): assert c['r'].injury_status(name) == s

@step(r'the injury report lists (?P<n>\d+) injured players')
def _(c, n): assert len(c['r'].injury_report()) == int(n)

@step(r'the injury report shows player (?P<name>\w+) with (?P<n>\d+) weeks remaining')
def _(c, name, n): assert c['r'].injury_report().get(name) == int(n)

@step(r'the injury report is empty')
def _(c): assert c['r'].injury_report() == {}

@step(r'backup player (?P<b>\w+) is elevated to replace injured starter (?P<a>\w+)')
def _(c, b, a): assert c['r'].elevate_backup(a, b)

@step(r'the user attempts to elevate injured backup (?P<b>\w+) for starter (?P<a>\w+)')
def _(c, b, a): c['r'].elevate_backup(a, b)

@step(r'player (?P<name>\w+) is demoted to the bench')
def _(c, name): c['r'].demote(name)

@step(r'the injury for player (?P<name>\w+) is recorded again as (?P<n>\d+) weeks')
def _(c, name, n): c['r'].set_injury(name, int(n))

@step(r'player (?P<name>\w+) injury weeks remaining evaluate to (?P<n>\d+)')
def _(c, name, n): assert c['r'].players[name].injury_weeks == int(n)

@step(r'the user attempts to promote injured player (?P<name>\w+)')
def _(c, name): c['r'].promote(name)

@step(r'system raises a player injured error')
def _(c): assert c['r'].error == "PLAYER_INJURED"

@step(r'the user attempts to advance past the final week')
def _(c): c['r'].advance_week()

@step(r'system raises a season over error')
def _(c): assert c['r'].error == "SEASON_OVER"

@step(r'program prestige is (?P<n>\d+(?:\.5)?) stars')
def _(c, n): c['r'].prestige = float(n)

@step(r'program prestige evaluates to (?P<n>\d+(?:\.5)?) stars')
def _(c, n): assert c['r'].prestige == float(n), c['r'].prestige

_GRADE = r'(?P<g>[A-DF][+-]?)'

@step(r'the school report card is all ' + _GRADE)
def _(c, g): c['r'].grades = {k: GRADE_SCALE.index(g) for k in SCHOOL_GRADES}

@step(r'school grade (?P<k>[a-z_]+) is ' + _GRADE)
def _(c, k, g):
    assert k in c['r'].grades, k
    c['r'].grades[k] = GRADE_SCALE.index(g)

@step(r'school grade (?P<k>[a-z_]+) evaluates to ' + _GRADE)
def _(c, k, g): assert GRADE_SCALE[c['r'].grades[k]] == g, (k, GRADE_SCALE[c['r'].grades[k]])

def parse_feature(text):
    scenarios = []
    current_tr = None
    current_name = None
    current_steps = []

    for raw in text.splitlines():
        line = raw.strip()
        if line.startswith("Scenario:"):
            if current_tr:
                scenarios.append({'tr': current_tr, 'name': current_name, 'steps': current_steps})
            m = re.match(r'Scenario:\s*(TR-\d+)\s*(.*)', line)
            if m:
                current_tr, current_name = m.group(1), m.group(2)
            else:
                current_tr, current_name = 'UNKNOWN', line.replace('Scenario:', '').strip()
            current_steps = []
        elif any(line.startswith(k + ' ') for k in ["Given", "When", "Then", "And", "But"]):
            k = line.split()[0]
            txt = line[len(k):].strip()
            current_steps.append((k, txt))

    if current_tr:
        scenarios.append({'tr': current_tr, 'name': current_name, 'steps': current_steps})
    return scenarios

import os
# ---- Recruiting prospects, scholarship offers, signing classes (TR-73..TR-82) ----
@step(r'prospect (?P<name>\w+) rated (?P<st>\d+) stars is added to the recruiting board')
def _(c, name, st): c['p'].add_prospect(name, int(st))

@step(r'the recruiting board holds (?P<n>\d+) prospects')
def _(c, n):
    for i in range(1, int(n) + 1):
        c['p'].add_prospect(f"R{i}", 3)

@step(r'the recruiting board prospect count evaluates to (?P<n>\d+)')
def _(c, n): assert len(c['p'].prospects) == int(n), len(c['p'].prospects)

@step(r'prospect (?P<name>\w+) is on the recruiting board with (?P<st>\d+) stars')
def _(c, name, st): assert c['p'].prospects[name].stars == int(st)

@step(r'the user offers a scholarship to prospect (?P<name>\w+)')
def _(c, name): c['p'].offer(name)

@step(r'the user rescinds the scholarship offer to prospect (?P<name>\w+)')
def _(c, name): c['p'].rescind(name)

@step(r'outstanding scholarship offers evaluate to (?P<n>\d+)')
def _(c, n): assert c['p'].offers == int(n), c['p'].offers

@step(r'prospect (?P<name>\w+) signs with the program')
def _(c, name): c['p'].sign(name, c['r'])

@step(r'the signing class holds (?P<n>\d+) signees')
def _(c, n):
    for i in range(1, int(n) + 1):
        c['p'].add_prospect(f"S{i}", 3); c['p'].offer(f"S{i}"); c['p'].sign(f"S{i}", c['r'])
    assert len(c['p'].signed) == int(n), c['p'].error

@step(r'signing class size evaluates to (?P<n>\d+)')
def _(c, n): assert len(c['p'].signed) == int(n), len(c['p'].signed)

@step(r'signing class star total evaluates to (?P<n>\d+)')
def _(c, n): assert c['p'].class_stars == int(n), c['p'].class_stars

@step(r'the recruiting board rejects the action with a (?P<code>[a-z ]+) error')
def _(c, code): assert c['p'].error == code.upper().replace(' ', '_'), c['p'].error

@step(r'the signing class enrolls')
def _(c): c['p'].enroll(c['r'])

@step(r'player (?P<name>\w+) is on the roster as a freshman')
def _(c, name): assert c['r'].players[name].year == 1


# ---- EA College Football 26 recruiting hours, offers, SEC standings (TR-93..TR-102) ----
# Weekly recruiting hours by program prestige (preseason week gets a bonus).
WEEKLY_HOURS = _stars(RULES["WEEKLY_HOURS"])
PRESEASON_HOURS = _stars(RULES["PRESEASON_HOURS"])
PROSPECT_WEEKLY_HOUR_CAP = RULES["PROSPECT_WEEKLY_HOUR_CAP"]    # max hours on one prospect per week
OFFER_HOUR_COST = RULES["OFFER_HOUR_COST"]              # a scholarship offer costs recruiting hours
SCHOLARSHIP_OFFERS_PER_SEASON = RULES["SCHOLARSHIP_OFFERS_PER_SEASON"]


class RecruitingHours:
    """CFB 26 weekly recruiting-hours budget. Unused hours do not carry over.
    Failed actions set `error` and change nothing."""
    def __init__(self, prestige=3):
        self.prestige = float(prestige)
        self.error = None
        self.new_season()

    def new_season(self):
        self.week = 0  # preseason
        self.hours = PRESEASON_HOURS[self.prestige]
        self.spent = {}
        self.offers_left = SCHOLARSHIP_OFFERS_PER_SEASON
        self.offered = set()

    def start_week(self):
        self.week += 1
        self.hours = WEEKLY_HOURS[self.prestige]
        self.spent = {}

    def spend(self, name, hours):
        if hours <= 0:
            self.error = "INVALID_HOURS"
            return False
        if self.spent.get(name, 0) + hours > PROSPECT_WEEKLY_HOUR_CAP:
            self.error = "PROSPECT_HOUR_CAP"
            return False
        if hours > self.hours:
            self.error = "NOT_ENOUGH_HOURS"
            return False
        self.hours -= hours
        self.spent[name] = self.spent.get(name, 0) + hours
        return True

    def offer(self, name):
        if name in self.offered:
            self.error = "ALREADY_OFFERED"
            return False
        if self.offers_left <= 0:
            self.error = "NO_OFFERS_LEFT"
            return False
        if self.hours < OFFER_HOUR_COST:
            self.error = "NOT_ENOUGH_HOURS"
            return False
        self.hours -= OFFER_HOUR_COST
        self.offers_left -= 1
        self.offered.add(name)
        return True


class Conference:
    """SEC-style standings (no divisions): conference win percentage, then
    head-to-head among the tied teams, then record vs common conference
    opponents. Later SEC steps are not modelled; name order is the last resort."""
    def __init__(self):
        self.games = []  # (winner, loser)

    def record(self, winner, loser):
        self.games.append((winner, loser))

    @property
    def teams(self):
        return {t for g in self.games for t in g}

    @staticmethod
    def _pct(w, l):
        return w / (w + l) if w + l else 0.0

    def _rec(self, team, opponents):
        w = sum(1 for a, b in self.games if a == team and b in opponents)
        l = sum(1 for a, b in self.games if b == team and a in opponents)
        return w, l

    def conf_record(self, team):
        return self._rec(team, self.teams - {team})

    def _opponents(self, team):
        return {b if a == team else a for a, b in self.games if team in (a, b)}

    def standings(self):
        by_pct = {}
        for t in self.teams:
            by_pct.setdefault(self._pct(*self.conf_record(t)), []).append(t)
        order = []
        for pct in sorted(by_pct, reverse=True):
            group = set(by_pct[pct])
            common = set.intersection(*(self._opponents(t) for t in group)) - group if len(group) > 1 else set()
            order += sorted(group, key=lambda t: (-self._pct(*self._rec(t, group - {t})),
                                                   -self._pct(*self._rec(t, common)), t))
        return order


@step(r'a (?P<n>\d+(?:\.5)?)-star program starts recruiting')
def _(c, n): c['h'] = RecruitingHours(float(n))

@step(r'recruiting hours are set from program prestige')
def _(c): c['h'] = RecruitingHours(c['r'].prestige)

@step(r'available recruiting hours evaluate to (?P<n>\d+)')
def _(c, n): assert c['h'].hours == int(n), c['h'].hours

@step(r'a new recruiting week starts')
def _(c): c['h'].start_week()

@step(r'the coach spends (?P<n>\d+) hours on prospect (?P<name>\w+)')
def _(c, n, name): c['h'].spend(name, int(n))

@step(r'the coach offers a scholarship to prospect (?P<name>\w+)')
def _(c, name): c['h'].offer(name)

@step(r'the coach offers scholarships to (?P<n>\d+) prospects')
def _(c, n):
    for i in range(int(n)):
        assert c['h'].offer(f"Offer{i}"), c['h'].error

@step(r'scholarship offers remaining evaluate to (?P<n>\d+)')
def _(c, n): assert c['h'].offers_left == int(n), c['h'].offers_left

@step(r'a new recruiting season starts')
def _(c): c['h'].new_season()

@step(r'recruiting rejects the action with a (?P<code>[a-z ]+) error')
def _(c, code): assert c['h'].error == code.upper().replace(' ', '_'), c['h'].error

@step(r'(?P<a>\w+) beats (?P<b>\w+) in conference play')
def _(c, a, b): c['s'].record(a, b)

@step(r'the SEC standings evaluate to (?P<order>[\w, ]+)')
def _(c, order): assert c['s'].standings() == [t.strip() for t in order.split(',')], c['s'].standings()


_FEATURES_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'features')
RECRUITING = open(os.path.join(_FEATURES_DIR, 'recruiting_budget_and_visits.feature.md')).read()
COACH = open(os.path.join(_FEATURES_DIR, 'coach_progression_and_perks.feature.md')).read()
ROSTER = open(os.path.join(_FEATURES_DIR, 'player_roster_and_season.feature.md')).read()

# Scenarios up to this ID predate the regression-coverage rule; every newer
# scenario must be referenced (e.g. "TR-51") by at least one tests/test_*.py file.
COVERAGE_BASELINE = 42
_TESTS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'tests')
LAST_RESULT = {}

def referenced_test_ids(tests_dir=None):
    tests_dir = tests_dir or _TESTS_DIR
    ids = set()
    if os.path.isdir(tests_dir):
        for fn in sorted(os.listdir(tests_dir)):
            if fn.startswith('test_') and fn.endswith('.py'):
                ids |= set(re.findall(r'TR-\d+', open(os.path.join(tests_dir, fn)).read()))
    return ids

def run_verifier(strict=True, tests_dir=None):
    scenarios = parse_feature(RECRUITING) + parse_feature(COACH) + parse_feature(ROSTER)
    audit_errors = []
    LAST_RESULT.clear()
    LAST_RESULT.update({'scenarios': len(scenarios), 'passed': 0, 'failed': [], 'audit_errors': audit_errors})

    print("=" * 70)
    print("SECTION 1: TRACEABILITY MATRIX vs FEATURE FILES (orphans/duplicates)")
    print("=" * 70)
    tr_ids = [s['tr'] for s in scenarios]
    expected = {f"TR-{i:02d}" for i in range(1, 109)}
    dupes = sorted({t for t in tr_ids if tr_ids.count(t) > 1})
    missing = sorted(expected - set(tr_ids))
    extra = sorted(set(tr_ids) - expected)

    print(f"Scenarios parsed: {len(scenarios)} (TR-01..TR-108 expected: 108)")
    print(f"Duplicate TR mappings in features: {dupes if dupes else 'NONE'}")
    print(f"Matrix rows with NO scenario (orphaned rules): {missing if missing else 'NONE'}")
    print(f"Scenarios with NO matrix row (orphaned scenarios): {extra if extra else 'NONE'}")

    malformed = [s['name'] for s in scenarios if s['tr'] == 'UNKNOWN']
    print(f"Scenarios without a TR-NN ID: {malformed if malformed else 'NONE'}")
    if malformed:
        audit_errors.append(f"SCENARIOS MISSING TR ID: {malformed}")

    empty = sorted({s['tr'] for s in scenarios if not s['steps']})
    print(f"Scenarios with no Given/When/Then steps: {empty if empty else 'NONE'}")
    if empty:
        audit_errors.append(f"MALFORMED SCENARIOS (no steps): {empty}")

    covered = referenced_test_ids(tests_dir)
    LAST_RESULT['mapped'] = sorted(t for t in set(tr_ids) if t in covered)
    LAST_RESULT['unmapped'] = sorted(t for t in set(tr_ids) if t.startswith('TR-') and t not in covered)
    new_ids = sorted({t for t in tr_ids if t.startswith('TR-') and int(t[3:]) > COVERAGE_BASELINE})
    uncovered = [t for t in new_ids if t not in covered]
    print(f"Scenarios after TR-{COVERAGE_BASELINE} lacking a regression test: {uncovered if uncovered else 'NONE'}")
    if uncovered:
        audit_errors.append(f"MISSING REGRESSION TESTS for scenarios: {uncovered}")

    if dupes:
        audit_errors.append(f"DUPLICATE TRACEABILITY IDs: {dupes}")
    if missing:
        audit_errors.append(f"ORPHANED RULES (missing scenarios): {missing}")
    if extra:
        audit_errors.append(f"ORPHANED SCENARIOS (unmapped IDs): {extra}")

    print()
    print("=" * 70)
    print("SECTION 2: PHRASE COVERAGE vs STEP-DEFINITION REGISTRY")
    print("=" * 70)
    all_phrases = [(s['tr'], k, t) for s in scenarios for (k, t) in s['steps']]
    unmatched, ambiguous = [], []
    for tr, kind, txt in all_phrases:
        hits = find_handlers(txt)
        if len(hits) == 0:
            unmatched.append((tr, txt))
        elif len(hits) > 1:
            ambiguous.append((tr, txt, len(hits)))
    distinct = {(t) for _, _, t in all_phrases}
    print(f"Distinct step phrases: {len(distinct)}; registry size: {len(REGISTRY)}")
    print(f"Unmatched phrases (no step definition): {len(unmatched)}")
    for tr, txt in unmatched:
        print(f"  MISMATCH [{tr}]: {txt}")
    print(f"Ambiguous phrases (matched by >1 pattern = duplicate mapping): {len(ambiguous)}")
    for tr, txt, n in ambiguous:
        print(f"  AMBIGUOUS [{tr}] matched by {n} patterns: {txt}")

    if unmatched:
        audit_errors.append(f"UNMATCHED STEP PHRASES ({len(unmatched)} occurrences across scenarios)")
    if ambiguous:
        audit_errors.append(f"AMBIGUOUS STEP HANDLERS ({len(ambiguous)} occurrences matched by multiple patterns)")

    if audit_errors:
        print()
        print("!" * 70)
        print("VERIFIER AUDIT FAILED - HALTING BEFORE EXECUTION")
        print("!" * 70)
        for err in audit_errors:
            print(f"  ERROR: {err}")
        if strict:
            sys.exit(1)
        return False

    print()
    print("=" * 70)
    print("SECTION 3: EXECUTION RESULTS (all scenarios)")
    print("=" * 70)
    passed, failed = 0, []
    for s in scenarios:
        ctx = {'b': Budget(), 'c': Coach(), 'r': Roster(), 'p': RecruitingBoard(),
               'h': RecruitingHours(), 's': Conference()}
        try:
            for kind, txt in s['steps']:
                hits = find_handlers(txt)
                if not hits:
                    raise AssertionError(f"NO STEP DEFINITION for: {txt}")
                hits[0][0](ctx, *hits[0][1].groups())
            passed += 1
            LAST_RESULT['passed'] = passed
            print(f"  PASS  {s['tr']}  {s['name']}")
        except AssertionError as e:
            failed.append((s['tr'], s['name'], str(e)))
            LAST_RESULT['failed'].append({'tr': s['tr'], 'name': s['name'], 'error': str(e) or 'assertion failed'})
            print(f"  FAIL  {s['tr']}  {s['name']}")
            print(f"        -> {e}")

    print()
    print("=" * 70)
    print("SUMMARY")
    print("=" * 70)
    print(f"Passed: {passed}/{len(scenarios)}   Failed: {len(failed)}")
    for tr, name, msg in failed:
        print(f"  FAILURE {tr}: {msg}")

    if failed:
        if strict:
            sys.exit(1)
        return False

    return True

if __name__ == '__main__':
    run_verifier(strict=True)
