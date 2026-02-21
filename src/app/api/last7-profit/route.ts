import { NextResponse } from "next/server";
import { getSupabaseAdmin } from "@/lib/supabase-server";

export const dynamic = "force-dynamic";

/** GET /api/last7-profit - Sum of profit_loss for all settled bets in last 7 days. Server-side, bypasses RLS. */
export async function GET() {
  let supabase;
  try {
    supabase = getSupabaseAdmin();
  } catch {
    return NextResponse.json({ error: "Server misconfigured", total: 0, count: 0 }, { status: 500 });
  }

  // Use start of day 7 days ago (UTC) to avoid timezone edge cases
  const sevenDaysAgo = new Date();
  sevenDaysAgo.setUTCDate(sevenDaysAgo.getUTCDate() - 7);
  sevenDaysAgo.setUTCHours(0, 0, 0, 0);
  const cutoff = sevenDaysAgo.toISOString();

  const { data, error } = await supabase
    .from("bets")
    .select("profit_loss")
    .in("status", ["won", "lost"])
    .not("settled_at", "is", null)
    .gte("settled_at", cutoff);

  if (error) {
    return NextResponse.json({ error: error.message, total: 0, count: 0 }, { status: 500 });
  }

  const total = (data || []).reduce((s, b) => s + (Number(b.profit_loss) || 0), 0);
  const count = (data || []).length;

  const res = NextResponse.json({ total, count });
  res.headers.set("Cache-Control", "no-store, no-cache, must-revalidate");
  return res;
}
