import type { Metadata } from "next";
import { BASE_URL } from "@/lib/config";

const title = "Goalscorer Value Picks | Shadow Tracking Live";
const description =
  "Selective anytime-goalscorer value picks from Il Margine's live shadow tracker, updated around confirmed lineups across four major leagues.";
const url = `${BASE_URL}/anytime-goalscorer`;

export const metadata: Metadata = {
  title,
  description,
  alternates: { canonical: url },
  openGraph: {
    type: "website",
    locale: "en_GB",
    url,
    siteName: "Il Margine",
    title,
    description,
    images: [{ url: "/og.png", width: 1200, height: 630, alt: "Il Margine - Goalscorer Model" }],
  },
  twitter: {
    card: "summary_large_image",
    title,
    description,
    images: ["/og.png"],
  },
};

export default function AnytimeGoalscorerLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return <>{children}</>;
}
