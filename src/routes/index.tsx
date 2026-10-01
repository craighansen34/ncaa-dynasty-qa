import { createFileRoute, Link } from "@tanstack/react-router";
import { useRef, useState } from "react";

export const Route = createFileRoute("/")({
  head: () => ({
    meta: [
      { title: "Surviving Mutant Test Advisor — NCAA Dynasty QA" },
      {
        name: "description",
        content: "Paste a surviving verifier mutation and its test output to get an AI-suggested regression test.",
      },
      { property: "og:title", content: "Surviving Mutant Test Advisor — NCAA Dynasty QA" },
      {
        property: "og:description",
        content: "AI-suggested regression tests for verifier mutations the NCAA Dynasty unit suite missed.",
      },
      { property: "og:type", content: "website" },
      { name: "twitter:card", content: "summary" },
    ],
  }),
  component: Index,
});

const RULES = [
  "duplicate-id",
  "regression-mapping",
  "missing-id",
  "no-steps",
  "unknown-step",
  "ambiguous-step",
  "orphaned-rule",
  "orphaned-scenario",
  "scenario-execution",
  "other",
];

// Real-world breaks for rules that had no mutants; each one survived the suite before its test was added.
const PRESETS = [
  {
    rule: "orphaned-rule",
    mutantName: "orphaned rules only checked up to baseline",
    original: "missing = sorted(expected - set(tr_ids))",
    mutated: "missing = sorted(t for t in expected - set(tr_ids) if int(t[3:]) <= COVERAGE_BASELINE)",
  },
  {
    rule: "orphaned-rule",
    mutantName: "orphaned-rule check disabled",
    original: "if missing:\n    audit_errors.append(f\"ORPHANED RULES (missing scenarios): {missing}\")",
    mutated: "if False:\n    audit_errors.append(f\"ORPHANED RULES (missing scenarios): {missing}\")",
  },
  {
    rule: "orphaned-scenario",
    mutantName: "orphaned scenarios only flagged for two-digit IDs",
    original: "extra = sorted(set(tr_ids) - expected)",
    mutated: "extra = sorted(t for t in set(tr_ids) - expected if len(t) == 5)",
  },
  {
    rule: "orphaned-scenario",
    mutantName: "orphaned-scenario check disabled",
    original: "if extra:\n    audit_errors.append(f\"ORPHANED SCENARIOS (unmapped IDs): {extra}\")",
    mutated: "if False:\n    audit_errors.append(f\"ORPHANED SCENARIOS (unmapped IDs): {extra}\")",
  },
  {
    rule: "scenario-execution",
    mutantName: "failing scenarios do not fail the run",
    original: "if failed:\n    if strict:\n        sys.exit(1)\n    return False",
    mutated: "if False:\n    if strict:\n        sys.exit(1)\n    return False",
  },
  {
    rule: "scenario-execution",
    mutantName: "assertion failures counted as passes",
    original: "except AssertionError as e:\n    failed.append((s['tr'], s['name'], str(e)))",
    mutated: "except AssertionError as e:\n    passed += 1",
  },
].map((p) => ({ ...p, testOutput: "Ran 13 tests in 0.3s\n\nOK   (enforcement suite still passes with this mutant)" }));

const EXAMPLE = {
  rule: "duplicate-id",
  mutantName: "duplicate-ID detection off-by-one",
  original: "dupes = sorted({t for t in tr_ids if tr_ids.count(t) > 1})",
  mutated: "dupes = sorted({t for t in tr_ids if tr_ids.count(t) > 2})",
  testOutput:
    "test_real_suite_is_clean ... ok\ntest_missing_regression_mapping_is_rejected ... ok\n----------------------------------------------------------------------\nRan 6 tests in 0.041s\n\nOK",
};

type Status = "idle" | "streaming" | "done" | "error";

