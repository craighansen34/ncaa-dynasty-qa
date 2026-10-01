import { Link } from "@tanstack/react-router";
import { useEffect, useState } from "react";
import { RULES, RULES_EVENT } from "@/lib/dynasty/engine";
import { loadOnlineRules } from "@/lib/rules-online";

type Any = Record<string, any>;

const chip = "rounded-full border border-border px-2 py-0.5 text-[11px] text-muted-foreground";

// Which rule-check IDs (see /rule-tests) exercise each rule.
const CHECKS: Record<string, string[]> = {
  MAX_ROSTER: ["roster-cap-fill", "roster-cap-block"],
  TRANSFER_DEADLINE_WEEK: ["transfer-open", "transfer-closed"],
  SEASON_WEEKS: ["season-games", "season-stop"],
  MIN_PRESTIGE: ["prestige-range"],
  MAX_PRESTIGE: ["prestige-range"],
  PRESTIGE_STEP: ["hours-table"],
  GRADE_SCALE: ["prestige-formula"],
  SCHOOL_GRADES: ["prestige-formula"],
  GRADE_SEASON_CHANGES: ["prestige-formula", "grade-championship_contender", "grade-brand_exposure", "grade-program_tradition"],
  WEEKLY_HOURS: ["hours-table", "hours-order", "hours-next"],
  PRESEASON_HOURS: ["hours-preseason"],
  PROSPECT_WEEKLY_HOUR_CAP: ["prospect-cap"],
  OFFER_HOUR_COST: ["offer-cost"],
  SCHOLARSHIP_OFFERS_PER_SEASON: ["offers-season"],
};

const FALLBACK: Record<string, string> = {
  MIN_PRESTIGE: "Lowest prestige a program can fall to (half a star).",
  MAX_PRESTIGE: "Highest prestige a program can reach (five stars).",
  PRESTIGE_STEP: "Prestige moves in half-star steps.",
  GRADE_SCALE: "My School report card grades, in order from worst to best; each grade is an index 0–10.",
  SCHOOL_GRADES: "The 11 report card categories; Team Prestige is their average converted to stars.",
  GRADE_SEASON_CHANGES: "Win totals that move each results-driven grade one step up or down after a season.",
};

function UsedBy({ rule }: { rule: string }) {
  const ids = CHECKS[rule];
  return (
    <span className="flex flex-wrap gap-1.5">
      <span className={chip}>Game engine</span>
      <span className={chip}>Test suite</span>
      {ids && (
        <Link to="/rule-tests" className={`${chip} hover:border-primary hover:text-primary`} title="Open the rules test suite">
          Rule tests: {ids.join(", ")}
        </Link>
      )}
    </span>
  );
}

function Value({ v }: { v: any }) {
  if (Array.isArray(v)) return <span className="font-mono text-xs">{v.join(" → ")}</span>;
  if (typeof v === "object" && v !== null) return <span className="font-mono text-xs">{JSON.stringify(v)}</span>;
  return <span className="font-mono">{String(v)}</span>;
}

