import { Link } from "@tanstack/react-router";
import { useServerFn } from "@tanstack/react-start";
import { useEffect, useState } from "react";
import { supabase } from "@/integrations/supabase/client";
import R from "../../ncaa-dynasty-qa/rules.json";
import { applyRules, RULES_EVENT, setLiveRulesDraft } from "@/lib/dynasty/engine";
import { RulesPreview } from "@/components/RulesPreview";
import { SaveSeasonsPreview } from "@/components/SaveSeasonsPreview";
import { EditableRules, saveRules, type Editable } from "@/lib/rules.functions";

const pick = (): Editable => JSON.parse(JSON.stringify({
  MAX_ROSTER: R.MAX_ROSTER, TRANSFER_DEADLINE_WEEK: R.TRANSFER_DEADLINE_WEEK, SEASON_WEEKS: R.SEASON_WEEKS,
  WEEKLY_HOURS: R.WEEKLY_HOURS, PRESEASON_HOURS: R.PRESEASON_HOURS, PROSPECT_WEEKLY_HOUR_CAP: R.PROSPECT_WEEKLY_HOUR_CAP,
  OFFER_HOUR_COST: R.OFFER_HOUR_COST, SCHOLARSHIP_OFFERS_PER_SEASON: R.SCHOLARSHIP_OFFERS_PER_SEASON,
  GRADE_SEASON_CHANGES: R.GRADE_SEASON_CHANGES,
  _descriptions: (R as { _descriptions?: Record<string, string> })._descriptions ?? {},
}));
const LEVELS = ["0.5", "1", "1.5", "2", "2.5", "3", "3.5", "4", "4.5", "5"];
const nice = (k: string) => k.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());

function Slider({ label, value, min, max, step = 1, onChange }: { label: string; value: number; min: number; max: number; step?: number; onChange: (n: number) => void }) {
  return (
    <label className="grid grid-cols-[1fr_auto] items-center gap-x-3 text-sm">
      <span>{label}</span>
      <input type="number" aria-label={label} value={value} min={min} max={max} step={step}
        onChange={(e) => onChange(e.target.valueAsNumber)}
        className="w-20 rounded-md border border-input bg-background px-2 py-0.5 text-right font-mono" />
      <input type="range" aria-hidden tabIndex={-1} className="col-span-2 accent-primary" value={value} min={min} max={max} step={step}
        onChange={(e) => onChange(Number(e.target.value))} />
    </label>
  );
}

