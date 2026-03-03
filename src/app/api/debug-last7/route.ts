import { NextResponse } from "next/server";
import { cookies } from "next/headers";
import { createHmac } from "crypto";
import { getSupabaseAdmin } from "@/lib/supabase-server";

const ADMIN_PASSWORD = process.env.ADMIN_PASSWORD;
const COOKIE_NAME = "admin_session";

function getSignedToken(): string {
  if (!ADMIN_PASSWORD) return "";
  return createHmac("sha256", ADMIN_PASSWORD).update("admin_session").digest("base64url");
}

async function isAdmin(): Promise<boolean> {
  if (!ADMIN_PASSWORD) return false;
  const cookieStore = await cookies();
  const token = cookieStore.get(COOKIE_NAME)?.value;
  return token === getSignedToken();
}

/** GET /api/debug-last7 - Returns all settled bets from last 7 days for verification. Admin only. */
export async function GET() {
  if (!(await isAdmin())) return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  let supabase;
  try {
    supabase = getSupabaseAdmin();
  } catch {
    return NextResponse.json({ error: "Server misconfigured" }, { status: 500 });
  }

  const sevenDaysAgo = new Date();
  sevenDaysAgo.setDate(sevenDaysAgo.getDate() - 7);

  const { data, error } = await supabase
    .from("bets")
    .select("id, event, selection, odds, stake, profit_loss, settled_at, market, category, status")
    .in("status", ["won", "lost"])
    .not("settled_at", "is", null)
    .gte("settled_at", sevenDaysAgo.toISOString())
    .order("settled_at", { ascending: false });

  if (error) return NextResponse.json({ error: error.message }, { status: 500 });

  const sum = (data || []).reduce((s, b) => s + (Number(b.profit_loss) || 0), 0);

  return NextResponse.json({
    sevenDaysAgo: sevenDaysAgo.toISOString(),
    count: (data || []).length,
    totalProfit: sum,
    bets: data || [],
  });
}
