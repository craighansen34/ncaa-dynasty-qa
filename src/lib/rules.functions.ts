import { createServerFn } from "@tanstack/react-start";
import { z } from "zod";
import { requireSupabaseAuth } from "@/integrations/supabase/auth-middleware";

const LEVELS = ["5", "4.5", "4", "3.5", "3", "2.5", "2", "1.5", "1", "0.5"] as const;
const hours = z.object(Object.fromEntries(LEVELS.map((l) => [l, z.number().int().min(0).max(10000)]))) as z.ZodType<Record<string, number>>;
export const DESCRIBED = ["MAX_ROSTER", "TRANSFER_DEADLINE_WEEK", "SEASON_WEEKS", "PROSPECT_WEEKLY_HOUR_CAP", "OFFER_HOUR_COST",
  "SCHOLARSHIP_OFFERS_PER_SEASON", "WEEKLY_HOURS", "PRESEASON_HOURS", "championship_contender", "brand_exposure", "program_tradition"] as const;
const descriptions = z.object(Object.fromEntries(DESCRIBED.map((k) => [k, z.string().trim().max(300, "Descriptions can be at most 300 characters.").optional()]))) as z.ZodType<Partial<Record<(typeof DESCRIBED)[number], string>>>;
const threshold = z.object({ up_wins: z.number().int().min(0).max(20), down_wins: z.number().int().min(0).max(20) });

export const EditableRules = z
  .object({
    MAX_ROSTER: z.number().int().min(1).max(200),
    TRANSFER_DEADLINE_WEEK: z.number().int().min(1).max(20),
    SEASON_WEEKS: z.number().int().min(1).max(20),
    WEEKLY_HOURS: hours,
    PRESEASON_HOURS: hours,
    PROSPECT_WEEKLY_HOUR_CAP: z.number().int().min(1).max(10000),
    OFFER_HOUR_COST: z.number().int().min(0).max(1000),
    SCHOLARSHIP_OFFERS_PER_SEASON: z.number().int().min(1).max(200),
    _descriptions: descriptions.optional(),
    GRADE_SEASON_CHANGES: z.object({
      championship_contender: threshold,
      brand_exposure: threshold,
      program_tradition: threshold,
    }),
  })
  .superRefine((r, ctx) => {
    if (r.TRANSFER_DEADLINE_WEEK > r.SEASON_WEEKS)
      ctx.addIssue({ code: "custom", message: "The transfer deadline can't be after the last week of the season." });
    for (const [g, t] of Object.entries(r.GRADE_SEASON_CHANGES))
      if (t.down_wins >= t.up_wins) ctx.addIssue({ code: "custom", message: `${g.replace(/_/g, " ")}: the "down" win total must be below the "up" one.` });
    for (const l of LEVELS)
      if ((r.PRESEASON_HOURS[l] ?? 0) < (r.WEEKLY_HOURS[l] ?? 0)) ctx.addIssue({ code: "custom", message: `Preseason hours at ${l}★ can't be below weekly hours.` });
  });
export type Editable = z.infer<typeof EditableRules>;

const rulesPath = async () => (await import("node:path")).join(process.cwd(), "ncaa-dynasty-qa", "rules.json");

export const saveRules = createServerFn({ method: "POST" })
  .middleware([requireSupabaseAuth])
  .inputValidator((d: unknown) => EditableRules.parse(d))
  .handler(async ({ data, context }) => {
    const { data: owner } = await context.supabase.rpc("claim_rules_owner");
    if (!owner) return { ok: false as const, error: "Only the rules owner can save changes." };
    const { error } = await context.supabase.from("rules_config")
      .upsert({ id: 1, data: data as never, updated_at: new Date().toISOString(), updated_by: context.userId });
    if (error) { console.error("saveRules db", error); return { ok: false as const, error: "Couldn't save the rules online. Try again." }; }
    // Editor preview only: also update the rules file the test suite reads.
    try {
      const fs = await import("node:fs/promises");
      const p = await rulesPath();
      const current = JSON.parse(await fs.readFile(p, "utf8"));
      await fs.writeFile(p, JSON.stringify({ ...current, ...data }, null, 1) + "\n");
    } catch { /* published site: file is read-only; the online copy is what counts */ }
    return { ok: true as const };
  });
