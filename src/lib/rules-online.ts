import { supabase } from "@/integrations/supabase/client";
import { applyRules } from "@/lib/dynasty/engine";
import { EditableRules } from "@/lib/rules.functions";

/** Loads the rules saved online (if any) and swaps them into the game. */
export async function loadOnlineRules() {
  const { data } = await supabase.from("rules_config").select("data").eq("id", 1).maybeSingle();
  if (!data?.data) return;
  const parsed = EditableRules.safeParse(data.data);
  if (parsed.success) applyRules(parsed.data);
}
