import { createFileRoute, Link } from "@tanstack/react-router";
import { RulesEditorPanel } from "@/components/RulesEditorPanel";

export const Route = createFileRoute("/rules")({
  head: () => ({
    meta: [
      { title: "Rules Editor — NCAA Dynasty" },
      { name: "description", content: "Edit prestige, recruiting hours and roster limits shared by the dynasty game and the QA suite." },
      { property: "og:title", content: "Rules Editor — NCAA Dynasty" },
      { property: "og:description", content: "One place to change the dynasty rules for the game and the tests." },
      { property: "og:type", content: "website" },
      { name: "twitter:card", content: "summary" },
    ],
  }),
  component: RulesEditor,
});

function RulesEditor() {
  return (
    <main className="mx-auto max-w-5xl px-4 py-8">
      <header className="mb-6 flex flex-wrap items-baseline justify-between gap-4">
        <div>
          <p className="font-mono text-xs uppercase tracking-[0.25em] text-primary">NCAA Dynasty · Rules</p>
          <h1 className="text-3xl font-bold">Rules editor</h1>
          <p className="text-sm text-muted-foreground">One set of rules for the Play dynasty page, its staff advisor and the test suite.</p>
        </div>
        <nav className="flex gap-4 text-sm text-primary">
          <Link to="/prestige" className="hover:underline">Prestige formula</Link>
          <Link to="/saves" className="hover:underline">Dynasty saves</Link>
          <Link to="/rules-doc" className="hover:underline">Rules document</Link>
          <Link to="/rule-tests" className="hover:underline">Rules test suite</Link>
          <Link to="/game" className="hover:underline">Play dynasty</Link>
          <Link to="/dashboard" className="hover:underline">QA dashboard</Link>
        </nav>
      </header>

      <RulesEditorPanel />
    </main>
  );
}