function HoursTable({ label, hours }: { label: string; hours: Record<string, number> }) {
  const rows = Object.entries(hours).sort((a, b) => Number(b[0]) - Number(a[0]));
  return (
    <div>
      <p className="mb-1 text-xs font-semibold uppercase tracking-wide text-muted-foreground">{label}</p>
      <table className="text-xs">
        <tbody>
          {rows.map(([p, h]) => (
            <tr key={p}>
              <td className="pr-3 font-mono text-primary">{p}★</td>
              <td className="font-mono">{h} h</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function RulesDocContent() {
  const [, setTick] = useState(0);
  useEffect(() => {
    loadOnlineRules();
    const on = () => setTick((t) => t + 1);
    window.addEventListener(RULES_EVENT, on);
    return () => window.removeEventListener(RULES_EVENT, on);
  }, []);

  const R = RULES as any; // eslint-disable-line @typescript-eslint/no-explicit-any
  const desc = (k: string) => R._descriptions?.[k] ?? FALLBACK[k] ?? "";
  const prestigeLevels = Object.keys(R.WEEKLY_HOURS as Any).sort((a, b) => Number(b) - Number(a));

  const simple: [string, string][] = [
    ["MAX_ROSTER", "players on the roster"],
    ["TRANSFER_DEADLINE_WEEK", `last transfer week (blocked from week ${(R.TRANSFER_DEADLINE_WEEK as number) + 1})`],
    ["SEASON_WEEKS", "games per season"],
    ["PROSPECT_WEEKLY_HOUR_CAP", "h per prospect per week"],
    ["OFFER_HOUR_COST", "h per scholarship offer"],
    ["SCHOLARSHIP_OFFERS_PER_SEASON", "offers per season"],
  ];

  return (
    <>
      <p className="mb-6 rounded-lg border bg-card p-4 text-sm text-muted-foreground" data-testid="doc-note">
        These are the live values the game is using right now (saved rules loaded automatically). The test suite reads the same shared
        rules file directly, and the rules test suite re-checks every one of them against a played season.
      </p>

      {/* --- Roster & season --- */}
      <section className="mb-8">
        <h2 className="mb-2 text-lg font-semibold">Roster & season</h2>
        <table className="w-full text-sm" data-testid="doc-roster">
          <thead className="text-left text-xs uppercase tracking-wide text-muted-foreground">
            <tr><th className="py-2">Rule</th><th className="py-2">Threshold</th><th className="py-2">Description</th><th className="py-2">Used by</th></tr>
          </thead>
          <tbody>
            {simple.map(([k, unit]) => (
              <tr key={k} className="border-t align-top" data-rule={k}>
                <td className="py-2 pr-3 font-mono text-xs text-primary">{k}</td>
                <td className="py-2 pr-3 font-mono">{String(R[k])} <span className="text-xs text-muted-foreground">{unit}</span></td>
                <td className="py-2 pr-3 text-muted-foreground">{desc(k)}</td>
                <td className="py-2"><UsedBy rule={k} /></td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>

      {/* --- Prestige --- */}
      <section className="mb-8">
        <h2 className="mb-2 text-lg font-semibold">Prestige & report card</h2>
        <table className="w-full text-sm" data-testid="doc-prestige">
          <thead className="text-left text-xs uppercase tracking-wide text-muted-foreground">
            <tr><th className="py-2">Rule</th><th className="py-2">Threshold</th><th className="py-2">Description</th><th className="py-2">Used by</th></tr>
          </thead>
          <tbody>
            <tr className="border-t align-top" data-rule="MIN_PRESTIGE">
              <td className="py-2 pr-3 font-mono text-xs text-primary">MIN_PRESTIGE / MAX_PRESTIGE</td>
              <td className="py-2 pr-3 font-mono">{R.MIN_PRESTIGE}★ – {R.MAX_PRESTIGE}★</td>
              <td className="py-2 pr-3 text-muted-foreground">{desc("MIN_PRESTIGE")} {desc("MAX_PRESTIGE")}</td>
              <td className="py-2"><UsedBy rule="MIN_PRESTIGE" /></td>
            </tr>
            <tr className="border-t align-top" data-rule="PRESTIGE_STEP">
              <td className="py-2 pr-3 font-mono text-xs text-primary">PRESTIGE_STEP</td>
              <td className="py-2 pr-3 font-mono">{R.PRESTIGE_STEP}★</td>
              <td className="py-2 pr-3 text-muted-foreground">{desc("PRESTIGE_STEP")}</td>
              <td className="py-2"><UsedBy rule="PRESTIGE_STEP" /></td>
            </tr>
            <tr className="border-t align-top" data-rule="GRADE_SCALE">
              <td className="py-2 pr-3 font-mono text-xs text-primary">GRADE_SCALE</td>
              <td className="py-2 pr-3"><Value v={R.GRADE_SCALE} /></td>
              <td className="py-2 pr-3 text-muted-foreground">{desc("GRADE_SCALE")}</td>
              <td className="py-2"><UsedBy rule="GRADE_SCALE" /></td>
            </tr>
            <tr className="border-t align-top" data-rule="SCHOOL_GRADES">
              <td className="py-2 pr-3 font-mono text-xs text-primary">SCHOOL_GRADES</td>
              <td className="py-2 pr-3 font-mono text-xs">{(R.SCHOOL_GRADES as string[]).length} categories</td>
              <td className="py-2 pr-3 text-muted-foreground">{desc("SCHOOL_GRADES")} <span className="font-mono text-xs">{(R.SCHOOL_GRADES as string[]).join(", ")}</span></td>
              <td className="py-2"><UsedBy rule="SCHOOL_GRADES" /></td>
            </tr>
            {(R.GRADE_SEASON_CHANGES as Any) && Object.entries(R.GRADE_SEASON_CHANGES as Any).map(([g, th]: [string, any]) => (
              <tr key={g} className="border-t align-top" data-rule={`grade-${g}`}>
                <td className="py-2 pr-3 font-mono text-xs text-primary">{g}</td>
                <td className="py-2 pr-3 font-mono">up at ≥ {th.up_wins} wins · down at ≤ {th.down_wins}</td>
                <td className="py-2 pr-3 text-muted-foreground">{R._descriptions?.[g] ?? desc("GRADE_SEASON_CHANGES")}</td>
                <td className="py-2"><UsedBy rule="GRADE_SEASON_CHANGES" /></td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>

      {/* --- Recruiting --- */}
      <section className="mb-8">
        <h2 className="mb-2 text-lg font-semibold">Recruiting</h2>
        <table className="w-full text-sm" data-testid="doc-recruiting">
          <thead className="text-left text-xs uppercase tracking-wide text-muted-foreground">
            <tr><th className="py-2">Rule</th><th className="py-2">Threshold</th><th className="py-2">Description</th><th className="py-2">Used by</th></tr>
          </thead>
          <tbody>
            <tr className="border-t align-top" data-rule="WEEKLY_HOURS">
              <td className="py-2 pr-3 align-top font-mono text-xs text-primary">WEEKLY_HOURS</td>
              <td className="py-2 pr-3 align-top"><HoursTable label="By prestige" hours={R.WEEKLY_HOURS as Any} /></td>
              <td className="py-2 pr-3 align-top text-muted-foreground">
                {desc("WEEKLY_HOURS")}
                <p className="mt-1 text-xs">Prestige levels covered: {prestigeLevels.length} ({prestigeLevels.at(-1)}★–{prestigeLevels[0]}★)</p>
              </td>
              <td className="py-2 align-top"><UsedBy rule="WEEKLY_HOURS" /></td>
            </tr>
            <tr className="border-t align-top" data-rule="PRESEASON_HOURS">
              <td className="py-2 pr-3 align-top font-mono text-xs text-primary">PRESEASON_HOURS</td>
              <td className="py-2 pr-3 align-top"><HoursTable label="By prestige" hours={R.PRESEASON_HOURS as Any} /></td>
              <td className="py-2 pr-3 align-top text-muted-foreground">{desc("PRESEASON_HOURS")}</td>
              <td className="py-2 align-top"><UsedBy rule="PRESEASON_HOURS" /></td>
            </tr>
            {(["PROSPECT_WEEKLY_HOUR_CAP", "OFFER_HOUR_COST", "SCHOLARSHIP_OFFERS_PER_SEASON"] as const).map((k) => (
              <tr key={k} className="border-t align-top" data-rule={k}>
                <td className="py-2 pr-3 font-mono text-xs text-primary">{k}</td>
                <td className="py-2 pr-3 font-mono">{String(R[k])} h</td>
                <td className="py-2 pr-3 text-muted-foreground">{desc(k)}</td>
                <td className="py-2"><UsedBy rule={k} /></td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>

      {/* --- Suite-only constants --- */}
      <section className="mb-8">
        <h2 className="mb-2 text-lg font-semibold">Test-suite-only limits</h2>
        <p className="mb-2 text-sm text-muted-foreground">
          Enforced by the test suite only (fixed constants in <span className="font-mono text-xs">verify.py</span>); they are not in the shared rules file, so the game does not read them.
        </p>
        <table className="w-full text-sm" data-testid="doc-suite-only">
          <thead className="text-left text-xs uppercase tracking-wide text-muted-foreground">
            <tr><th className="py-2">Rule</th><th className="py-2">Threshold</th><th className="py-2">Description</th><th className="py-2">Used by</th></tr>
          </thead>
          <tbody>
            <tr className="border-t align-top" data-rule="BOARD_LIMIT">
              <td className="py-2 pr-3 font-mono text-xs text-primary">BOARD_LIMIT</td>
              <td className="py-2 pr-3 font-mono">35</td>
              <td className="py-2 pr-3 text-muted-foreground">Prospects tracked on the recruiting board at once.</td>
              <td className="py-2"><span className={chip}>Test suite</span></td>
            </tr>
            <tr className="border-t align-top" data-rule="SIGNING_CLASS_LIMIT">
              <td className="py-2 pr-3 font-mono text-xs text-primary">SIGNING_CLASS_LIMIT</td>
              <td className="py-2 pr-3 font-mono">25</td>
              <td className="py-2 pr-3 text-muted-foreground">Signees allowed per recruiting class.</td>
              <td className="py-2"><span className={chip}>Test suite</span></td>
            </tr>
          </tbody>
        </table>
      </section>

      <p className="text-sm text-muted-foreground">
        Want to change a number? Open the <Link to="/rules" className="text-primary underline">Rules editor</Link> — the game,
        the test suite and this document all follow it. Failing rules show up on the{" "}
        <Link to="/rule-tests" className="text-primary underline">Rules test suite</Link> page.
      </p>
    </>
  );
}
