import type { Metadata } from "next";
import { BASE_URL, FAIR_ODDS_INDEXABLE } from "@/lib/config";

const title = "Fair Odds & Match Analysis | Daily Tennis";
const description =
  "Daily tennis matches with model-based fair odds, serve/return stats by surface, and matchup analysis.";
const url = `${BASE_URL}/fair-odds`;

export const metadata: Metadata = {
  title,
  description,
  alternates: { canonical: url },
  robots: { index: FAIR_ODDS_INDEXABLE, follow: true },
  openGraph: {
    title,
    description,
    url,
    siteName: "Il Margine",
    type: "website",
  },
  twitter: {
    card: "summary_large_image",
    title,
    description,
  },
};

export default function FairOddsLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return <>{children}</>;
}
