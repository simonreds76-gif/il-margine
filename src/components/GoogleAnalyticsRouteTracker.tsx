"use client";

import { usePathname } from "next/navigation";
import { useEffect } from "react";

declare global {
  interface Window {
    gtag?: (command: string, targetId: string, config?: Record<string, unknown>) => void;
  }
}

interface Props {
  measurementId: string;
}

export default function GoogleAnalyticsRouteTracker({ measurementId }: Props) {
  const pathname = usePathname();

  useEffect(() => {
    if (typeof window === "undefined" || !window.gtag) return;
    window.gtag("config", measurementId, { page_path: pathname || "/" });
  }, [pathname, measurementId]);

  return null;
}
