import { NextResponse } from "next/server";
import { getSupabaseAdmin } from "@/lib/supabase-server";

export const dynamic = "force-dynamic";
export const runtime = "nodejs";

const CACHE_HEADER = "public, s-maxage=90, stale-while-revalidate=900";
const LIVE_RECORD_CACHE_HEADER = "no-store";
const TIMEOUT_MS = 8000;

type PublicScope = "home" | "tennis" | "props" | "calculator" | "monthly";
type MonthlyScope = "combined" | "props" | "tennis";

const MARKET_BY_SCOPE: Record<"tennis" | "props", string> = {
  tennis: "tennis",
  props: "props",
};

const MONTHLY_VIEW_BY_SCOPE: Record<MonthlyScope, string> = {
  combined: "monthly_stats",
  props: "monthly_stats_props",
  tennis: "monthly_stats_tennis",
};

const MONTHLY_SETTING_BY_SCOPE: Record<MonthlyScope, string> = {
  combined: "monthly_breakdown_combined_public",
  props: "monthly_breakdown_props_public",
  tennis: "monthly_breakdown_tennis_public",
};

function cachedJson(payload: unknown, cacheHeader = CACHE_HEADER) {
  const res = NextResponse.json({
    ...((payload && typeof payload === "object") ? payload : { data: payload }),
    cachedAt: new Date().toISOString(),
  });
  res.headers.set("Cache-Control", cacheHeader);
  return res;
}

function errorJson(message: string, status = 500) {
  const res = NextResponse.json({ error: message, cachedAt: new Date().toISOString() }, { status });
  res.headers.set("Cache-Control", "no-store");
  return res;
}

async function withTimeout<T>(promise: PromiseLike<T>, label: string): Promise<T> {
  let timer: ReturnType<typeof setTimeout> | null = null;
  const timeout = new Promise<never>((_, reject) => {
    timer = setTimeout(() => reject(new Error(`${label} timed out after ${TIMEOUT_MS}ms`)), TIMEOUT_MS);
  });

  try {
    return await Promise.race([promise, timeout]);
  } finally {
    if (timer) clearTimeout(timer);
  }
}

async function fetchHomePayload() {
  const supabase = getSupabaseAdmin();
  const sevenDaysAgo = new Date();
  sevenDaysAgo.setDate(sevenDaysAgo.getDate() - 7);
  const cutoff = sevenDaysAgo.toISOString();

  const [statsResponse, recentResponse, pendingResponse, last7Response] = await withTimeout(
    Promise.all([
      supabase.from("market_stats").select("*"),
      supabase
        .from("bets")
        .select("*, bookmaker:bookmakers(*)")
        .in("status", ["won", "lost", "void"])
        .order("match_date", { ascending: false, nullsFirst: false })
        .order("settled_at", { ascending: false, nullsFirst: false })
        .order("posted_at", { ascending: false, nullsFirst: false })
        .order("id", { ascending: false })
        .limit(5),
      supabase
        .from("bets")
        .select("*, bookmaker:bookmakers(*)")
        .eq("status", "pending")
        .order("posted_at", { ascending: false })
        .limit(20),
      supabase
        .from("bets")
        .select("profit_loss")
        .in("status", ["won", "lost"])
        .not("settled_at", "is", null)
        .gte("settled_at", cutoff),
    ]),
    "public home record query",
  );

  const error = statsResponse.error || recentResponse.error || pendingResponse.error || last7Response.error;
  if (error) throw new Error(error.message);

  const last7Rows = last7Response.data ?? [];
  const last7Total = last7Rows.reduce((sum, row) => sum + (Number(row.profit_loss) || 0), 0);

  return {
    stats: statsResponse.data ?? [],
    recent: recentResponse.data ?? [],
    pending: pendingResponse.data ?? [],
    last7: {
      total: last7Total,
      count: last7Rows.length,
    },
  };
}

async function fetchMarketPayload(scope: "tennis" | "props") {
  const supabase = getSupabaseAdmin();
  const market = MARKET_BY_SCOPE[scope];

  const [pendingResponse, recentResponse, categoryStatsResponse] = await withTimeout(
    Promise.all([
      supabase
        .from("bets")
        .select("*, bookmaker:bookmakers(*)")
        .eq("market", market)
        .eq("status", "pending")
        .order("posted_at", { ascending: false })
        .limit(50),
      supabase
        .from("bets")
        .select("*, bookmaker:bookmakers(*)")
        .eq("market", market)
        .in("status", ["won", "lost", "void"])
        .order("match_date", { ascending: false, nullsFirst: false })
        .order("settled_at", { ascending: false, nullsFirst: false })
        .order("posted_at", { ascending: false, nullsFirst: false })
        .order("id", { ascending: false })
        .limit(50),
      supabase.from("category_stats").select("*").eq("market", market),
    ]),
    `public ${scope} record query`,
  );

  const error = pendingResponse.error || recentResponse.error || categoryStatsResponse.error;
  if (error) throw new Error(error.message);

  return {
    pending: pendingResponse.data ?? [],
    recent: recentResponse.data ?? [],
    stats: categoryStatsResponse.data ?? [],
  };
}

async function fetchCalculatorPayload() {
  const supabase = getSupabaseAdmin();
  const response = await withTimeout(supabase.from("category_stats").select("*"), "public calculator stats query");
  if (response.error) throw new Error(response.error.message);
  return { stats: response.data ?? [] };
}

async function fetchMonthlyPayload(monthlyScope: MonthlyScope) {
  const supabase = getSupabaseAdmin();
  const settingKey = MONTHLY_SETTING_BY_SCOPE[monthlyScope];
  const view = MONTHLY_VIEW_BY_SCOPE[monthlyScope];

  const settingResponse = await withTimeout(
    supabase.from("site_settings").select("value").eq("key", settingKey).single(),
    `monthly ${monthlyScope} setting query`,
  );
  if (settingResponse.error) throw new Error(settingResponse.error.message);

  const show = settingResponse.data?.value === true;
  if (!show) return { show: false, rows: [] };

  const rowsResponse = await withTimeout(
    supabase.from(view).select("*").order("month", { ascending: false }).limit(24),
    `monthly ${monthlyScope} rows query`,
  );
  if (rowsResponse.error) throw new Error(rowsResponse.error.message);

  return {
    show: true,
    rows: rowsResponse.data ?? [],
  };
}

function parseScope(value: string | null): PublicScope {
  if (value === "home" || value === "tennis" || value === "props" || value === "calculator" || value === "monthly") {
    return value;
  }
  return "home";
}

function parseMonthlyScope(value: string | null): MonthlyScope {
  if (value === "combined" || value === "props" || value === "tennis") return value;
  return "combined";
}

export async function GET(request: Request) {
  const url = new URL(request.url);
  const scope = parseScope(url.searchParams.get("scope"));

  try {
    if (scope === "home") return cachedJson(await fetchHomePayload(), LIVE_RECORD_CACHE_HEADER);
    if (scope === "tennis" || scope === "props") {
      return cachedJson(await fetchMarketPayload(scope), LIVE_RECORD_CACHE_HEADER);
    }
    if (scope === "calculator") return cachedJson(await fetchCalculatorPayload());
    return cachedJson(await fetchMonthlyPayload(parseMonthlyScope(url.searchParams.get("monthlyScope"))));
  } catch (error) {
    const message = error instanceof Error ? error.message : "Unknown public record query error";
    return errorJson(message);
  }
}
