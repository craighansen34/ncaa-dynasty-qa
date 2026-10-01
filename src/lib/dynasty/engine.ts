// TypeScript port of verify.py's Roster rules. Numbers come from the rules file
// shared with the test suite (ncaa-dynasty-qa/rules.json).
import R from "../../../ncaa-dynasty-qa/rules.json";

export const RULES = R;

// Live rules editor: after a save, swap the new numbers in place so every
// open page uses them at once (no reload), and tell listeners to re-render.
export const RULES_EVENT = "dynasty-rules-changed";
export function applyRules(next: object) {
  Object.assign(R, JSON.parse(JSON.stringify(next)));
  if (typeof window !== "undefined") window.dispatchEvent(new Event(RULES_EVENT));
}

// Live rules editor draft (numbers + descriptions, possibly unsaved). The
// advisor reads this at ask time so its answers follow edits as they're typed.
let liveDraft: object | null = null;
export function setLiveRulesDraft(draft: object | null) { liveDraft = draft; }
export function getLiveRulesDraft() { return liveDraft; }

export type Player = { name: string; year: number; redshirted: boolean; starter: boolean; injuryWeeks: number };
export type SeasonRecord = { season: number; wins: number; losses: number; games_played: number };
export type Transition = { player: string; from_year: number; to_year: number | null; action: "advanced" | "redshirt_hold" | "graduated" };
export type AuditEntry = {
  season_id: number;
  archived_record: SeasonRecord;
  completed_at: string;
  prestige_before: number;
  prestige_after: number;
  transitions: Transition[];
};
export type GameState = {
  players: Player[];
  wins: number;
  losses: number;
  gamesPlayed: number;
  season: number;
  week: number;
  prestige: number;
  /** My School report card: GRADE_SCALE index (0-10) per school grade. Missing in old saves. */
  grades?: Record<string, number>;
  history: SeasonRecord[];
  auditLog: AuditEntry[];
};
export type Result = { state: GameState; error?: string };

export const ERRORS: Record<string, string> = {
  ROSTER_FULL: `The roster is full (${R.MAX_ROSTER} players).`,
  DEADLINE_PASSED: `The transfer deadline (week ${R.TRANSFER_DEADLINE_WEEK}) has passed.`,
  PLAYER_INJURED: "Injured players can't start until fully healed.",
  SEASON_OVER: `Week ${R.SEASON_WEEKS} is the last week — roll over to the next season.`,
  UNKNOWN_PLAYER: "That player isn't on the roster.",
  INVALID_INJURY: "Injury length can't be negative.",
  DUPLICATE_PLAYER: "A player with that name is already on the roster.",
  SEASON_COMPLETE: `All ${R.SEASON_WEEKS} games have been played.`,
};

const FIRST = ["Jalen", "Marcus", "Tre", "Caleb", "Deion", "Bryce", "Malik", "Cam", "Isaiah", "Quinn", "Drew", "Jaxon"];
const LAST = ["Carter", "Hill", "Brooks", "Reed", "Price", "Ward", "Hayes", "Moss", "Tate", "Banks", "Cole", "Frost"];

export function newGame(): GameState {
  const players: Player[] = [];
  for (let i = 0; i < 12; i++) {
    players.push({ name: `${FIRST[i]} ${LAST[(i * 5) % 12]}`, year: (i % 4) + 1, redshirted: false, starter: false, injuryWeeks: 0 });
  }
  return { players, wins: 0, losses: 0, gamesPlayed: 0, season: 1, week: 1, prestige: 3, grades: uniformGrades(3), history: [], auditLog: [] };
}

const fail = (state: GameState, error: string): Result => ({ state, error });
const find = (s: GameState, name: string) => s.players.find((p) => p.name === name);
const update = (s: GameState, name: string, f: (p: Player) => Partial<Player>): GameState => ({
  ...s,
  players: s.players.map((p) => (p.name === name ? { ...p, ...f(p) } : p)),
});

export function addPlayer(s: GameState, name: string, year: number, transfer = false): Result {
  if (transfer && s.week > R.TRANSFER_DEADLINE_WEEK) return fail(s, "DEADLINE_PASSED");
  if (s.players.length >= R.MAX_ROSTER) return fail(s, "ROSTER_FULL");
  if (find(s, name)) return fail(s, "DUPLICATE_PLAYER");
  return { state: { ...s, players: [...s.players, { name, year, redshirted: false, starter: false, injuryWeeks: 0 }] } };
}

export const cut = (s: GameState, name: string): Result => ({ state: { ...s, players: s.players.filter((p) => p.name !== name) } });
export const redshirt = (s: GameState, name: string): Result => ({ state: update(s, name, (p) => ({ redshirted: !p.redshirted })) });
export const demote = (s: GameState, name: string): Result => ({ state: update(s, name, () => ({ starter: false })) });

