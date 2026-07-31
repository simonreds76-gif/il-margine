import { parseTipSlugId, slugifyTip } from "@/lib/slugify";

// Migration-only marker from the unpromoted manual-approval implementation.
export const TIP_SEO_MARKER = "[[SEO_READY_V1]]";

const INDEXABLE_CATEGORIES: Record<string, Set<string>> = {
  tennis: new Set(["atp", "ausopen", "rolandgarros", "wimbledon", "usopen"]),
  props: new Set(["pl", "seriea", "laliga", "bundesliga", "ligue1", "ucl"]),
};
const MATCH_DATE_RE = /^\d{4}-\d{2}-\d{2}$/;
const STABLE_HASH_RE = /^[a-z0-9]{7}$/;

export type TipSeoCandidate = {
  id?: number;
  market?: string | null;
  category?: string | null;
  event?: string | null;
  match_date?: string | null;
  notes?: string | null;
  odds?: number | string | null;
  stake?: number | string | null;
  status?: string | null;
};

export type TipSeoAssessment = {
  eligible: boolean;
  analysis: string;
  reason: string | null;
};

export type ParsedTipPreviewSlug =
  | { kind: "stable"; market: "tennis" | "props"; matchDate: string; fixtureHash: string }
  | { kind: "legacy"; seedId: number }
  | null;

function normalizeCategory(value?: string | null): string {
  return String(value || "")
    .normalize("NFKD")
    .replace(/[\u0300-\u036f]/g, "")
    .replace(/[^a-z0-9]+/gi, "")
    .toLowerCase();
}

function isSupportedMarket(value?: string | null): value is "tennis" | "props" {
  return value === "tennis" || value === "props";
}

function hasTwoParticipants(event?: string | null): boolean {
  const value = String(event || "").replace(/\s+/g, " ").trim();
  if (!value) return false;
  const parts = value.split(/\s+(?:vs?\.?|at)\s+/i).map((part) => part.trim()).filter(Boolean);
  return parts.length === 2;
}

function finiteNumber(value: number | string | null | undefined): number | null {
  if (value === null || value === undefined || value === "") return null;
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : null;
}

export function stripTipSeoMarker(notes?: string | null): string {
  const value = String(notes || "").trim();
  if (!value.startsWith(TIP_SEO_MARKER)) return value;
  return value.slice(TIP_SEO_MARKER.length).trim();
}

export function normalizeTipEvent(event?: string | null): string {
  const normalized = String(event || "")
    .normalize("NFKD")
    .replace(/[\u0300-\u036f]/g, "")
    .replace(/&/g, " and ")
    .replace(/[^a-z0-9]+/gi, " ")
    .trim()
    .toLowerCase()
    .replace(/\s+/g, " ");
  const participants = normalized
    .split(/\s+(?:vs?|at)\s+/)
    .map((part) => part.trim())
    .filter(Boolean);
  return participants.length === 2 ? `${participants[0]} vs ${participants[1]}` : normalized;
}

export function assessTipSeoStructure(tip: TipSeoCandidate): TipSeoAssessment {
  const analysis = stripTipSeoMarker(tip.notes);
  if (!isSupportedMarket(tip.market)) {
    return { eligible: false, analysis, reason: "unsupported_market" };
  }
  if (!hasTwoParticipants(tip.event)) {
    return { eligible: false, analysis, reason: "invalid_event" };
  }
  if (!MATCH_DATE_RE.test(String(tip.match_date || ""))) {
    return { eligible: false, analysis, reason: "missing_match_date" };
  }
  if (!INDEXABLE_CATEGORIES[tip.market].has(normalizeCategory(tip.category))) {
    return { eligible: false, analysis, reason: "unsupported_category" };
  }
  const odds = finiteNumber(tip.odds);
  if (odds === null || odds < 1.01 || odds > 100) {
    return { eligible: false, analysis, reason: "invalid_odds" };
  }
  return { eligible: true, analysis, reason: null };
}

export function assessTipSeoReadiness(tip: TipSeoCandidate): TipSeoAssessment {
  const structural = assessTipSeoStructure(tip);
  if (!structural.eligible) return structural;
  const stake = finiteNumber(tip.stake);
  if (stake === null || stake < 0.5 || stake > 5) {
    return { ...structural, eligible: false, reason: "low_or_invalid_stake" };
  }
  return structural;
}

export function tipFixtureKey(
  tip: Pick<TipSeoCandidate, "market" | "event" | "match_date">,
): string {
  return [
    String(tip.market || "").trim().toLowerCase(),
    String(tip.match_date || "").trim(),
    normalizeTipEvent(tip.event),
  ].join("::");
}

export function tipFixtureHash(
  tip: Pick<TipSeoCandidate, "market" | "event" | "match_date">,
): string {
  const value = tipFixtureKey(tip);
  let hash = 0x811c9dc5;
  for (let index = 0; index < value.length; index += 1) {
    hash ^= value.charCodeAt(index);
    hash = Math.imul(hash, 0x01000193);
  }
  return (hash >>> 0).toString(36).padStart(7, "0").slice(-7);
}

export function tipPreviewSlug(
  tip: Pick<TipSeoCandidate, "market" | "event" | "match_date">,
): string {
  const market = isSupportedMarket(tip.market) ? tip.market : "tennis";
  const eventSlug = normalizeTipEvent(tip.event).replace(/\s+/g, "-") || "match";
  const matchDate = MATCH_DATE_RE.test(String(tip.match_date || ""))
    ? String(tip.match_date)
    : "date-pending";
  return `${market}-${eventSlug}-prediction-${matchDate}-${tipFixtureHash(tip)}`;
}

export function tipPreviewPath(
  tip: Pick<TipSeoCandidate, "market" | "event" | "match_date">,
): string {
  return `/betting-tips/${tipPreviewSlug(tip)}`;
}

export function parseTipPreviewSlug(slug: string): ParsedTipPreviewSlug {
  const normalizedSlug = slug.trim().toLowerCase();
  const stable = normalizedSlug.match(
    /^(tennis|props)-.+-prediction-(\d{4}-\d{2}-\d{2})-([a-z0-9]{7})$/,
  );
  if (stable && STABLE_HASH_RE.test(stable[3])) {
    return {
      kind: "stable",
      market: stable[1] as "tennis" | "props",
      matchDate: stable[2],
      fixtureHash: stable[3],
    };
  }
  // Stable canonicals own these namespaces. A malformed or truncated stable
  // slug must 404 rather than falling through and treating part of its date
  // or hash as a legacy bet ID.
  if (/^(?:tennis|props)-/.test(normalizedSlug)) return null;
  if (!/^\d+$/.test(normalizedSlug) && !/-\d+$/.test(normalizedSlug)) return null;
  const seedId = parseTipSlugId(normalizedSlug);
  return seedId === null ? null : { kind: "legacy", seedId };
}

export function publicTipPath(tip: TipSeoCandidate): string {
  if (assessTipSeoReadiness(tip).eligible) return tipPreviewPath(tip);
  return `/tips/${slugifyTip(String(tip.event || "tip"), Number(tip.id || 0))}`;
}
