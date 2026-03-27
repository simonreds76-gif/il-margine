import type { Metadata } from "next";
import { BASE_URL } from "@/lib/config";

const title = "Our Methodology | How We Find Betting Edge | Il Margine";
const description =
  "Former odds compiler methodology: how Il Margine strips bookmaker margin to find mathematical edge in player props and ATP tennis markets.";
const url = `${BASE_URL}/the-edge`;

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
    title: "Betting Methodology from a Former Odds Compiler | Il Margine",
    description:
      "25 years in the betting industry. Former odds compiler. Proprietary models that strip bookmaker margin to find true odds in player props and ATP tennis.",
    images: [{ url: "/og.png", width: 1200, height: 630, alt: "Il Margine - The Edge" }],
  },
  twitter: {
    card: "summary_large_image",
    title: "Betting Methodology from a Former Odds Compiler | Il Margine",
    description:
      "25 years in the betting industry. Former odds compiler. Proprietary models that strip bookmaker margin to find true odds in player props and ATP tennis.",
    images: ["/og.png"],
  },
};

export default function TheEdgeLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return children;
}

