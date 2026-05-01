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
    src: "/icons/markets/atp-brandmark-cropped.png",
    label: "ATP Tour",
    containerClassName: "h-7 w-7",
    imageClassName: "h-full w-full object-contain",
  },
  challenger: { src: "/icons/markets/tennis.svg", label: "Challenger" },
  ausopen: { src: "/icons/markets/tennis.svg", label: "Aus Open" },
  rolandgarros: { src: "/icons/markets/tennis.svg", label: "Roland Garros" },
  wimbledon: { src: "/icons/markets/tennis.svg", label: "Wimbledon" },
  usopen: { src: "/icons/markets/tennis.svg", label: "US Open" },
  pl: { src: "/league-logos/epl.png", label: "Premier League", containerClassName: "h-8 w-8", imageClassName: "h-8 w-8 object-contain" },
  seriea: { src: "/league-logos/serie-a.png", label: "Serie A", containerClassName: "h-8 w-8", imageClassName: "h-8 w-8 object-contain" },
  laliga: { src: "/league-logos/la-liga.png", label: "La Liga", containerClassName: "h-8 w-8", imageClassName: "h-8 w-8 object-contain" },
  bundesliga: { src: "/league-logos/bundesliga.png", label: "Bundesliga", containerClassName: "h-8 w-8", imageClassName: "h-8 w-8 object-contain" },
  ligue1: { src: "/league-logos/ligue-1.png", label: "Ligue 1", containerClassName: "h-8 w-8", imageClassName: "h-8 w-8 object-contain" },
  ucl: { src: "/icons/markets/ucl-official.svg", label: "Champions League", invertForDark: true },
  other: { src: "/icons/markets/other-football.svg", label: "Other football", containerClassName: "h-7 w-7", imageClassName: "h-7 w-7 object-contain" },
  worldcup: { src: "/icons/markets/other-football.svg", label: "World Cup", containerClassName: "h-7 w-7", imageClassName: "h-7 w-7 object-contain" },
  betbuilders: { src: "/icons/markets/other-football.svg", label: "Bet Builders", containerClassName: "h-7 w-7", imageClassName: "h-7 w-7 object-contain" },
  atg: { src: "/icons/markets/other-football.svg", label: "ATG", containerClassName: "h-7 w-7", imageClassName: "h-7 w-7 object-contain" },
};

function getConfig(market: string, category: string, event?: string | null): MarketConfig {
  const marketKey = (market ?? "").trim().toLowerCase();
  const categoryKey = getDisplayBetCategory({ market, category, event });

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
  event?: string | null;
  showLabel?: boolean;
  className?: string;
  /** Hide badge on mobile (md and up only) */
  hideOnMobile?: boolean;
}

export default function MarketBadge({ market, category, event, showLabel = false, className = "", hideOnMobile = false }: MarketBadgeProps) {
  const { src, label, invertForDark, wide, containerClassName, imageClassName } = getConfig(market, category ?? "", event);
  return (
    <span
      className={`inline-flex items-center gap-1.5 ${hideOnMobile ? "hidden md:inline-flex" : ""} ${className}`}
      title={label}
    >
      <span className={`inline-flex items-center justify-center shrink-0 ${containerClassName ?? (wide ? "h-6 w-8" : "h-6 w-6")}`}>
        <img
          src={`${src}?v=9`}
          alt={label}
          width={wide ? 32 : 24}
          height={24}
          className={`${imageClassName ?? (wide ? "h-[18px] w-auto" : "h-6 w-auto")} object-contain shrink-0 ${invertForDark ? "brightness-0 invert" : ""}`}
        />
      </span>
      {showLabel && <span className="text-xs font-medium text-slate-400">{label}</span>}
    </span>
  );
}
