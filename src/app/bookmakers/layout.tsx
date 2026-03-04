import type { Metadata } from "next";
import Script from "next/script";
import { BASE_URL, BOOKMAKERS_INDEXABLE } from "@/lib/config";

const title = "Recommended Bookmakers | 8 Field-Tested Operators & Betting Glossary";
const description =
  "Eight recommended bookmakers (Midnite, BetVictor, Bwin, Coral, Ladbrokes, BetMGM, William Hill, Betfred): honest reviews, welcome offers, key concepts, comparison table, and industry glossary.";
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

/** William Hill affiliate impression script (S.ashx). Loads on /bookmakers so William Hill can track page views. */
const WH_IMPRESSION_SCRIPT =
  "https://campaigns.williamhill.com/S.ashx?btag=a_214702b_1456c_&affid=1744894&siteid=214702&adid=1456&c=";

export default function BookmakersLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <>
      <Script src={WH_IMPRESSION_SCRIPT} strategy="lazyOnload" />
      {children}
    </>
  );
}
