import type { Metadata } from "next";
import { BASE_URL } from "@/lib/config";

const title = "Fair Odds & Match Analysis | Daily Tennis";
const description =
  "Daily tennis matches with model-based fair odds, serve/return stats by surface, and matchup analysis.";
const url = `${BASE_URL}/fair-odds`;

export const metadata: Metadata = {
  title,
  description,
  alternates: { canonical: url },
  robots: { index: false, follow: true },
};

export default function FairOddsLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return <>{children}</>;
}
