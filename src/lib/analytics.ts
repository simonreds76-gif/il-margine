/**
 * GA4 custom event helper. Use for calculator, conversion, and error tracking.
 * No-op if GA is not configured or gtag is not yet loaded.
 * window.gtag is declared in GoogleAnalyticsRouteTracker.tsx.
 */

export function track(eventName: string, params?: Record<string, unknown>): void {
  if (typeof window === "undefined") return;
  const id = process.env.NEXT_PUBLIC_GA_MEASUREMENT_ID;
  if (!id || !window.gtag) return;
  window.gtag("event", eventName, params);
}
