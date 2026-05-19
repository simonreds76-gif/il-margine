"use client";

import { getDisplayBetCategory } from "@/lib/bet-category";

type MarketConfig = {
  src: string;
  label: string;
  invertForDark?: boolean;
  wide?: boolean;
  containerClassName?: string;
  imageClassName?: string;
};

/** Maps market + category to SVG icon path and label. Used in picks tables. */
const MARKET_CONFIG: Record<string, MarketConfig> = {
  tennis: { src: "/icons/markets/tennis.svg", label: "Tennis" },
  atp: {
    src: "/icons/markets/atp-logo.png",
    label: "ATP Tour",
    containerClassName: "h-8 w-12",
    imageClassName: "max-h-8 w-12 object-contain",
  },
  challenger: { src: "/icons/markets/tennis.svg", label: "Challenger" },
  ausopen: {
    src: "/icons/markets/slams/australian-open.png",
    label: "Australian Open",
    containerClassName: "h-8 w-12",
    imageClassName: "max-h-8 w-12 object-contain",
  },
  rolandgarros: {
    src: "/icons/markets/slams/roland-garros.png",
    label: "Roland Garros",
    containerClassName: "h-8 w-12",
    imageClassName: "h-8 w-8 object-contain",
  },
  wimbledon: {
    src: "/icons/markets/slams/wimbledon.png",
    label: "Wimbledon",
    containerClassName: "h-8 w-12",
    imageClassName: "h-8 w-8 object-contain",
  },
  usopen: {
    src: "/icons/markets/slams/us-open.png",
    label: "US Open",
    containerClassName: "h-8 w-12",
    imageClassName: "max-h-8 w-12 object-contain",
  },
  pl: { src: "/league-logos/epl.png", label: "Premier League", containerClassName: "h-8 w-8", imageClassName: "h-8 w-8 object-contain" },
  seriea: { src: "/league-logos/serie-a.png", label: "Serie A", containerClassName: "h-8 w-8", imageClassName: "h-8 w-8 object-contain" },
  laliga: { src: "/league-logos/la-liga.png", label: "La Liga", containerClassName: "h-8 w-8", imageClassName: "h-8 w-8 object-contain" },
  bundesliga: { src: "/league-logos/bundesliga.png", label: "Bundesliga", containerClassName: "h-8 w-8", imageClassName: "h-8 w-8 object-contain" },
  ligue1: { src: "/league-logos/ligue-1.png", label: "Ligue 1", containerClassName: "h-8 w-8", imageClassName: "h-8 w-8 object-contain" },
  ucl: {
    src: "/icons/markets/ucl-official.svg",
    label: "Champions League",
    containerClassName: "h-8 w-8",
    imageClassName: "h-7 w-7 object-contain",
  },
  other: { src: "/icons/markets/other-football.svg", label: "Other football", containerClassName: "h-7 w-7", imageClassName: "h-6 w-6 object-contain" },
  worldcup: { src: "/icons/markets/other-football.svg", label: "World Cup", containerClassName: "h-7 w-7", imageClassName: "h-6 w-6 object-contain" },
  betbuilders: { src: "/icons/markets/other-football.svg", label: "Bet Builders", containerClassName: "h-7 w-7", imageClassName: "h-6 w-6 object-contain" },
  atg: { src: "/icons/markets/other-football.svg", label: "ATG", containerClassName: "h-7 w-7", imageClassName: "h-6 w-6 object-contain" },
};

function getConfig(market: string, category: string, event?: string | null): MarketConfig {
  const marketKey = (market ?? "").trim().toLowerCase();
  const categoryKey = getDisplayBetCategory({ market, category, event });

  if (marketKey === "tennis") {
    if (categoryKey === "other") return MARKET_CONFIG.tennis;
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
  event?: string | null;
  showLabel?: boolean;
  className?: string;
  /** Hide badge on mobile (md and up only) */
  hideOnMobile?: boolean;
  /** Compact badge for inline mobile placement inside dense tables. */
  compact?: boolean;
}

export default function MarketBadge({ market, category, event, showLabel = false, className = "", hideOnMobile = false, compact = false }: MarketBadgeProps) {
  const { src, label, invertForDark, wide, containerClassName, imageClassName } = getConfig(market, category ?? "", event);
  const resolvedContainerClassName = compact ? "h-7 w-7" : containerClassName ?? (wide ? "h-7 w-9" : "h-7 w-7");
  const resolvedImageClassName = compact ? "max-h-[1.25rem] max-w-[1.45rem] object-contain" : imageClassName ?? (wide ? "max-h-5 w-auto" : "max-h-5 max-w-5 object-contain");

  return (
    <span
      className={`inline-flex items-center gap-1.5 ${hideOnMobile ? "hidden md:inline-flex" : ""} ${className}`}
      title={label}
    >
      <span
        className={`inline-flex shrink-0 items-center justify-center overflow-hidden rounded-lg bg-[radial-gradient(circle_at_30%_20%,rgba(87,209,150,0.18)_0%,rgba(15,23,42,0.92)_46%,rgba(2,6,23,0.96)_100%)] p-1 ring-1 ring-[#57d196]/28 shadow-[inset_0_1px_0_rgba(255,255,255,0.08),0_0_14px_rgba(87,209,150,0.08)] ${resolvedContainerClassName}`}
      >
        <img
          src={`${src}?v=12`}
          alt={label}
          width={wide ? 32 : 24}
          height={24}
          className={`${resolvedImageClassName} shrink-0 drop-shadow-[0_0_3px_rgba(255,255,255,0.34)] ${invertForDark ? "brightness-0" : ""}`}
        />
      </span>
      {showLabel && <span className="text-xs font-medium text-slate-400">{label}</span>}
    </span>
  );
}
