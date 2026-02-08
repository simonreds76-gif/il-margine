"use client";

import Image from "next/image";
import Link from "next/link";
import { Bookmaker } from "@/lib/supabase";

interface BookmakerLogoProps {
  bookmaker: Bookmaker | null | undefined;
  size?: "sm" | "md" | "lg";
  showName?: boolean;
  className?: string;
}

// Map bookmaker short names to logo filenames (try PNG first, fallback to SVG)
const bookmakerLogos: Record<string, string> = {
  "bet365": "bet365",
  "Bet365": "bet365",
  "Betfair": "betfair",
  "betfair": "betfair",
  "Paddy Power": "paddypower",
  "Paddy": "paddypower",
  "paddypower": "paddypower",
  "William Hill": "williamhill",
  "WH": "williamhill",
  "williamhill": "williamhill",
  "Ladbrokes": "ladbrokes",
  "ladbrokes": "ladbrokes",
  "Coral": "coral",
  "coral": "coral",
  "Sky Bet": "skybet",
  "SkyBet": "skybet",
  "skybet": "skybet",
  "Unibet": "unibet",
  "unibet": "unibet",
  "Betway": "betway",
  "betway": "betway",
  "888sport": "888sport",
  "Betvictor": "betvictor",
  "betvictor": "betvictor",
  "Betfred": "betfred",
  "betfred": "betfred",
  "BoyleSports": "boylesports",
  "Pinnacle": "pinnacle",
  "pinnacle": "pinnacle",
  "Marathon": "marathon",
  "BetMGM": "betmgm",
  "betmgm": "betmgm",
  "Midnite": "midnite",
  "midnite": "midnite",
  "BetVictor": "betvictor",
  "DraftKings": "draftkings",
  "FanDuel": "fanduel",
  // Add more as needed
};

const sizeClasses = {
  sm: "w-6 h-6",
  md: "w-8 h-8",
  lg: "w-10 h-10",
};

export default function BookmakerLogo({
  bookmaker,
  size = "sm",
  showName = false,
  className = "",
}: BookmakerLogoProps) {
  if (!bookmaker) {
    return (
      <span className={`text-xs text-slate-600 ${className}`}>-</span>
    );
  }

  const logoBase = bookmakerLogos[bookmaker.short_name] || bookmakerLogos[bookmaker.name];
  // Try PNG first, fallback to SVG
  const logoPath = logoBase ? (
    `/bookmakers/${logoBase}.png` // Will try PNG first
  ) : null;
  const logoSvgPath = logoBase ? `/bookmakers/${logoBase}.svg` : null;
  
  // Determine link - use affiliate if available, otherwise placeholder
  const link = bookmaker.affiliate_link || "#";
  const hasAffiliate = !!bookmaker.affiliate_link;

  const content = (
    <div className={`flex items-center justify-center gap-2 ${className}`}>
      {logoPath || logoSvgPath ? (
        <div className={`${sizeClasses[size]} relative flex-shrink-0 mx-auto`}>
          <Image
            src={logoPath || logoSvgPath || ""}
            alt={bookmaker.short_name || bookmaker.name}
            fill
            className="object-contain"
            unoptimized
            onError={(e) => {
              // If PNG fails and we have SVG, try SVG
              if (logoPath && logoSvgPath && e.currentTarget.src.includes('.png')) {
                e.currentTarget.src = logoSvgPath;
              } else {
                e.currentTarget.style.display = "none";
              }
            }}
          />
        </div>
      ) : (
        <div className={`${sizeClasses[size]} bg-slate-800 rounded flex items-center justify-center flex-shrink-0`}>
          <span className="text-[10px] text-slate-500 font-medium">
            {bookmaker.short_name?.charAt(0) || bookmaker.name.charAt(0)}
          </span>
        </div>
      )}
      {showName && (
        <span className="text-xs text-slate-300">{bookmaker.short_name || bookmaker.name}</span>
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
      title={hasAffiliate ? `Visit ${bookmaker.short_name || bookmaker.name}` : undefined}
    >
      {content}
    </Link>
  );
}
