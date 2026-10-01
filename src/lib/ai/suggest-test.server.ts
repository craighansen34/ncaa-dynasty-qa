import { createOpenAI } from "@ai-sdk/openai";
import { APICallError, streamText } from "ai";
import { z } from "zod";

import {
  createLovableAiGatewayRunIdFetch,
  getLovableAiGatewayRunId,
  withLovableAiGatewayRunIdHeader,
} from "./run-id.server";

const GATEWAY_URL = "https://ai.gateway.lovable.dev/v1";
const MODEL = "openai/gpt-6-astra";

export const suggestTestInput = z.object({
  rule: z.string().trim().max(200).default(""),
  mutantName: z.string().trim().max(200).default(""),
  original: z.string({ required_error: "Original code is required" }).trim().min(1, "Original code is required").max(4000),
  mutated: z.string({ required_error: "Mutated code is required" }).trim().min(1, "Mutated code is required").max(4000),
  testOutput: z.string().trim().max(20000).default(""),
});

const SYSTEM = `You help QA maintainers of a dependency-free Python QA suite for an NCAA Football Dynasty game.
Context:
- verify.py parses Gherkin scenarios (IDs TR-01..TR-102, contiguous: run_verifier builds expected = {TR-01..TR-102}) from features/*.feature.md and audits them before executing.
- Audit rules append strings to audit_errors: DUPLICATE TRACEABILITY IDs, ORPHANED RULES, ORPHANED SCENARIOS, SCENARIOS MISSING TR ID, MALFORMED SCENARIOS (no steps), MISSING REGRESSION TESTS for scenarios (IDs above COVERAGE_BASELINE=42 must be named in some tests/test_*.py), UNMATCHED STEP PHRASES, AMBIGUOUS STEP HANDLERS. ORPHANED RULES (missing scenarios) lists expected IDs no scenario uses (e.g. delete a scenario block); ORPHANED SCENARIOS (unmapped IDs) lists scenario IDs outside the expected range (e.g. rename a scenario to TR-199 or TR-150).
- Scenario execution (runs only if the audit is clean): each scenario's steps run their handler; an AssertionError marks the scenario failed, LAST_RESULT['failed'] gets {tr, name, error}, and run_verifier(strict=False) returns False if any scenario failed. To force a failure, change a Then value in the feature text (e.g. 'roster size evaluates to 84' -> 'roster size evaluates to 83') or register a step handler that raises AssertionError.
- verify.run_verifier(strict=False, tests_dir=None) returns True/False and fills verify.LAST_RESULT (keys: scenarios, passed, failed, audit_errors, mapped, unmapped). Module globals verify.RECRUITING (includes TR-73..TR-92 recruiting prospects/offers/signing), verify.COACH and verify.ROSTER hold the feature text (ROSTER has TR-51..TR-102, including TR-93..TR-102 CFB 26 recruiting hours, scholarship offers and SEC standings).
- Step definitions live in the module list verify.REGISTRY of (compiled_regex, fn) tuples; the decorator verify.step(pattern) appends (re.compile(pattern + r'\\Z'), fn). verify.find_handlers(phrase) returns every (fn, match) whose regex matches. To create ambiguity or extra handlers in a test, append to verify.REGISTRY and restore it in a try/finally (e.g. saved = list(verify.REGISTRY) ... verify.REGISTRY[:] = saved). Never use sys.settrace, AST inspection or source introspection.
- Feature step lines start with Given/When/Then/And/But followed by a space; scenario headings look like "Scenario: TR-07 name". Prefer small, readable fixtures built by editing self._orig text with str.replace or re.sub.
- tests/test_verifier_enforcement.py has class VerifierEnforcementTests(unittest.TestCase) with setUp saving self._orig = (verify.RECRUITING, verify.COACH, verify.ROSTER), tearDown restoring them, and a helper self.run_with(recruiting=None, coach=None, roster=None, tests_dir=None) -> (ok, stdout, audit_errors).
- Mutation testing replaces one snippet of verify.py; a mutant "survives" when the enforcement suite still passes.
Task: given a surviving mutation, explain in 1-3 sentences what behaviour the mutation breaks that no test detects, then give ONE focused unittest method to add to VerifierEnforcementTests that passes on the real verifier and fails on the mutant. Standard library only. Reuse run_with and self._orig. Then one line saying why it kills the mutant.
Format in Markdown with headings "Gap", "Suggested test" (a single \`\`\`python block) and "Why it catches the mutant". Stay under 60 lines of code. Do not invent verify.py APIs beyond those listed.`;

function describeError(error: unknown) {
  if (APICallError.isInstance(error)) {
    const s = error.statusCode;
    if (s === 402) return "AI credits are used up. Add credits in Settings → Plans & credits, then try again.";
    if (s === 429) return "Too many requests right now. Wait a minute, then try again.";
    if (s === 403) return "The AI request was denied for this workspace. Check workspace AI settings.";
    if (s === 401) return "AI isn't configured for this app (missing or invalid key).";
    if (s && s >= 500) return "The AI service had a temporary problem. Try again shortly.";
    return error.message || "The AI request failed.";
  }
  return error instanceof Error ? error.message : "The AI request failed.";
}

export async function handleSuggestTest(request: Request) {
  let body: unknown;
  try {
    body = await request.json();
  } catch {
    return Response.json({ error: "Request body must be JSON." }, { status: 400 });
  }
  const parsed = suggestTestInput.safeParse(body);
  if (!parsed.success) {
    return Response.json({ error: parsed.error.issues.map((i) => i.message).join("; ") }, { status: 400 });
  }
  const apiKey = process.env['LOVABLE_API_KEY'];
  if (!apiKey) return Response.json({ error: "AI isn't configured for this app." }, { status: 500 });

  const d = parsed.data;
  const prompt = [
    `Verifier rule: ${d.rule || "(not specified)"}`,
    `Mutant: ${d.mutantName || "(unnamed)"}`,
    "Original code in verify.py:",
    "```python", d.original, "```",
    "Mutated code:",
    "```python", d.mutated, "```",
    "Test output with the mutant applied (suite still passed):",
    "```", d.testOutput || "(none provided)", "```",
  ].join("\n");

  const runIdFetch = createLovableAiGatewayRunIdFetch(getLovableAiGatewayRunId(request));
  const provider = createOpenAI({
    baseURL: GATEWAY_URL,
    apiKey,
    headers: { "Lovable-API-Key": apiKey, "X-Lovable-AIG-SDK": "vercel-ai-sdk" },
    fetch: runIdFetch.fetch,
  });
  const result = streamText({
    model: provider.responses(MODEL),
    system: SYSTEM,
    prompt,
    abortSignal: request.signal,
    maxRetries: 0,
    providerOptions: {
      openai: {
        forceReasoning: true,
        reasoningEffort: "medium",
        reasoningSummary: "auto",
        store: false,
        include: ["reasoning.encrypted_content"],
      },
    },
  });
  return withLovableAiGatewayRunIdHeader(
    result.toUIMessageStreamResponse({ sendReasoning: true, onError: describeError }),
    runIdFetch,
  );
}
