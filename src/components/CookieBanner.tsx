"use client";

import { useSyncExternalStore } from "react";
import { usePathname } from "next/navigation";
import Script from "next/script";
import GoogleAnalyticsRouteTracker from "./GoogleAnalyticsRouteTracker";
import AiReferralTracker from "./AiReferralTracker";
import { readConsentSnapshot, readServerConsentSnapshot, saveConsent, subscribeToConsent } from "@/lib/cookie-consent";

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

export default function CookieBanner({ measurementId }: Props) {
  const pathname = usePathname();
  const consent = useSyncExternalStore(subscribeToConsent, readConsentSnapshot, readServerConsentSnapshot);

  const isPolicyPage = pathname && POLICY_PATHS.some((p) => pathname.startsWith(p));

  const accept = () => saveConsent("accepted");
  const reject = () => saveConsent("rejected");

  if (!measurementId) return null;

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
      data-consent-banner
      className="pointer-events-none fixed inset-x-0 bottom-0 z-[100] flex justify-center px-3 pt-3 pb-[max(0.75rem,env(safe-area-inset-bottom))] sm:justify-end sm:px-5 sm:pb-5"
      role="region"
      aria-labelledby="cookie-consent-title"
    >
      <div className="pointer-events-auto w-full max-w-[400px] rounded-xl border border-[#30434b] bg-[#111a20] p-4 shadow-xl">
        <h2 id="cookie-consent-title" className="mb-2 text-base font-semibold text-slate-100">Google Analytics cookies</h2>
        <p className="mb-3 text-sm leading-snug text-slate-300">
          We’d like to use them to understand visits and feature use. Vercel’s cookieless traffic and performance measurement runs separately.{" "}
          <a href="/cookies-policy" target="_blank" rel="noopener noreferrer" className="text-emerald-400 underline hover:text-emerald-300">
            Cookies policy
          </a>
        </p>
        <div className="grid grid-cols-2 gap-2">
          <button
            type="button"
            onClick={accept}
            aria-label="Allow Google Analytics cookies"
            className="min-h-11 rounded-lg border border-[#3a5560] bg-[#172630] px-4 py-2 text-sm font-medium text-slate-100 hover:border-emerald-400 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-emerald-400 focus-visible:ring-offset-2 focus-visible:ring-offset-[#111a20]"
          >
            Allow
          </button>
          <button
            type="button"
            onClick={reject}
            aria-label="Decline Google Analytics cookies"
            className="min-h-11 rounded-lg border border-[#3a5560] bg-[#172630] px-4 py-2 text-sm font-medium text-slate-100 hover:border-emerald-400 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-emerald-400 focus-visible:ring-offset-2 focus-visible:ring-offset-[#111a20]"
          >
            Decline
          </button>
        </div>
      </div>
    </div>
  );
}
