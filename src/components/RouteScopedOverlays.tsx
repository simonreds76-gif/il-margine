"use client";

import { usePathname } from "next/navigation";
import dynamic from "next/dynamic";

// Load the tournament overlay only on the routes that use it.
const WorldCupTelegramOverlay = dynamic(() => import("@/components/WorldCupTelegramOverlay"));

function shouldShowWorldCupTelegram(pathname: string | null): boolean {
  if (!pathname) return false;
  return (
    pathname.startsWith("/penalty-takers/world-cup-2026") ||
    pathname.startsWith("/world-cup-2026-free-picks")
  );
}

export default function RouteScopedOverlays() {
  const pathname = usePathname();

  if (shouldShowWorldCupTelegram(pathname)) {
    return <WorldCupTelegramOverlay />;
  }

  return null;
}
