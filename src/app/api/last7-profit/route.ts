import { NextResponse } from "next/server";
import { getSupabaseAdmin } from "@/lib/supabase-server";

/** GET /api/last7-profit - Sum of profit_loss for all settled bets in last 7 days. Server-side, bypasses RLS. */
export async function GET() {
  let supabase;
  try {
    supabase = getSupabaseAdmin();
  } catch {
    return NextResponse.json({ error: "Server misconfigured", total: 0, count: 0 }, { status: 500 });
  }
  const sevenDaysAgo = new Date();
  sevenDaysAgo.setDate(sevenDaysAgo.getDate() - 7);

  const { data, error } = await supabase
    .from("bets")
    .select("profit_loss")
    .in("status", ["won", "lost"])
    .not("settled_at", "is", null)
    .gte("settled_at", sevenDaysAgo.toISOString());

  if (error) {
    return NextResponse.json({ error: error.message, total: 0, count: 0 }, { status: 500 });
  }

  const total = (data || []).reduce((s, b) => s + (Number(b.profit_loss) || 0), 0);
  const count = (data || []).length;

  return NextResponse.json({ total, count });
}
