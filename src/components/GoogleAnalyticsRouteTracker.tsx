"use client";

import { usePathname, useSearchParams } from "next/navigation";
import { useEffect } from "react";

declare global {
  interface Window {
    gtag?: (command: string, a?: string, b?: Record<string, unknown>) => void;
  }
}

interface Props {
  measurementId: string;
}

export default function GoogleAnalyticsRouteTracker({ measurementId }: Props) {
  const pathname = usePathname();
  const searchParams = useSearchParams();

  useEffect(() => {
    if (typeof window === "undefined" || !window.gtag) return;
    const query = searchParams?.toString();
    const pagePath = query ? `${pathname || "/"}?${query}` : pathname || "/";
    window.gtag("config", measurementId, {
      page_path: pagePath,
      page_location: window.location.href,
      page_referrer: document.referrer || undefined,
    });
  }, [pathname, searchParams, measurementId]);

  return null;
}
