"use client";

/** Maps market + category to icon (emoji) and label. Used in picks tables. */
const MARKET_CONFIG: Record<string, { icon: string; label: string }> = {
  // Tennis – single icon for all
  tennis: { icon: "🎾", label: "Tennis" },
  atp: { icon: "🎾", label: "ATP" },
  challenger: { icon: "🎾", label: "Challenger" },
  ausopen: { icon: "🎾", label: "Aus Open" },
  rolandgarros: { icon: "🎾", label: "Roland Garros" },
  wimbledon: { icon: "🎾", label: "Wimbledon" },
  usopen: { icon: "🎾", label: "US Open" },
  // Props – league flags
  pl: { icon: "🇬🇧", label: "Premier League" },
  seriea: { icon: "🇮🇹", label: "Serie A" },
  ucl: { icon: "🇪🇺", label: "Champions League" },
  // Other / future (World Cup etc.)
  other: { icon: "🌍", label: "Other" },
  worldcup: { icon: "🌍", label: "World Cup" },
  betbuilders: { icon: "⚽", label: "Bet Builders" },
  atg: { icon: "⚽", label: "ATG" },
};

function getConfig(market: string, category: string): { icon: string; label: string } {
  if (market === "tennis") return MARKET_CONFIG.tennis;
  if (market === "betbuilders") return MARKET_CONFIG.betbuilders;
  if (market === "atg") return MARKET_CONFIG.atg;
  const key = category?.toLowerCase() || "other";
  return MARKET_CONFIG[key] ?? MARKET_CONFIG.other;
}

interface MarketBadgeProps {
  market: string;
  category?: string | null;
  /** Show label next to icon (default: icon only for compact tables) */
  showLabel?: boolean;
  className?: string;
}

export default function MarketBadge({ market, category, showLabel = false, className = "" }: MarketBadgeProps) {
  const { icon, label } = getConfig(market, category ?? "");
  return (
    <span
      className={`inline-flex items-center gap-1.5 text-base ${className}`}
      title={label}
    >
      <span aria-hidden>{icon}</span>
      {showLabel && <span className="text-xs font-medium text-slate-400">{label}</span>}
    </span>
  );
}
