import type { Metadata } from "next";
import { BASE_URL } from "@/lib/config";

// The root layout applies the "%s | Il Margine" template, so the brand is not
// repeated here. Search engines may still choose their own display title.
const title = "Betting Calculators: Kelly, Fair Odds, CLV";
const description =
  "Four betting calculators: flat-stake returns with simulated drawdown, fractional Kelly stake sizing, no-vig fair odds and closing line value.";
const url = `${BASE_URL}/calculator`;

export const metadata: Metadata = {
  title,
  description,
  keywords: [
    "betting calculator",
    "kelly criterion calculator",
    "no vig calculator",
    "fair odds calculator",
    "closing line value calculator",
    "bankroll drawdown calculator",
  ],
  alternates: { canonical: url },
  openGraph: {
    type: "website",
    locale: "en_GB",
    url,
    siteName: "Il Margine",
    title: `${title} | Il Margine`,
    description,
    images: [{ url: "/brand/20260913/social.png", width: 1200, height: 630, alt: "Il Margine - Calculator" }],
  },
  twitter: {
    card: "summary_large_image",
    title: `${title} | Il Margine`,
    description,
    images: ["/brand/20260913/social.png"],
  },
};

export default function CalculatorLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return <>{children}</>;
}
