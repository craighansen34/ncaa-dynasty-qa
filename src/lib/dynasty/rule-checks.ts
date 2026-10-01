// Runs every gameplay rule against one real season played through the game
// engine. Expected values are computed independently from rules.json so a
// broken engine rule (or a nonsensical rules.json value) shows up as a failure.
import * as E from "./engine";
import type { GameState } from "./engine";

export type RuleCheck = { id: string; rule: string; group: string; pass: boolean; expected: string; actual: string; fix: string };

const R = E.RULES as typeof E.RULES & Record<string, any>;

function seasonFrom(base: GameState | null): GameState {
  const s = base ?? E.newGame();
  // Same roster and prestige as the real save, but a fresh season to play.
  return { ...s, wins: 0, losses: 0, gamesPlayed: 0, week: 1, history: s.history.filter((h) => h.season !== s.season),
    players: s.players.map((p) => ({ ...p, injuryWeeks: 0, starter: false })) };
}

export function runRuleChecks(base: GameState | null, targetWins: number): RuleCheck[] {
  const out: RuleCheck[] = [];
  const add = (id: string, group: string, rule: string, pass: boolean, expected: unknown, actual: unknown, fix: string) =>
    out.push({ id, group, rule, pass, expected: String(expected), actual: String(actual), fix });
  const weeks = R.SEASON_WEEKS as number;
  const wins = Math.max(0, Math.min(weeks, targetWins));
  let s = seasonFrom(base);

  // --- Roster
  const room = R.MAX_ROSTER - s.players.length;
  let filled = s;
  for (let i = 0; i < Math.max(0, room); i++) filled = E.addPlayer(filled, `Walk-on ${i}`, 1).state;
  add("roster-cap-fill", "Roster", `Roster can be filled to ${R.MAX_ROSTER}`, filled.players.length === Math.max(R.MAX_ROSTER, s.players.length), R.MAX_ROSTER, filled.players.length, "Check the roster limit on the Rules editor.");
  const over = E.addPlayer(filled, "One too many", 1);
  add("roster-cap-block", "Roster", "Signing past the roster limit is blocked", over.error === "ROSTER_FULL", "ROSTER_FULL", over.error ?? "allowed", "Roster limit isn't enforced when adding players.");
  const dup = E.addPlayer(s, s.players[0]?.name ?? "x", 1);
  add("roster-duplicate", "Roster", "Duplicate player names are rejected", !s.players[0] || dup.error === "DUPLICATE_PLAYER", "DUPLICATE_PLAYER", dup.error ?? "allowed", "Duplicate names must be blocked.");

  // --- Transfers (checked at the deadline week and one past it)
  let t = s;
  while (t.week < R.TRANSFER_DEADLINE_WEEK && t.gamesPlayed < weeks) t = E.playWeek(t, true).state;
  const atDeadline = E.addPlayer({ ...t, players: t.players.slice(0, R.MAX_ROSTER - 1) }, "Deadline transfer", 2, true);
  add("transfer-open", "Transfers", `Transfers allowed through week ${R.TRANSFER_DEADLINE_WEEK}`, !atDeadline.error, "allowed", atDeadline.error ?? "allowed", "Transfer deadline week blocks too early.");
  const past = E.playWeek(t, true).state;
  const late = E.addPlayer({ ...past, players: past.players.slice(0, R.MAX_ROSTER - 1) }, "Late transfer", 2, true);
  add("transfer-closed", "Transfers", `Transfers blocked after week ${R.TRANSFER_DEADLINE_WEEK}`, R.TRANSFER_DEADLINE_WEEK >= weeks || late.error === "DEADLINE_PASSED", "DEADLINE_PASSED", late.error ?? "allowed", "Transfer deadline isn't enforced.");

  // --- Injuries and lineup
  const hurt = s.players[0]?.name;
  if (hurt) {
    s = E.setInjury(s, hurt, 3).state;
    const start = E.promote(s, hurt);
    add("injury-no-start", "Injuries", "Injured players can't start", start.error === "PLAYER_INJURED", "PLAYER_INJURED", start.error ?? "started", "Promote must refuse injured players.");
    const neg = E.setInjury(s, hurt, -1);
    add("injury-negative", "Injuries", "Negative injury length is rejected", neg.error === "INVALID_INJURY", "INVALID_INJURY", neg.error ?? "allowed", "Reject negative injury weeks.");
  }
  const second = s.players[1]?.name;
  if (second) { s = E.promote(s, second).state; s = E.redshirt(s, second).state; }

  // --- Play the season: win the first `wins` games
  const injuryLog: number[] = [];
  for (let g = 0; g < weeks; g++) {
    const r = E.playWeek(s, g < wins);
    if (r.error) break;
    s = r.state;
    if (hurt) injuryLog.push(s.players.find((p) => p.name === hurt)?.injuryWeeks ?? 0);
  }
  if (hurt) {
    const expectedHeal = Array.from({ length: injuryLog.length }, (_, i) => Math.max(0, 3 - (i + 1)));
    const heal = weeks > 1 ? expectedHeal.slice(0, weeks - 1) : [];
    add("injury-heal", "Injuries", "Injuries heal one week per game, never below zero", JSON.stringify(injuryLog.slice(0, heal.length)) === JSON.stringify(heal) && injuryLog.every((w) => w >= 0), heal.slice(0, 4).join(","), injuryLog.slice(0, 4).join(","), "Healing should drop one week per game.");
  }
  add("season-games", "Season", `A season is ${weeks} games`, s.gamesPlayed === weeks, weeks, s.gamesPlayed, "Check games per season.");
  add("season-record", "Season", "Wins and losses add up to games played", s.wins === wins && s.losses === weeks - wins, `${wins}-${weeks - wins}`, `${s.wins}-${s.losses}`, "Win/loss tally is off.");
  const extra = E.playWeek(s, true);
  add("season-stop", "Season", `No game ${weeks + 1}`, extra.error === "SEASON_COMPLETE", "SEASON_COMPLETE", extra.error ?? "played", "Game count must stop at the season length.");

  // --- Rollover
  const before = s;
  const r1 = E.rollover(before).state;
  const grads = before.players.filter((p) => p.year >= 4 && !p.redshirted).length;
  add("rollover-graduate", "Rollover", "Seniors graduate unless redshirted", r1.players.length === before.players.length - grads, before.players.length - grads, r1.players.length, "Graduation rule in rollover.");
  const heldOk = before.players.filter((p) => p.redshirted).every((p) => r1.players.find((q) => q.name === p.name)?.year === p.year);
  add("rollover-redshirt", "Rollover", "Redshirted players stay in their year", heldOk, "held", heldOk ? "held" : "advanced", "Redshirts must keep their year.");
  const reset = r1.wins === 0 && r1.losses === 0 && r1.gamesPlayed === 0 && r1.week === 1 && r1.players.every((p) => !p.starter && p.injuryWeeks === 0);
  add("rollover-reset", "Rollover", "Record, week, starters and injuries reset", reset, "reset", reset ? "reset" : "not reset", "Rollover must clear season state.");
  const again = E.rollover(r1);
  add("rollover-archive", "Rollover", "Season archived exactly once", r1.history.filter((h) => h.season === before.season).length === 1 && again.state.history.length === r1.history.length + 1, 1, r1.history.filter((h) => h.season === before.season).length, "Archive once per season.");
  const twice = E.rollover(before).state;
  add("rollover-idempotent", "Rollover", "Rolling the same season twice changes nothing extra", JSON.stringify({ ...twice.auditLog.at(-1), completed_at: 0 }) === JSON.stringify({ ...r1.auditLog.at(-1), completed_at: 0 }), "same", "same", "Rollover must be repeatable.");

  // --- Prestige (independent report-card math)
  const g0 = E.gradesOf(before);
  const max = R.GRADE_SCALE.length - 1;
  const g1: Record<string, number> = { ...g0 };
  for (const [g, th] of Object.entries(R.GRADE_SEASON_CHANGES as Record<string, { up_wins: number; down_wins: number }>)) {
    if (wins >= th.up_wins) g1[g] = Math.min(max, (g1[g] ?? 0) + 1); else if (wins <= th.down_wins) g1[g] = Math.max(0, (g1[g] ?? 0) - 1);
  }
  const avg = Object.values(g1).reduce((a, b) => a + b, 0) / Object.values(g1).length;
  const exp = Math.max(R.MIN_PRESTIGE, Math.min(R.MAX_PRESTIGE, Math.floor(avg + 0.5) / 2));
  add("prestige-formula", "Prestige", `After ${wins} wins, prestige = report-card average (half stars)`, r1.prestige === exp, `${exp}★`, `${r1.prestige}★`, "Check grade win thresholds on the Rules editor.");
  add("prestige-range", "Prestige", `Prestige stays between ${R.MIN_PRESTIGE}★ and ${R.MAX_PRESTIGE}★`, r1.prestige >= R.MIN_PRESTIGE && r1.prestige <= R.MAX_PRESTIGE, `${R.MIN_PRESTIGE}–${R.MAX_PRESTIGE}`, r1.prestige, "Prestige limits.");
  for (const [g, th] of Object.entries(R.GRADE_SEASON_CHANGES as Record<string, { up_wins: number; down_wins: number }>)) {
    add(`grade-${g}`, "Prestige", `${g}: "up" win total is above "down"`, th.up_wins > th.down_wins && th.up_wins <= weeks, `down < up ≤ ${weeks}`, `down ${th.down_wins}, up ${th.up_wins}`, "Fix this grade's win totals on the Rules editor.");
  }

  // --- Recruiting hours
  const steps: number[] = [];
  for (let p = R.MIN_PRESTIGE; p <= R.MAX_PRESTIGE; p += R.PRESTIGE_STEP) steps.push(p);
  const hrs = steps.map((p) => E.weeklyHours(p));
  add("hours-table", "Recruiting", "Every prestige level has weekly hours", hrs.every((h) => h > 0), `${steps.length} levels`, `${hrs.filter((h) => h > 0).length} levels`, "Fill in the missing weekly hours.");
  add("hours-order", "Recruiting", "Higher prestige never gives fewer hours", hrs.every((h, i) => i === 0 || h >= (hrs[i - 1] ?? 0)), "rising", hrs.join(" "), "Weekly hours should rise with prestige.");
  add("hours-next", "Recruiting", "Next season's hours follow the new prestige", E.weeklyHours(r1.prestige) === (R.WEEKLY_HOURS as Record<string, number>)[String(exp)], (R.WEEKLY_HOURS as Record<string, number>)[String(exp)], E.weeklyHours(r1.prestige), "Hours lookup by prestige.");
  const pre = steps.map((p) => E.preseasonHours(p));
  add("hours-preseason", "Recruiting", "Preseason hours are at least weekly hours", pre.every((h, i) => h >= (hrs[i] ?? 0)), "≥ weekly", pre.join(" "), "Preseason hours should not be below weekly.");
  add("prospect-cap", "Recruiting", "Per-prospect cap fits in the lowest weekly hours", R.PROSPECT_WEEKLY_HOUR_CAP > 0 && R.PROSPECT_WEEKLY_HOUR_CAP <= Math.min(...hrs), `≤ ${Math.min(...hrs)}`, R.PROSPECT_WEEKLY_HOUR_CAP, "Lower the per-prospect weekly cap.");
  add("offer-cost", "Recruiting", "Offer cost fits in one prospect's cap", R.OFFER_HOUR_COST > 0 && R.OFFER_HOUR_COST <= R.PROSPECT_WEEKLY_HOUR_CAP, `≤ ${R.PROSPECT_WEEKLY_HOUR_CAP}`, R.OFFER_HOUR_COST, "Offer cost can't exceed the prospect cap.");
  add("offers-season", "Recruiting", "Offers per season is a positive number", R.SCHOLARSHIP_OFFERS_PER_SEASON > 0, "> 0", R.SCHOLARSHIP_OFFERS_PER_SEASON, "Set offers per season.");
  return out;
}
