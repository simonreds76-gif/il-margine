import { resolveBookmakerLogo } from "@/lib/bookmaker-logos";

// Reuse established redirects so affiliate tags have one source of truth.
const PARTNERS: Record<string, { name: string; path: string }> = {
  betway: { name: "Betway", path: "/api/go/betway" },
  williamhill: { name: "William Hill", path: "/api/go/william-hill" },
};

export function telegramBookmakerPartner(bookmaker: string | null, baseUrl: string) {
  const key = resolveBookmakerLogo(bookmaker)?.key;
  const partner = key ? PARTNERS[key] : null;
  return partner ? { name: partner.name, url: `${baseUrl}${partner.path}` } : null;
}
