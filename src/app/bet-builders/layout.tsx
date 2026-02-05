import type { Metadata } from "next";
import { BASE_URL } from "@/lib/config";

const title = "Football Bet Builder Tips | Same Game Combo Analysis";
const description =
  "Football bet builder tips and same game combo analysis, focusing on structure, correlation and risk control.";
const url = `${BASE_URL}/bet-builders`;

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
    images: [{ url: "/og.png", width: 1200, height: 630, alt: "Il Margine - Bet Builders" }],
  },
  twitter: {
    card: "summary_large_image",
    title,
    description,
    images: ["/og.png"],
  },
};

export default function BetBuildersLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return <>{children}</>;
}
