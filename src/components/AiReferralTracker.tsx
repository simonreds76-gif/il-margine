"use client";

import { useEffect } from "react";
import { usePathname, useSearchParams } from "next/navigation";

const AI_REFERRAL_SESSION_KEY = "ilmargine_ai_referral_logged";
const FIRST_TOUCH_KEY = "ilmargine_first_touch_source";

declare global {
  interface Window {
    gtag?: (command: string, a?: string, b?: Record<string, unknown>) => void;
  }
}

type AiSource = "chatgpt" | "perplexity" | "claude" | "copilot" | "gemini" | "grok";

function sourceFromText(value: string): AiSource | null {
  const v = value.toLowerCase();
  if (v.includes("chatgpt") || v.includes("openai")) return "chatgpt";
  if (v.includes("perplexity")) return "perplexity";
  if (v.includes("claude") || v.includes("anthropic")) return "claude";
  if (v.includes("copilot")) return "copilot";
  if (v.includes("gemini")) return "gemini";
  if (v.includes("grok") || v.includes("x.ai")) return "grok";
  return null;
}

function sourceFromReferrer(referrer: string): AiSource | null {
  try {
    if (!referrer) return null;
    const url = new URL(referrer);
    const host = url.hostname.toLowerCase();
    const path = url.pathname.toLowerCase();
    if (host === "x.com" && path.startsWith("/i/grok")) return "grok";
    const fromHost = sourceFromText(host);
    if (fromHost) return fromHost;
    const fullReferrer = `${host}${path}${url.search}`.toLowerCase();
    return sourceFromText(fullReferrer);
  } catch {
    return null;
  }
}

function detectAiReferral(
  searchParams: URLSearchParams,
  referrer: string
): { source: AiSource; via: "utm" | "referrer" } | null {
  const utmSource = searchParams.get("utm_source");
  const sourceFromUtm = utmSource ? sourceFromText(utmSource) : null;
  if (sourceFromUtm) return { source: sourceFromUtm, via: "utm" };

  const sourceFromRef = sourceFromReferrer(referrer);
  if (!sourceFromRef) return null;
  return { source: sourceFromRef, via: "referrer" };
}

export default function AiReferralTracker() {
  const pathname = usePathname();
  const searchParams = useSearchParams();

  useEffect(() => {
    if (typeof window === "undefined") return;
    const params = new URLSearchParams(searchParams?.toString() ?? "");
    const detected = detectAiReferral(params, document.referrer || "");
    if (!detected) return;

    const query = params.toString();
    const landingPath = query ? `${pathname || "/"}?${query}` : pathname || "/";

    try {
      const firstTouchExists = localStorage.getItem(FIRST_TOUCH_KEY);
      if (!firstTouchExists) {
        localStorage.setItem(
          FIRST_TOUCH_KEY,
          JSON.stringify({
            source: detected.source,
            via: detected.via,
            landing_path: landingPath,
            captured_at: new Date().toISOString(),
          })
        );
      }
    } catch {
      // ignore localStorage failures
    }

    const sentForSession = sessionStorage.getItem(AI_REFERRAL_SESSION_KEY);
    if (sentForSession === detected.source) return;

    let cancelled = false;
    let retries = 0;

    const send = () => {
      if (cancelled) return;
      if (!window.gtag) {
        if (retries < 10) {
          retries += 1;
          window.setTimeout(send, 500);
        }
        return;
      }

      window.gtag("event", "ai_referral_landing", {
        source: detected.source,
        via: detected.via,
        landing_path: landingPath,
        utm_source: params.get("utm_source") || undefined,
        utm_medium: params.get("utm_medium") || undefined,
        utm_campaign: params.get("utm_campaign") || undefined,
      });
      sessionStorage.setItem(AI_REFERRAL_SESSION_KEY, detected.source);
    };

    send();
    return () => {
      cancelled = true;
    };
  }, [pathname, searchParams]);

  return null;
}
