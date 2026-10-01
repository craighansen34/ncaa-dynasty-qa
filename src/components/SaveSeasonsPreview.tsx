import { useEffect, useState } from "react";
import R from "../../ncaa-dynasty-qa/rules.json";
import type { Editable } from "@/lib/rules.functions";
import type { GameState } from "@/lib/dynasty/engine";
import { supabase } from "@/integrations/supabase/client";
import { hasBackendConfig } from "@/lib/rules-online";

// Replays real season results (Play dynasty save, save file, or seasons stored online) through the draft formula.
const SAVE_KEY = "ncaa-dynasty-game-v1";
const GRADE_MAX = R.GRADE_SCALE.length - 1;

type Season = { season: number; wins: number; losses: number; roster?: number | null; before?: number | null; after?: number | null };

function prestigeOf(g: Record<string, number>) {
  const v = Object.values(g), n = v.length, t = v.reduce((a, b) => a + b, 0);
  return Math.max(R.MIN_PRESTIGE, Math.min(R.MAX_PRESTIGE, Math.floor((2 * t + n) / (2 * n)) / 2));
}
function step(r: Editable, g: Record<string, number>, wins: number) {
  const out = { ...g }; let up = 0, down = 0;
  for (const [k, t] of Object.entries(r.GRADE_SEASON_CHANGES)) {
    if (wins >= t.up_wins) { if ((out[k] ?? 0) < GRADE_MAX) up++; out[k] = Math.min(GRADE_MAX, (out[k] ?? 0) + 1); }
    else if (wins <= t.down_wins) { if ((out[k] ?? 0) > 0) down++; out[k] = Math.max(0, (out[k] ?? 0) - 1); }
  }
  return { g: out, up, down };
}
function fromSave(s: GameState): Season[] {
  return s.history.map((h) => {
    const a = s.auditLog?.find((x) => x.season_id === h.season);
    return { season: h.season, wins: h.wins, losses: h.losses, roster: a ? a.transitions.length : null, before: a?.prestige_before ?? null, after: a?.prestige_after ?? null };
  });
}

