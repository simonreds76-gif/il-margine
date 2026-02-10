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
  "BetVictor": "betvictor",
  "Betvictor": "betvictor",
  "betvictor": "betvictor",
  "Unibet": "Unibet_idYHeiKVm__1.png",
  "unibet": "Unibet_idYHeiKVm__1.png",
  "Coral": "coral",
  "coral": "coral",
  "CR": "coral",
  "Ladbrokes": "ladbrokes",
  "ladbrokes": "ladbrokes",
  "BetMGM": "BetMGM UK_idPMHl2t9c_0.png",
  "betmgm": "BetMGM UK_idPMHl2t9c_0.png",
  "LeoVegas": "BetMGM UK_idPMHl2t9c_0.png",
  "William Hill": "williamhill",
  "WH": "williamhill",
  "williamhill": "williamhill",
  "Betfred": "betfred",
  "betfred": "betfred",
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
  "Marathon": "marathon",
  "DraftKings": "draftkings",
  "FanDuel": "fanduel",
};

const sizeClasses = {
  sm: "w-6 h-6",
  md: "w-8 h-8",
  lg: "w-10 h-10",
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
  const logoPaths: string[] = logoBase
    ? hasExtension
      ? [`/bookmakers/${encodeURIComponent(logoBase)}`]
      : [
          `/bookmakers/${logoBase}.png`,
          `/bookmakers/${logoBase}.svg`,
          `/bookmakers/${logoBase}.jpeg`,
          `/bookmakers/${logoBase}.jpg`,
        ]
    : [];
  const [srcIndex, setSrcIndex] = useState(0);
  const [imageFailed, setImageFailed] = useState(false);
  const currentSrc = logoPaths[srcIndex] || null;

  const link = bookmaker.affiliate_link || "#";
  const hasAffiliate = !!bookmaker.affiliate_link;

  const showImage = currentSrc && !imageFailed;

  const content = (
    <div className={`flex items-center justify-center gap-2 ${className}`}>
      {showImage ? (
        <div className={`${sizeClasses[size]} min-w-[1.5rem] min-h-[1.5rem] relative flex-shrink-0 mx-auto`}>
          <Image
            src={currentSrc}
            alt={bookmaker.short_name || bookmaker.name}
            fill
            sizes="32px"
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
