import { createFileRoute, Link } from "@tanstack/react-router";
import { useEffect, useState } from "react";
import * as G from "@/lib/dynasty/engine";
import { DynastyAdvisor } from "@/components/DynastyAdvisor";
import { RulesEditorPanel } from "@/components/RulesEditorPanel";
import { RulesDocContent } from "@/components/RulesDocContent";
import { SaveViewer } from "@/components/SaveViewer";
import { PrestigeFormulaPanel } from "@/components/PrestigeFormulaPanel";

export const Route = createFileRoute("/game")({
  head: () => ({
    meta: [
      { title: "Dynasty Mode — NCAA Dynasty" },
      { name: "description", content: "Manage your roster, injuries, season and program prestige using the NCAA Dynasty ruleset." },
      { property: "og:title", content: "Dynasty Mode — NCAA Dynasty" },
      { property: "og:description", content: "Run a college football dynasty: roster, injuries, seasons and prestige." },
      { property: "og:type", content: "website" },
      { name: "twitter:card", content: "summary" },
    ],
  }),
  component: Game,
});

const KEY = "ncaa-dynasty-game-v1";
const YEARS = ["", "FR", "SO", "JR", "SR"];
const btn = "rounded-md border border-border px-2 py-1 text-xs hover:bg-accent disabled:opacity-40";
const primary = "rounded-md bg-primary px-3 py-2 text-sm font-semibold text-primary-foreground hover:bg-primary/90 disabled:opacity-40";

function Stars({ value }: { value: number }) {
  return (
    <span className="font-mono text-primary" aria-label={`${value} stars`}>
      {Array.from({ length: 5 }, (_, i) => (value >= i + 1 ? "★" : value >= i + 0.5 ? "⯪" : "☆")).join("")}
    </span>
  );
}

