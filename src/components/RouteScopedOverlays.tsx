"use client";

import { usePathname } from "next/navigation";
import ChatWidget from "@/components/ChatWidget";
import RogerTeaser from "@/components/RogerTeaser";

function shouldHideOverlays(pathname: string | null): boolean {
  return pathname?.startsWith("/penalty-takers/world-cup-2026") ?? false;
}

export default function RouteScopedOverlays() {
  const pathname = usePathname();

  if (shouldHideOverlays(pathname)) {
    return null;
  }

  return (
    <>
      <ChatWidget />
      <RogerTeaser />
    </>
  );
}
