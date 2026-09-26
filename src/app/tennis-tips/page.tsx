import Link from "next/link";
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
    <>
    <div className="mx-auto max-w-7xl px-4 py-4 text-sm text-slate-300"><Link prefetch={false} href="/tennis-matchup" className="inline-flex min-h-11 items-center gap-2 text-emerald-200">Research a matchup: H2H, aces and serve statistics →</Link></div>
    <TennisTipsClient
      initialPendingBets={payload.pending}
      initialRecentBets={payload.recent}
      initialStats={payload.stats}
      initialProgressionRows={payload.progression}
    />
    </>
  );
}
