import { createFileRoute } from "@tanstack/react-router";
import { handleSuggestTest } from "@/lib/ai/suggest-test.server";

export const Route = createFileRoute("/api/suggest-test")({
  server: { handlers: { POST: ({ request }) => handleSuggestTest(request) } },
});
