import { NextResponse } from "next/server";

import { isAdminSession } from "@/lib/admin-auth";
import { getSupabaseAdmin } from "@/lib/supabase-server";
import { TELEGRAM_CLICK_TABLE, utcDayKey } from "@/lib/telegram-clicks";

export const dynamic = "force-dynamic";
export const runtime = "nodejs";

type ClickRow = {
  source: string;
  clicked_at: string;
};

function startOfUtcDay(date: Date): Date {
  return new Date(Date.UTC(date.getUTCFullYear(), date.getUTCMonth(), date.getUTCDate()));
}

export async function GET() {
  if (!(await isAdminSession())) return NextResponse.json({ error: "Unauthorized" }, { status: 401 });

  try {
    const now = new Date();
    const todayStart = startOfUtcDay(now);
    const sevenDayStart = new Date(todayStart);
    sevenDayStart.setUTCDate(sevenDayStart.getUTCDate() - 6);
    const thirtyDayStart = new Date(todayStart);
    thirtyDayStart.setUTCDate(thirtyDayStart.getUTCDate() - 29);

    const { data, error } = await getSupabaseAdmin()
      .from(TELEGRAM_CLICK_TABLE)
      .select("source, clicked_at")
      .gte("clicked_at", thirtyDayStart.toISOString())
      .order("clicked_at", { ascending: true })
      .limit(10_000);

    if (error) throw new Error(error.message);

    const rows = (data ?? []) as ClickRow[];
    const dailyCounts = new Map<string, number>();
    const sourceCounts = new Map<string, number>();

    for (const row of rows) {
      const day = utcDayKey(row.clicked_at);
      if (day) dailyCounts.set(day, (dailyCounts.get(day) ?? 0) + 1);
      const source = row.source || "unknown";
      sourceCounts.set(source, (sourceCounts.get(source) ?? 0) + 1);
    }

    const daily = Array.from({ length: 30 }, (_, index) => {
      const date = new Date(thirtyDayStart);
      date.setUTCDate(date.getUTCDate() + index);
      const day = utcDayKey(date);
      return { day, clicks: dailyCounts.get(day) ?? 0 };
    });

    const sources = [...sourceCounts.entries()]
      .map(([source, clicks]) => ({ source, clicks }))
      .sort((a, b) => b.clicks - a.clicks || a.source.localeCompare(b.source));

    return NextResponse.json({
      generated_at: now.toISOString(),
      timezone: "UTC",
      totals: {
        today: rows.filter((row) => new Date(row.clicked_at) >= todayStart).length,
        seven_days: rows.filter((row) => new Date(row.clicked_at) >= sevenDayStart).length,
        thirty_days: rows.length,
      },
      daily,
      sources,
    });
  } catch (error) {
    const message = error instanceof Error ? error.message : "Unable to load Telegram clicks";
    return NextResponse.json({ error: message }, { status: 500 });
  }
}
