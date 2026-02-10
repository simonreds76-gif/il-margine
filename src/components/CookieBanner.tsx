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
  const [consented, setConsented] = useState<boolean | null>(null);

  useEffect(() => {
    setConsented(typeof window !== "undefined" && localStorage.getItem(CONSENT_KEY) === "1");
  }, []);

  const accept = () => {
    localStorage.setItem(CONSENT_KEY, "1");
    setConsented(true);
  };

  if (!measurementId) return null;
  if (consented === null) return null;
  if (consented) {
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

  return (
    <div
      className="fixed bottom-0 left-0 right-0 z-50 border-t border-slate-700/60 bg-slate-900/95 backdrop-blur px-4 py-3 text-center text-sm text-slate-300"
      role="dialog"
      aria-label="Cookie consent"
    >
      <p className="max-w-2xl mx-auto">
        We use cookies for analytics so we can improve the site.{" "}
        <Link href="/cookies-policy" className="text-emerald-400 hover:text-emerald-300 underline">
          Cookies policy
        </Link>
        {" · "}
        <button
          type="button"
          onClick={accept}
          className="font-medium text-slate-100 hover:text-white underline focus:outline-none focus:ring-2 focus:ring-emerald-500 focus:ring-offset-2 focus:ring-offset-slate-900 rounded"
        >
          Accept
        </button>
      </p>
    </div>
  );
}
