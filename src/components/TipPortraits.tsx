"use client";
import { useState } from "react";
import type { TipPortrait } from "@/lib/tip-artwork-types";
import styles from "./TipPortraits.module.css";

function PickPortrait({ portrait }: { portrait: TipPortrait }) {
  const [failed, setFailed] = useState<string[]>([]);
  const src = [portrait.src, portrait.fallbackSrc].find((url) => url && !failed.includes(url));
  const isClub = portrait.kind === "club" || (src != null && src === portrait.fallbackSrc);
  return <span className={`${styles.portrait} ${isClub ? styles.crest : ""}`} title={portrait.name} aria-hidden="true">
    {src ? (
      // The existing small portraits are served directly; fixed dimensions avoid
      // layout shift and lazy loading keeps off-screen cards inexpensive.
      // eslint-disable-next-line @next/next/no-img-element
      <img src={src} alt="" width={48} height={48} loading="lazy" decoding="async"
        onError={() => setFailed((urls) => [...urls, src])} />
    ) : <svg viewBox="0 0 48 48" fill="none" aria-hidden="true">
      {portrait.kind === "club" ? <path d="M12 10l12-4 12 4v13c0 9-12 17-12 17S12 32 12 23V10Z" stroke="currentColor" strokeWidth="2" /> : <><circle cx="24" cy="17" r="7" fill="currentColor"/><path d="M10 41v-5a14 14 0 0128 0v5" fill="currentColor"/></>}
    </svg>}
  </span>;
}

export default function TipPortraits({ portraits, size = "card", className = "" }: { portraits?: TipPortrait[]; size?: "card" | "compact" | "hero"; className?: string }) {
  if (!portraits?.length) return null;
  return <span className={`${styles.portraitGroup} ${styles[size]} ${className}`}>
    {portraits.map((portrait, index) => <PickPortrait key={`${index}:${portrait.name}:${portrait.src}`} portrait={portrait} />)}
  </span>;
}
