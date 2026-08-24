"use client";

import { useState } from "react";
import Image from "next/image";
import Link from "next/link";
import { Bookmaker } from "@/lib/supabase";
import { resolveBookmakerLogo } from "@/lib/bookmaker-logos";

interface BookmakerLogoProps {
  /** Single bookmaker or array (Supabase sometimes returns relation as array) */
  bookmaker: Bookmaker | Bookmaker[] | null | undefined;
  size?: "sm" | "md" | "lg";
  showName?: boolean;
  className?: string;
  /** When true, render logo only (no Link). Use when already inside a Link to avoid invalid nested anchors. */
  noLink?: boolean;
  /** When true, prevent parent click handlers from firing when the logo link is tapped. */
  stopPropagationOnClick?: boolean;
}

// Logos that have lots of padding in the asset - scale up so they match others' visual size.
const logoScale: Record<string, number> = {
  "10bet": 1,
  ballybet: 1.08,
  pinnacle: 2,
  ladbrokes: 0.85,
  bwin: 1.05,
  betway: 1.14,
  boylesports: 0.92,
  spreadex: 0.95,
  sbk: 1,
  virginbet: 1,
};

const logoFrameClasses: Record<string, string> = {
  "10bet": "rounded-md border border-slate-200/90 bg-white px-1 py-0.5 shadow-[inset_0_1px_0_rgba(255,255,255,0.8)]",
  ballybet: "rounded-md border border-red-300/70 bg-[#c8102e] px-1.5 py-1 shadow-[inset_0_1px_0_rgba(255,255,255,0.18)]",
  bwin: "rounded-md border border-slate-200/90 bg-white p-1 shadow-[inset_0_1px_0_rgba(255,255,255,0.8)]",
  spreadex: "rounded-md border border-slate-200/90 bg-white px-1 py-0.5 shadow-[inset_0_1px_0_rgba(255,255,255,0.8)]",
  sbk: "rounded-md border border-slate-200/90 bg-white px-2 py-1 shadow-[inset_0_1px_0_rgba(255,255,255,0.8)]",
};

// All logos one step larger so thumbnails are easier to recognise (was 24/32/40px)
const sizeClasses = {
  sm: "w-16 h-8",
  md: "w-20 h-10",
  lg: "w-24 h-12",
};

export default function BookmakerLogo({
  bookmaker: bookmakerProp,
  size = "sm",
  showName = false,
  className = "",
  noLink = false,
  stopPropagationOnClick = false,
}: BookmakerLogoProps) {
  const bookmaker = Array.isArray(bookmakerProp) ? bookmakerProp[0] : bookmakerProp;
  const [srcIndex, setSrcIndex] = useState(0);
  const [imageFailed, setImageFailed] = useState(false);

  if (!bookmaker) {
    return (
      <span className={`text-xs text-slate-600 ${className}`}>-</span>
    );
  }

  const resolvedLogo = resolveBookmakerLogo(bookmaker);
  const logoPaths = resolvedLogo?.paths ?? [];
  const currentSrc = logoPaths[srcIndex] || null;

  const link = bookmaker.affiliate_link || "#";
  const hasAffiliate = !!bookmaker.affiliate_link;

  const showImage = currentSrc && !imageFailed;
  const scale = logoScale[resolvedLogo?.key ?? ""] ?? 1;
  const frameClassName = logoFrameClasses[resolvedLogo?.key ?? ""] ?? "";

  const displayName =
    resolvedLogo?.displayName ||
    bookmaker.name ||
    bookmaker.short_name ||
    "";

  const content = (
    <div className={`flex items-center justify-center gap-2 ${className}`}>
      {showImage ? (
        <div
          className={`${sizeClasses[size]} min-h-[2rem] relative flex-shrink-0 mx-auto overflow-hidden ${frameClassName}`}
        >
          <div className="relative h-full w-full">
            <div className="absolute inset-0" style={{ transform: `scale(${scale})` }}>
              <Image
                src={currentSrc}
                alt={displayName}
                fill
                sizes="96px"
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

  // If no affiliate link or noLink prop (e.g. already inside a Link), just show the logo
  if (!hasAffiliate || noLink) {
    return content;
  }

  return (
    <Link
      href={link}
      target="_blank"
      rel="noopener noreferrer"
      className="hover:opacity-80 transition-opacity"
      title={hasAffiliate ? `Visit ${displayName}` : undefined}
      onClick={stopPropagationOnClick ? (event) => event.stopPropagation() : undefined}
      onMouseDown={stopPropagationOnClick ? (event) => event.stopPropagation() : undefined}
      onTouchStart={stopPropagationOnClick ? (event) => event.stopPropagation() : undefined}
    >
      {content}
    </Link>
  );
}
