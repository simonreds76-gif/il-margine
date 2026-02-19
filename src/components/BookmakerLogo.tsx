"use client";

import { useState } from "react";
import Image from "next/image";
import Link from "next/link";
import { Bookmaker } from "@/lib/supabase";

interface BookmakerLogoProps {
  /** Single bookmaker or array (Supabase sometimes returns relation as array) */
  bookmaker: Bookmaker | Bookmaker[] | null | undefined;
  size?: "sm" | "md" | "lg";
  showName?: boolean;
  className?: string;
}

// Map bookmaker short_name / name (from DB or copy) to logo filename in public/bookmakers/.
// When adding a new bookmaker: add row in Supabase bookmakers, add logo file, then add entry here (name + short_name variants).
const bookmakerLogos: Record<string, string> = {
  // Recommended 8 + common variants
  "Midnite": "midnite",
  "midnite": "midnite",
  "Midnight": "midnite",
  "midnight": "midnite",
  "MN": "midnite",
  "BetVictor": "betvictor",
  "Betvictor": "betvictor",
  "betvictor": "betvictor",
  "Bet Victor": "betvictor",
  "bet victor": "betvictor",
  "BV": "betvictor",
  "Unibet": "Unibet_idYHeiKVm__1.png",
  "unibet": "Unibet_idYHeiKVm__1.png",
  "Coral": "coral",
  "coral": "coral",
  "CR": "coral",
  "Ladbrokes": "ladbrokes",
  "ladbrokes": "ladbrokes",
  "LAD": "ladbrokes",
  "Bwin": "bwin",
  "bwin": "bwin",
  "BW": "bwin",
  "BetMGM": "BetMGM UK_idPMHl2t9c_0.png",
  "betmgm": "BetMGM UK_idPMHl2t9c_0.png",
  "LeoVegas": "BetMGM UK_idPMHl2t9c_0.png",
  "William Hill": "williamhill",
  "WH": "williamhill",
  "williamhill": "williamhill",
  "Betfred": "betfred",
  "betfred": "betfred",
  "Bet Fred": "betfred",
  "bet fred": "betfred",
  "BF": "betfred",
  // Others (admin / legacy)
  "bet365": "bet365",
  "Bet365": "bet365",
  "Betfair": "betfair",
  "betfair": "betfair",
  "Paddy Power": "paddypower",
  "Paddy": "paddypower",
  "paddypower": "paddypower",
  "Sky Bet": "skybet",
  "SkyBet": "skybet",
  "skybet": "skybet",
  "Betway": "betway",
  "betway": "betway",
  "888sport": "888sport",
  "BoyleSports": "boylesports",
  "Pinnacle": "pinnacle",
  "pinnacle": "pinnacle",
  "Pinnacle Bet": "pinnacle",
  "pinnacle bet": "pinnacle",
  "Marathon": "marathon",
  "DraftKings": "draftkings",
  "FanDuel": "fanduel",
};

// Override for display when short_name is abbreviated (e.g. CR -> Coral)
const bookmakerDisplayNames: Record<string, string> = {
  "CR": "Coral",
  "WH": "William Hill",
  "LAD": "Ladbrokes",
  "BV": "BetVictor",
  "BF": "Betfred",
  "BW": "Bwin",
};

// Logos that have lots of padding in the asset – scale up so they match others’ visual size
const logoScale: Record<string, number> = {
  pinnacle: 2,
  ladbrokes: 0.85,
};

// Prefer SVG for crisp scaling (avoids pixelation when PNG is low-res)
const preferSvg: Record<string, boolean> = {
  bet365: true,
};

// All logos one step larger so thumbnails are easier to recognise (was 24/32/40px)
const sizeClasses = {
  sm: "w-8 h-8",
  md: "w-10 h-10",
  lg: "w-12 h-12",
};

export default function BookmakerLogo({
  bookmaker: bookmakerProp,
  size = "sm",
  showName = false,
  className = "",
}: BookmakerLogoProps) {
  const bookmaker = Array.isArray(bookmakerProp) ? bookmakerProp[0] : bookmakerProp;
  if (!bookmaker) {
    return (
      <span className={`text-xs text-slate-600 ${className}`}>-</span>
    );
  }

  const logoBase = bookmakerLogos[bookmaker.short_name] || bookmakerLogos[bookmaker.name];
  const hasExtension = logoBase?.includes(".");
  const scaleKey = logoBase?.split(".")[0] ?? "";
  const useSvgFirst = preferSvg[scaleKey];
  // Prefer SVG for some logos (crisp at any size); otherwise try png/jpeg/jpg then svg
  const logoPaths: string[] = logoBase
    ? hasExtension
      ? [`/bookmakers/${encodeURIComponent(logoBase)}`]
      : useSvgFirst
        ? [
            `/bookmakers/${logoBase}.svg`,
            `/bookmakers/${logoBase}.png`,
            `/bookmakers/${logoBase}.jpeg`,
            `/bookmakers/${logoBase}.jpg`,
          ]
        : [
            `/bookmakers/${logoBase}.png`,
            `/bookmakers/${logoBase}.jpeg`,
            `/bookmakers/${logoBase}.jpg`,
            `/bookmakers/${logoBase}.svg`,
          ]
    : [];
  const [srcIndex, setSrcIndex] = useState(0);
  const [imageFailed, setImageFailed] = useState(false);
  const currentSrc = logoPaths[srcIndex] || null;

  const link = bookmaker.affiliate_link || "#";
  const hasAffiliate = !!bookmaker.affiliate_link;

  const showImage = currentSrc && !imageFailed;
  const scale = logoScale[scaleKey] ?? 1;

  // Prefer name for display; use override so "CR" shows as "Coral" etc.
  const displayName =
    bookmaker.name ||
    bookmakerDisplayNames[bookmaker.short_name] ||
    bookmaker.short_name ||
    "";

  const content = (
    <div className={`flex items-center justify-center gap-2 ${className}`}>
      {showImage ? (
        <div className={`${sizeClasses[size]} min-w-[2rem] min-h-[2rem] relative flex-shrink-0 mx-auto overflow-hidden`}>
          <div className="absolute inset-0" style={{ transform: `scale(${scale})` }}>
            <Image
              src={currentSrc}
              alt={displayName}
              fill
              sizes="48px"
              className="object-contain"
              unoptimized
              onError={() => {
                if (srcIndex < logoPaths.length - 1) {
                  setSrcIndex((i) => i + 1);
                } else {
                  setImageFailed(true);
                }
              }}
            />
          </div>
        </div>
      ) : (
        <div className={`${sizeClasses[size]} bg-slate-800 rounded flex items-center justify-center flex-shrink-0`}>
          <span className="text-[10px] text-slate-500 font-medium">
            {displayName.charAt(0)}
          </span>
        </div>
      )}
      {showName && (
        <span className="text-xs text-slate-300">{displayName}</span>
      )}
    </div>
  );

  // If no affiliate link, just show the logo without link
  if (!hasAffiliate) {
    return content;
  }

  return (
    <Link
      href={link}
      target="_blank"
      rel="noopener noreferrer"
      className="hover:opacity-80 transition-opacity"
      title={hasAffiliate ? `Visit ${displayName}` : undefined}
    >
      {content}
    </Link>
  );
}
