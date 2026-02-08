"use client";

import dynamic from "next/dynamic";

// Vercel Speed Insights: works automatically when deployed on Vercel (no extra config).
const SpeedInsights = dynamic(
  () => import("@vercel/speed-insights/next").then((m) => m.SpeedInsights),
  { ssr: false }
);

export default function SpeedInsightsClient() {
  return <SpeedInsights />;
}
