import { NextResponse } from "next/server";

import { isAdminSession } from "@/lib/admin-auth";
import { getSupabaseAdmin } from "@/lib/supabase-server";
import { TELEGRAM_CLICK_TABLE, utcDayKey } from "@/lib/telegram-clicks";

export const dynamic = "force-dynamic";
export const runtime = "nodejs";

type ClickRow = {
  source: string;
  clicked_at: string;
  visitor_hash: string | null;
  country_code: string | null;
  device_type: string | null;
  browser_family: string | null;
};

type PeriodSummary = {
  clicks: number;
  unique_visitors: number;
};

function startOfUtcDay(date: Date): Date {
  return new Date(Date.UTC(date.getUTCFullYear(), date.getUTCMonth(), date.getUTCDate()));
}

function countUniqueVisitors(rows: ClickRow[]): number {
  return new Set(rows.map((row) => row.visitor_hash).filter(Boolean)).size;
}

function summarizePeriod(rows: ClickRow[], start: Date): PeriodSummary {
  const periodRows = rows.filter((row) => new Date(row.clicked_at) >= start);
  return { clicks: periodRows.length, unique_visitors: countUniqueVisitors(periodRows) };
}

function buildBreakdown(rows: ClickRow[], selectKey: (row: ClickRow) => string) {
  const groups = new Map<string, { clicks: number; visitors: Set<string> }>();

  for (const row of rows) {
    const key = selectKey(row) || "unknown";
    const group = groups.get(key) ?? { clicks: 0, visitors: new Set<string>() };
    group.clicks += 1;
    if (row.visitor_hash) group.visitors.add(row.visitor_hash);
    groups.set(key, group);
  }

  return [...groups.entries()]
    .map(([key, value]) => ({ key, clicks: value.clicks, unique_visitors: value.visitors.size }))
    .sort((a, b) => b.clicks - a.clicks || a.key.localeCompare(b.key));
}

async function readClickRows(thirtyDayStart: Date): Promise<{ rows: ClickRow[]; enrichedSchema: boolean }> {
  const supabase = getSupabaseAdmin();
  const enriched = await supabase
    .from(TELEGRAM_CLICK_TABLE)
    .select("source, clicked_at, visitor_hash, country_code, device_type, browser_family")
    .gte("clicked_at", thirtyDayStart.toISOString())
    .order("clicked_at", { ascending: true })
    .limit(10_000);

  if (!enriched.error) return { rows: (enriched.data ?? []) as ClickRow[], enrichedSchema: true };

  // During a rolling schema deployment, preserve the original total-click dashboard.
  if (enriched.error.code !== "PGRST204" && !/column .* does not exist/i.test(enriched.error.message)) {
    throw new Error(enriched.error.message);
  }

  const legacy = await supabase
    .from(TELEGRAM_CLICK_TABLE)
    .select("source, clicked_at")
    .gte("clicked_at", thirtyDayStart.toISOString())
    .order("clicked_at", { ascending: true })
    .limit(10_000);
  if (legacy.error) throw new Error(legacy.error.message);

  return {
    rows: (legacy.data ?? []).map((row) => ({
      source: row.source,
      clicked_at: row.clicked_at,
      visitor_hash: null,
      country_code: null,
      device_type: null,
      browser_family: null,
    })),
    enrichedSchema: false,
  };
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

    const { rows, enrichedSchema } = await readClickRows(thirtyDayStart);
    const enrichedRows = rows.filter((row) => Boolean(row.visitor_hash));
    const geographicRows = rows.filter((row) => Boolean(row.country_code));
    const uniqueThirtyDays = countUniqueVisitors(enrichedRows);
    const dailyCounts = new Map<string, ClickRow[]>();

    for (const row of rows) {
      const day = utcDayKey(row.clicked_at);
      if (day) dailyCounts.set(day, [...(dailyCounts.get(day) ?? []), row]);
    }

    const daily = Array.from({ length: 30 }, (_, index) => {
      const date = new Date(thirtyDayStart);
      date.setUTCDate(date.getUTCDate() + index);
      const day = utcDayKey(date);
      const dayRows = dailyCounts.get(day) ?? [];
      return { day, clicks: dayRows.length, unique_visitors: countUniqueVisitors(dayRows) };
    });

    return NextResponse.json({
      generated_at: now.toISOString(),
      timezone: "UTC",
      totals: {
        today: summarizePeriod(rows, todayStart),
        seven_days: summarizePeriod(rows, sevenDayStart),
        thirty_days: { clicks: rows.length, unique_visitors: uniqueThirtyDays },
      },
      engagement: {
        repeat_clicks: Math.max(0, enrichedRows.length - uniqueThirtyDays),
        repeat_rate: enrichedRows.length
          ? Number((((enrichedRows.length - uniqueThirtyDays) / enrichedRows.length) * 100).toFixed(1))
          : 0,
      },
      coverage: {
        schema_ready: enrichedSchema,
        identifiable_clicks: enrichedRows.length,
        identifiable_percent: rows.length ? Number(((enrichedRows.length / rows.length) * 100).toFixed(1)) : 0,
        geographic_clicks: geographicRows.length,
        geographic_percent: rows.length ? Number(((geographicRows.length / rows.length) * 100).toFixed(1)) : 0,
        unique_tracking_since: enrichedRows[0]?.clicked_at ?? null,
      },
      daily,
      sources: buildBreakdown(rows, (row) => row.source).map(({ key: source, ...item }) => ({ source, ...item })),
      countries: buildBreakdown(rows, (row) => row.country_code?.toUpperCase() || "unknown")
        .map(({ key: country, ...item }) => ({ country, ...item })),
      devices: buildBreakdown(rows, (row) => row.device_type || "unknown")
        .map(({ key: device, ...item }) => ({ device, ...item })),
      browsers: buildBreakdown(rows, (row) => row.browser_family || "unknown")
        .map(({ key: browser, ...item }) => ({ browser, ...item })),
    });
  } catch (error) {
    const message = error instanceof Error ? error.message : "Unable to load Telegram clicks";
    return NextResponse.json({ error: message }, { status: 500 });
  }
}
