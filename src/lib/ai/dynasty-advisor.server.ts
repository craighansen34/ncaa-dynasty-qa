import { createOpenAI } from "@ai-sdk/openai";
import { APICallError, streamText } from "ai";
import { z } from "zod";
import R from "../../../ncaa-dynasty-qa/rules.json";
import { EditableRules } from "../rules.functions";
import {
  createLovableAiGatewayRunIdFetch,
  getLovableAiGatewayRunId,
  withLovableAiGatewayRunIdHeader,
} from "./run-id.server";

const GATEWAY_URL = "https://ai.gateway.lovable.dev/v1";
const MODEL = "openai/gpt-6-astra";

const player = z.object({
  name: z.string().max(80),
  year: z.number().int().min(1).max(4),
  redshirted: z.boolean(),
  starter: z.boolean(),
  injuryWeeks: z.number().int().min(0).max(52),
});
export const advisorInput = z.object({
  season: z.number().int().min(1),
  week: z.number().int().min(1),
  wins: z.number().int().min(0),
  losses: z.number().int().min(0),
  prestige: z.number().min(0).max(5),
  players: z.array(player).max(R.MAX_ROSTER),
  team: z.string().trim().min(1).max(40).default("Your team"),
  standings: z.array(z.object({ team: z.string().trim().min(1).max(40), wins: z.number().int().min(0).max(20), losses: z.number().int().min(0).max(20) })).max(16).default([]),
  grades: z.record(z.string(), z.number().int().min(0).max(10)).optional(),
  history: z.array(z.object({ season: z.number().int(), wins: z.number().int(), losses: z.number().int() }).passthrough()).max(100).default([]),
  question: z.string().trim().max(500).default(""),
  // Live rules editor draft; validated with EditableRules before use.
  rules: z.unknown().optional(),
});

const YEARS = ["", "FR", "SO", "JR", "SR"];
const hours = (p: number) => (R.WEEKLY_HOURS as Record<string, number>)[String(p)] ?? 0;

// Built per request from the current rules (file + any live editor draft), so
// edits to thresholds and descriptions shape the very next answer.
function systemPrompt() {
  const descs = (R as { _descriptions?: Record<string, string> })._descriptions ?? {};
  const notes = Object.entries(descs).filter(([, v]) => v.trim())
    .map(([k, v]) => `- ${k.replace(/_/g, " ")}: ${v.trim()}`).join("\n");
  return `You are the staff advisor for a college football dynasty that follows EA College Football 26 dynasty rules, SEC conference.
Game rules (authoritative, do not contradict):
- Roster limit ${R.MAX_ROSTER}. Incoming transfers only through week ${R.TRANSFER_DEADLINE_WEEK}; season is ${R.SEASON_WEEKS} games.
- Injured players cannot start until fully healed; each game heals one week; the offseason heals everyone. 1 week left = questionable, more = out.
- Rollover: non-redshirted seniors graduate, redshirted players hold their class year once, everyone else moves up a year.
- Prestige ${R.MIN_PRESTIGE}-${R.MAX_PRESTIGE} stars in ${R.PRESTIGE_STEP} steps. Prestige is the average of the school report card (${R.SCHOOL_GRADES.join(', ')}; scale ${R.GRADE_SCALE.join(' ')}, each step = half a star), rounded to the nearest half star. Only these grades move with results, one step per season: ${Object.entries(R.GRADE_SEASON_CHANGES).map(([g, t]) => `${g} up at ${t.up_wins}+ wins, down at ${t.down_wins} or fewer`).join('; ')}. So one great season rarely changes prestige; it takes several. Weekly recruiting hours by prestige: ${JSON.stringify(R.WEEKLY_HOURS)}; max ${R.PROSPECT_WEEKLY_HOUR_CAP} hours per prospect per week; an offer costs ${R.OFFER_HOUR_COST} hours; ${R.SCHOLARSHIP_OFFERS_PER_SEASON} offers per season.
- SEC standings: conference win % first, then head-to-head, then record vs common opponents.
${notes ? `Coach's own notes on what each rule means (treat as the coach's intent, never override the numbers above):\n${notes}\n` : ""}Players have no positions or ratings in this game, only name, class year, redshirt, starter and injury state. Do not invent positions, ratings or prospects' names; reason from class balance, injuries, remaining weeks, deadline, prestige and standings.
Answer in Markdown with three short headings: "Signees", "Injury rotation", "Lineup". Under each, 2-4 concrete bullets naming actual roster players where relevant. Keep it under 250 words. If the user asked a question, answer it first in one line.`;
}

