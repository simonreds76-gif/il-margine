import { NextResponse } from "next/server";
import { getSupabaseAdmin } from "@/lib/supabase-server";
import { createBoundedAsyncCache } from "@/lib/bounded-async-cache";
import { getDisplayBetCategory } from "@/lib/bet-category";

export const dynamic = "force-dynamic";
export const runtime = "nodejs";

const CACHE_HEADER = "public, s-maxage=90, stale-while-revalidate=900";
// A shared 30-second response avoids repeating four database queries per
// visitor/focus event. No stale-while-revalidate for current pending records.
const LIVE_RECORD_CACHE_HEADER = "public, max-age=0, s-maxage=30, must-revalidate";
const TIMEOUT_MS = 8000;
const MARKET_RECENT_LIMIT = 500;

type PublicScope = "home" | "tennis" | "props" | "calculator" | "monthly";
type MonthlyScope = "combined" | "props" | "tennis";

const MARKET_BY_SCOPE: Record<"tennis" | "props", string> = {
  tennis: "tennis",
  props: "props",
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

type MonthlyBetRow = {
  match_date: string | null;
  settled_at: string | null;
  status: string | null;
  stake: number | string | null;
  profit_loss: number | string | null;
};

type MonthlyAccumulator = {
  month: string;
  total_bets: number;
  wins: number;
  losses: number;
  total_stake: number;
  total_profit: number;
};

type ProgressionBetRow = {
  id: number;
  market: string | null;
  category: string | null;
  event: string | null;
  player: string | null;
  selection: string | null;
  status: string | null;
  stake: number | string | null;
  profit_loss: number | string | null;
  match_date: string | null;
  settled_at: string | null;
  posted_at: string | null;
};

function roundUnits(value: number): number {
  return Math.round((value + Number.EPSILON) * 10000) / 10000;
}

function monthKeyFromBet(row: MonthlyBetRow): string | null {
  const raw = row.match_date || row.settled_at;
  if (!raw || raw.length < 7) return null;
  return raw.slice(0, 7);
}

function buildMonthlyRows(rows: MonthlyBetRow[]) {
  const byMonth = new Map<string, MonthlyAccumulator>();

  for (const row of rows) {
    const status = (row.status || "").toLowerCase();
    if (status !== "won" && status !== "lost") continue;

    const month = monthKeyFromBet(row);
    if (!month) continue;

    const stake = Number(row.stake);
    const profit = Number(row.profit_loss);
    const safeStake = Number.isFinite(stake) && stake > 0 ? stake : 1;
    const safeProfit = Number.isFinite(profit) ? profit : status === "lost" ? -safeStake : 0;

    const acc = byMonth.get(month) ?? {
      month,
      total_bets: 0,
      wins: 0,
      losses: 0,
      total_stake: 0,
      total_profit: 0,
    };

    acc.total_bets += 1;
    if (status === "won") acc.wins += 1;
    if (status === "lost") acc.losses += 1;
    acc.total_stake += safeStake;
    acc.total_profit += safeProfit;
    byMonth.set(month, acc);
  }

  return Array.from(byMonth.values())
    .sort((a, b) => b.month.localeCompare(a.month))
    .slice(0, 24)
    .map((row) => {
      const totalStake = roundUnits(row.total_stake);
      const totalProfit = roundUnits(row.total_profit);
      return {
        month: row.month,
        total_bets: row.total_bets,
        wins: row.wins,
        losses: row.losses,
        total_stake: totalStake,
        total_profit: totalProfit,
        roi: totalStake > 0 ? roundUnits((totalProfit / totalStake) * 100) : 0,
      };
    });
}

function buildProgressionRows(rows: ProgressionBetRow[]) {
  return rows
    .filter((row) => {
      const status = (row.status || "").toLowerCase();
      const profit = Number(row.profit_loss);
      return (status === "won" || status === "lost") && Number.isFinite(profit);
    })
    .sort((a, b) => {
      const aDate = a.match_date || a.settled_at || a.posted_at || "";
      const bDate = b.match_date || b.settled_at || b.posted_at || "";
      const dateCompare = aDate.localeCompare(bDate);
      if (dateCompare !== 0) return dateCompare;
      return (a.id || 0) - (b.id || 0);
    })
    .map((row) => ({
      id: row.id,
      date: row.match_date || row.settled_at || row.posted_at || null,
      category: getDisplayBetCategory({ market: row.market, category: row.category, event: row.event }),
      event: row.event || "Unknown event",
      player: row.player || "",
      selection: row.selection || "Selection",
      status: row.status || "settled",
      stake: roundUnits(Number(row.stake) || 0),
      profit_loss: roundUnits(Number(row.profit_loss) || 0),
    }));
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

  const [pendingResponse, recentResponse, categoryStatsResponse, progressionResponse] = await withTimeout(
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
        .limit(MARKET_RECENT_LIMIT),
      supabase.from("category_stats").select("*").eq("market", market),
      supabase
        .from("bets")
        .select("id, market, category, event, player, selection, status, stake, profit_loss, match_date, settled_at, posted_at")
        .eq("market", market)
        .in("status", ["won", "lost"])
        .not("profit_loss", "is", null)
        .order("match_date", { ascending: true, nullsFirst: false })
        .order("settled_at", { ascending: true, nullsFirst: false })
        .order("posted_at", { ascending: true, nullsFirst: false })
        .order("id", { ascending: true })
        .limit(5000),
    ]),
    `public ${scope} record query`,
  );

  const error = pendingResponse.error || recentResponse.error || categoryStatsResponse.error || progressionResponse.error;
  if (error) throw new Error(error.message);

  return {
    pending: pendingResponse.data ?? [],
    recent: recentResponse.data ?? [],
    stats: categoryStatsResponse.data ?? [],
    progression: buildProgressionRows((progressionResponse.data ?? []) as ProgressionBetRow[]),
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

  const settingResponse = await withTimeout(
    supabase.from("site_settings").select("value").eq("key", settingKey).single(),
    `monthly ${monthlyScope} setting query`,
  );
  if (settingResponse.error) throw new Error(settingResponse.error.message);

  const show = settingResponse.data?.value === true;
  if (!show) return { show: false, rows: [] };

  let rowsQuery = supabase
    .from("bets")
    .select("match_date, settled_at, status, stake, profit_loss")
    .in("status", ["won", "lost"])
    .not("profit_loss", "is", null)
    .order("match_date", { ascending: false, nullsFirst: false })
    .limit(5000);

  if (monthlyScope === "props" || monthlyScope === "tennis") {
    rowsQuery = rowsQuery.eq("market", MARKET_BY_SCOPE[monthlyScope]);
  }

  const rowsResponse = await withTimeout(rowsQuery, `monthly ${monthlyScope} raw bets query`);
  if (rowsResponse.error) throw new Error(rowsResponse.error.message);

  return {
    show: true,
    rows: buildMonthlyRows((rowsResponse.data ?? []) as MonthlyBetRow[]),
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

// Canonical scope keys also coalesce simultaneous CDN misses/query variants.
// Seven valid keys maximum; failures are never cached.
const payloadCache = createBoundedAsyncCache<unknown>(7);

export async function GET(request: Request) {
  const url = new URL(request.url);
  const scope = parseScope(url.searchParams.get("scope"));

  try {
    if (scope === "home") return cachedJson(await payloadCache.get(scope, 15_000, fetchHomePayload), LIVE_RECORD_CACHE_HEADER);
    if (scope === "tennis" || scope === "props") {
      return cachedJson(await payloadCache.get(scope, 15_000, () => fetchMarketPayload(scope)), LIVE_RECORD_CACHE_HEADER);
    }
    if (scope === "calculator") return cachedJson(await payloadCache.get(scope, 30_000, fetchCalculatorPayload));
    const monthlyScope = parseMonthlyScope(url.searchParams.get("monthlyScope"));
    return cachedJson(await payloadCache.get(`monthly:${monthlyScope}`, 30_000, () => fetchMonthlyPayload(monthlyScope)));
  } catch (error) {
    const message = error instanceof Error ? error.message : "Unknown public record query error";
    return errorJson(message);
  }
}
