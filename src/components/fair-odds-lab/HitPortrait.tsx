"use client";

import Image from "next/image";
import { useState, type ReactNode } from "react";

export function HitPortrait({ name, photoUrl, fallback }: { name: string; photoUrl?: string; fallback: ReactNode }) {
  const [failedUrl, setFailedUrl] = useState<string | null>(null);
  const allowed = /^https:\/\/images\.fotmob\.com\/image_resources\/playerimages\/\d+\.png$/.test(photoUrl ?? "");
  return <div className="relative flex h-40 w-32 shrink-0 items-end justify-center overflow-hidden rounded-t-[2rem] bg-gradient-to-t from-emerald-400/15 to-transparent sm:h-44 sm:w-36">
    {allowed && failedUrl !== photoUrl ? <Image src={photoUrl!} alt={name} width={176} height={176} unoptimized loading="lazy" className="relative h-full w-full object-contain object-bottom drop-shadow-[0_8px_15px_rgba(0,0,0,0.4)]" onError={() => setFailedUrl(photoUrl!)} /> : <div className="w-24 pb-3" aria-label={`${name} · portrait unavailable`}>{fallback}</div>}
  </div>;
}
