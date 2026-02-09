import type { Metadata } from "next";
import { BASE_URL, BOOKMAKERS_INDEXABLE } from "@/lib/config";

const title = "Recommended Bookmakers | 8 Field-Tested Operators & Betting Glossary";
const description =
  "Eight recommended bookmakers (Midnite, BetVictor, Unibet, Coral, Ladbrokes, BetMGM, William Hill, Betfred): honest reviews, welcome offers, key concepts, comparison table, and industry glossary.";
const url = `${BASE_URL}/bookmakers`;

export const metadata: Metadata = {
  title,
  description,
  alternates: { canonical: url },
  robots: { index: BOOKMAKERS_INDEXABLE, follow: true },
  openGraph: {
    type: "website",
    locale: "en_GB",
    url,
    siteName: "Il Margine",
    title,
    description,
    images: [{ url: `${BASE_URL}/banner.png`, width: 1200, height: 400, alt: "Il Margine - Recommended Bookmakers", type: "image/png" }],
  },
  twitter: {
    card: "summary_large_image",
    title,
    description,
    images: [`${BASE_URL}/banner.png`],
  },
};

export default function BookmakersLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return <>{children}</>;
}
