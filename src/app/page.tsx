import HomepageClient from "./HomepageClient";
import { fetchHomePayload } from "@/lib/public-record";

// Admin bet mutations invalidate this page immediately. The daily value is a
// fallback for any automated settlement that writes directly to Supabase.
export const revalidate = 86400;

export default async function Home() {
  const payload = await fetchHomePayload().catch((error) => {
    console.error("[home] failed to load initial public record", error);
    return { stats: [], recent: [], pending: [], last7: null };
  });

  return (
    <HomepageClient
      initialMarketStats={payload.stats}
      initialRecentBets={payload.recent}
      initialPendingBets={payload.pending}
      initialLast7={payload.last7}
    />
  );
}
