"use client";

import { SpeedInsights } from "@vercel/speed-insights/next";

export default function SpeedInsightsClient() {
  return (
    <SpeedInsights
      sampleRate={1}
      beforeSend={(data) => {
        const pathname = new URL(data.url, "https://ilmargine.bet").pathname;
        const internal = ["/admin", "/model-monitor"].some(
          (prefix) => pathname === prefix || pathname.startsWith(`${prefix}/`),
        );
        return internal ? null : data;
      }}
    />
  );
}
