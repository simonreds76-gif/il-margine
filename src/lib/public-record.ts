import "server-only";

import { getSupabaseAdmin, hasSupabaseAdminConfig } from "@/lib/supabase-server";

const TIMEOUT_MS = 8000;

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

function emptyHomePayload() {
  return { stats: [], recent: [], pending: [], last7: null };
}

function emptyMarketPayload() {
  return { pending: [], recent: [], stats: [] };
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

export async function fetchHomePayload() {
  if (!hasSupabaseAdminConfig()) return emptyHomePayload();

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

export async function fetchMarketPayload(scope: "tennis" | "props") {
  if (!hasSupabaseAdminConfig()) return emptyMarketPayload();

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

export async function fetchCalculatorPayload() {
  if (!hasSupabaseAdminConfig()) return { stats: [] };

  const supabase = getSupabaseAdmin();
  const response = await withTimeout(supabase.from("category_stats").select("*"), "public calculator stats query");
  if (response.error) throw new Error(response.error.message);
  return { stats: response.data ?? [] };
}

export async function fetchMonthlyPayload(monthlyScope: MonthlyScope) {
  if (!hasSupabaseAdminConfig()) return { show: false, rows: [] };

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
