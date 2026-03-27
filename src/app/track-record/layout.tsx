import type { Metadata } from "next";
import { BASE_URL } from "@/lib/config";

const title = "Track Record | Verified Betting Results";
const description =
  "Verified betting track record: 1,227+ settled bets, +19% combined ROI across player props and ATP tennis. Pre-match timestamps, immutable records.";
const url = `${BASE_URL}/track-record`;

export const metadata: Metadata = {
  title,
  description,
  alternates: {
    canonical: url,
  },
  robots: "index, follow",
  openGraph: {
    type: "website",
    locale: "en_GB",
    siteName: "Il Margine",
    url,
    title: "Verified Betting Track Record - Player Props & ATP Tennis | Il Margine",
    description:
      "1,227+ settled bets with +19% combined ROI. Every selection posted before kick-off, every result logged transparently. No edits, no deletions.",
    images: [{ url: "/og.png", width: 1200, height: 630, alt: "Il Margine - Track Record" }],
  },
  twitter: {
    card: "summary_large_image",
    title: "Verified Betting Track Record - Player Props & ATP Tennis | Il Margine",
    description:
      "1,227+ settled bets with +19% combined ROI. Every selection posted before kick-off, every result logged transparently. No edits, no deletions.",
    images: ["/og.png"],
  },
};

export default function TrackRecordLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return children;
}
