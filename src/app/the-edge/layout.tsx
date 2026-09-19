import type { Metadata } from "next";
import { BASE_URL } from "@/lib/config";

const title = "Our Methodology | How We Find Betting Edge";
const description =
  "How Il Margine uses evidence, estimated fair odds and market prices to assess betting value. Explore the method, assumptions and published results.";
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
    description,
    images: [{ url: "/brand/20260913/social.png", width: 1200, height: 630, alt: "Il Margine - The Edge" }],
  },
  twitter: {
    card: "summary_large_image",
    title: "Betting Methodology from a Former Odds Compiler | Il Margine",
    description,
    images: ["/brand/20260913/social.png"],
  },
};

export default function TheEdgeLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return children;
}