function Index() {
  const [form, setForm] = useState({ rule: "", mutantName: "", original: "", mutated: "", testOutput: "" });
  const [answer, setAnswer] = useState("");
  const [reasoning, setReasoning] = useState("");
  const [status, setStatus] = useState<Status>("idle");
  const [error, setError] = useState("");
  const abortRef = useRef<AbortController | null>(null);

  const set = (k: keyof typeof form) => (e: { target: { value: string } }) =>
    setForm((f) => ({ ...f, [k]: e.target.value }));

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!form.original.trim() || !form.mutated.trim()) {
      setError("Paste both the original and the mutated code.");
      setStatus("error");
      return;
    }
    const ctrl = new AbortController();
    abortRef.current = ctrl;
    setAnswer("");
    setReasoning("");
    setError("");
    setStatus("streaming");
    try {
      const res = await fetch("/api/suggest-test", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(form),
        signal: ctrl.signal,
      });
      if (!res.ok || !res.body) {
        const j = await res.json().catch(() => null);
        throw new Error(j?.error ?? `Request failed (${res.status}).`);
      }
      const reader = res.body.getReader();
      const dec = new TextDecoder();
      let buf = "";
      let gotText = false;
      for (;;) {
        const { value, done } = await reader.read();
        if (done) break;
        buf += dec.decode(value, { stream: true });
        const lines = buf.split("\n");
        buf = lines.pop() ?? "";
        for (const line of lines) {
          if (!line.startsWith("data: ")) continue;
          const data = line.slice(6).trim();
          if (data === "[DONE]") continue;
          let ev: { type: string; delta?: string; errorText?: string };
          try {
            ev = JSON.parse(data);
          } catch {
            continue;
          }
          if (ev.type === "text-delta" && ev.delta) {
            gotText = true;
            setAnswer((a) => a + ev.delta);
          } else if (ev.type === "reasoning-delta" && ev.delta) {
            setReasoning((r) => r + ev.delta);
          } else if (ev.type === "error") {
            throw new Error(ev.errorText || "The AI request failed.");
          }
        }
      }
      if (!gotText) throw new Error("The AI returned no suggestion. Add more detail and try again.");
      setStatus("done");
    } catch (err) {
      if ((err as Error).name === "AbortError") {
        setStatus("done");
        return;
      }
      setError((err as Error).message);
      setStatus("error");
    } finally {
      abortRef.current = null;
    }
  }

  const code = answer.match(/```python\n([\s\S]*?)```/)?.[1];

  return (
    <main className="min-h-screen bg-background text-foreground font-sans">
      <div className="mx-auto max-w-6xl px-5 py-10">
        <header className="mb-8 border-b border-border pb-6">
          <div className="flex justify-between gap-4"><p className="font-mono text-xs uppercase tracking-[0.25em] text-primary">NCAA Dynasty QA · Film Room</p><span className="flex gap-4"><Link to="/game" className="text-sm text-primary underline-offset-4 hover:underline">Play dynasty →</Link><Link to="/dashboard" className="text-sm text-primary underline-offset-4 hover:underline">QA dashboard →</Link></span></div>
          <h1 className="mt-2 text-3xl font-bold tracking-tight sm:text-4xl">Surviving mutant test advisor</h1>
          <p className="mt-2 max-w-2xl text-muted-foreground">
            A mutant survived CI? Paste the code change and the passing test output. Lovable AI drafts one focused
            test for <code className="font-mono text-sm">test_verifier_enforcement.py</code> that should catch it.
          </p>
        </header>

        <div className="grid gap-6 lg:grid-cols-2">
          <form onSubmit={submit} className="space-y-4 rounded-lg border border-border bg-card p-5">
            <div className="grid gap-4 sm:grid-cols-2">
              <label className="block text-sm font-medium">
                Verifier rule
                <select
                  value={form.rule}
                  onChange={set("rule")}
                  className="mt-1 w-full rounded-md border border-input bg-background px-3 py-2 font-mono text-sm"
                >
                  <option value="">Not sure</option>
                  {RULES.map((r) => (
                    <option key={r} value={r}>
                      {r}
                    </option>
                  ))}
                </select>
              </label>
              <label className="block text-sm font-medium">
                Mutant name
                <input
                  value={form.mutantName}
                  onChange={set("mutantName")}
                  maxLength={200}
                  placeholder="e.g. no-steps check disabled"
                  className="mt-1 w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
                />
              </label>
            </div>
            {(
              [
                ["original", "Original code (verify.py)", 3],
                ["mutated", "Mutated code", 3],
                ["testOutput", "Test output with the mutant applied", 7],
              ] as const
            ).map(([k, label, rows]) => (
              <label key={k} className="block text-sm font-medium">
                {label}
                <textarea
                  value={form[k]}
                  onChange={set(k)}
                  rows={rows}
                  maxLength={k === "testOutput" ? 20000 : 4000}
                  spellCheck={false}
                  className="mt-1 w-full rounded-md border border-input bg-background px-3 py-2 font-mono text-xs leading-relaxed"
                />
              </label>
            ))}
            <div className="flex flex-wrap gap-2">
              {status === "streaming" ? (
                <button
                  type="button"
                  onClick={() => abortRef.current?.abort()}
                  className="rounded-md border border-border px-4 py-2 text-sm font-semibold hover:bg-accent"
                >
                  Stop
                </button>
              ) : (
                <button
                  type="submit"
                  className="rounded-md bg-primary px-4 py-2 text-sm font-semibold text-primary-foreground hover:bg-primary/90"
                >
                  Suggest a test
                </button>
              )}
              <button
                type="button"
                onClick={() => setForm(EXAMPLE)}
                className="rounded-md border border-border px-4 py-2 text-sm hover:bg-accent"
              >
                Load example
              </button>
              <select
                aria-label="Load a real-world mutant"
                value=""
                onChange={(e) => {
                  const p = PRESETS[Number(e.target.value)];
                  if (p) setForm(p);
                }}
                className="rounded-md border border-border bg-background px-3 py-2 text-sm"
              >
                <option value="">Load a real-world mutant…</option>
                {PRESETS.map((p, i) => (
                  <option key={p.mutantName} value={i}>
                    {p.rule}: {p.mutantName}
                  </option>
                ))}
              </select>
            </div>
          </form>

          <section className="rounded-lg border border-border bg-card p-5" aria-live="polite">
            <div className="mb-3 flex items-center justify-between">
              <h2 className="font-mono text-xs uppercase tracking-[0.2em] text-muted-foreground">Suggestion</h2>
              {code && (
                <button
                  onClick={() => navigator.clipboard.writeText(code)}
                  className="rounded border border-border px-2 py-1 text-xs hover:bg-accent"
                >
                  Copy test
                </button>
              )}
            </div>
            {status === "idle" && (
              <p className="text-sm text-muted-foreground">Fill in the mutation details, or load the example.</p>
            )}
            {status === "error" && (
              <p role="alert" className="rounded-md border border-destructive/50 bg-destructive/10 p-3 text-sm text-destructive">
                {error}
              </p>
            )}
            {status === "streaming" && !answer && (
              <p className="text-sm text-muted-foreground">{reasoning ? "Thinking…" : "Starting…"}</p>
            )}
            {reasoning && (
              <details className="mb-3 text-xs text-muted-foreground">
                <summary className="cursor-pointer">Reasoning summary</summary>
                <p className="mt-2 whitespace-pre-wrap">{reasoning}</p>
              </details>
            )}
            {answer && (
              <pre className="max-h-[70vh] overflow-auto whitespace-pre-wrap font-mono text-xs leading-relaxed">
                {answer}
              </pre>
            )}
            {answer && (
              <p className="mt-3 text-xs text-muted-foreground">
                Review before adding. Then run <code className="font-mono">python3 ci_summary.py</code> to confirm the
                mutant is detected.
              </p>
            )}
          </section>
        </div>
      </div>
    </main>
  );
}