export function PrestigeFormulaPanel() {
  const save = useServerFn(saveRules);
  const [saved, setSaved] = useState<Editable>(pick);
  const [r, setR] = useState<Editable>(pick);
  const [email, setEmail] = useState<string | null>(null);
  const [msg, setMsg] = useState<string | null>(null);
  const check = EditableRules.safeParse(r);
  const dirty = JSON.stringify(r) !== JSON.stringify(saved);

  useEffect(() => {
    const on = () => { const n = pick(); setSaved(n); setR((cur) => (JSON.stringify(cur) === JSON.stringify(saved) ? n : cur)); };
    window.addEventListener(RULES_EVENT, on);
    void supabase.auth.getUser().then(({ data }) => setEmail(data.user?.email ?? null));
    return () => window.removeEventListener(RULES_EVENT, on);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);
  // Share the draft so the staff advisor answers with it right away.
  useEffect(() => { setLiveRulesDraft(check.success ? r : null); }, [r, check.success]);
  useEffect(() => () => setLiveRulesDraft(null), []);

  const grade = (g: string, k: "up_wins" | "down_wins", v: number) => {
    const gc = r.GRADE_SEASON_CHANGES as Record<string, { up_wins: number; down_wins: number }>;
    setR({ ...r, GRADE_SEASON_CHANGES: { ...gc, [g]: { ...gc[g]!, [k]: v } } as Editable["GRADE_SEASON_CHANGES"] });
  };
  const hours = (k: "WEEKLY_HOURS" | "PRESEASON_HOURS", lvl: string, v: number) => setR({ ...r, [k]: { ...r[k], [lvl]: v } });
  const card = "rounded-lg border border-border bg-card p-4";

  async function onSave() {
    if (!check.success) return;
    if (!email) { setMsg("Sign in to save rule changes."); return; }
    const res = await save({ data: r });
    if (res.ok) { applyRules(r); setSaved(r); setMsg("Saved online. The game, advisor and test suite now use these numbers."); }
    else setMsg(res.error);
  }

  return (
    <div data-testid="prestige-formula">
      <p className="mb-4 max-w-3xl text-sm text-muted-foreground">
        Prestige = average of {R.SCHOOL_GRADES.length} school grades (F=0 … A+=10), rounded to the nearest half star, kept between {R.MIN_PRESTIGE}★ and {R.MAX_PRESTIGE}★. Each season a grade goes up one step at or above its "up" wins and down one step at or below its "down" wins.
      </p>
      <div className="grid gap-4 md:grid-cols-3">
        <section className={card} aria-labelledby="g-h">
          <h2 id="g-h" className="mb-3 font-semibold">Grade win totals</h2>
          <div className="space-y-4">
            {Object.entries(r.GRADE_SEASON_CHANGES).map(([g, t]) => (
              <div key={g} className="space-y-2">
                <h3 className="text-sm font-medium">{nice(g)}</h3>
                <Slider label={`${nice(g)} up at`} value={t.up_wins} min={0} max={r.SEASON_WEEKS || 12} onChange={(v) => grade(g, "up_wins", v)} />
                <Slider label={`${nice(g)} down at`} value={t.down_wins} min={0} max={r.SEASON_WEEKS || 12} onChange={(v) => grade(g, "down_wins", v)} />
              </div>
            ))}
          </div>
        </section>

        <section className={card} aria-labelledby="h-h">
          <h2 id="h-h" className="mb-3 font-semibold">Recruiting hours by prestige</h2>
          <table className="w-full font-mono text-sm">
            <thead className="text-xs text-muted-foreground"><tr><th className="text-left">★</th><th>Weekly</th><th>Preseason</th></tr></thead>
            <tbody>
              {LEVELS.map((l) => (
                <tr key={l} className="border-t border-border">
                  <td className="py-1">{l}</td>
                  {(["WEEKLY_HOURS", "PRESEASON_HOURS"] as const).map((k) => (
                    <td key={k} className="text-right">
                      <input type="number" aria-label={`${k === "WEEKLY_HOURS" ? "Weekly" : "Preseason"} hours at ${l} stars`} value={r[k][l] ?? 0}
                        onChange={(e) => hours(k, l, e.target.valueAsNumber)}
                        className="w-20 rounded-md border border-input bg-background px-2 py-0.5 text-right" />
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </section>

        <section className={card} aria-labelledby="l-h">
          <h2 id="l-h" className="mb-3 font-semibold">Limits</h2>
          <div className="space-y-3">
            <Slider label="Roster limit" value={r.MAX_ROSTER} min={1} max={130} onChange={(v) => setR({ ...r, MAX_ROSTER: v })} />
            <Slider label="Hours per prospect per week" value={r.PROSPECT_WEEKLY_HOUR_CAP} min={1} max={200} onChange={(v) => setR({ ...r, PROSPECT_WEEKLY_HOUR_CAP: v })} />
            <Slider label="Hours per offer" value={r.OFFER_HOUR_COST} min={0} max={50} onChange={(v) => setR({ ...r, OFFER_HOUR_COST: v })} />
            <Slider label="Offers per season" value={r.SCHOLARSHIP_OFFERS_PER_SEASON} min={1} max={100} onChange={(v) => setR({ ...r, SCHOLARSHIP_OFFERS_PER_SEASON: v })} />
          </div>
          <div className="mt-6 space-y-2 text-sm">
            {!check.success && <p className="text-destructive" data-testid="prestige-invalid">Some numbers are out of range: {check.error.issues[0]?.message}</p>}
            <div className="flex gap-2">
              <button disabled={!dirty || !check.success} onClick={() => void onSave()}
                className="rounded-md bg-primary px-3 py-1.5 text-primary-foreground disabled:opacity-50">Save</button>
              <button disabled={!dirty} onClick={() => setR(saved)} className="rounded-md border border-border px-3 py-1.5 disabled:opacity-50">Reset</button>
            </div>
            {msg && <p data-testid="prestige-msg">{msg}</p>}
            {!email && <p className="text-xs text-muted-foreground"><Link to="/auth" className="text-primary underline">Sign in</Link> to save. Changes preview live without saving.</p>}
          </div>
        </section>

        <SaveSeasonsPreview draft={r} />
        <RulesPreview draft={r} saved={saved} />
      </div>
    </div>
  );
}