function Game() {
  const [s, setS] = useState<G.GameState>(G.newGame);
  const [error, setError] = useState<string | null>(null);
  const [loaded, setLoaded] = useState(false);
  const [name, setName] = useState("");
  const [year, setYear] = useState(1);
  const [injury, setInjury] = useState<Record<string, string>>({});

  useEffect(() => {
    const raw = localStorage.getItem(KEY);
    if (raw) try { setS(JSON.parse(raw)); } catch { /* ignore */ }
    setLoaded(true);
  }, []);
  const [, setRulesVersion] = useState(0);
  useEffect(() => {
    const bump = () => setRulesVersion((n) => n + 1);
    window.addEventListener(G.RULES_EVENT, bump);
    return () => window.removeEventListener(G.RULES_EVENT, bump);
  }, []);
  useEffect(() => { if (loaded) localStorage.setItem(KEY, JSON.stringify(s)); }, [s, loaded]);

  const run = (r: G.Result) => { setS(r.state); setError(r.error ? G.ERRORS[r.error] ?? r.error : null); };
  const seasonDone = s.gamesPlayed >= G.RULES.SEASON_WEEKS;
  const injured = s.players.filter((p) => p.injuryWeeks > 0);
  const lastAudit = s.auditLog[s.auditLog.length - 1];

  return (
    <main data-loaded={loaded} className="min-h-screen bg-background font-sans text-foreground">
      <div className="mx-auto max-w-6xl px-5 py-10">
        <header className="mb-6 border-b border-border pb-6">
          <div className="flex flex-wrap justify-between gap-4">
            <p className="font-mono text-xs uppercase tracking-[0.25em] text-primary">NCAA Dynasty · Dynasty Mode</p>
            <nav className="flex gap-4 text-sm text-primary">
              <Link to="/dashboard" className="hover:underline">QA dashboard</Link>
              <Link to="/rules" className="hover:underline">Edit rules</Link>
              <Link to="/saves" className="hover:underline">Dynasty saves</Link>
              <Link to="/" className="hover:underline">Test advisor</Link>
            </nav>
          </div>
          <h1 className="mt-2 text-3xl font-bold tracking-tight sm:text-4xl">Season {s.season}</h1>
          <div className="mt-4 grid gap-3 sm:grid-cols-4">
            <Stat label="Record" testId="record" value={`${s.wins}–${s.losses}`} />
            <Stat label="Week" value={`${Math.min(s.gamesPlayed + 1, G.RULES.SEASON_WEEKS)} of ${G.RULES.SEASON_WEEKS}`} />
            <Stat label="Roster" testId="roster" value={`${s.players.length} / ${G.RULES.MAX_ROSTER}`} />
            <div className="rounded-lg border border-border bg-card p-3">
              <p className="text-xs text-muted-foreground">Program prestige</p>
              <p className="text-lg"><Stars value={s.prestige} /> <span data-testid="prestige" className="font-mono text-sm">{s.prestige}</span></p>
              <p className="text-xs text-muted-foreground"><span data-testid="hours">{G.weeklyHours(s.prestige)}</span> recruiting hrs/week</p>
            </div>
          </div>
        </header>

        {error && <p role="alert" className="mb-4 rounded-md border border-destructive bg-destructive/10 px-3 py-2 text-sm text-destructive">{error}</p>}

        <div className="grid gap-6 lg:grid-cols-3">
          <section className="lg:col-span-2">
            <h2 className="mb-3 text-xl font-semibold">Roster</h2>
            <form
              className="mb-3 flex flex-wrap gap-2"
              onSubmit={(e) => { e.preventDefault(); if (name.trim()) { run(G.addPlayer(s, name.trim(), year)); setName(""); } }}
            >
              <input value={name} onChange={(e) => setName(e.target.value)} placeholder="Player name" aria-label="Player name"
                className="min-w-40 flex-1 rounded-md border border-input bg-card px-3 py-2 text-sm" />
              <select value={year} onChange={(e) => setYear(Number(e.target.value))} aria-label="Class year"
                className="rounded-md border border-input bg-card px-2 text-sm">
                {[1, 2, 3, 4].map((y) => <option key={y} value={y}>{YEARS[y]}</option>)}
              </select>
              <button className={primary}>Sign player</button>
              <button type="button" className={btn} onClick={() => { if (name.trim()) { run(G.addPlayer(s, name.trim(), year, true)); setName(""); } }}>
                Add as transfer
              </button>
            </form>
            <div className="overflow-x-auto rounded-lg border border-border bg-card">
              <table className="w-full text-left text-sm">
                <thead className="text-muted-foreground">
                  <tr><th className="p-2">Player</th><th>Year</th><th>Status</th><th>Injury (wks)</th><th className="p-2">Actions</th></tr>
                </thead>
                <tbody>
                  {s.players.map((p) => {
                    const st = G.injuryStatus(p);
                    return (
                      <tr key={p.name} className="border-t border-border">
                        <td className="p-2 font-medium">
                          {p.name}
                          {p.starter && <span className="ml-2 rounded bg-primary px-1.5 text-xs text-primary-foreground">Starter</span>}
                          {p.redshirted && <span className="ml-2 rounded border border-border px-1.5 text-xs">Redshirt</span>}
                        </td>
                        <td className="font-mono">{YEARS[p.year]}</td>
                        <td className={st === "healthy" ? "text-muted-foreground" : "text-destructive"}>
                          {st}{p.injuryWeeks > 0 && ` (${p.injuryWeeks})`}
                        </td>
                        <td>
                          <form className="flex gap-1" onSubmit={(e) => {
                            e.preventDefault();
                            const w = Number(injury[p.name]);
                            if (injury[p.name] !== undefined && injury[p.name] !== "" && !Number.isNaN(w)) run(G.setInjury(s, p.name, w));
                          }}>
                            <input type="number" aria-label={`Injury weeks for ${p.name}`} value={injury[p.name] ?? ""}
                              onChange={(e) => setInjury({ ...injury, [p.name]: e.target.value })}
                              className="w-14 rounded border border-input bg-background px-1 text-xs" />
                            <button className={btn}>Set</button>
                          </form>
                        </td>
                        <td className="p-2">
                          <div className="flex flex-wrap gap-1">
                            {p.starter
                              ? <button className={btn} onClick={() => run(G.demote(s, p.name))}>Bench</button>
                              : <button className={btn} onClick={() => run(G.promote(s, p.name))}>Start</button>}
                            <button className={btn} onClick={() => run(G.redshirt(s, p.name))}>{p.redshirted ? "Undo redshirt" : "Redshirt"}</button>
                            <button className={btn} onClick={() => run(G.cut(s, p.name))}>Cut</button>
                          </div>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </section>

          <aside className="space-y-6">
            <DynastyAdvisor state={s} />
            <section className="rounded-lg border border-border bg-card p-4">
              <h2 className="mb-3 text-lg font-semibold">This week</h2>
              <div className="flex gap-2">
                <button className={primary} disabled={seasonDone} onClick={() => run(G.playWeek(s, true))}>Win</button>
                <button className={primary} disabled={seasonDone} onClick={() => run(G.playWeek(s, false))}>Loss</button>
              </div>
              <p className="mt-2 text-xs text-muted-foreground">
                Each game heals injuries by one week. Transfers close after week {G.RULES.TRANSFER_DEADLINE_WEEK}.
              </p>
              <button className={`${primary} mt-4 w-full`} onClick={() => run(G.rollover(s))}>
                End season {s.season} &amp; roll over
              </button>
              <p className="mt-2 text-xs text-muted-foreground">
                Prestige is the average of your school report card. Seniors graduate, redshirts hold their year, injuries heal.
              </p>
              <details className="mt-3 text-sm" data-testid="report-card">
                <summary className="cursor-pointer text-xs text-muted-foreground">School report card</summary>
                <ul className="mt-2 grid grid-cols-2 gap-x-4 font-mono text-xs">
                  {Object.entries(G.gradesOf(s)).map(([g, i]) => {
                    const t = (G.RULES.GRADE_SEASON_CHANGES as Record<string, { up_wins: number; down_wins: number }>)[g];
                    return (
                      <li key={g} className="flex justify-between" title={t ? `Up a step at ${t.up_wins}+ wins, down at ${t.down_wins} or fewer` : "Doesn't change with results"}>
                        <span>{g.replace(/_/g, " ")}{t ? " *" : ""}</span><span data-testid={`grade-${g}`}>{G.gradeLetter(i)}</span>
                      </li>
                    );
                  })}
                </ul>
                <p className="mt-1 text-xs text-muted-foreground">* moves one step per season with your record; the rest stay fixed.</p>
              </details>
            </section>

            <section className="rounded-lg border border-border bg-card p-4">
              <h2 className="mb-2 text-lg font-semibold">Injury report</h2>
              {injured.length === 0 ? <p className="text-sm text-muted-foreground">Everyone is healthy.</p> : (
                <ul className="text-sm">
                  {injured.map((p) => <li key={p.name} className="flex justify-between"><span>{p.name}</span><span className="text-destructive">{p.injuryWeeks} wk</span></li>)}
                </ul>
              )}
            </section>

            <section className="rounded-lg border border-border bg-card p-4">
              <h2 className="mb-2 text-lg font-semibold">Season history</h2>
              {s.auditLog.length === 0 ? <p className="text-sm text-muted-foreground">No completed seasons yet.</p> : (
                <ul className="space-y-1 text-sm">
                  {[...s.auditLog].reverse().map((e) => (
                    <li key={e.season_id} className="flex justify-between">
                      <span>Season {e.season_id}: {e.archived_record.wins}–{e.archived_record.losses}</span>
                      <span className="font-mono text-xs text-muted-foreground">{e.prestige_before}★ → {e.prestige_after}★</span>
                    </li>
                  ))}
                </ul>
              )}
              {lastAudit && (
                <details className="mt-3 text-xs">
                  <summary className="cursor-pointer text-muted-foreground">Last rollover changes</summary>
                  <ul className="mt-2 space-y-0.5">
                    {lastAudit.transitions.map((t) => (
                      <li key={t.player}>{t.player}: {t.action === "graduated" ? "graduated" : t.action === "redshirt_hold" ? `held at ${YEARS[t.from_year]}` : `${YEARS[t.from_year]} → ${YEARS[t.to_year ?? 0]}`}</li>
                    ))}
                  </ul>
                </details>
              )}
            </section>

            <button className={`${btn} w-full`} onClick={() => { if (confirm("Start a new dynasty? This clears your progress.")) run({ state: G.newGame() }); }}>
              Start a new dynasty
            </button>
          </aside>
        </div>

        <details className="mt-8 rounded-lg border border-border bg-card/40 p-4" aria-label="Save viewer" data-testid="game-save-viewer">
          <summary className="cursor-pointer text-lg font-semibold">Save viewer</summary>
          <p className="mb-4 mt-1 text-sm text-muted-foreground">
            Pick a season from your save, open a save file, or type in numbers from a real dynasty save, and compare its wins, hours and roster with the rules.
          </p>
          <SaveViewer state={s} />
        </details>

        <details className="mt-8 rounded-lg border border-border bg-card/40 p-4" aria-label="Prestige formula" data-testid="game-prestige">
          <summary className="cursor-pointer text-lg font-semibold">Prestige formula</summary>
          <p className="mb-4 mt-1 text-sm text-muted-foreground">
            Tweak the prestige, hours and roster numbers and watch the results change as you type. Sign in and save to keep them.
          </p>
          <PrestigeFormulaPanel />
        </details>

        <details className="mt-8 rounded-lg border border-border bg-card/40 p-4" aria-label="Rules document" data-testid="game-rules-doc">
          <summary className="cursor-pointer text-lg font-semibold">Rules document</summary>
          <p className="mb-4 mt-1 text-sm text-muted-foreground">
            Every rule the game is using right now — prestige, recruiting hours and roster limits — with its threshold and description.
          </p>
          <RulesDocContent />
        </details>

        <details className="mt-8 rounded-lg border border-border bg-card/40 p-4" aria-label="Live rules editor">
          <summary className="cursor-pointer text-lg font-semibold">Live rules editor</summary>
          <p className="mb-4 mt-1 text-sm text-muted-foreground">
            Changes save on their own a moment after you stop typing. This page and the staff advisor switch to them straight away, and the test suite uses them on its next run.
          </p>
          <RulesEditorPanel live />
        </details>
      </div>
    </main>
  );
}

function Stat({ label, value, testId }: { label: string; value: string; testId?: string }) {
  return (
    <div className="rounded-lg border border-border bg-card p-3">
      <p className="text-xs text-muted-foreground">{label}</p>
      <p data-testid={testId} className="font-mono text-lg">{value}</p>
    </div>
  );
}
