import TrackRecordClient from "./TrackRecordClient";
import { fetchRecordMarketStats, fetchMonthlyPayload } from "@/lib/public-record";

// Admin settlements invalidate this route; the long fallback TTL limits Vercel work.
export const revalidate = 86400;

export default async function TrackRecordPage() {
  const [stats, monthly] = await Promise.all([
    fetchRecordMarketStats(),
    fetchMonthlyPayload("combined").catch(() => undefined),
  ]);
  return <TrackRecordClient initialStats={stats} initialMonthly={monthly} />;
}