/** SEC order by win % (ties by name; head-to-head isn't tracked in the game). Our row comes from the game record. */
function rankStandings(d: z.infer<typeof advisorInput>) {
  const rows = [{ team: `${d.team} (us)`, wins: d.wins, losses: d.losses }, ...d.standings];
  const pct = (r: { wins: number; losses: number }) => (r.wins + r.losses ? r.wins / (r.wins + r.losses) : 0);
  rows.sort((a, b) => pct(b) - pct(a) || a.team.localeCompare(b.team));
  if (rows.length === 1) return `SEC standings: only our record is known (${d.wins}-${d.losses}); no other teams entered.`;
  return ["SEC standings (entered by the coach, ours from the game):", ...rows.map((r, i) => `${i + 1}. ${r.team} ${r.wins}-${r.losses}`)].join("\n");
}

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

export async function handleDynastyAdvisor(request: Request) {
  // Re-read the rules file so edits from the live rules editor apply to the very next answer.
  try {
    const fs = await import("node:fs/promises");
    const path = await import("node:path");
    Object.assign(R, JSON.parse(await fs.readFile(path.join(process.cwd(), "ncaa-dynasty-qa", "rules.json"), "utf8")));
  } catch { /* published site: use the bundled rules */ }
  // Saved online rules (shared by preview and published site) win over the file.
  try {
    const url = process.env["SUPABASE_URL"], key = process.env["SUPABASE_PUBLISHABLE_KEY"];
    if (url && key) {
      const res = await fetch(`${url}/rest/v1/rules_config?id=eq.1&select=data`, { headers: { apikey: key } });
      const rows = res.ok ? ((await res.json()) as { data: object }[]) : [];
      if (rows[0]?.data) Object.assign(R, rows[0].data);
    }
  } catch { /* fall back to the file */ }
  let body: unknown;
  // A live editor draft (valid, possibly unsaved) wins over the file.
  // Defer applying it until after parsing — handled below.
  try { body = await request.json(); } catch { return Response.json({ error: "Request body must be JSON." }, { status: 400 }); }
  const parsed = advisorInput.safeParse(body);
  if (!parsed.success) return Response.json({ error: parsed.error.issues.map((i) => i.message).join("; ") }, { status: 400 });
  if (parsed.data.rules !== undefined) {
    const live = EditableRules.safeParse(parsed.data.rules);
    if (live.success) Object.assign(R, JSON.parse(JSON.stringify(live.data)));
  }
  const apiKey = process.env["LOVABLE_API_KEY"];
  if (!apiKey) return Response.json({ error: "AI isn't configured for this app." }, { status: 500 });

  const d = parsed.data;
  const byYear = [1, 2, 3, 4].map((y) => `${YEARS[y]} ${d.players.filter((p) => p.year === y).length}`).join(", ");
  const prompt = [
    `Season ${d.season}, week ${d.week} of ${R.SEASON_WEEKS}, record ${d.wins}-${d.losses}.`,
    `Prestige ${d.prestige} stars (${hours(d.prestige)} recruiting hours/week). Transfers ${d.week > R.TRANSFER_DEADLINE_WEEK ? "closed" : "open"}.`,
    `Roster ${d.players.length}/${R.MAX_ROSTER} (${byYear}). Open spots: ${R.MAX_ROSTER - d.players.length}.`,
    "Players:",
    ...d.players.map((p) => `- ${p.name} | ${YEARS[p.year]}${p.redshirted ? " (redshirt)" : ""}${p.starter ? " | starter" : ""}${p.injuryWeeks ? ` | injured ${p.injuryWeeks} wk` : ""}`),
    d.grades ? `School report card: ${Object.entries(d.grades).map(([g, i]) => `${g} ${R.GRADE_SCALE[i]}`).join(", ")}.` : "",
    d.history.length ? `Past seasons: ${d.history.map((h) => `S${h.season} ${h.wins}-${h.losses}`).join(", ")}.` : "Past seasons: none yet.",
    `Injury report: ${d.players.filter((p) => p.injuryWeeks > 0).map((p) => `${p.name} ${p.injuryWeeks} wk (${p.injuryWeeks === 1 ? "questionable" : "out"})${p.starter ? ", starter" : ""}`).join("; ") || "everyone healthy"}.`,
    rankStandings(d),
    d.question ? `Coach's question: ${d.question}` : "",
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
    system: systemPrompt(),
    prompt,
    abortSignal: request.signal,
    maxRetries: 0,
    providerOptions: {
      openai: { forceReasoning: true, reasoningEffort: "low", reasoningSummary: "auto", store: false, include: ["reasoning.encrypted_content"] },
    },
  });
  return withLovableAiGatewayRunIdHeader(result.toUIMessageStreamResponse({ sendReasoning: true, onError: describeError }), runIdFetch);
}
