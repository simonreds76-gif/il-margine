import type { Metadata } from "next";
import Script from "next/script";
import { BASE_URL, BOOKMAKERS_INDEXABLE } from "@/lib/config";

const title = "UK Bookmaker Margin Index | Football & Tennis";
const description =
  "Compare measured UK bookmaker margins by football and tennis market, with dated samples, transparent methodology, independent reviews and clearly labelled partner offers.";
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
    images: [{ url: `${BASE_URL}/banner.png`, width: 1200, height: 400, alt: "Il Margine UK bookmaker margin index", type: "image/png" }],
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
