import { useState } from "react";
import * as G from "@/lib/dynasty/engine";

type Row = { label: string; value: string; limit: string; ok: boolean | null; note?: string };
type Season = { label: string; wins: number; games: number; prestige: number; roster: number };

function seasonsOf(s: G.GameState): Season[] {
  const out: Season[] = s.history.map((h) => {
    const a = s.auditLog.find((e) => e.season_id === h.season);
    return { label: `Season ${h.season}`, wins: h.wins, games: h.games_played, prestige: a?.prestige_before ?? s.prestige, roster: s.players.length };
  });
  out.push({ label: `Season ${s.season} (current)`, wins: s.wins, games: s.gamesPlayed, prestige: s.prestige, roster: s.players.length });
  return out.reverse();
}

/** Compare a season from a dynasty save (or numbers typed in from a real save) against the rules. */
export function SaveViewer({ state }: { state: G.GameState }) {
  const [uploaded, setUploaded] = useState<G.GameState | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const save = uploaded ?? state;
  const seasons = seasonsOf(save);
  const [idx, setIdx] = useState(0);
  const [manual, setManual] = useState<Season | null>(null);
  const picked = manual ?? seasons[Math.min(idx, seasons.length - 1)]!;
  const R = G.RULES as any;

  const rows: Row[] = [
    { label: "Games played", value: String(picked.games), limit: `${R.SEASON_WEEKS} per season`, ok: picked.games <= R.SEASON_WEEKS },
    { label: "Roster size", value: String(picked.roster), limit: `max ${R.MAX_ROSTER}`, ok: picked.roster <= R.MAX_ROSTER, note: `${Math.max(0, R.MAX_ROSTER - picked.roster)} open spots` },
    { label: "Prestige", value: `${picked.prestige}★`, limit: `${R.MIN_PRESTIGE}★–${R.MAX_PRESTIGE}★`, ok: picked.prestige >= R.MIN_PRESTIGE && picked.prestige <= R.MAX_PRESTIGE },
    { label: "Weekly hours", value: String(G.weeklyHours(picked.prestige)), limit: `table at ${picked.prestige}★`, ok: null },
    { label: "Preseason hours", value: String(G.preseasonHours(picked.prestige)), limit: `table at ${picked.prestige}★`, ok: null },
    { label: "Hours per prospect", value: "—", limit: `max ${R.PROSPECT_WEEKLY_HOUR_CAP}/week`, ok: null },
    { label: "Offers", value: "—", limit: `${R.SCHOLARSHIP_OFFERS_PER_SEASON} per season, ${R.OFFER_HOUR_COST}h each`, ok: null },
  ];
  const grades = Object.entries(R.GRADE_SEASON_CHANGES as Record<string, { up_wins: number; down_wins: number }>);
  const next = G.prestigeFromGrades(G.seasonGrades(G.uniformGrades(picked.prestige), picked.wins));
  const nice = (k: string) => k.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
  const input = "w-20 rounded-md border border-input bg-background px-2 py-0.5 text-right font-mono";

  async function onFile(f: File) {
    try {
      const j = JSON.parse(await f.text());
      if (!Array.isArray(j.players) || !Array.isArray(j.history)) throw new Error();
      setUploaded({ auditLog: [], ...j }); setIdx(0); setManual(null); setErr(null);
    } catch { setErr("That file isn't a Play dynasty save."); }
  }
  function download() {
    const url = URL.createObjectURL(new Blob([JSON.stringify(state, null, 2)], { type: "application/json" }));
    const a = document.createElement("a"); a.href = url; a.download = "dynasty-save.json"; a.click(); URL.revokeObjectURL(url);
  }

  return (
    <div className="space-y-4" data-testid="save-viewer">
      <div className="flex flex-wrap items-center gap-3 text-sm">
        <label className="flex items-center gap-2">Season
          <select aria-label="Season" value={manual ? "manual" : idx} className="rounded-md border border-input bg-background px-2 py-1"
            onChange={(e) => { if (e.target.value === "manual") setManual({ ...picked, label: "Typed in" }); else { setManual(null); setIdx(Number(e.target.value)); } }}>
            {seasons.map((s, i) => <option key={s.label} value={i}>{s.label}</option>)}
            <option value="manual">Type in numbers from a real save…</option>
          </select>
        </label>
        <label className="cursor-pointer text-primary underline">Open save file
          <input type="file" accept="application/json" className="hidden" onChange={(e) => e.target.files?.[0] && void onFile(e.target.files[0])} />
        </label>
        {uploaded && <button className="text-primary underline" onClick={() => { setUploaded(null); setIdx(0); }}>Back to my save</button>}
        <button className="text-primary underline" onClick={download}>Download my save</button>
      </div>
      {err && <p className="text-sm text-destructive">{err}</p>}
      {manual && (
        <div className="flex flex-wrap gap-4 text-sm">
          {(["wins", "games", "roster"] as const).map((k) => (
            <label key={k} className="flex items-center gap-2">{nice(k)}
              <input type="number" aria-label={`Typed ${k}`} className={input} value={manual[k]} onChange={(e) => setManual({ ...manual, [k]: e.target.valueAsNumber || 0 })} />
            </label>
          ))}
          <label className="flex items-center gap-2">Prestige
            <select aria-label="Typed prestige" className="rounded-md border border-input bg-background px-2 py-1" value={manual.prestige}
              onChange={(e) => setManual({ ...manual, prestige: Number(e.target.value) })}>
              {Object.keys(R.WEEKLY_HOURS).map((l) => <option key={l} value={Number(l)}>{l}★</option>)}
            </select>
          </label>
        </div>
      )}

      <div className="grid gap-4 md:grid-cols-2">
        <table className="w-full text-sm" data-testid="save-limits">
          <thead className="text-xs text-muted-foreground"><tr><th className="text-left">Rule</th><th className="text-right">This season</th><th className="text-right">Rule</th><th /></tr></thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.label} className="border-t border-border">
                <td className="py-1">{r.label}{r.note && <span className="block text-xs text-muted-foreground">{r.note}</span>}</td>
                <td className="text-right font-mono">{r.value}</td>
                <td className="text-right text-muted-foreground">{r.limit}</td>
                <td className="pl-2 text-right">{r.ok === null ? "" : r.ok ? <span className="text-primary">✓</span> : <span className="text-destructive">✗ over</span>}</td>
              </tr>
            ))}
          </tbody>
        </table>
        <div>
          <table className="w-full text-sm" data-testid="save-grades">
            <thead className="text-xs text-muted-foreground"><tr><th className="text-left">Grade</th><th className="text-right">Up at</th><th className="text-right">Down at</th><th className="text-right">{picked.wins} wins →</th></tr></thead>
            <tbody>
              {grades.map(([g, t]) => {
                const res = picked.wins >= t.up_wins ? "up" : picked.wins <= t.down_wins ? "down" : "same";
                return (
                  <tr key={g} className="border-t border-border">
                    <td className="py-1">{nice(g)}</td>
                    <td className="text-right font-mono">{t.up_wins}</td>
                    <td className="text-right font-mono">{t.down_wins}</td>
                    <td className={`text-right ${res === "up" ? "text-primary" : res === "down" ? "text-destructive" : "text-muted-foreground"}`}>{res === "up" ? "▲ up" : res === "down" ? "▼ down" : "no change"}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
          <p className="mt-2 text-sm" data-testid="save-next">
            With {picked.wins} wins, prestige goes {picked.prestige}★ → <strong>{next}★</strong>, giving {G.weeklyHours(next)} weekly hours next season.
          </p>
        </div>
      </div>
      <p className="text-xs text-muted-foreground">Hours per prospect and offers aren't recorded in saves, so only their limits are shown.</p>
    </div>
  );
}
