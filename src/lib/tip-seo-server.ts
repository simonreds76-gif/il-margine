import "server-only";

import { cache } from "react";
import { getSupabaseAdmin, hasSupabaseAdminConfig } from "@/lib/supabase-server";
import {
  assessTipSeoReadiness,
  parseTipPreviewSlug,
  tipFixtureHash,
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
  allVoid: boolean;
};

type SitemapTipRow = Pick<
  SeoTipBet,
  | "id"
  | "market"
  | "category"
  | "event"
  | "match_date"
  | "odds"
  | "stake"
  | "status"
  | "posted_at"
  | "settled_at"
>;

const FIXTURE_PAGE_SIZE = 500;
const MAX_FIXTURE_DAY_PAGES = 40;
const SITEMAP_PAGE_SIZE = 1000;
const MAX_SITEMAP_PAGES = 100;

function maxTimestamp(values: Array<string | null | undefined>, fallback: string): string {
  const valid = values.filter(Boolean).sort();
  return valid.at(-1) || fallback;
}

function minTimestamp(values: Array<string | null | undefined>, fallback: string): string {
  const valid = values.filter(Boolean).sort();
  return valid.at(0) || fallback;
}

function fixtureFallbackTimestamp(matchDate: string): string {
  return `${matchDate}T12:00:00.000Z`;
}

function isFixtureEligible(bets: Array<Pick<SeoTipBet, keyof SitemapTipRow>>): boolean {
  return bets.some((bet) => assessTipSeoReadiness(bet).eligible);
}

async function fetchFixtureDayRows(
  market: "tennis" | "props",
  matchDate: string,
): Promise<SeoTipBet[]> {
  const rows: SeoTipBet[] = [];
  let afterId: number | null = null;

  for (let pageNumber = 0; pageNumber < MAX_FIXTURE_DAY_PAGES; pageNumber += 1) {
    let query = getSupabaseAdmin()
      .from("bets")
      .select("*, bookmaker:bookmakers(*)")
      .eq("market", market)
      .eq("match_date", matchDate)
      .order("id", { ascending: true })
      .limit(FIXTURE_PAGE_SIZE);
    if (afterId !== null) query = query.gt("id", afterId);

    const response = await query;
    if (response.error) {
      throw new Error(`[tip-seo] fixture query failed: ${response.error.message}`);
    }
    const page = (response.data ?? []) as SeoTipBet[];
    rows.push(...page);
    if (page.length < FIXTURE_PAGE_SIZE) return rows;
    afterId = page[page.length - 1].id;
  }

  throw new Error(
    `[tip-seo] fixture query exceeded ${FIXTURE_PAGE_SIZE * MAX_FIXTURE_DAY_PAGES} rows for ${market} ${matchDate}`,
  );
}

export const fetchSeoTipFixture = cache(async (slug: string): Promise<SeoTipFixture | null> => {
  if (!hasSupabaseAdminConfig()) return null;
  const parsed = parseTipPreviewSlug(slug);
  if (!parsed) return null;

  let rows: SeoTipBet[] = [];
  let fixtureRows: SeoTipBet[] = [];

  if (parsed.kind === "legacy") {
    const seedResponse = await getSupabaseAdmin()
      .from("bets")
      .select("*, bookmaker:bookmakers(*)")
      .eq("id", parsed.seedId)
      .maybeSingle();
    if (seedResponse.error) {
      throw new Error(`[tip-seo] legacy seed query failed: ${seedResponse.error.message}`);
    }
    if (!seedResponse.data) return null;
    const legacySeed = seedResponse.data as SeoTipBet;
    if (legacySeed.market !== "tennis" && legacySeed.market !== "props") return null;
    if (!legacySeed.match_date) return null;
    rows = await fetchFixtureDayRows(legacySeed.market, legacySeed.match_date);
    const key = tipFixtureKey(legacySeed);
    fixtureRows = rows.filter((bet) => tipFixtureKey(bet) === key);
  } else {
    rows = await fetchFixtureDayRows(parsed.market, parsed.matchDate);
    const grouped = new Map<string, SeoTipBet[]>();
    for (const bet of rows) {
      if (tipFixtureHash(bet) !== parsed.fixtureHash) continue;
      const key = tipFixtureKey(bet);
      const group = grouped.get(key) ?? [];
      group.push(bet);
      grouped.set(key, group);
    }
    if (grouped.size !== 1) return null;
    fixtureRows = Array.from(grouped.values())[0];
  }

  if (!fixtureRows.length || !isFixtureEligible(fixtureRows)) return null;
  const bets = [...fixtureRows].sort((left, right) => left.id - right.id);
  const seed = bets[0];
  const analyses = bets
    .map((bet) => ({ bet, assessment: assessTipSeoReadiness(bet) }))
    .filter((entry) => Boolean(entry.assessment.analysis.trim()));
  const fallbackTimestamp = fixtureFallbackTimestamp(seed.match_date);

  return {
    seed,
    bets,
    analyses,
    canonicalId: seed.id,
    canonicalPath: tipPreviewPath(seed),
    datePublished: minTimestamp(bets.map((bet) => bet.posted_at), fallbackTimestamp),
    dateModified: maxTimestamp(
      bets.flatMap((bet) => [bet.posted_at, bet.settled_at]),
      fallbackTimestamp,
    ),
    allVoid: bets.every((bet) => bet.status === "void"),
  };
});

