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

// Map bookmaker short names to logo filenames
const bookmakerLogos: Record<string, string> = {
  "Bet365": "bet365.png",
  "Betfair": "betfair.png",
  "Paddy Power": "paddypower.png",
  "William Hill": "williamhill.png",
  "Ladbrokes": "ladbrokes.png",
  "Coral": "coral.png",
  "Sky Bet": "skybet.png",
  "Unibet": "unibet.png",
  "Betway": "betway.png",
  "888sport": "888sport.png",
  "Betvictor": "betvictor.png",
  "Betfred": "betfred.png",
  "BoyleSports": "boylesports.png",
  "Pinnacle": "pinnacle.png",
  "Marathon": "marathon.png",
  "DraftKings": "draftkings.png",
  "FanDuel": "fanduel.png",
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

  const logoFilename = bookmakerLogos[bookmaker.short_name] || bookmakerLogos[bookmaker.name];
  const logoPath = logoFilename ? `/bookmakers/${logoFilename}` : null;
  
  // Determine link - use affiliate if available, otherwise placeholder
  const link = bookmaker.affiliate_link || "#";
  const hasAffiliate = !!bookmaker.affiliate_link;

  const content = (
    <div className={`flex items-center gap-2 ${className}`}>
      {logoPath ? (
        <div className={`${sizeClasses[size]} relative flex-shrink-0`}>
          <Image
            src={logoPath}
            alt={bookmaker.short_name || bookmaker.name}
            fill
            className="object-contain"
            onError={(e) => {
              // Fallback if image doesn't exist
              e.currentTarget.style.display = "none";
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
