import PlayerPropsClient from "./PlayerPropsClient";
import { fetchMarketPayload } from "@/lib/public-record";

// Admin bet mutations invalidate this page immediately. The hourly value is a
// safety net for automated settlements that write directly to Supabase.
export const revalidate = 3600;

export default async function PlayerProps() {
  const payload = await fetchMarketPayload("props").catch((error) => {
    console.error("[player-props] failed to load initial public record", error);
    return { pending: [], recent: [], stats: [], progression: [] };
  });

  return (
    <PlayerPropsClient
      initialPendingBets={payload.pending}
      initialRecentBets={payload.recent}
      initialStats={payload.stats}
      initialProgressionRows={payload.progression}
    />
  );
}
