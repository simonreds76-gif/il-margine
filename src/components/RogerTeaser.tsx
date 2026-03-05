"use client";

import { useEffect } from "react";
import { usePathname } from "next/navigation";
import { useChatContext } from "@/contexts/ChatContext";

const ROGER_TEASER_KEY = "roger_teaser_seen";
const ROGER_TEASER_DELAY_MS = 5000;
const ROGER_ENABLED = process.env.NODE_ENV !== "production";

const TENNIS_PAGES = ["/", "/tennis-tips", "/player-props", "/atp-tennis", "/fair-odds"];

export default function RogerTeaser() {
  const pathname = usePathname();
  const openChat = useChatContext()?.openChat;

  useEffect(() => {
    if (typeof window === "undefined") return;
    if (!ROGER_ENABLED) return;
    if (!TENNIS_PAGES.includes(pathname || "")) return;
    if (pathname === "/resources/roger") return;

    const seen = sessionStorage.getItem(ROGER_TEASER_KEY);
    if (seen) return;

    const t = setTimeout(() => {
      sessionStorage.setItem(ROGER_TEASER_KEY, "1");
      openChat?.();
    }, ROGER_TEASER_DELAY_MS);

    return () => clearTimeout(t);
  }, [pathname, openChat]);

  return null;
}
