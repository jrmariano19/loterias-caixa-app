import { createFileRoute } from "@tanstack/react-router";
import { TicketApp } from "@/components/ticket-app";
import { getLatest } from "@/lib/caixa.functions";
import type { LatestDraw } from "@/lib/loterias";

export const Route = createFileRoute("/")({
  loader: async (): Promise<LatestDraw | null> => {
    try {
      return await getLatest({ data: { id: "megasena" } });
    } catch {
      return null;
    }
  },
  component: Home,
});

function Home() {
  const initial = Route.useLoaderData();
  return <TicketApp initial={initial} />;
}
