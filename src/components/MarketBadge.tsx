"use client";

/** Maps market + category to SVG icon path and label. Used in picks tables. */
const MARKET_CONFIG: Record<string, { src: string; label: string; invertForDark?: boolean }> = {
  tennis: { src: "/icons/markets/tennis.svg", label: "Tennis" },
  atp: { src: "/icons/markets/tennis.svg", label: "ATP" },
  challenger: { src: "/icons/markets/tennis.svg", label: "Challenger" },
  ausopen: { src: "/icons/markets/tennis.svg", label: "Aus Open" },
  rolandgarros: { src: "/icons/markets/tennis.svg", label: "Roland Garros" },
  wimbledon: { src: "/icons/markets/tennis.svg", label: "Wimbledon" },
  usopen: { src: "/icons/markets/tennis.svg", label: "US Open" },
  pl: { src: "/icons/markets/pl.svg", label: "Premier League" },
  seriea: { src: "/icons/markets/seriea.svg", label: "Serie A" },
  ucl: { src: "/icons/markets/ucl-official.svg", label: "Champions League", invertForDark: true },
  other: { src: "/icons/markets/other.svg", label: "Other" },
  worldcup: { src: "/icons/markets/other.svg", label: "World Cup" },
  betbuilders: { src: "/icons/markets/other.svg", label: "Bet Builders" },
  atg: { src: "/icons/markets/other.svg", label: "ATG" },
};

function getConfig(market: string, category: string): { src: string; label: string; invertForDark?: boolean } {
  if (market === "tennis") return MARKET_CONFIG.tennis;
  if (market === "betbuilders") return MARKET_CONFIG.betbuilders;
  if (market === "atg") return MARKET_CONFIG.atg;
  const key = category?.toLowerCase() || "other";
  return MARKET_CONFIG[key] ?? MARKET_CONFIG.other;
}

interface MarketBadgeProps {
  market: string;
  category?: string | null;
  showLabel?: boolean;
  className?: string;
  /** Hide badge on mobile (md and up only) */
  hideOnMobile?: boolean;
}

export default function MarketBadge({ market, category, showLabel = false, className = "", hideOnMobile = false }: MarketBadgeProps) {
  const { src, label, invertForDark } = getConfig(market, category ?? "");
  return (
    <span
      className={`inline-flex items-center gap-1.5 ${hideOnMobile ? "hidden lg:inline-flex" : ""} ${className}`}
      title={label}
    >
      <img
        src={`${src}?v=3`}
        alt={label}
        width={24}
        height={24}
        className={`h-6 w-6 shrink-0 ${invertForDark ? "brightness-0 invert" : ""}`}
      />
      {showLabel && <span className="text-xs font-medium text-slate-400">{label}</span>}
    </span>
  );
}
