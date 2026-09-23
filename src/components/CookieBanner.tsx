"use client";

import { useSyncExternalStore } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import Script from "next/script";
import GoogleAnalyticsRouteTracker from "./GoogleAnalyticsRouteTracker";
import AiReferralTracker from "./AiReferralTracker";

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

const POLICY_PATHS = ["/cookies-policy", "/privacy-policy"];
const CONSENT_EVENT = "ilmargine-consent-change";

type ConsentState = "accepted" | "rejected" | "pending" | null;

function readConsentSnapshot(): ConsentState {
  if (typeof window === "undefined") return null;
  const stored = window.localStorage.getItem(CONSENT_KEY);
  return stored === "1" ? "accepted" : stored === "0" ? "rejected" : "pending";
}

function subscribeToConsent(onStoreChange: () => void) {
  if (typeof window === "undefined") return () => {};
  const handler = () => onStoreChange();
  window.addEventListener("storage", handler);
  window.addEventListener(CONSENT_EVENT, handler);
  return () => {
    window.removeEventListener("storage", handler);
    window.removeEventListener(CONSENT_EVENT, handler);
  };
}

export default function CookieBanner({ measurementId }: Props) {
  const pathname = usePathname();
  const consent = useSyncExternalStore(subscribeToConsent, readConsentSnapshot, () => null);

  const isPolicyPage = pathname && POLICY_PATHS.some((p) => pathname.startsWith(p));

  const accept = () => {
    window.localStorage.setItem(CONSENT_KEY, "1");
    window.dispatchEvent(new Event(CONSENT_EVENT));
  };

  const reject = () => {
    window.localStorage.setItem(CONSENT_KEY, "0");
    window.dispatchEvent(new Event(CONSENT_EVENT));
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
            <AiReferralTracker />
          </>
        )}
      </>
    );
  }

  if (consent === "rejected") {
    // Remember either choice. Analytics load only after an explicit acceptance.
    return null;
  }

  // On policy pages, never block — let the user read the policy before deciding.
  if (isPolicyPage) return null;

  // Both choices persist; only Accept loads analytics.
  return (
    <div
      className="fixed bottom-0 left-0 right-0 z-[100] flex justify-center p-3 sm:justify-end sm:p-5 pointer-events-none"
      role="dialog"
      aria-label="Cookie consent"
    >
      <div className="pointer-events-auto w-full max-w-md rounded-2xl border border-[#30434b] bg-[#111a20] p-5 shadow-xl">
        <h2 className="text-lg font-semibold text-slate-100 mb-2">We use cookies</h2>
        <p className="text-sm text-slate-400 mb-4">
          Allow Google Analytics cookies to help us understand visits and feature usage. Vercel’s cookieless traffic and performance measurement runs separately.{" "}
          <Link href="/cookies-policy" target="_blank" rel="noopener noreferrer" className="text-emerald-400 hover:text-emerald-300 underline">
            Cookies policy
          </Link>
        </p>
        <div className="flex flex-col sm:flex-row gap-3">
          <button
            type="button"
            onClick={accept}
            className="flex-1 px-4 py-3 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white font-medium transition-colors focus:outline-none focus:ring-2 focus:ring-emerald-500 focus:ring-offset-2 focus:ring-offset-slate-900"
          >
            Allow analytics
          </button>
          <button
            type="button"
            onClick={reject}
            className="flex-1 px-4 py-3 rounded-lg border border-slate-600 text-slate-400 hover:text-slate-300 hover:border-slate-500 transition-colors focus:outline-none focus:ring-2 focus:ring-slate-500 focus:ring-offset-2 focus:ring-offset-slate-900"
          >
            Decline Google Analytics
          </button>
        </div>
      </div>
    </div>
  );
}