export function SaveSeasonsPreview({ draft }: { draft: Editable }) {
  const [local, setLocal] = useState<Season[]>([]);
  const [localName, setLocalName] = useState("your Play dynasty save");
  const [stored, setStored] = useState<Season[]>([]);
  const [src, setSrc] = useState<"local" | "stored">("local");
  const [user, setUser] = useState<string | null>(null);
  const [msg, setMsg] = useState<string | null>(null);
  const [form, setForm] = useState({ season: "", wins: "", losses: "", roster: "", before: "", after: "" });

  async function loadStored() {
    const { data, error } = await supabase.from("dynasty_seasons").select("*").order("season");
    if (error) return setMsg("Couldn't load your stored seasons.");
    const rows = (data ?? []).map((d) => ({ season: d.season, wins: d.wins, losses: d.losses, roster: d.roster_size, before: d.prestige_before === null ? null : Number(d.prestige_before), after: d.prestige_after === null ? null : Number(d.prestige_after) }));
    setStored(rows);
    if (rows.length) setSrc("stored");
  }
  useEffect(() => {
    try { const raw = localStorage.getItem(SAVE_KEY); if (raw) setLocal(fromSave(JSON.parse(raw))); } catch { /* ignore */ }
    if (!hasBackendConfig()) return; // offline (e.g. CI): local save only
    supabase.auth.getUser().then(({ data }) => { setUser(data.user?.id ?? null); if (data.user) void loadStored(); });
  }, []);

  async function onFile(f: File) {
    try {
      const j = JSON.parse(await f.text());
      if (!Array.isArray(j.history)) throw new Error();
      setLocal(fromSave({ auditLog: [], ...j })); setLocalName(f.name); setSrc("local"); setMsg(null);
    } catch { setMsg("That file isn't a Play dynasty save."); }
  }
  async function upsert(rows: Season[]) {
    const { error } = await supabase.from("dynasty_seasons").upsert(
      rows.map((r) => ({ season: r.season, wins: r.wins, losses: r.losses, roster_size: r.roster ?? null, prestige_before: r.before ?? null, prestige_after: r.after ?? null, user_id: user! })),
      { onConflict: "user_id,dynasty,season" });
    if (error) return setMsg("Couldn't store those seasons.");
    setMsg(`Stored ${rows.length} season${rows.length === 1 ? "" : "s"}.`);
    await loadStored();
  }
  async function addManual(e: React.FormEvent) {
    e.preventDefault();
    const n = (v: string) => (v.trim() === "" ? null : Number(v));
    if (n(form.season) === null || n(form.wins) === null) return setMsg("Season and wins are needed.");
    await upsert([{ season: n(form.season)!, wins: n(form.wins)!, losses: n(form.losses) ?? 0, roster: n(form.roster), before: n(form.before), after: n(form.after) }]);
    setForm({ season: "", wins: "", losses: "", roster: "", before: "", after: "" });
  }
  async function remove(season: number) {
    await supabase.from("dynasty_seasons").delete().eq("season", season);
    await loadStored();
  }

  const seasons = src === "stored" ? stored : local;
  const from = src === "stored" ? "your stored seasons" : localName;
  const start = seasons[0]?.before ?? 3;
  let g: Record<string, number> = Object.fromEntries(R.SCHOOL_GRADES.map((k) => [k, Math.round(start * 2)]));
  let before = start;
  const rows = seasons.map((h) => {
    const s = step(draft, g, h.wins); g = s.g;
    const after = prestigeOf(g);
    const row = { ...h, calcBefore: before, calcAfter: after, up: s.up, down: s.down, hours: (draft.WEEKLY_HOURS as Record<string, number>)[String(after)] ?? 0 };
    before = after;
    return row;
  });
  const inp = "w-16 rounded border border-input bg-background px-1 py-0.5 text-sm";

  return (
    <section className="rounded-lg border border-border bg-card p-4 md:col-span-3" aria-labelledby="ss-h" data-testid="save-seasons">
      <div className="mb-3 flex flex-wrap items-baseline justify-between gap-2">
        <h2 id="ss-h" className="font-semibold">Your real seasons</h2>
        <div className="flex flex-wrap gap-3 text-sm">
          <button type="button" className={src === "local" ? "font-semibold" : "text-primary underline"} onClick={() => setSrc("local")}>This save ({local.length})</button>
          <button type="button" className={src === "stored" ? "font-semibold" : "text-primary underline"} onClick={() => setSrc("stored")} data-testid="src-stored">Stored online ({stored.length})</button>
          <label className="cursor-pointer text-primary underline">Open save file
            <input type="file" accept="application/json" className="hidden" onChange={(e) => e.target.files?.[0] && void onFile(e.target.files[0])} />
          </label>
        </div>
      </div>
      {msg && <p className="mb-2 text-sm text-muted-foreground" data-testid="ss-msg">{msg}</p>}
      {rows.length === 0 ? (
        <p className="text-sm text-muted-foreground" data-testid="save-seasons-empty">
          No seasons in {from} yet. Finish a season in Play dynasty, open a save file, or type in a real season below.
        </p>
      ) : (
        <>
          <p className="mb-2 text-sm text-muted-foreground">
            Win totals from {from}, played through the numbers above, starting at {start}★. "Saved" is the prestige your dynasty actually recorded.
          </p>
          <table className="w-full font-mono text-sm">
            <thead className="text-xs text-muted-foreground"><tr><th className="text-left">Season</th><th className="text-right">Record</th><th className="text-right">Roster</th><th className="text-right">Grades</th><th className="text-right">Prestige</th><th className="text-right">Saved</th><th className="text-right">Next hours</th>{src === "stored" && <th />}</tr></thead>
            <tbody>
              {rows.map((r) => (
                <tr key={r.season} className="border-t border-border" data-season={r.season}>
                  <td className="py-1">{r.season}</td>
                  <td className="text-right">{r.wins}–{r.losses}</td>
                  <td className={`text-right ${r.roster != null && r.roster > draft.MAX_ROSTER ? "font-semibold text-destructive" : ""}`}>{r.roster != null ? `${r.roster}/${draft.MAX_ROSTER}` : "—"}</td>
                  <td className="text-right">+{r.up} / −{r.down}</td>
                  <td className="text-right">{r.calcBefore}★ → <strong>{r.calcAfter}★</strong></td>
                  <td className={`text-right ${r.after != null && r.after !== r.calcAfter ? "font-semibold text-primary" : "text-muted-foreground"}`}>{r.after != null ? `${r.after}★` : "—"}</td>
                  <td className="text-right">{r.hours}</td>
                  {src === "stored" && <td className="text-right"><button type="button" className="text-xs text-destructive underline" onClick={() => void remove(r.season)}>Remove</button></td>}
                </tr>
              ))}
            </tbody>
          </table>
          {rows.some((r) => r.after != null) && (
            <p className="mt-2 text-sm" data-testid="ss-match">
              The formula matches {rows.filter((r) => r.after != null && r.after === r.calcAfter).length} of {rows.filter((r) => r.after != null).length} saved prestige values.
            </p>
          )}
        </>
      )}
      <div className="mt-4 border-t border-border pt-3">
        {!user ? (
          <p className="text-sm text-muted-foreground"><a href="/auth" className="text-primary underline">Sign in</a> to store your real seasons so this table uses them on every visit.</p>
        ) : (
          <div className="space-y-2">
            {src === "local" && local.length > 0 && (
              <button type="button" className="rounded bg-primary px-3 py-1 text-sm text-primary-foreground" onClick={() => void upsert(local)} data-testid="store-local">Store these {local.length} seasons online</button>
            )}
            <form onSubmit={addManual} className="flex flex-wrap items-end gap-2 text-xs" data-testid="ss-form">
              {([["season", "Season"], ["wins", "Wins"], ["losses", "Losses"], ["roster", "Roster"], ["before", "Prestige before"], ["after", "Prestige after"]] as const).map(([k, l]) => (
                <label key={k} className="flex flex-col">{l}
                  <input className={inp} inputMode="decimal" value={form[k]} onChange={(e) => setForm({ ...form, [k]: e.target.value })} aria-label={l} />
                </label>
              ))}
              <button type="submit" className="rounded border border-border px-3 py-1 text-sm">Add real season</button>
            </form>
          </div>
        )}
      </div>
    </section>
  );
}
