"use client";

import dynamic from "next/dynamic";
import { usePathname } from "next/navigation";

const ChatWidget = dynamic(() => import("@/components/ChatWidget"), { ssr: false });
const RogerTeaser = dynamic(() => import("@/components/RogerTeaser"), { ssr: false });

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
