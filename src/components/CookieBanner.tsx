"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import Script from "next/script";
import GoogleAnalyticsRouteTracker from "./GoogleAnalyticsRouteTracker";

const CONSENT_KEY = "ilmargine_cookie_consent";

declare global {
  interface Window {
    dataLayer?: unknown[];
    gtag?: (command: string, a?: string, b?: Record<string, unknown>) => void;
  }
}

interface Props {
  measurementId: string;
}

export default function CookieBanner({ measurementId }: Props) {
  const [consent, setConsent] = useState<"accepted" | "rejected" | "pending" | null>(null);

  useEffect(() => {
    if (typeof window === "undefined") return;
    const stored = localStorage.getItem(CONSENT_KEY);
    setConsent(stored === "1" ? "accepted" : stored === "0" ? "rejected" : "pending");
  }, []);

  const accept = () => {
    localStorage.setItem(CONSENT_KEY, "1");
    setConsent("accepted");
  };

  const reject = () => {
    // Don't persist — modal will show again on next visit. Only Accept gets you off the hook.
    setConsent("rejected");
  };

  if (!measurementId) return null;
  if (consent === null) return null;

  if (consent === "accepted") {
    return (
      <>
        {measurementId && (
          <>
            <Script
              src={`https://www.googletagmanager.com/gtag/js?id=${measurementId}`}
              strategy="afterInteractive"
            />
            <Script id="ga-config" strategy="afterInteractive">
              {`window.dataLayer = window.dataLayer || []; function gtag(){dataLayer.push(arguments);} gtag('js', new Date()); gtag('config', '${measurementId}');`}
            </Script>
            <GoogleAnalyticsRouteTracker measurementId={measurementId} />
          </>
        )}
      </>
    );
  }

  if (consent === "rejected") {
    // They clicked "Essential only" — dismiss for this session only. No persist, so modal reappears on next visit.
    return null;
  }

  // Modal overlay — blocks the page. "Accept" persists and loads GA. "Essential only" dismisses now but modal shows again next visit.
  return (
    <div
      className="fixed inset-0 z-[100] flex items-center justify-center bg-slate-950/90 backdrop-blur-sm p-4"
      role="dialog"
      aria-modal="true"
      aria-label="Cookie consent"
    >
      <div className="w-full max-w-md rounded-xl border border-slate-700/60 bg-slate-900 p-6 shadow-2xl">
        <h2 className="text-lg font-semibold text-slate-100 mb-2">We use cookies</h2>
        <p className="text-sm text-slate-400 mb-6">
          We use analytics cookies to improve the site and understand how you use it — including what you ask Roger, our tennis chatbot.{" "}
          <Link href="/cookies-policy" className="text-emerald-400 hover:text-emerald-300 underline">
            Cookies policy
          </Link>
        </p>
        <div className="flex flex-col sm:flex-row gap-3">
          <button
            type="button"
            onClick={accept}
            className="flex-1 px-4 py-3 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white font-medium transition-colors focus:outline-none focus:ring-2 focus:ring-emerald-500 focus:ring-offset-2 focus:ring-offset-slate-900"
          >
            Accept
          </button>
          <button
            type="button"
            onClick={reject}
            className="flex-1 px-4 py-3 rounded-lg border border-slate-600 text-slate-400 hover:text-slate-300 hover:border-slate-500 transition-colors focus:outline-none focus:ring-2 focus:ring-slate-500 focus:ring-offset-2 focus:ring-offset-slate-900"
          >
            Essential only
          </button>
        </div>
      </div>
    </div>
  );
}
