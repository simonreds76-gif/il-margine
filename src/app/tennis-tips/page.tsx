import TennisTipsClient from "./TennisTipsClient";
import { fetchMarketPayload } from "@/lib/public-record";

export const revalidate = 60;

export default async function TennisTips() {
  const payload = await fetchMarketPayload("tennis").catch((error) => {
    console.error("[tennis-tips] failed to load initial public record", error);
    return { pending: [], recent: [], stats: [], progression: [] };
  });

  return (
    <TennisTipsClient
      initialPendingBets={payload.pending}
      initialRecentBets={payload.recent}
      initialStats={payload.stats}
      initialProgressionRows={payload.progression}
    />
  );
}
