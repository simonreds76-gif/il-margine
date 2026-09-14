"use client";

import Image from "next/image";
import { useState } from "react";

/** Decorative portrait; the adjacent server-rendered name remains authoritative. */
export default function PenaltyTakerPortrait({ name, src, rank, size = "large" }: {
  name: string; src?: string | null; rank: number; size?: "small" | "medium" | "large";
}) {
  const [failedSrc, setFailedSrc] = useState<string | null>(null);
  const pixels = size === "small" ? 36 : size === "medium" ? 48 : 56;
  const valid = src && /^https:\/\/images\.fotmob\.com\/image_resources\/playerimages\/\d+\.png$/.test(src) && failedSrc !== src;
  const initials = name.trim().split(/\s+/).filter(Boolean).map(word => Array.from(word)[0]).filter(Boolean);
  return <span aria-hidden="true" className={`relative inline-flex shrink-0 rounded-full border ${rank === 1 ? "border-emerald-300/40 bg-emerald-400/10" : "border-slate-600/60 bg-slate-800"}`} style={{ width: pixels, height: pixels }}>
    <span className="flex h-full w-full items-center justify-center overflow-hidden rounded-full">
      {valid ? <Image src={src} alt="" width={pixels} height={pixels} unoptimized loading="lazy" className="h-full w-full object-contain object-bottom" onError={() => setFailedSrc(src)} />
        : <span className="text-xs font-semibold tracking-wide text-slate-300">{initials.length > 1 ? initials[0] + initials.at(-1) : initials[0] || "—"}</span>}
    </span>
    <span className={`absolute -bottom-1 -right-1 flex h-5 w-5 items-center justify-center rounded-full border-2 border-slate-900 text-[10px] font-bold tabular-nums ${rank === 1 ? "bg-emerald-300 text-slate-950" : "bg-slate-600 text-white"}`}>{rank}</span>
  </span>;
}
