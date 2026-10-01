import { createFileRoute } from "@tanstack/react-router";
import { handleDynastyAdvisor } from "@/lib/ai/dynasty-advisor.server";

export const Route = createFileRoute("/api/dynasty-advisor")({
  server: { handlers: { POST: ({ request }) => handleDynastyAdvisor(request) } },
});
