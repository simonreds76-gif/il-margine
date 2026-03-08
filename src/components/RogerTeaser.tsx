"use client";

import { useEffect } from "react";
import { usePathname } from "next/navigation";
import { useChatContext } from "@/contexts/ChatContext";

const ROGER_TEASER_KEY = "roger_teaser_seen";
const ROGER_TEASER_DELAY_MS = 5000;
const ROGER_ENABLED = true;

const TENNIS_PAGES = ["/", "/tennis-tips", "/player-props", "/atp-tennis", "/fair-odds"];

export default function RogerTeaser() {
  const pathname = usePathname();
  const openChat = useChatContext()?.openChat;

  useEffect(() => {
    if (typeof window === "undefined") return;
    if (!ROGER_ENABLED) return;
    if (!TENNIS_PAGES.includes(pathname || "")) return;
    if (pathname === "/resources/roger") return;

    // Only auto-open for first-time visitors (localStorage persists across sessions)
    const seenEver = localStorage.getItem(ROGER_TEASER_KEY);
    if (seenEver) return;

    // Also skip if already shown this session (belt-and-suspenders)
    const seenThisSession = sessionStorage.getItem(ROGER_TEASER_KEY);
    if (seenThisSession) return;

    const t = setTimeout(() => {
      localStorage.setItem(ROGER_TEASER_KEY, "1");
      sessionStorage.setItem(ROGER_TEASER_KEY, "1");
      openChat?.();
    }, ROGER_TEASER_DELAY_MS);

    return () => clearTimeout(t);
  }, [pathname, openChat]);

  return null;
}
