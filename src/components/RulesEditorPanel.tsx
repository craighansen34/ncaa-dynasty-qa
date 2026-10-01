import { useServerFn } from "@tanstack/react-start";
import { useEffect, useRef, useState } from "react";
import { Link } from "@tanstack/react-router";
import { supabase } from "@/integrations/supabase/client";
import R from "../../ncaa-dynasty-qa/rules.json";
import { applyRules, RULES_EVENT, setLiveRulesDraft } from "@/lib/dynasty/engine";
import { RulesPreview } from "@/components/RulesPreview";
import { EditableRules, type DESCRIBED, saveRules, type Editable } from "@/lib/rules.functions";
import { hasBackendConfig } from "@/lib/rules-online";

const LEVELS = ["5", "4.5", "4", "3.5", "3", "2.5", "2", "1.5", "1", "0.5"];
const pick = (): Editable => JSON.parse(JSON.stringify({
  MAX_ROSTER: R.MAX_ROSTER, TRANSFER_DEADLINE_WEEK: R.TRANSFER_DEADLINE_WEEK, SEASON_WEEKS: R.SEASON_WEEKS,
  WEEKLY_HOURS: R.WEEKLY_HOURS, PRESEASON_HOURS: R.PRESEASON_HOURS, PROSPECT_WEEKLY_HOUR_CAP: R.PROSPECT_WEEKLY_HOUR_CAP,
  OFFER_HOUR_COST: R.OFFER_HOUR_COST, SCHOLARSHIP_OFFERS_PER_SEASON: R.SCHOLARSHIP_OFFERS_PER_SEASON,
  GRADE_SEASON_CHANGES: R.GRADE_SEASON_CHANGES,
  _descriptions: (R as { _descriptions?: Record<string, string> })._descriptions ?? {},
}));
type DescKey = (typeof DESCRIBED)[number];
const input = "w-20 rounded-md border border-input bg-background px-2 py-1 text-right font-mono text-sm";

function Desc({ label, value, onChange }: { label: string; value: string; onChange: (t: string) => void }) {
  return (
    <textarea aria-label={`Description of ${label}`} rows={1} maxLength={300} value={value} placeholder="Describe this rule"
      onChange={(e) => onChange(e.target.value)}
      className="mt-1 w-full resize-y rounded-md border border-input bg-background px-2 py-1 text-xs text-muted-foreground" />
  );
}

function Num({ label, value, onChange, desc, onDesc }: { label: string; value: number; onChange: (n: number) => void; desc: string; onDesc: (t: string) => void }) {
  return (
    <div>
      <label className="flex items-center justify-between gap-3 text-sm">
        <span>{label}</span>
        <input type="number" aria-label={label} className={input} value={Number.isNaN(value) ? "" : value} onChange={(e) => onChange(e.target.valueAsNumber)} />
      </label>
      <Desc label={label} value={desc} onChange={onDesc} />
    </div>
  );
}

