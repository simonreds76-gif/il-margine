import { slugifyTip } from "@/lib/slugify";

export const TIP_SEO_MARKER = "[[SEO_READY_V1]]";

type TipSeoCandidate = {
  id: number;
  market?: string | null;
  event?: string | null;
  match_date?: string | null;
  notes?: string | null;
};

export type TipSeoAssessment = {
  eligible: boolean;
  analysis: string;
  reason: string | null;
};

export function stripTipSeoMarker(notes?: string | null): string {
  const value = String(notes || "").trim();
  if (!value.startsWith(TIP_SEO_MARKER)) return value;
  return value.slice(TIP_SEO_MARKER.length).trim();
}

export function assessTipSeoReadiness(tip: TipSeoCandidate): TipSeoAssessment {
  const analysis = stripTipSeoMarker(tip.notes);
  if (tip.market !== "tennis" && tip.market !== "props") {
    return { eligible: false, analysis, reason: "unsupported_market" };
  }
  if (!String(tip.event || "").trim()) {
    return { eligible: false, analysis, reason: "missing_event" };
  }
  if (!/^\d{4}-\d{2}-\d{2}$/.test(String(tip.match_date || ""))) {
    return { eligible: false, analysis, reason: "missing_match_date" };
  }
  return { eligible: true, analysis, reason: null };
}

export function tipPreviewSlug(event: string, matchDate: string, id: number): string {
  const base = slugifyTip(event, id).replace(/-betting-tip-\d+$/, "");
  return `${base}-prediction-${matchDate}-${id}`;
}

export function tipPreviewPath(tip: TipSeoCandidate): string {
  return `/betting-tips/${tipPreviewSlug(
    String(tip.event || "match"),
    String(tip.match_date || "date-pending"),
    tip.id,
  )}`;
}

export function publicTipPath(tip: TipSeoCandidate): string {
  if (assessTipSeoReadiness(tip).eligible) return tipPreviewPath(tip);
  return `/tips/${slugifyTip(String(tip.event || "tip"), tip.id)}`;
}

export function tipFixtureKey(tip: Pick<TipSeoCandidate, "market" | "event" | "match_date">): string {
  return [
    String(tip.market || "").trim().toLowerCase(),
    String(tip.match_date || "").trim(),
    String(tip.event || "").trim().toLowerCase().replace(/\s+/g, " "),
  ].join("::");
}
