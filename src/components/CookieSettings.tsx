"use client";
import { useState, useSyncExternalStore } from "react";
import { GA_MEASUREMENT_ID } from "@/lib/config";
import { readConsentSnapshot, readServerConsentSnapshot, saveConsent, subscribeToConsent } from "@/lib/cookie-consent";
export default function CookieSettings() {
  const consent = useSyncExternalStore(subscribeToConsent, readConsentSnapshot, readServerConsentSnapshot);
  const [error, setError] = useState("");
  function save(accept: boolean) {
    try {
      if (!accept) {
        if (GA_MEASUREMENT_ID) (window as unknown as Record<string, unknown>)[`ga-disable-${GA_MEASUREMENT_ID}`] = true;
        window.gtag?.("consent", "update", { analytics_storage: "denied" });
        try { localStorage.removeItem("ilmargine_first_touch_source"); } catch { /* Storage may be blocked. */ }
        try { sessionStorage.removeItem("ilmargine_ai_referral_logged"); } catch { /* Still withdraw analytics. */ }
        try {
          const parts = location.hostname.split(".");
          const domains = ["", ...parts.map((_, i) => parts.slice(i).join(".")).filter(d => d.includes("."))];
          for (const cookie of document.cookie.split(";")) {
            const name = cookie.split("=", 1)[0].trim();
            if (!/^_ga(?:_|$)/.test(name)) continue;
            for (const domain of domains) document.cookie = `${name}=; Max-Age=0; Path=/;${domain ? ` Domain=${domain};` : ""}`;
          }
        } catch { /* A blocked cookie API must not prevent withdrawal. */ }
      }
      const persisted = saveConsent(accept ? "accepted" : "rejected");
      if (accept && !persisted) {
        setError("Google Analytics is allowed for this page session only. Your browser blocked saving the choice.");
        return;
      }
      // Reload unloads an already-running analytics script after withdrawal.
      window.location.reload();
    } catch { setError("Your browser blocked saving this choice. Allow site storage or clear this site’s data in browser settings, then try again."); }
  }
  return <div className="cookie-choices" id="cookie-settings"><h2>Your Google Analytics choice</h2><p aria-live="polite">{consent === "accepted" ? "Currently allowed on this browser." : consent === "rejected" ? "Currently switched off on this browser." : "No saved choice on this browser. Google Analytics stays off until you accept."}</p><div className="flex flex-wrap gap-3"><button type="button" onClick={() => save(true)}>Allow Google Analytics</button><button type="button" onClick={() => save(false)}>Turn Google Analytics off</button></div><p>The page reloads to apply your choice. This setting does not switch off hosting logs or Vercel’s cookieless measurement.</p>{error && <p role="alert">{error}</p>}</div>;
}