export function RulesEditorPanel({ live = false }: { live?: boolean }) {
  const save = useServerFn(saveRules);
  const [r, setR] = useState<Editable>(pick);
  const [msg, setMsg] = useState<{ ok: boolean; text: string } | null>(null);
  const [busy, setBusy] = useState(false);
  const set = <K extends keyof Editable>(k: K, v: Editable[K]) => { setR({ ...r, [k]: v }); setMsg(null); };
  const check = EditableRules.safeParse(r);
  const dirty = JSON.stringify(r) !== JSON.stringify(pick());
  const d = (k: DescKey) => r._descriptions?.[k] ?? "";
  const setD = (k: DescKey) => (t: string) => set("_descriptions", { ...r._descriptions, [k]: t });
  const num = (k: "MAX_ROSTER" | "TRANSFER_DEADLINE_WEEK" | "SEASON_WEEKS" | "PROSPECT_WEEKLY_HOUR_CAP" | "OFFER_HOUR_COST" | "SCHOLARSHIP_OFFERS_PER_SEASON", label: string) =>
    <Num label={label} value={r[k]} onChange={(n) => set(k, n)} desc={d(k)} onDesc={setD(k)} />;

  // When the saved online rules arrive, refresh the boxes unless you've started editing.
  const base = useRef(JSON.stringify(r));
  const rRef = useRef(r); rRef.current = r;
  useEffect(() => {
    const on = () => { if (JSON.stringify(rRef.current) === base.current) { const n = pick(); base.current = JSON.stringify(n); setR(n); } };
    window.addEventListener(RULES_EVENT, on);
    return () => window.removeEventListener(RULES_EVENT, on);
  }, []);
  const [email, setEmail] = useState<string | null | undefined>(undefined);
  useEffect(() => {
    if (!hasBackendConfig()) { setEmail(null); return; }
    void supabase.auth.getUser().then(({ data }) => setEmail(data.user?.email ?? null));
    const { data } = supabase.auth.onAuthStateChange((_e, sess) => setEmail(sess?.user?.email ?? null));
    return () => data.subscription.unsubscribe();
  }, []);
  const [auto, setAuto] = useState(live);
  // Live mode: share the current draft (numbers + descriptions) so the advisor
  // answers with it even before auto-save writes the file.
  useEffect(() => {
    if (!live) return;
    setLiveRulesDraft(check.success ? r : null);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [live, JSON.stringify(r), check.success]);
  useEffect(() => () => { if (live) setLiveRulesDraft(null); }, [live]);
  // Live mode: save a moment after the last valid edit, so the game (and the suite's next run) pick it up with no Save click.
  useEffect(() => {
    if (!auto || !dirty || !check.success) return;
    const t = setTimeout(() => { void onSave(); }, 600);
    return () => clearTimeout(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [auto, JSON.stringify(r)]);

  async function onSave() {
    if (!check.success) return;
    if (!email) { setMsg({ ok: false, text: "Sign in to save rule changes." }); return; }
    setBusy(true);
    try {
      const res = await save({ data: r });
      if (res.ok) { base.current = JSON.stringify(r); applyRules(r); }
      setMsg(res.ok ? { ok: true, text: `Saved online ${new Date().toLocaleTimeString()}. Every visit to the game, advisor and editor now uses these rules.` } : { ok: false, text: res.error });
    } catch {
      setMsg({ ok: false, text: "Couldn't save the rules. Check the values and try again." });
    } finally { setBusy(false); }
  }

  const card = "rounded-lg border border-border bg-card p-4";
  return (
    <div data-testid="rules-editor">
      <p className="mb-4 rounded-md border border-border bg-card px-3 py-2 text-sm" data-testid="rules-auth">
        {email === undefined ? "Checking sign-in…" : email
          ? <>Signed in as {email} — your saves are kept online. <button className="text-primary underline" onClick={() => void supabase.auth.signOut()}>Sign out</button></>
          : <>Viewing the saved rules. <Link to="/auth" className="text-primary underline">Sign in</Link> to change them.</>}
      </p>
      <div className="grid gap-4 md:grid-cols-2">
        <section className={card}>
          <h2 className="mb-3 text-lg font-semibold">Roster &amp; season</h2>
          <div className="space-y-2">
            {num("MAX_ROSTER", "Roster limit")}
            {num("TRANSFER_DEADLINE_WEEK", "Transfer deadline (week)")}
            {num("SEASON_WEEKS", "Games per season")}
          </div>
          <h2 className="mb-3 mt-6 text-lg font-semibold">Recruiting</h2>
          <div className="space-y-2">
            {num("PROSPECT_WEEKLY_HOUR_CAP", "Max hours per prospect per week")}
            {num("OFFER_HOUR_COST", "Hours per scholarship offer")}
            {num("SCHOLARSHIP_OFFERS_PER_SEASON", "Offers per season")}
          </div>
        </section>

        <section className={card}>
          <h2 className="mb-1 text-lg font-semibold">Prestige</h2>
          <p className="mb-3 text-xs text-muted-foreground">Win totals that move each school grade one step after a season.</p>
          <table className="w-full text-sm">
            <thead className="text-muted-foreground"><tr><th className="text-left">Grade</th><th>Up at ≥ wins</th><th>Down at ≤ wins</th></tr></thead>
            <tbody>
              {(Object.keys(r.GRADE_SEASON_CHANGES) as (keyof Editable["GRADE_SEASON_CHANGES"])[]).flatMap((g) => [
                <tr key={g}>
                  <td className="py-1 capitalize">{g.replace(/_/g, " ")}</td>
                  {(["up_wins", "down_wins"] as const).map((k) => (
                    <td key={k} className="text-center">
                      <input type="number" aria-label={`${g} ${k}`} className={input} value={Number.isNaN(r.GRADE_SEASON_CHANGES[g][k]) ? "" : r.GRADE_SEASON_CHANGES[g][k]}
                        onChange={(e) => set("GRADE_SEASON_CHANGES", { ...r.GRADE_SEASON_CHANGES, [g]: { ...r.GRADE_SEASON_CHANGES[g], [k]: e.target.valueAsNumber } })} />
                    </td>
                  ))}
                </tr>,
                <tr key={`${g}-d`}><td colSpan={3} className="pb-2"><Desc label={g.replace(/_/g, " ")} value={d(g)} onChange={setD(g)} /></td></tr>,
              ])}
            </tbody>
          </table>
        </section>

        <section className={`${card} md:col-span-2`}>
          <h2 className="mb-3 text-lg font-semibold">Recruiting hours by prestige</h2>
          <table className="w-full text-sm">
            <thead className="text-muted-foreground"><tr><th className="text-left">Prestige</th>{LEVELS.map((l) => <th key={l}>{l}★</th>)}</tr></thead>
            <tbody>
              {(["WEEKLY_HOURS", "PRESEASON_HOURS"] as const).map((k) => (
                <tr key={k}>
                  <td className="py-1">{k === "WEEKLY_HOURS" ? "Weekly" : "Preseason"}</td>
                  {LEVELS.map((l) => (
                    <td key={l} className="px-0.5">
                      <input type="number" aria-label={`${k === "WEEKLY_HOURS" ? "Weekly" : "Preseason"} hours at ${l} stars`} className={`${input} w-full`}
                        value={Number.isNaN(r[k][l]) ? "" : r[k][l]} onChange={(e) => set(k, { ...r[k], [l]: e.target.valueAsNumber })} />
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
          <div className="mt-2 grid gap-2 md:grid-cols-2">
            <Desc label="Weekly hours" value={d("WEEKLY_HOURS")} onChange={setD("WEEKLY_HOURS")} />
            <Desc label="Preseason hours" value={d("PRESEASON_HOURS")} onChange={setD("PRESEASON_HOURS")} />
          </div>
        </section>

        <RulesPreview draft={r} saved={pick()} />
      </div>

      <div className="mt-6 flex flex-wrap items-center gap-4">
        <button className="rounded-md bg-primary px-4 py-2 font-semibold text-primary-foreground hover:bg-primary/90 disabled:opacity-40"
          disabled={!check.success || !dirty || busy} onClick={onSave}>{busy ? "Saving…" : auto ? "Save now" : "Save rules"}</button>
        <label className="flex items-center gap-2 text-sm">
          <input type="checkbox" checked={auto} onChange={(e) => setAuto(e.target.checked)} /> Save changes automatically
        </label>
        <button className="rounded-md border border-border px-4 py-2 text-sm hover:bg-accent disabled:opacity-40" disabled={!dirty} onClick={() => { setR(pick()); setMsg(null); }}>Undo changes</button>
        {msg && <p role="status" className={`text-sm ${msg.ok ? "text-primary" : "text-destructive"}`}>{msg.text}</p>}
      </div>
      {!check.success && (
        <ul role="alert" className="mt-3 list-disc pl-5 text-sm text-destructive">
          {[...new Set(check.error.issues.map((i) => (i.code === "custom" ? i.message : "Every number box needs a whole number in a sensible range; descriptions can be up to 300 characters.")))].map((m) => <li key={m}>{m}</li>)}
        </ul>
      )}
      <p className="mt-6 text-xs text-muted-foreground">
        Some tests check specific numbers (for example the 85-player limit). After a change, those tests will fail until they're updated to the new value — that's them doing their job.
      </p>
    </div>
  );
}
