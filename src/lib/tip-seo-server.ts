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
  approved: Array<{ bet: SeoTipBet; assessment: TipSeoAssessment }>;
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
    (bet) => tipFixtureKey(bet) === seedFixtureKey,
  );
  if (!bets.length) return null;
  const approved = bets
    .map((bet) => ({ bet, assessment: assessTipSeoReadiness(bet) }))
    .filter((entry) => entry.assessment.eligible);
  if (!approved.length) return null;

  const canonicalId = Math.min(...approved.map((entry) => entry.bet.id));
  const canonicalBet = approved.find((entry) => entry.bet.id === canonicalId)?.bet ?? seed;
  return {
    seed,
    bets,
    approved,
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
  const [approvedResponse, latestResponse] = await Promise.all([
    supabase
      .from("bets")
      .select("id, market, event, match_date, notes, posted_at, settled_at")
      .in("market", ["tennis", "props"])
      .like("notes", "[[SEO_READY_V1]]%")
      .order("posted_at", { ascending: false })
      .limit(1000),
    supabase
      .from("bets")
      .select("market, posted_at, settled_at")
      .in("market", ["tennis", "props"])
      .order("posted_at", { ascending: false })
      .limit(200),
  ]);

  if (approvedResponse.error) {
    console.error("[tip-seo] sitemap preview query failed", approvedResponse.error.message);
  }
  if (latestResponse.error) {
    console.error("[tip-seo] sitemap hub freshness query failed", latestResponse.error.message);
  }

  const grouped = new Map<string, SitemapTipRow[]>();
  for (const raw of (approvedResponse.data ?? []) as SitemapTipRow[]) {
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