async function fetchSitemapRows(sitemapCutoff: string): Promise<SitemapTipRow[]> {
  const rows: SitemapTipRow[] = [];
  let beforeId: number | null = null;

  for (let pageNumber = 0; pageNumber < MAX_SITEMAP_PAGES; pageNumber += 1) {
    let query = getSupabaseAdmin()
      .from("bets")
      .select("id, market, category, event, match_date, odds, stake, status, posted_at, settled_at")
      .in("market", ["tennis", "props"])
      .gte("match_date", sitemapCutoff)
      .order("id", { ascending: false })
      .limit(SITEMAP_PAGE_SIZE);
    if (beforeId !== null) query = query.lt("id", beforeId);

    const response = await query;
    if (response.error) {
      throw new Error(`[tip-seo] sitemap preview query failed: ${response.error.message}`);
    }
    const page = (response.data ?? []) as SitemapTipRow[];
    rows.push(...page);
    if (page.length < SITEMAP_PAGE_SIZE) return rows;
    beforeId = page[page.length - 1].id;
  }

  throw new Error(
    `[tip-seo] sitemap query exceeded ${SITEMAP_PAGE_SIZE * MAX_SITEMAP_PAGES} rows inside the 400-day window`,
  );
}

export async function fetchSeoTipSitemapState(): Promise<{
  previews: Array<{ url: string; lastModified: Date }>;
  latestByMarket: Partial<Record<"tennis" | "props", Date>>;
}> {
  if (!hasSupabaseAdminConfig()) return { previews: [], latestByMarket: {} };
  const sitemapCutoff = new Date(Date.now() - 400 * 24 * 60 * 60 * 1000).toISOString().slice(0, 10);
  const [previewRows, latestResponse] = await Promise.all([
    fetchSitemapRows(sitemapCutoff),
    getSupabaseAdmin()
      .from("bets")
      .select("market, posted_at, settled_at")
      .in("market", ["tennis", "props"])
      .order("id", { ascending: false })
      .limit(200),
  ]);

  if (latestResponse.error) {
    throw new Error(`[tip-seo] sitemap hub freshness query failed: ${latestResponse.error.message}`);
  }

  const grouped = new Map<string, SitemapTipRow[]>();
  for (const raw of previewRows) {
    const key = tipFixtureKey(raw);
    const rows = grouped.get(key) ?? [];
    rows.push(raw);
    grouped.set(key, rows);
  }

  const previews = Array.from(grouped.values())
    .filter((rows) => isFixtureEligible(rows) && !rows.every((row) => row.status === "void"))
    .map((rows) => {
      const representative = [...rows].sort((left, right) => left.id - right.id)[0];
      const fallbackTimestamp = fixtureFallbackTimestamp(representative.match_date);
      const lastModified = maxTimestamp(
        rows.flatMap((row) => [row.posted_at, row.settled_at]),
        fallbackTimestamp,
      );
      return {
        url: tipPreviewPath(representative),
        lastModified: new Date(lastModified),
      };
    });

  const latestByMarket: Partial<Record<"tennis" | "props", Date>> = {};
  for (const row of latestResponse.data ?? []) {
    const market = row.market as "tennis" | "props";
    if (market !== "tennis" && market !== "props") continue;
    const fallback = new Date().toISOString();
    const date = new Date(maxTimestamp([row.posted_at, row.settled_at], fallback));
    if (!latestByMarket[market] || date > latestByMarket[market]!) {
      latestByMarket[market] = date;
    }
  }

  return { previews, latestByMarket };
}
