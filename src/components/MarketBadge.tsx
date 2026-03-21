"use client";

type MarketConfig = {
  src: string;
  label: string;
  invertForDark?: boolean;
  wide?: boolean;
  frameClassName?: string;
  imageClassName?: string;
};

/** Maps market + category to SVG icon path and label. Used in picks tables. */
const MARKET_CONFIG: Record<string, MarketConfig> = {
  tennis: { src: "/icons/markets/tennis.svg", label: "Tennis" },
  atp: { src: "/icons/markets/tennis.svg", label: "ATP" },
  challenger: { src: "/icons/markets/tennis.svg", label: "Challenger" },
  ausopen: { src: "/icons/markets/tennis.svg", label: "Aus Open" },
  rolandgarros: { src: "/icons/markets/tennis.svg", label: "Roland Garros" },
  wimbledon: { src: "/icons/markets/tennis.svg", label: "Wimbledon" },
  usopen: { src: "/icons/markets/tennis.svg", label: "US Open" },
  pl: {
    src: "/icons/markets/pl.svg",
    label: "Premier League",
    wide: true,
    frameClassName: "rounded-md border border-fuchsia-500/25 bg-[#33003d] shadow-[inset_0_1px_0_rgba(255,255,255,0.05)]",
    imageClassName: "h-[13px] w-auto",
  },
  seriea: {
    src: "/icons/markets/seriea.svg",
    label: "Serie A",
    frameClassName: "rounded-md border border-sky-400/20 bg-white shadow-[0_0_0_1px_rgba(255,255,255,0.04)]",
    imageClassName: "h-[18px] w-auto",
  },
  ucl: {
    src: "/icons/markets/ucl-official.svg",
    label: "Champions League",
    invertForDark: true,
    frameClassName: "rounded-md border border-sky-400/20 bg-[#071a39] shadow-[inset_0_1px_0_rgba(255,255,255,0.04)]",
    imageClassName: "h-[16px] w-auto",
  },
  other: { src: "/icons/markets/other.svg", label: "Other" },
  worldcup: { src: "/icons/markets/other.svg", label: "World Cup" },
  betbuilders: { src: "/icons/markets/other.svg", label: "Bet Builders" },
  atg: { src: "/icons/markets/other.svg", label: "ATG" },
};

function normalizeCategory(value: string): string {
  const raw = (value ?? "").trim().toLowerCase();
  if (!raw) return "other";
  const compact = raw.replace(/[\s_-]+/g, "");

  if (compact === "pl" || compact === "epl" || compact === "premierleague" || compact === "englishpremierleague") {
    return "pl";
  }
  if (compact === "seriea" || compact === "italianseriea" || compact === "seriaa") {
    return "seriea";
  }
  if (compact === "ucl" || compact === "championsleague" || compact === "uefachampionsleague") {
    return "ucl";
  }
  if (compact === "atp" || compact === "challenger" || compact === "ausopen" || compact === "rolandgarros" || compact === "wimbledon" || compact === "usopen") {
    return compact;
  }
  return compact;
}

function getConfig(market: string, category: string): MarketConfig {
  const marketKey = (market ?? "").trim().toLowerCase();
  const categoryKey = normalizeCategory(category ?? "");

  if (marketKey === "tennis") {
    return MARKET_CONFIG[categoryKey] ?? MARKET_CONFIG.tennis;
  }

  if (marketKey === "betbuilders" || marketKey === "atg" || marketKey === "props") {
    return MARKET_CONFIG[categoryKey] ?? MARKET_CONFIG[marketKey] ?? MARKET_CONFIG.other;
  }

  return MARKET_CONFIG[categoryKey] ?? MARKET_CONFIG.other;
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
  const { src, label, invertForDark, wide, frameClassName, imageClassName } = getConfig(market, category ?? "");
  return (
    <span
      className={`inline-flex items-center gap-1.5 ${hideOnMobile ? "hidden lg:inline-flex" : ""} ${className}`}
      title={label}
    >
      <span
        className={`inline-flex items-center justify-center shrink-0 ${wide ? "h-6 w-10 px-1.5" : "h-6 w-7 px-1"} ${frameClassName ?? ""}`}
      >
        <img
          src={`${src}?v=5`}
          alt={label}
          width={wide ? 40 : 28}
          height={24}
          className={`${imageClassName ?? (wide ? "h-[18px] w-auto" : "h-6 w-auto")} object-contain shrink-0 ${invertForDark ? "brightness-0 invert" : ""}`}
        />
      </span>
      {showLabel && <span className="text-xs font-medium text-slate-400">{label}</span>}
    </span>
  );
}
