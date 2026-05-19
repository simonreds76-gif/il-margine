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

const DARK_MARK_FILTER =
  "[filter:brightness(0)_invert(1)_drop-shadow(0_0_4px_rgba(255,255,255,0.58))_drop-shadow(0_0_11px_rgba(87,209,150,0.2))]";

const LOW_CONTRAST_MARK_FILTER =
  "[filter:brightness(1.9)_saturate(1.45)_contrast(1.15)_drop-shadow(0_0_4px_rgba(255,255,255,0.5))_drop-shadow(0_0_10px_rgba(87,209,150,0.18))]";

const NATURAL_MARK_FILTER =
  "[filter:drop-shadow(0_0_4px_rgba(255,255,255,0.32))_drop-shadow(0_0_10px_rgba(87,209,150,0.12))]";

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
  pl: { src: "/league-logos/epl.png", label: "Premier League", containerClassName: "h-8 w-8", imageClassName: `h-8 w-8 object-contain ${LOW_CONTRAST_MARK_FILTER}` },
  seriea: { src: "/league-logos/serie-a.png", label: "Serie A", containerClassName: "h-8 w-8", imageClassName: `h-8 w-8 object-contain ${NATURAL_MARK_FILTER}` },
  laliga: { src: "/league-logos/la-liga.png", label: "La Liga", containerClassName: "h-8 w-8", imageClassName: `h-8 w-8 object-contain ${NATURAL_MARK_FILTER}` },
  bundesliga: { src: "/league-logos/bundesliga.png", label: "Bundesliga", containerClassName: "h-8 w-8", imageClassName: `h-8 w-8 object-contain ${NATURAL_MARK_FILTER}` },
  ligue1: { src: "/league-logos/ligue-1.png", label: "Ligue 1", containerClassName: "h-8 w-8", imageClassName: `h-8 w-8 object-contain ${DARK_MARK_FILTER}` },
  ucl: {
    src: "/icons/markets/ucl-official.svg",
    label: "Champions League",
    containerClassName: "h-8 w-8",
    imageClassName: `h-7 w-7 object-contain opacity-95 ${DARK_MARK_FILTER}`,
  },
  other: { src: "/icons/markets/other-football.svg", label: "Other football", containerClassName: "h-8 w-8", imageClassName: `h-8 w-8 object-contain ${NATURAL_MARK_FILTER}` },
  worldcup: { src: "/icons/markets/other-football.svg", label: "World Cup", containerClassName: "h-8 w-8", imageClassName: `h-8 w-8 object-contain ${NATURAL_MARK_FILTER}` },
  betbuilders: { src: "/icons/markets/other-football.svg", label: "Bet Builders", containerClassName: "h-8 w-8", imageClassName: `h-8 w-8 object-contain ${NATURAL_MARK_FILTER}` },
  atg: { src: "/icons/markets/other-football.svg", label: "ATG", containerClassName: "h-8 w-8", imageClassName: `h-8 w-8 object-contain ${NATURAL_MARK_FILTER}` },
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
        className={`inline-flex shrink-0 items-center justify-center overflow-visible ${resolvedContainerClassName}`}
      >
        <img
          src={`${src}?v=13`}
          alt={label}
          width={wide ? 32 : 24}
          height={24}
          className={`${resolvedImageClassName} shrink-0 ${invertForDark ? "brightness-0" : ""}`}
        />
      </span>
      {showLabel && <span className="text-xs font-medium text-slate-400">{label}</span>}
    </span>
  );
}
