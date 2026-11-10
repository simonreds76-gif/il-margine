import type { TipPortrait } from "@/lib/tip-artwork-types";
import { smallTipPhoto } from "@/lib/small-tip-photo";
import PickPortrait from "./PickPortrait";
import styles from "./TipPortraits.module.css";

export default function TipPortraits({ portraits, size = "card", className = "" }: { portraits?: TipPortrait[]; size?: "card" | "compact" | "hero"; className?: string }) {
  if (!portraits?.length) return null;
  const pixels = size === "hero" ? 80 : size === "compact" ? 32 : 48;
  return <span className={`${styles.portraitGroup} ${styles[size]} ${className}`}>
    {portraits.map((portrait, index) => <PickPortrait key={`${index}:${portrait.name}:${portrait.src}`} portrait={{ ...portrait, small: smallTipPhoto(portrait.src, pixels), smallFallback: smallTipPhoto(portrait.fallbackSrc, pixels) }} />)}
  </span>;
}
