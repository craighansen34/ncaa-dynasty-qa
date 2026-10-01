import { useState } from "react";
import R from "../../ncaa-dynasty-qa/rules.json";
import type { Editable } from "@/lib/rules.functions";

// Live preview of a draft rule set (not yet saved): same maths as the game engine
// and verify.py, but driven by the draft numbers.
const GRADE_MAX = R.GRADE_SCALE.length - 1;
const LEVELS = ["0.5", "1", "1.5", "2", "2.5", "3", "3.5", "4", "4.5", "5"];

function prestigeOf(grades: number[]) {
  const n = grades.length, total = grades.reduce((a, b) => a + b, 0);
  return Math.max(R.MIN_PRESTIGE, Math.min(R.MAX_PRESTIGE, Math.floor((2 * total + n) / (2 * n)) / 2));
}
function afterSeasons(r: Editable, start: number, wins: number, seasons: number) {
  let g: Record<string, number> = Object.fromEntries(R.SCHOOL_GRADES.map((k) => [k, Math.round(start * 2)]));
  for (let i = 0; i < seasons; i++) {
    const next = { ...g };
    for (const [k, t] of Object.entries(r.GRADE_SEASON_CHANGES)) {
      if (wins >= t.up_wins) next[k] = Math.min(GRADE_MAX, (next[k] ?? 0) + 1);
      else if (wins <= t.down_wins) next[k] = Math.max(0, (next[k] ?? 0) - 1);
    }
    g = next;
  }
  return prestigeOf(Object.values(g));
}
const SIGNING_CLASS_LIMIT = 25; // verify.py SIGNING_CLASS_LIMIT (not in rules.json)
const ok = (n: number) => Number.isFinite(n);