export function promote(s: GameState, name: string): Result {
  const p = find(s, name);
  if (!p) return fail(s, "UNKNOWN_PLAYER");
  if (p.injuryWeeks > 0) return fail(s, "PLAYER_INJURED");
  return { state: update(s, name, () => ({ starter: true })) };
}

export function setInjury(s: GameState, name: string, weeks: number): Result {
  if (!find(s, name)) return fail(s, "UNKNOWN_PLAYER");
  if (weeks < 0) return fail(s, "INVALID_INJURY");
  return { state: update(s, name, (p) => ({ injuryWeeks: weeks, starter: weeks > 0 ? false : p.starter })) };
}

export function injuryStatus(p: Player): "healthy" | "questionable" | "out" {
  return p.injuryWeeks === 0 ? "healthy" : p.injuryWeeks === 1 ? "questionable" : "out";
}

/** Plays this week's game, then advances the week (injuries heal one week). */
export function playWeek(s: GameState, won: boolean): Result {
  if (s.gamesPlayed >= R.SEASON_WEEKS) return fail(s, "SEASON_COMPLETE");
  const played = { ...s, gamesPlayed: s.gamesPlayed + 1, wins: s.wins + (won ? 1 : 0), losses: s.losses + (won ? 0 : 1) };
  if (s.week >= R.SEASON_WEEKS) return { state: played };
  return {
    state: {
      ...played,
      week: s.week + 1,
      players: played.players.map((p) => ({ ...p, injuryWeeks: Math.max(0, p.injuryWeeks - 1) })),
    },
  };
}

const GRADE_MAX = R.GRADE_SCALE.length - 1;
export const uniformGrades = (stars: number): Record<string, number> =>
  Object.fromEntries(R.SCHOOL_GRADES.map((g) => [g, Math.round(stars * 2)]));
export const gradesOf = (s: GameState) => s.grades ?? uniformGrades(s.prestige);
export const gradeLetter = (i: number) => R.GRADE_SCALE[i];

/** Average grade rounded half-up to the nearest half star, clamped (same as verify.py). */
export function prestigeFromGrades(grades: Record<string, number>): number {
  const vals = Object.values(grades);
  const n = vals.length;
  const total = vals.reduce((a, b) => a + b, 0);
  const half = Math.floor((2 * total + n) / (2 * n));
  return Math.max(R.MIN_PRESTIGE, Math.min(R.MAX_PRESTIGE, half / 2));
}

/** Each result-driven grade moves one step at its win thresholds. */
export function seasonGrades(grades: Record<string, number>, wins: number): Record<string, number> {
  const out = { ...grades };
  for (const [g, t] of Object.entries(R.GRADE_SEASON_CHANGES)) {
    if (wins >= t.up_wins) out[g] = Math.min(GRADE_MAX, (out[g] ?? 0) + 1);
    else if (wins <= t.down_wins) out[g] = Math.max(0, (out[g] ?? 0) - 1);
  }
  return out;
}

/** Idempotent rollover: archive, graduate/advance, reset season state, update prestige. */
export function rollover(s: GameState, now = new Date()): Result {
  if (s.history.some((h) => h.season === s.season)) return { state: s };
  const transitions: Transition[] = [];
  const players: Player[] = [];
  for (const p of [...s.players].sort((a, b) => a.name.localeCompare(b.name))) {
    if (p.year >= 4 && !p.redshirted) {
      transitions.push({ player: p.name, from_year: p.year, to_year: null, action: "graduated" });
      continue;
    }
    const year = p.redshirted ? p.year : p.year + 1;
    transitions.push({ player: p.name, from_year: p.year, to_year: year, action: p.redshirted ? "redshirt_hold" : "advanced" });
    players.push({ ...p, year, redshirted: false, starter: false, injuryWeeks: 0 });
  }
  const record = { season: s.season, wins: s.wins, losses: s.losses, games_played: s.gamesPlayed };
  const grades = seasonGrades(gradesOf(s), s.wins);
  const prestige = prestigeFromGrades(grades);
  return {
    state: {
      players,
      wins: 0,
      losses: 0,
      gamesPlayed: 0,
      season: s.season + 1,
      week: 1,
      prestige,
      grades,
      history: [...s.history, record],
      auditLog: [
        ...s.auditLog,
        { season_id: s.season, archived_record: record, completed_at: now.toISOString(), prestige_before: s.prestige, prestige_after: prestige, transitions },
      ],
    },
  };
}

export const weeklyHours = (prestige: number) => (R.WEEKLY_HOURS as Record<string, number>)[String(prestige)] ?? 0;
export const preseasonHours = (prestige: number) => (R.PRESEASON_HOURS as Record<string, number>)[String(prestige)] ?? 0;
