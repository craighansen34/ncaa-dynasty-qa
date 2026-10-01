import { useEffect, useRef, useState } from "react";
import { getLiveRulesDraft, gradesOf, type GameState } from "@/lib/dynasty/engine";

const STANDINGS_KEY = "ncaa-dynasty-standings-v2";
const TEAM_KEY = "ncaa-dynasty-team";
type Row = { team: string; wins: number; losses: number };

export function DynastyAdvisor({ state }: { state: GameState }) {
  const [standings, setStandings] = useState<Row[]>([]);
  const [team, setTeam] = useState("Your team");
  const [newTeam, setNewTeam] = useState("");
  const [question, setQuestion] = useState("");
  const [answer, setAnswer] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const abort = useRef<AbortController | null>(null);
  useEffect(() => {
    try { setStandings(JSON.parse(localStorage.getItem(STANDINGS_KEY) ?? "[]")); } catch { /* ignore */ }
    setTeam(localStorage.getItem(TEAM_KEY) || "Your team");
  }, []);
  const saveRows = (rows: Row[]) => { setStandings(rows); localStorage.setItem(STANDINGS_KEY, JSON.stringify(rows)); };
  const setRow = (i: number, k: "wins" | "losses", v: number) =>
    saveRows(standings.map((r, j) => (j === i ? { ...r, [k]: Math.max(0, Math.min(20, v || 0)) } : r)));

  async function ask() {
    localStorage.setItem(TEAM_KEY, team);
    const ctrl = new AbortController();
    abort.current = ctrl;
    setAnswer(""); setError(""); setBusy(true);
    try {
      const res = await fetch("/api/dynasty-advisor", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          season: state.season, week: state.week, wins: state.wins, losses: state.losses,
          prestige: state.prestige, players: state.players, team: team.trim() || "Your team", standings, question,
          grades: gradesOf(state), history: state.history, rules: getLiveRulesDraft() ?? undefined,
        }),
        signal: ctrl.signal,
      });
      if (!res.ok || !res.body) {
        const j = await res.json().catch(() => null);
        throw new Error(j?.error ?? `Request failed (${res.status}).`);
      }
      const reader = res.body.getReader();
      const dec = new TextDecoder();
      let buf = "", got = false;
      for (;;) {
        const { value, done } = await reader.read();
        if (done) break;
        buf += dec.decode(value, { stream: true });
        const lines = buf.split("\n");
        buf = lines.pop() ?? "";
        for (const line of lines) {
          if (!line.startsWith("data: ")) continue;
          let ev: { type: string; delta?: string; errorText?: string };
          try { ev = JSON.parse(line.slice(6)); } catch { continue; }
          if (ev.type === "text-delta" && ev.delta) { got = true; setAnswer((a) => a + ev.delta); }
          else if (ev.type === "error") throw new Error(ev.errorText || "The AI request failed.");
        }
      }
      if (!got) throw new Error("The advisor returned nothing. Try again.");
    } catch (e) {
      if ((e as Error).name !== "AbortError") setError((e as Error).message);
    } finally {
      setBusy(false); abort.current = null;
    }
  }

  return (
    <section className="rounded-lg border border-border bg-card p-4">
      <h2 className="mb-1 text-lg font-semibold">Staff advisor</h2>
      <p className="mb-3 text-xs text-muted-foreground">Suggests signees, injury rotations and lineup moves from your roster, prestige and SEC standings.</p>
      <p className="mb-1 text-xs text-muted-foreground">Uses your live roster, injuries, record, report card and past seasons. The game doesn't play other SEC teams, so add their records below.</p>
      <table className="mb-2 w-full text-xs" data-testid="standings">
        <thead className="text-muted-foreground"><tr><th className="text-left">SEC team</th><th>W</th><th>L</th><th /></tr></thead>
        <tbody>
          <tr className="font-semibold">
            <td><input aria-label="Your team name" value={team} onChange={(e) => setTeam(e.target.value)} className="w-full rounded border border-input bg-background px-1" /></td>
            <td className="text-center font-mono">{state.wins}</td><td className="text-center font-mono">{state.losses}</td><td className="text-[10px] text-muted-foreground">from game</td>
          </tr>
          {standings.map((r, i) => (
            <tr key={r.team}>
              <td>{r.team}</td>
              {(["wins", "losses"] as const).map((k) => (
                <td key={k} className="text-center"><input type="number" min={0} aria-label={`${r.team} ${k}`} value={r[k]} onChange={(e) => setRow(i, k, e.target.valueAsNumber)} className="w-10 rounded border border-input bg-background px-1 text-right font-mono" /></td>
              ))}
              <td><button aria-label={`Remove ${r.team}`} onClick={() => saveRows(standings.filter((_, j) => j !== i))} className="px-1 text-muted-foreground hover:text-destructive">×</button></td>
            </tr>
          ))}
        </tbody>
      </table>
      <form className="mb-2 flex gap-1" onSubmit={(e) => { e.preventDefault(); const t = newTeam.trim(); if (t && !standings.some((r) => r.team === t) && standings.length < 15) { saveRows([...standings, { team: t, wins: 0, losses: 0 }]); setNewTeam(""); } }}>
        <input value={newTeam} onChange={(e) => setNewTeam(e.target.value)} placeholder="Add SEC team (e.g. Georgia)" aria-label="Add SEC team" maxLength={40}
          className="flex-1 rounded-md border border-input bg-background px-2 py-1 text-xs" />
        <button className="rounded-md border border-border px-2 text-xs hover:bg-accent">Add</button>
      </form>
      <input value={question} onChange={(e) => setQuestion(e.target.value)} placeholder="Ask something (optional)" aria-label="Question for the advisor"
        className="mb-2 w-full rounded-md border border-input bg-background px-2 py-1 text-sm" />
      <div className="flex gap-2">
        <button onClick={ask} disabled={busy}
          className="flex-1 rounded-md bg-primary px-3 py-2 text-sm font-semibold text-primary-foreground hover:bg-primary/90 disabled:opacity-40">
          {busy ? "Thinking…" : "Get advice"}
        </button>
        {busy && <button onClick={() => abort.current?.abort()} className="rounded-md border border-border px-2 text-xs hover:bg-accent">Stop</button>}
      </div>
      {error && <p role="alert" className="mt-2 text-sm text-destructive">{error}</p>}
      {answer && <div data-testid="advisor-answer" className="mt-3 whitespace-pre-wrap text-sm leading-relaxed">{answer.replace(/\*\*/g, "")}</div>}
    </section>
  );
}
