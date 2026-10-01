import { createFileRoute, Link } from "@tanstack/react-router";
import { useEffect, useMemo, useState } from "react";
import { RULES, RULES_EVENT, type GameState } from "@/lib/dynasty/engine";
import { runRuleChecks } from "@/lib/dynasty/rule-checks";

export const Route = createFileRoute("/rule-tests")({
  head: () => ({
    meta: [
      { title: "Rules Test Suite — NCAA Dynasty" },
      { name: "description", content: "Run every dynasty rule against a real season and see which rules fail." },
      { property: "og:title", content: "Rules Test Suite — NCAA Dynasty" },
      { property: "og:description", content: "Every roster, season, prestige and recruiting rule checked against a played season." },
      { property: "og:type", content: "website" },
      { name: "twitter:card", content: "summary" },
    ],
  }),
  component: RuleTests,
});

function RuleTests() {
  const [save, setSave] = useState<GameState | null>(null);
  const [loaded, setLoaded] = useState(false);
  const [wins, setWins] = useState(9);
  const [tick, setTick] = useState(0);
  const [onlyFails, setOnlyFails] = useState(false);

  useEffect(() => {
    try { const raw = localStorage.getItem("ncaa-dynasty-game-v1"); if (raw) setSave(JSON.parse(raw)); } catch { /* ignore */ }
    setLoaded(true);
    const on = () => setTick((t) => t + 1);
    window.addEventListener(RULES_EVENT, on);
    return () => window.removeEventListener(RULES_EVENT, on);
  }, []);

  const checks = useMemo(() => (loaded ? runRuleChecks(save, wins) : []), [loaded, save, wins, tick]);
  const failed = checks.filter((c) => !c.pass);
  const shown = onlyFails ? failed : [...failed, ...checks.filter((c) => c.pass)];

  return (
    <main className="mx-auto max-w-5xl px-4 py-8" data-loaded={loaded}>
      <header className="mb-6 flex flex-wrap items-baseline justify-between gap-4">
        <div>
          <p className="font-mono text-xs uppercase tracking-[0.25em] text-primary">NCAA Dynasty · Rules</p>
          <h1 className="text-3xl font-bold">Rules test suite</h1>
          <p className="text-sm text-muted-foreground">
            Plays one full season with {save ? "your saved Play dynasty roster" : "a new team (no saved game found)"} and checks every rule.
          </p>
        </div>
        <nav className="flex gap-4 text-sm text-primary">
          <Link to="/rules" className="hover:underline">Rules editor</Link>
          <Link to="/rules-doc" className="hover:underline">Rules document</Link>
          <Link to="/game" className="hover:underline">Play dynasty</Link>
          <Link to="/dashboard" className="hover:underline">QA dashboard</Link>
        </nav>
      </header>

      <section className="mb-6 flex flex-wrap items-center gap-4 rounded-lg border bg-card p-4">
        <label className="text-sm">Season wins
          <input type="number" min={0} max={RULES.SEASON_WEEKS} value={wins} onChange={(e) => setWins(Number(e.target.value) || 0)}
            className="ml-2 w-16 rounded border bg-background px-2 py-1" />
          <span className="ml-1 text-muted-foreground">of {RULES.SEASON_WEEKS}</span>
        </label>
        <button onClick={() => setTick((t) => t + 1)} className="rounded bg-primary px-3 py-1.5 text-sm text-primary-foreground">Run again</button>
        <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={onlyFails} onChange={(e) => setOnlyFails(e.target.checked)} />Show failures only</label>
        <p className="ml-auto text-sm font-semibold" data-testid="rule-summary">
          {checks.length - failed.length} / {checks.length} rules pass
          {failed.length > 0 && <span className="ml-2 text-destructive">· {failed.length} failing</span>}
        </p>
      </section>

      <table className="w-full text-sm" data-testid="rule-checks">
        <thead className="text-left text-muted-foreground">
          <tr><th className="py-2">Result</th><th>Area</th><th>Rule</th><th>Expected</th><th>Got</th></tr>
        </thead>
        <tbody>
          {shown.map((c) => (
            <tr key={c.id} className="border-t align-top" data-status={c.pass ? "pass" : "fail"} data-check={JSON.stringify({ ...c, wins })}>
              <td className={`py-2 font-semibold ${c.pass ? "text-primary" : "text-destructive"}`}>{c.pass ? "Pass" : "FAIL"}</td>
              <td className="pr-2 text-muted-foreground">{c.group}</td>
              <td className="pr-2">{c.rule}{!c.pass && <div className="text-xs text-destructive">How to fix: {c.fix} <Link to="/rules" className="underline">Open Rules editor</Link></div>}</td>
              <td className="pr-2 font-mono">{c.expected}</td>
              <td className="font-mono">{c.actual}</td>
            </tr>
          ))}
          {shown.length === 0 && <tr><td colSpan={5} className="py-6 text-center text-muted-foreground">No failing rules.</td></tr>}
        </tbody>
      </table>
    </main>
  );
}
