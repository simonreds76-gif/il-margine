import TennisTipsClient from "./TennisTipsClient";
import { fetchMarketPayload } from "@/lib/public-record";

// Admin bet mutations invalidate this page immediately. The daily value is a
// fallback for any automated settlement that writes directly to Supabase.
export const revalidate = 86400;

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
