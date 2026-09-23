"use client";
import { useState, useSyncExternalStore } from "react";
import { GA_MEASUREMENT_ID } from "@/lib/config";
const KEY = "ilmargine_cookie_consent";
function subscribe(update: () => void) {
  window.addEventListener("storage", update); window.addEventListener("ilmargine-consent-change", update);
  return () => { window.removeEventListener("storage", update); window.removeEventListener("ilmargine-consent-change", update); };
}
function snapshot() { try { return localStorage.getItem(KEY); } catch { return null; } }
export default function CookieSettings() {
  const consent = useSyncExternalStore(subscribe, snapshot, () => null);
  const [error, setError] = useState("");
  function save(accept: boolean) {
    try {
      localStorage.setItem(KEY, accept ? "1" : "0");
      if (!accept) {
        if (GA_MEASUREMENT_ID) (window as unknown as Record<string, unknown>)[`ga-disable-${GA_MEASUREMENT_ID}`] = true;
        window.gtag?.("consent", "update", { analytics_storage: "denied" });
        localStorage.removeItem("ilmargine_first_touch_source");
        sessionStorage.removeItem("ilmargine_ai_referral_logged");
        const parts = location.hostname.split(".");
        const domains = ["", ...parts.map((_, i) => parts.slice(i).join(".")).filter(d => d.includes("."))];
        for (const cookie of document.cookie.split(";")) {
          const name = cookie.split("=", 1)[0].trim();
          if (!/^_ga(?:_|$)/.test(name)) continue;
          for (const domain of domains) document.cookie = `${name}=; Max-Age=0; Path=/;${domain ? ` Domain=${domain};` : ""}`;
        }
      }
      window.dispatchEvent(new Event("ilmargine-consent-change"));
      // Reload unloads an already-running analytics script after withdrawal.
      window.location.reload();
    } catch { setError("Your browser blocked saving this choice. Allow site storage or clear this site’s data in browser settings, then try again."); }
  }
  return <div className="cookie-choices" id="cookie-settings"><h2>Your Google Analytics choice</h2><p aria-live="polite">{consent === "1" ? "Currently allowed on this browser." : consent === "0" ? "Currently switched off on this browser." : "No saved choice on this browser. Google Analytics stays off until you accept."}</p><div className="flex flex-wrap gap-3"><button type="button" onClick={() => save(true)}>Allow Google Analytics</button><button type="button" onClick={() => save(false)}>Turn Google Analytics off</button></div><p>The page reloads to apply your choice. This setting does not switch off hosting logs or Vercel’s cookieless measurement.</p>{error && <p role="alert">{error}</p>}</div>;
}
