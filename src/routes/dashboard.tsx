import { createFileRoute, Link } from "@tanstack/react-router";
import { useEffect, useState, type ChangeEvent } from "react";
import { useServerFn } from "@tanstack/react-start";
import snapshot from "@/data/qa-snapshot.json";
import parityData from "@/data/game-parity.json";
import ruleChecksData from "@/data/rule-checks.json";

type ParityCheck = { check: string; web: unknown; rules: unknown; ok: boolean };
type Parity = { generated_at: string; passed: number; total: number; checks: ParityCheck[] };
const localParity = parityData as Parity;
type RuleCheckRow = { id: string; group: string; rule: string; pass: boolean; expected: string; actual: string; fix: string; wins: number };
type RuleChecks = { generated_at: string; passed: number; total: number; checks: RuleCheckRow[] };
const localRuleChecks = ruleChecksData as RuleChecks;
import { listQaRuns, loadQaRun, type QaRun, type VersionResult } from "@/lib/github.functions";

const REPO_KEY = "qa-dashboard-github-repo";

function GitHubRuns({ onLoad }: { onLoad: (label: string, results: unknown, history: unknown, parity?: unknown, ruleChecks?: unknown) => void }) {
  const fetchRuns = useServerFn(listQaRuns);
  const fetchRun = useServerFn(loadQaRun);
  const [repo, setRepo] = useState("");
  const [runs, setRuns] = useState<QaRun[] | null>(null);
  const [versions, setVersions] = useState<{ run: QaRun; list: VersionResult[] } | null>(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  useEffect(() => { setRepo(localStorage.getItem(REPO_KEY) ?? ""); }, []);

  async function go<T>(f: () => Promise<T>) {
    setBusy(true); setErr(null);
    try { return await f(); } catch (e) { setErr((e as Error).message); return undefined; } finally { setBusy(false); }
  }
  const pick = (run: QaRun, v: VersionResult) =>
    onLoad(`GitHub run #${run.number} (${run.branch} @ ${run.commit}) · Python ${v.python}`, v.results, v.history, v.parity, v.ruleChecks);
  async function showRun(r: QaRun) {
    const list = await fetchRun({ data: { repo: repo.trim() || localStorage.getItem(REPO_KEY) || "", runId: r.id } });
    setVersions({ run: r, list });
    if (list[0]) pick(r, list[0]); else setErr("This run has no saved results (still running, or expired).");
  }
  // Auto-load: with a remembered repository, open the newest finished run on page load.
  useEffect(() => {
    const saved = localStorage.getItem(REPO_KEY);
    if (!saved) return;
    void go(async () => {
      const list = await fetchRuns({ data: { repo: saved } });
      setRuns(list);
      const latest = list.find((r) => r.status === "completed");
      if (latest) {
        const vs = await fetchRun({ data: { repo: saved, runId: latest.id } });
        setVersions({ run: latest, list: vs });
        if (vs[0]) pick(latest, vs[0]);
      }
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <div className="mt-4 rounded-lg border border-border bg-card p-4">
      <form className="flex flex-wrap items-center gap-2" onSubmit={(e) => {
        e.preventDefault();
        localStorage.setItem(REPO_KEY, repo.trim());
        void go(async () => { setVersions(null); setRuns(await fetchRuns({ data: { repo: repo.trim() } })); });
      }}>
        <label className="text-sm font-medium" htmlFor="gh-repo">GitHub Actions runs</label>
        <input id="gh-repo" value={repo} onChange={(e) => setRepo(e.target.value)} placeholder="owner/repo"
          className="min-w-48 flex-1 rounded-md border border-input bg-background px-3 py-1.5 font-mono text-sm" />
        <button disabled={busy || !repo.trim()} className="rounded-md bg-primary px-3 py-1.5 text-sm font-semibold text-primary-foreground hover:bg-primary/90 disabled:opacity-40">
          {busy ? "Loading…" : "Load from GitHub"}
        </button>
      </form>
      {err && <p className="mt-2 text-sm text-destructive">{err}</p>}
      {runs && runs.length === 0 && <p className="mt-2 text-sm text-muted-foreground">No QA workflow runs yet.</p>}
      {runs && runs.length > 0 && (
        <ul className="mt-3 divide-y divide-border text-sm">
          {runs.map((r) => (
            <li key={r.id} className="flex flex-wrap items-center justify-between gap-2 py-1.5">
              <span>
                <span className={r.conclusion === "success" ? "text-primary" : r.conclusion ? "text-destructive" : "text-muted-foreground"}>
                  {r.conclusion ?? r.status}
                </span>{" "}
                #{r.number} · {r.branch} · <span className="font-mono">{r.commit}</span> · {new Date(r.created_at).toLocaleString()}
              </span>
              <button disabled={busy} className="rounded-md border border-border px-2 py-1 text-xs hover:bg-accent disabled:opacity-40"
                onClick={() => void go(() => showRun(r))}>
                Show results
              </button>
            </li>
          ))}
        </ul>
      )}
      {versions && versions.list.length > 0 && (
        <div className="mt-3 flex flex-wrap gap-2 text-sm">
          <span className="text-muted-foreground">Run #{versions.run.number} by Python version:</span>
          {versions.list.map((v) => {
            const m = (v.results as { mutants?: { outcome: string }[] } | null)?.mutants ?? [];
            const k = m.filter((x) => x.outcome === "killed").length;
            return (
              <button key={v.python} onClick={() => pick(versions.run, v)}
                className={`rounded-md border px-2 py-1 font-mono text-xs hover:bg-accent ${m.length && k === m.length ? "border-primary" : "border-destructive"}`}
                title={v.validation ?? undefined}>
                {v.python}: {v.results ? `${k}/${m.length}` : "no results"}{v.parity ? ` · game ${v.parity.passed}/${v.parity.total}` : ""}{v.ruleChecks ? ` · rules ${v.ruleChecks.passed}/${v.ruleChecks.total}` : ""}
              </button>
            );
          })}
        </div>
      )}
    </div>
  );
}

export const Route = createFileRoute("/dashboard")({
  head: () => ({
    meta: [
      { title: "QA Dashboard — NCAA Dynasty QA" },
      {
        name: "description",
        content: "Mutation history, per-rule mutation scores and the season-rollover audit log for the NCAA Dynasty test suite.",
      },
      { property: "og:title", content: "QA Dashboard — NCAA Dynasty QA" },
      {
        property: "og:description",
        content: "See mutation scores, run history and season rollovers without opening GitHub Actions.",
      },
      { property: "og:type", content: "website" },
      { name: "twitter:card", content: "summary" },
    ],
  }),
  component: Dashboard,
});

type RuleScore = { killed: number; total: number; survivors: string[]; score: number };
type Mutant = {
  rule: string;
  name: string;
  effective: boolean;
  executed: boolean;
  mutated_lines: number[];
  executed_lines: number[];
  outcome: string;
};
type Results = {
  baseline_ok?: boolean;
  rules: Record<string, RuleScore>;
  mutants: Mutant[];
  reproduce?: { seed?: number; python?: string; command?: string };
};
type HistoryRun = { run_id: string; python?: string; rules: Record<string, Record<string, number>> };
type Transition = { player: string; from_year: number; to_year: number | null; action: string };
type AuditEntry = {
  season_id: number;
  archived_record: { wins: number; losses: number; games_played: number };
  completed_at: string;
  transitions: Transition[];
  prestige_before?: number;
  prestige_after?: number;
};

const GAME_KEY = "ncaa-dynasty-game-v1"; // Play dynasty's saved game (same browser)
const YEARS = ["", "FR", "SO", "JR", "SR"];
const OUTCOMES = ["killed", "survived", "unreached", "ineffective", "target_not_found"];

function badRegression(prev: Record<string, number> | undefined, cur: Record<string, number> | undefined) {
  if (!prev) return false;
  if (!cur) return true;
  if ((cur['killed'] ?? 0) < (prev['killed'] ?? 0)) return true;
  return OUTCOMES.slice(1).some((o) => (cur[o] ?? 0) > (prev[o] ?? 0));
}

function Dashboard() {
  const [results, setResults] = useState<Results | null>(snapshot.results as Results | null);
  const [history, setHistory] = useState<HistoryRun[]>(snapshot.history as HistoryRun[]);
  const [audit, setAudit] = useState<AuditEntry[]>(snapshot.audit_log as AuditEntry[]);
  const [gameAudit, setGameAudit] = useState<AuditEntry[] | null>(null);
  useEffect(() => {
    const read = () => {
      try {
        const log = JSON.parse(localStorage.getItem(GAME_KEY) ?? "null")?.auditLog as AuditEntry[] | undefined;
        setGameAudit(log && log.length ? [...log].reverse() : null);
      } catch { setGameAudit(null); }
    };
    read();
    const onStorage = (e: StorageEvent) => { if (e.key === GAME_KEY) read(); };
    window.addEventListener("storage", onStorage);
    return () => window.removeEventListener("storage", onStorage);
  }, []);
  const shownAudit = gameAudit ?? audit;
  const [source, setSource] = useState(`Latest local run, exported ${new Date(snapshot.generated_at).toLocaleString()}`);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [parity, setParity] = useState<Parity>(localParity);
  const [paritySource, setParitySource] = useState("local run");
  const [ruleChecks, setRuleChecks] = useState<RuleChecks>(localRuleChecks);
  const [ruleChecksSource, setRuleChecksSource] = useState("local run");

  async function onFiles(e: ChangeEvent<HTMLInputElement>) {
    setLoadError(null);
    const names: string[] = [];
    for (const f of Array.from(e.target.files ?? [])) {
      try {
        const d = JSON.parse(await f.text());
        if (Array.isArray(d) && d[0]?.transitions) setAudit(d);
        else if (d.audit_log) {
          setAudit(d.audit_log);
          if (d.results) setResults(d.results);
          if (d.history) setHistory(d.history);
        } else if (d.mutants && d.rules) setResults(d);
        else if (Array.isArray(d.runs)) setHistory(d.runs);
        else throw new Error("not a recognised file");
        names.push(f.name);
      } catch (err) {
        setLoadError(`${f.name}: ${(err as Error).message}`);
      }
    }
    if (names.length) setSource(`Loaded ${names.join(", ")}`);
  }

  const rules = results ? Object.entries(results.rules).sort(([a], [b]) => a.localeCompare(b)) : [];
  const total = results?.mutants.length ?? 0;
  const killed = results?.mutants.filter((m) => m.outcome === "killed").length ?? 0;
  const ruleNames = Array.from(new Set(history.flatMap((r) => Object.keys(r.rules)))).sort();
  const runs = history.slice(-10);

  return (
    <main className="min-h-screen bg-background text-foreground font-sans">
      <div className="mx-auto max-w-6xl px-5 py-10">
        <header className="mb-8 border-b border-border pb-6">
          <p className="font-mono text-xs uppercase tracking-[0.25em] text-primary">NCAA Dynasty QA · Film Room</p>
          <div className="mt-2 flex flex-wrap items-end justify-between gap-4">
            <h1 className="text-3xl font-bold tracking-tight sm:text-4xl">QA dashboard</h1>
            <Link to="/" className="text-sm text-primary underline-offset-4 hover:underline">
              Mutant test advisor →
            </Link>
          </div>
          <p className="mt-2 text-muted-foreground">{source}</p>
          <label className="mt-4 inline-flex cursor-pointer items-center gap-2 rounded-md border border-border bg-card px-3 py-2 text-sm hover:bg-accent">
            Load files from a CI run (mutation-results.json, mutation-history.json)
            <input type="file" accept=".json" multiple className="sr-only" onChange={onFiles} />
          </label>
          {loadError && <p className="mt-2 text-sm text-destructive">{loadError}</p>}
          <GitHubRuns
            onLoad={(label, r, h, p, rc) => {
              if (rc && Array.isArray((rc as RuleChecks).checks)) { setRuleChecks(rc as RuleChecks); setRuleChecksSource(label); }
              if (p && Array.isArray((p as Parity).checks)) { setParity(p as Parity); setParitySource(label); }
              setLoadError(null);
              if (r) setResults(r as Results);
              if (h && Array.isArray((h as { runs?: unknown }).runs)) setHistory((h as { runs: HistoryRun[] }).runs);
              setSource(label);
            }}
          />
        </header>

        <section className="mb-10" aria-labelledby="rulechecks-h" data-testid="rule-checks-dashboard">
          <div className="mb-3 flex flex-wrap items-baseline gap-4">
            <h2 id="rulechecks-h" className="text-xl font-semibold">Rules test suite</h2>
            <span className={`font-mono text-sm ${ruleChecks.passed === ruleChecks.total ? "text-primary" : "text-destructive"}`}>
              {ruleChecks.passed}/{ruleChecks.total} pass · {ruleChecksSource}{ruleChecks.generated_at ? ` · ${new Date(ruleChecks.generated_at).toLocaleString()}` : ""}
            </span>
            <Link to="/rule-tests" className="text-sm text-primary hover:underline">Open the rules test suite</Link>
          </div>
          {ruleChecks.total === 0 ? <p className="text-sm text-muted-foreground">No results yet.</p> : (() => {
            const failing = ruleChecks.checks.filter((c) => !c.pass);
            return failing.length === 0
              ? <p className="text-sm text-primary">Every rule passes in every season tested.</p>
              : (
                <table className="w-full text-left text-sm">
                  <thead className="text-muted-foreground"><tr><th className="p-2">Failing rule</th><th>Season wins</th><th>Expected</th><th>Got</th><th className="p-2">How to fix</th></tr></thead>
                  <tbody>
                    {failing.map((c) => (
                      <tr key={`${c.id}-${c.wins}`} className="border-t border-border align-top">
                        <td className="p-2"><span className="text-muted-foreground">{c.group} · </span>{c.rule}</td>
                        <td className="font-mono text-xs">{c.wins}</td>
                        <td className="font-mono text-xs">{c.expected}</td>
                        <td className="font-mono text-xs text-destructive">{c.actual}</td>
                        <td className="p-2 text-xs">{c.fix}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              );
          })()}
        </section>

        <section className="mb-10" aria-labelledby="parity-h">
          <div className="mb-3 flex flex-wrap items-baseline gap-4">
            <h2 id="parity-h" className="text-xl font-semibold">Play dynasty vs. test suite rules</h2>
            <span className={`font-mono text-sm ${parity.passed === parity.total ? "text-primary" : "text-destructive"}`}>
              {parity.passed}/{parity.total} match · {paritySource} · {new Date(parity.generated_at).toLocaleString()}
            </span>
          </div>
          <details className="rounded-lg border border-border bg-card">
            <summary className="cursor-pointer px-4 py-2 text-sm text-muted-foreground">
              Browser test playing the game page side by side with the rules — show every check
            </summary>
            <table className="w-full text-left text-sm">
              <thead className="text-muted-foreground"><tr><th className="p-2">Check</th><th>Game page</th><th>Rules</th><th className="p-2">Result</th></tr></thead>
              <tbody>
                {[...parity.checks].sort((a, b) => Number(a.ok) - Number(b.ok)).map((c) => (
                  <tr key={c.check} className="border-t border-border">
                    <td className="p-2">{c.check}</td>
                    <td className="font-mono text-xs">{String(c.web)}</td>
                    <td className="font-mono text-xs">{String(c.rules)}</td>
                    <td className={`p-2 font-semibold ${c.ok ? "text-primary" : "text-destructive"}`}>{c.ok ? "match" : "MISMATCH"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </details>
        </section>


        <section className="mb-10">
          <div className="mb-4 flex flex-wrap items-baseline gap-4">
            <h2 className="text-xl font-semibold">Per-rule mutation scores</h2>
            {results && (
              <span className="font-mono text-sm text-muted-foreground">
                {killed}/{total} caught · {total ? ((killed / total) * 100).toFixed(1) : "0"}%
                {results.reproduce?.python && ` · Python ${results.reproduce.python}`}
              </span>
            )}
          </div>
          {!results ? (
            <p className="text-muted-foreground">No mutation results yet — run the suite, then export.</p>
          ) : (
            <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
              {rules.map(([name, r]) => (
                <div key={name} className="rounded-lg border border-border bg-card p-4">
                  <div className="flex items-center justify-between">
                    <span className="font-mono text-sm">{name}</span>
                    <span className={`font-mono text-lg font-bold ${r.score >= 100 ? "text-primary" : "text-destructive"}`}>
                      {r.score.toFixed(0)}%
                    </span>
                  </div>
                  <div className="mt-2 h-2 overflow-hidden rounded bg-muted">
                    <div className={`h-full ${r.score >= 100 ? "bg-primary" : "bg-destructive"}`} style={{ width: `${r.score}%` }} />
                  </div>
                  <p className="mt-2 text-xs text-muted-foreground">
                    {r.killed} of {r.total} caught
                    {r.survivors.length > 0 && ` · survived: ${r.survivors.join(", ")}`}
                  </p>
                </div>
              ))}
            </div>
          )}
          {results && (
            <details className="mt-4 rounded-lg border border-border bg-card p-4">
              <summary className="cursor-pointer text-sm font-medium">All {total} mutants</summary>
              <div className="mt-3 overflow-x-auto">
                <table className="w-full text-left text-sm">
                  <thead className="text-muted-foreground">
                    <tr>
                      <th className="py-1 pr-3">Rule</th><th className="pr-3">Mutant</th><th className="pr-3">Effective</th>
                      <th className="pr-3">Lines run</th><th>Outcome</th>
                    </tr>
                  </thead>
                  <tbody>
                    {[...results.mutants]
                      .sort((a, b) => Number(a.outcome === "killed") - Number(b.outcome === "killed"))
                      .map((m) => (
                        <tr key={m.name} className="border-t border-border">
                          <td className="py-1 pr-3 font-mono text-xs">{m.rule}</td>
                          <td className="pr-3">{m.name}</td>
                          <td className="pr-3">{m.effective ? "yes" : "no"}</td>
                          <td className="pr-3 font-mono text-xs">{m.executed_lines.length}/{m.mutated_lines.length}</td>
                          <td className={m.outcome === "killed" ? "text-primary" : "text-destructive"}>{m.outcome}</td>
                        </tr>
                      ))}
                  </tbody>
                </table>
              </div>
            </details>
          )}
        </section>

        <section className="mb-10">
          <h2 className="mb-4 text-xl font-semibold">Mutation history</h2>
          {runs.length === 0 ? (
            <p className="text-muted-foreground">No saved runs yet.</p>
          ) : (
            <div className="overflow-x-auto rounded-lg border border-border bg-card p-4">
              <table className="w-full text-left text-sm">
                <thead className="text-muted-foreground">
                  <tr>
                    <th className="py-1 pr-4">Rule</th>
                    {runs.map((r) => (
                      <th key={r.run_id} className="pr-4 font-mono text-xs">{r.run_id}{r.python && ` (${r.python})`}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {ruleNames.map((rule) => (
                    <tr key={rule} className="border-t border-border">
                      <td className="py-1 pr-4 font-mono text-xs">{rule}</td>
                      {runs.map((r, i) => {
                        const cur = r.rules[rule];
                        const reg = i > 0 && badRegression(runs[i - 1]?.rules[rule], cur);
                        const text = cur ? Object.entries(cur).map(([k, v]) => `${v} ${k}`).join(", ") : "—";
                        return (
                          <td key={r.run_id} className={`pr-4 ${reg ? "font-semibold text-destructive" : ""}`}>
                            {text}{reg && " ▼ regressed"}
                          </td>
                        );
                      })}
                    </tr>
                  ))}
                </tbody>
              </table>
              {history.length < 2 && (
                <p className="mt-3 text-xs text-muted-foreground">Only one run saved so far — regressions show once there's a second.</p>
              )}
            </div>
          )}
        </section>

        <section data-testid="audit-log" data-source={gameAudit ? "game" : "sample"}>
          <h2 className="mb-1 text-xl font-semibold">Season-rollover audit log</h2>
          <p className="mb-4 text-sm text-muted-foreground">
            {gameAudit
              ? `Your Play dynasty seasons (${gameAudit.length}), newest first. Updates when you end a season.`
              : <>No Play dynasty seasons yet — showing a sample dynasty. <Link to="/game" className="text-primary hover:underline">End a season</Link> to see your own.</>}
          </p>
          <div className="space-y-3">
            {shownAudit.map((e) => (
              <details key={e.season_id} className="rounded-lg border border-border bg-card p-4" open={e === shownAudit[0]}>
                <summary className="flex cursor-pointer flex-wrap items-baseline gap-x-4">
                  <span className="font-semibold">Season {e.season_id}</span>
                  <span className="font-mono text-primary">{e.archived_record.wins}–{e.archived_record.losses}</span>
                  {e.prestige_before !== undefined && (
                    <span className="text-sm">prestige {e.prestige_before}★ → {e.prestige_after}★</span>
                  )}
                  <span className="text-xs text-muted-foreground">completed {new Date(e.completed_at).toLocaleString()}</span>
                </summary>
                <ul className="mt-3 grid gap-x-8 gap-y-1 text-sm sm:grid-cols-2">
                  {e.transitions.map((t) => (
                    <li key={t.player} className="flex justify-between border-t border-border py-1">
                      <span>{t.player}</span>
                      <span className="text-muted-foreground">
                        {t.action === "graduated"
                          ? `${YEARS[t.from_year]} → graduated`
                          : t.action === "redshirt_hold"
                            ? `${YEARS[t.from_year]} held (redshirt)`
                            : `${YEARS[t.from_year]} → ${YEARS[t.to_year ?? 0]}`}
                      </span>
                    </li>
                  ))}
                </ul>
              </details>
            ))}
          </div>
        </section>
      </div>
    </main>
  );
}
