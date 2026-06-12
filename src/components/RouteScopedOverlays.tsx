"use client";

import { usePathname } from "next/navigation";
import ChatWidget from "@/components/ChatWidget";
import WorldCupTelegramOverlay from "@/components/WorldCupTelegramOverlay";

function shouldShowWorldCupTelegram(pathname: string | null): boolean {
  if (!pathname) return false;
  return (
    pathname === "/" ||
    pathname.startsWith("/penalty-takers") ||
    pathname.startsWith("/anytime-goalscorer") ||
    pathname.startsWith("/world-cup-2026-free-picks")
  );
}

export default function RouteScopedOverlays() {
  const pathname = usePathname();

  if (shouldShowWorldCupTelegram(pathname)) {
    return <WorldCupTelegramOverlay />;
  }

  if (pathname === "/resources/roger") {
    return <ChatWidget />;
  }

  return null;
}
