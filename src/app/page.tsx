import HomepageClient from "./HomepageClient";
import { fetchHomePayload, fetchMonthlyPayload } from "@/lib/public-record";
import { CURRENTLY_WATCHING, HOMEPAGE_LAB_NOTES } from "@/lib/resources";

// Admin bet mutations invalidate this page immediately. The hourly value is a
// safety net for automated settlements that write directly to Supabase.
export const revalidate = 3600;

export default async function Home() {
  const [payload, monthlyPayload] = await Promise.all([
    fetchHomePayload().catch((error) => {
      console.error("[home] failed to load initial public record", error);
      return { stats: [], recent: [], pending: [], last7: null };
    }),
    fetchMonthlyPayload("combined").catch((error) => {
      console.error("[home] failed to load initial monthly breakdown", error);
      return undefined;
    }),
  ]);

  return (
    <HomepageClient
      initialMarketStats={payload.stats}
      initialRecentBets={payload.recent}
      initialPendingBets={payload.pending}
      initialLast7={payload.last7}
      initialMonthlyPayload={monthlyPayload}
      initialLabNotes={HOMEPAGE_LAB_NOTES}
      currentlyWatching={CURRENTLY_WATCHING}
    />
  );
}
