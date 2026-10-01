import { createFileRoute, Link } from "@tanstack/react-router";
import { useEffect, useState } from "react";
import R from "../../ncaa-dynasty-qa/rules.json";
import { supabase } from "@/integrations/supabase/client";
import { PrestigeTimeline } from "@/components/PrestigeTimeline";

const SAVE_KEY = "ncaa-dynasty-game-v1";

type Row = {
  season: number;
  wins: number;
  losses: number;
  roster: number | null;
  before: number | null;
  after: number | null;
  source: "This save" | "Stored online";
};

function hoursFor(prestige: number | null): number | null {
  if (prestige == null) return null;
  return (R.WEEKLY_HOURS as Record<string, number>)[String(prestige)] ?? null;
}

export const Route = createFileRoute("/saves")({
  head: () => ({
    meta: [
      { title: "Dynasty saves — NCAA Dynasty QA" },
      { name: "description", content: "Every recorded dynasty season with its wins, roster size, prestige and recruiting hours in one place." },
      { property: "og:title", content: "Dynasty saves — NCAA Dynasty QA" },
      { property: "og:description", content: "Every recorded dynasty season with its wins, roster size, prestige and recruiting hours in one place." },
      { property: "og:type", content: "website" },
      { name: "twitter:card", content: "summary" },
    ],
  }),
  component: SavesPage,
});

function SavesPage() {
  const [rows, setRows] = useState<Row[]>([]);
  const [user, setUser] = useState<string | null>(null);
  const [msg, setMsg] = useState<string | null>(null);

  useEffect(() => {
    const local: Row[] = [];
    try {
      const raw = localStorage.getItem(SAVE_KEY);
      if (raw) {
        const s = JSON.parse(raw);
        for (const h of s.history ?? []) {
          const a = s.auditLog?.find((x: { season_id: number }) => x.season_id === h.season);
          local.push({
            season: h.season, wins: h.wins, losses: h.losses,
            roster: a ? a.transitions.length : null,
            before: a?.prestige_before ?? null, after: a?.prestige_after ?? null,
            source: "This save",
          });
        }
      }
    } catch { /* ignore */ }
    setRows(local);
    supabase.auth.getUser().then(async ({ data }) => {
      setUser(data.user?.id ?? null);
      if (!data.user) return;
      const { data: stored, error } = await supabase.from("dynasty_seasons").select("*").order("season");
      if (error) return setMsg("Couldn't load your stored seasons.");
      const online: Row[] = (stored ?? []).map((d) => ({
        season: d.season, wins: d.wins, losses: d.losses,
        roster: d.roster_size,
        before: d.prestige_before === null ? null : Number(d.prestige_before),
        after: d.prestige_after === null ? null : Number(d.prestige_after),
        source: "Stored online",
      }));
      setRows([...local, ...online]);
    });
  }, []);

  const sorted = [...rows].sort((a, b) => a.source.localeCompare(b.source) || a.season - b.season);

  return (
    <main className="mx-auto max-w-4xl p-6" data-loaded="true">
      <nav className="mb-4 flex gap-4 text-sm text-muted-foreground">
        <Link to="/game" className="hover:underline">Play dynasty</Link>
        <Link to="/prestige" className="hover:underline">Prestige formula</Link>
        <Link to="/rules" className="hover:underline">Rules editor</Link>
        <Link to="/rules-doc" className="hover:underline">Rules document</Link>
      </nav>
      <h1 className="mb-1 text-2xl font-bold">Dynasty saves</h1>
      <p className="mb-4 text-sm text-muted-foreground">
        Every season you've recorded — from your Play dynasty save on this device and from seasons stored online — with its wins, roster, prestige and the weekly recruiting hours that prestige gives. Compare these real numbers against the thresholds on the Rules document page.
      </p>
      {msg && <p className="mb-2 text-sm text-muted-foreground" data-testid="saves-msg">{msg}</p>}
      <PrestigeTimeline rows={sorted} />
      {sorted.length === 0 ? (
        <p className="text-sm text-muted-foreground" data-testid="saves-empty">
          No seasons recorded yet. Finish a season in Play dynasty, or sign in and add real seasons on the Prestige formula page.
        </p>
      ) : (
        <table className="w-full font-mono text-sm" data-testid="saves-table">
          <thead className="text-xs text-muted-foreground">
            <tr>
              <th className="text-left">Source</th><th className="text-right">Season</th><th className="text-right">Record</th>
              <th className="text-right">Roster</th><th className="text-right">Prestige before</th><th className="text-right">Prestige after</th><th className="text-right">Hours/week</th>
            </tr>
          </thead>
          <tbody>
            {sorted.map((r) => (
              <tr key={`${r.source}-${r.season}`} className="border-t border-border" data-season={r.season} data-source={r.source}>
                <td className="py-1 font-sans text-xs">{r.source}</td>
                <td className="text-right">{r.season}</td>
                <td className="text-right">{r.wins}–{r.losses}</td>
                <td className={`text-right ${r.roster != null && r.roster > R.MAX_ROSTER ? "font-semibold text-destructive" : ""}`}>
                  {r.roster != null ? `${r.roster}/${R.MAX_ROSTER}` : "—"}
                </td>
                <td className="text-right">{r.before != null ? `${r.before}★` : "—"}</td>
                <td className="text-right">{r.after != null ? `${r.after}★` : "—"}</td>
                <td className="text-right">{hoursFor(r.after) ?? "—"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
      {!user && (
        <p className="mt-4 text-sm text-muted-foreground">
          <Link to="/auth" className="text-primary underline">Sign in</Link> to also see the seasons you've stored online.
        </p>
      )}
    </main>
  );
}
