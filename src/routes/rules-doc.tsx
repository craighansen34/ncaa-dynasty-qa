import { createFileRoute, Link } from "@tanstack/react-router";
import { RulesDocContent } from "@/components/RulesDocContent";

export const Route = createFileRoute("/rules-doc")({
  head: () => ({
    meta: [
      { title: "Rules Document — NCAA Dynasty" },
      { name: "description", content: "Every dynasty rule with its threshold and description, for comparing the game, the test suite and the rule checks." },
      { property: "og:title", content: "Rules Document — NCAA Dynasty" },
      { property: "og:description", content: "Every rule, threshold and description shared by the dynasty game and the QA test suite." },
      { property: "og:type", content: "website" },
      { name: "twitter:card", content: "summary" },
    ],
  }),
  component: RulesDoc,
});

function RulesDoc() {
  return (
    <main className="mx-auto max-w-5xl px-4 py-8">
      <header className="mb-6 flex flex-wrap items-baseline justify-between gap-4">
        <div>
          <p className="font-mono text-xs uppercase tracking-[0.25em] text-primary">NCAA Dynasty · Rules</p>
          <h1 className="text-3xl font-bold">Rules document</h1>
          <p className="text-sm text-muted-foreground">
            Every rule, threshold and description in the shared rules file — compare it to the game, the test suite and the rule checks.
          </p>
        </div>
        <nav className="flex gap-4 text-sm text-primary">
          <Link to="/rules" className="hover:underline">Rules editor</Link>
          <Link to="/rule-tests" className="hover:underline">Rules test suite</Link>
          <Link to="/game" className="hover:underline">Play dynasty</Link>
          <Link to="/dashboard" className="hover:underline">QA dashboard</Link>
        </nav>
      </header>
      <RulesDocContent />
    </main>
  );
}
