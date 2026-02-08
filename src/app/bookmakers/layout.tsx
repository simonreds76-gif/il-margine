import type { Metadata } from "next";
import { BASE_URL } from "@/lib/config";

export const dynamic = "force-dynamic";
export const revalidate = 0;

const title = "Recommended Bookmakers | Best Betting Sites for Tips";
const description =
  "Where to place your bets. We recommend bookmakers based on market coverage, odds quality, betting limits, and account management.";
const url = `${BASE_URL}/bookmakers`;

export const metadata: Metadata = {
  title,
  description,
  alternates: { canonical: url },
  robots: { index: false, follow: true },
  openGraph: {
    type: "website",
    locale: "en_GB",
    url,
    siteName: "Il Margine",
    title,
    description,
    images: [{ url: "/og.png", width: 1200, height: 630, alt: "Il Margine - Recommended Bookmakers" }],
  },
  twitter: {
    card: "summary_large_image",
    title,
    description,
    images: ["/og.png"],
  },
};

export default function BookmakersLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return <>{children}</>;
}
