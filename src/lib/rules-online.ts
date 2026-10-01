import { supabase } from "@/integrations/supabase/client";
import { applyRules } from "@/lib/dynasty/engine";
import { EditableRules } from "@/lib/rules.functions";

/** True when the backend URL/key are configured (browser or SSR). */
export function hasBackendConfig(): boolean {
  const url =
    import.meta.env['VITE_SUPABASE_URL'] ||
    (typeof process !== 'undefined' ? process.env['SUPABASE_URL'] : undefined);
  const key =
    import.meta.env['VITE_SUPABASE_PUBLISHABLE_KEY'] ||
    (typeof process !== 'undefined' ? process.env['SUPABASE_PUBLISHABLE_KEY'] : undefined);
  return Boolean(url && key);
}

/** Loads the rules saved online (if any) and swaps them into the game. */
export async function loadOnlineRules() {
  // Without backend config (e.g. CI or self-hosted preview), keep bundled rules.
  if (!hasBackendConfig()) return;
  const { data } = await supabase.from("rules_config").select("data").eq("id", 1).maybeSingle();
  if (!data?.data) return;
  const parsed = EditableRules.safeParse(data.data);
  if (parsed.success) applyRules(parsed.data);
}
