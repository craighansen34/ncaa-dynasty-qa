import { createServerFn } from "@tanstack/react-start";
import { z } from "zod";
import { unzipSync, strFromU8 } from "fflate";

const GATEWAY_URL = "https://connector-gateway.lovable.dev/github";
const repoSchema = z.string().trim().regex(/^[\w.-]+\/[\w.-]+$/, "Use the form owner/repo");

async function gh(path: string, binary = false) {
  const lovableKey = process.env['LOVABLE_API_KEY'];
  const ghKey = process.env['GITHUB_API_KEY'];
  if (!lovableKey || !ghKey) throw new Error("GitHub isn't connected to this project.");
  const res = await fetch(`${GATEWAY_URL}/${path}`, {
    headers: { Accept: "application/vnd.github+json", Authorization: `Bearer ${lovableKey}`, "X-Connection-Api-Key": ghKey },
  });
  if (!res.ok) {
    const body = await res.text();
    console.error(`GitHub request failed [${res.status}]: ${body}`);
    if (res.status === 404) throw new Error("Repository or workflow not found — check the name and that the QA workflow has run.");
    throw new Error(`GitHub request failed [${res.status}]: ${body.slice(0, 200)}`);
  }
  return binary ? new Uint8Array(await res.arrayBuffer()) : res.json();
}

export type QaRun = { id: number; number: number; branch: string; commit: string; conclusion: string | null; status: string; created_at: string; url: string };

export const listQaRuns = createServerFn({ method: "GET" })
  .inputValidator((d) => z.object({ repo: repoSchema }).parse(d))
  .handler(async ({ data }): Promise<QaRun[]> => {
    const j = await gh(`repos/${data.repo}/actions/workflows/qa.yml/runs?per_page=15`);
    return (j.workflow_runs ?? []).map((r: any) => ({
      id: r.id, number: r.run_number, branch: r.head_branch, commit: String(r.head_sha).slice(0, 7),
      conclusion: r.conclusion, status: r.status, created_at: r.created_at, url: r.html_url,
    }));
  });

// eslint-disable-next-line @typescript-eslint/no-explicit-any
export type VersionResult = { python: string; results: any; history: any; validation: string | null; parity: any; ruleChecks: any };

export const loadQaRun = createServerFn({ method: "GET" })
  .inputValidator((d) => z.object({ repo: repoSchema, runId: z.number().int().positive() }).parse(d))
  .handler(async ({ data }): Promise<VersionResult[]> => {
    const j = await gh(`repos/${data.repo}/actions/runs/${data.runId}/artifacts?per_page=50`);
    const all = (j.artifacts ?? []).filter((a: any) => !a.expired);
    const unzip = async (id: number) => {
      const files = unzipSync(await gh(`repos/${data.repo}/actions/artifacts/${id}/zip`, true));
      const read = (n: string) => (files[n] ? strFromU8(files[n]) : null);
      const parse = (n: string) => { const t = read(n); try { return t ? JSON.parse(t) : null; } catch { return null; } };
      return { read, parse };
    };
    const byPy = new Map<string, VersionResult>();
    const slot = (py: string) => byPy.get(py) ?? byPy.set(py, { python: py, results: null, history: null, validation: null, parity: null, ruleChecks: null }).get(py)!;
    for (const a of all) {
      const m = /^(mutation-results|game-parity|rule-checks)-py(.+)$/.exec(a.name);
      if (!m) continue;
      const f = await unzip(a.id);
      const v = slot(m[2]!);
      if (m[1] === "rule-checks") v.ruleChecks = f.parse("rule-checks.json");
      else if (m[1] === "game-parity") v.parity = f.parse("game-parity.json");
      else { v.results = f.parse("mutation-results.json"); v.history = f.parse("mutation-history.json"); v.validation = f.read("mutation-results.validation.txt"); }
    }
    return [...byPy.values()].sort((x, y) => x.python.localeCompare(y.python, undefined, { numeric: true }));
  });
