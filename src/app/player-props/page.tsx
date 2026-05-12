import PlayerPropsClient from "./PlayerPropsClient";
import { fetchMarketPayload } from "@/lib/public-record";

export const revalidate = 60;

export default async function PlayerProps() {
  const payload = await fetchMarketPayload("props").catch((error) => {
    console.error("[player-props] failed to load initial public record", error);
    return { pending: [], recent: [], stats: [] };
  });

  return (
    <PlayerPropsClient
      initialPendingBets={payload.pending}
      initialRecentBets={payload.recent}
      initialStats={payload.stats}
    />
  );
}