export function RulesPreview({ draft, saved }: { draft: Editable; saved: Editable }) {
  const [start, setStart] = useState(3);
  const [roster, setRoster] = useState(70);
  const weeks = ok(draft.SEASON_WEEKS) ? Math.min(Math.max(draft.SEASON_WEEKS, 1), 20) : saved.SEASON_WEEKS;
  const wins = Array.from({ length: weeks + 1 }, (_, i) => i);
  const diff = (a: unknown, b: unknown) => (a !== b ? "text-primary font-semibold" : "");
  const stars = (n: number) => `${n}★`;
  const card = "rounded-lg border border-border bg-card p-4";
  const limit = ok(draft.MAX_ROSTER) ? draft.MAX_ROSTER : saved.MAX_ROSTER;
  const deadline = ok(draft.TRANSFER_DEADLINE_WEEK) ? draft.TRANSFER_DEADLINE_WEEK : saved.TRANSFER_DEADLINE_WEEK;

  return (
    <section className={`${card} md:col-span-2`} data-testid="rules-preview" aria-labelledby="preview-h">
      <div className="mb-1 flex flex-wrap items-baseline justify-between gap-2">
        <h2 id="preview-h" className="text-lg font-semibold">Live preview</h2>
        <p className="text-xs text-muted-foreground">Updates as you type. <span className="text-primary font-semibold">Highlighted</span> = different from the saved rules.</p>
      </div>

      <div className="mt-3 grid gap-6 lg:grid-cols-3">
        <div className="lg:col-span-2">
          <div className="mb-2 flex items-center gap-2 text-sm">
            <h3 className="font-medium">Prestige after a season</h3>
            <label className="ml-auto flex items-center gap-1">starting at
              <select aria-label="Starting prestige" value={start} onChange={(e) => setStart(Number(e.target.value))}
                className="rounded-md border border-input bg-background px-1 py-0.5 font-mono">
                {LEVELS.map((l) => <option key={l} value={l}>{l}★</option>)}
              </select>
            </label>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-center font-mono text-xs" data-testid="preview-prestige">
              <thead className="text-muted-foreground">
                <tr><th className="text-left font-sans">Wins</th>{wins.map((w) => <th key={w} className="px-1">{w}</th>)}</tr>
              </thead>
              <tbody>
                {[1, 2].map((n) => (
                  <tr key={n} className="border-t border-border">
                    <td className="py-1 text-left font-sans">{n === 1 ? "1 season" : "2 seasons"}</td>
                    {wins.map((w) => {
                      const p = afterSeasons(draft, start, w, n);
                      return <td key={w} className={diff(p, afterSeasons(saved, start, w, n))}>{p}</td>;
                    })}
                  </tr>
                ))}
                <tr className="border-t border-border">
                  <td className="py-1 text-left font-sans">Weekly hours next season</td>
                  {wins.map((w) => {
                    const p = afterSeasons(draft, start, w, 1), q = afterSeasons(saved, start, w, 1);
                    const h = draft.WEEKLY_HOURS[String(p)];
                    return <td key={w} className={diff(h, saved.WEEKLY_HOURS[String(q)])}>{ok(h ?? NaN) ? h : "–"}</td>;
                  })}
                </tr>
              </tbody>
            </table>
          </div>
          <p className="mt-1 text-xs text-muted-foreground">Prestige is the average of {R.SCHOOL_GRADES.length} school grades; only the three result-driven grades move, one step per season.</p>
        </div>

        <div className="space-y-4 text-sm">
          <div>
            <h3 className="mb-1 font-medium">Recruiting at {stars(start)}</h3>
            <ul className="space-y-0.5" data-testid="preview-hours">
              <li>Weekly hours: <span className={diff(draft.WEEKLY_HOURS[String(start)], saved.WEEKLY_HOURS[String(start)])}>{draft.WEEKLY_HOURS[String(start)]}</span></li>
              <li>Preseason hours: <span className={diff(draft.PRESEASON_HOURS[String(start)], saved.PRESEASON_HOURS[String(start)])}>{draft.PRESEASON_HOURS[String(start)]}</span></li>
              <li>Prospects at the max each week: <span className={diff(Math.floor(draft.WEEKLY_HOURS[String(start)]! / draft.PROSPECT_WEEKLY_HOUR_CAP), Math.floor(saved.WEEKLY_HOURS[String(start)]! / saved.PROSPECT_WEEKLY_HOUR_CAP))}>
                {ok(draft.PROSPECT_WEEKLY_HOUR_CAP) && draft.PROSPECT_WEEKLY_HOUR_CAP > 0 ? Math.floor(draft.WEEKLY_HOURS[String(start)]! / draft.PROSPECT_WEEKLY_HOUR_CAP) : "–"}</span></li>
              <li>All {draft.SCHOLARSHIP_OFFERS_PER_SEASON} offers cost: <span className={diff(draft.OFFER_HOUR_COST * draft.SCHOLARSHIP_OFFERS_PER_SEASON, saved.OFFER_HOUR_COST * saved.SCHOLARSHIP_OFFERS_PER_SEASON)}>{draft.OFFER_HOUR_COST * draft.SCHOLARSHIP_OFFERS_PER_SEASON} hours</span></li>
            </ul>
          </div>
          <div>
            <h3 className="mb-1 flex items-center gap-2 font-medium">Roster with
              <input type="number" aria-label="Example roster size" value={roster} min={0} onChange={(e) => setRoster(e.target.valueAsNumber || 0)}
                className="w-16 rounded-md border border-input bg-background px-1 py-0.5 text-right font-mono" /> players
            </h3>
            <ul className="space-y-0.5" data-testid="preview-roster">
              <li>Limit: <span className={diff(limit, saved.MAX_ROSTER)}>{limit}</span></li>
              <li>Open spots: <span className={diff(limit - roster, saved.MAX_ROSTER - roster)}>{Math.max(0, limit - roster)}</span>{roster > limit && <span className="text-destructive"> (over the limit)</span>}</li>
              <li>Most a signing class can add: <span className={diff(limit, saved.MAX_ROSTER)}>{Math.max(0, Math.min(SIGNING_CLASS_LIMIT, limit - roster))}</span></li>
            </ul>
          </div>
          <div>
            <h3 className="mb-1 font-medium">Transfer window</h3>
            <div className="flex gap-0.5" data-testid="preview-weeks" aria-label={`Transfers open weeks 1 to ${deadline} of ${weeks}`}>
              {Array.from({ length: weeks }, (_, i) => i + 1).map((w) => (
                <span key={w} title={`Week ${w}`} className={`flex h-6 flex-1 items-center justify-center rounded-sm font-mono text-[10px] ${w <= deadline ? "bg-primary text-primary-foreground" : "bg-muted text-muted-foreground"}`}>{w}</span>
              ))}
            </div>
            <p className="mt-1 text-xs text-muted-foreground">Transfers open weeks 1–{deadline}, closed after.</p>
          </div>
        </div>
      </div>
    </section>
  );
}
