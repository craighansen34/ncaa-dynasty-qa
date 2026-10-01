import { createFileRoute, Link } from "@tanstack/react-router";
import { PrestigeFormulaPanel } from "@/components/PrestigeFormulaPanel";

export const Route = createFileRoute("/prestige")({
  head: () => ({
    meta: [
      { title: "Prestige Formula — NCAA Dynasty" },
      { name: "description", content: "Tweak the prestige formula numbers and watch prestige, recruiting hours and roster limits change live." },
      { property: "og:title", content: "Prestige Formula — NCAA Dynasty" },
      { property: "og:description", content: "Live prestige formula lab for the dynasty game and QA suite." },
      { property: "og:type", content: "website" },
      { name: "twitter:card", content: "summary" },
    ],
  }),
  component: PrestigePage,
});

function PrestigePage() {
  return (
    <main className="mx-auto max-w-6xl px-4 py-8" data-testid="prestige-page">
      <header className="mb-6 flex flex-wrap items-baseline justify-between gap-4">
        <div>
          <p className="font-mono text-xs uppercase tracking-[0.25em] text-primary">NCAA Dynasty · Prestige</p>
          <h1 className="text-3xl font-bold">Prestige formula</h1>
        </div>
        <nav className="flex gap-4 text-sm text-primary">
          <Link to="/rules" className="hover:underline">Rules editor</Link>
          <Link to="/rule-tests" className="hover:underline">Rules test suite</Link>
          <Link to="/game" className="hover:underline">Play dynasty</Link>
          <Link to="/dashboard" className="hover:underline">QA dashboard</Link>
        </nav>
      </header>
      <PrestigeFormulaPanel />
    </main>
  );
}
