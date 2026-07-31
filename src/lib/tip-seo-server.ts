import "server-only";

import { cache } from "react";
import { getSupabaseAdmin, hasSupabaseAdminConfig } from "@/lib/supabase-server";
import {
  assessTipSeoReadiness,
  tipFixtureKey,
  tipPreviewPath,
  type TipSeoAssessment,
} from "@/lib/tip-seo";

export type SeoTipBet = {
  id: number;
  market: string;
  category: string;
  event: string;
  player: string | null;
  selection: string;
  odds: number;
  stake: number;
  status: string;
  profit_loss: number | null;
  posted_at: string;
  settled_at: string | null;
  match_date: string;
  notes: string | null;
  bookmaker?: {
    id: number;
    name: string;
    short_name: string;
    affiliate_link: string | null;
    active: boolean;
  } | null;
};

export type SeoTipFixture = {
  seed: SeoTipBet;
  bets: SeoTipBet[];
  analyses: Array<{ bet: SeoTipBet; assessment: TipSeoAssessment }>;
  canonicalId: number;
  canonicalPath: string;
  datePublished: string;
  dateModified: string;
};

type SitemapTipRow = Pick<
  SeoTipBet,
  "id" | "market" | "event" | "match_date" | "notes" | "posted_at" | "settled_at"
>;

function maxTimestamp(values: Array<string | null | undefined>): string {
  return values.filter(Boolean).sort().at(-1) || new Date(0).toISOString();
}

function minTimestamp(values: Array<string | null | undefined>): string {
  return values.filter(Boolean).sort().at(0) || new Date(0).toISOString();
}

export const fetchSeoTipFixture = cache(async (seedId: number): Promise<SeoTipFixture | null> => {
  if (!hasSupabaseAdminConfig()) return null;
  const supabase = getSupabaseAdmin();
  const seedResponse = await supabase
    .from("bets")
    .select("*, bookmaker:bookmakers(*)")
    .eq("id", seedId)
    .single();
  if (seedResponse.error || !seedResponse.data) return null;

  const seed = seedResponse.data as SeoTipBet;
  if (!assessTipSeoReadiness(seed).eligible) return null;

  const fixtureResponse = await supabase
    .from("bets")
    .select("*, bookmaker:bookmakers(*)")
    .eq("market", seed.market)
    .eq("match_date", seed.match_date)
    .order("id", { ascending: true });
  if (fixtureResponse.error || !fixtureResponse.data?.length) return null;

  const seedFixtureKey = tipFixtureKey(seed);
  const bets = (fixtureResponse.data as SeoTipBet[]).filter(
    (bet) => tipFixtureKey(bet) === seedFixtureKey && assessTipSeoReadiness(bet).eligible,
  );
  if (!bets.length) return null;
  const analyses = bets
    .map((bet) => ({ bet, assessment: assessTipSeoReadiness(bet) }))
    .filter((entry) => Boolean(entry.assessment.analysis.trim()));

  const canonicalId = Math.min(...bets.map((bet) => bet.id));
  const canonicalBet = bets.find((bet) => bet.id === canonicalId) ?? seed;
  return {
    seed: canonicalBet,
    bets,
    analyses,
    canonicalId,
    canonicalPath: tipPreviewPath(canonicalBet),
    datePublished: minTimestamp(bets.map((bet) => bet.posted_at)),
    dateModified: maxTimestamp(bets.flatMap((bet) => [bet.posted_at, bet.settled_at])),
  };
});

export async function fetchSeoTipSitemapState(): Promise<{
  previews: Array<{ url: string; lastModified: Date }>;
  latestByMarket: Partial<Record<"tennis" | "props", Date>>;
}> {
  if (!hasSupabaseAdminConfig()) return { previews: [], latestByMarket: {} };
  const supabase = getSupabaseAdmin();
  const sitemapCutoff = new Date(Date.now() - 400 * 24 * 60 * 60 * 1000).toISOString().slice(0, 10);
  const previewRowsPromise = (async () => {
    const rows: SitemapTipRow[] = [];
    const pageSize = 1000;
    const maxRows = 3000;
    for (let offset = 0; offset < maxRows; offset += pageSize) {
      const response = await supabase
        .from("bets")
        .select("id, market, event, match_date, notes, posted_at, settled_at")
        .in("market", ["tennis", "props"])
        .gte("match_date", sitemapCutoff)
        .order("posted_at", { ascending: false })
        .range(offset, offset + pageSize - 1);
      if (response.error) return { rows, error: response.error.message };
      const page = (response.data ?? []) as SitemapTipRow[];
      rows.push(...page);
      if (page.length < pageSize) break;
    }
    return { rows, error: null };
  })();
  const [previewResult, latestResponse] = await Promise.all([
    previewRowsPromise,
    supabase
      .from("bets")
      .select("market, posted_at, settled_at")
      .in("market", ["tennis", "props"])
      .order("posted_at", { ascending: false })
      .limit(200),
  ]);

  if (previewResult.error) {
    console.error("[tip-seo] sitemap preview query failed", previewResult.error);
  }
  if (latestResponse.error) {
    console.error("[tip-seo] sitemap hub freshness query failed", latestResponse.error.message);
  }

  const grouped = new Map<string, SitemapTipRow[]>();
  for (const raw of previewResult.rows) {
    if (!assessTipSeoReadiness(raw).eligible) continue;
    const key = tipFixtureKey(raw);
    const rows = grouped.get(key) ?? [];
    rows.push(raw);
    grouped.set(key, rows);
  }

  const previews = Array.from(grouped.values()).map((rows) => {
    const canonical = [...rows].sort((a, b) => a.id - b.id)[0]!;
    const lastModified = maxTimestamp(rows.flatMap((row) => [row.posted_at, row.settled_at]));
    return {
      url: tipPreviewPath(canonical),
      lastModified: new Date(lastModified),
    };
  });

  const latestByMarket: Partial<Record<"tennis" | "props", Date>> = {};
  for (const row of latestResponse.data ?? []) {
    const market = row.market as "tennis" | "props";
    if (market !== "tennis" && market !== "props") continue;
    const timestamp = maxTimestamp([row.posted_at, row.settled_at]);
    const date = new Date(timestamp);
    if (!latestByMarket[market] || date > latestByMarket[market]!) {
      latestByMarket[market] = date;
    }
  }

  return { previews, latestByMarket };
}
