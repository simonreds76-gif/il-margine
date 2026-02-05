import type { Metadata } from "next";
import { BASE_URL } from "@/lib/config";

const title = "Anytime Goalscorer Betting Tips & Analysis";
const description =
  "Anytime goalscorer betting tips with analytical breakdowns based on roles, xG data and match context.";
const url = `${BASE_URL}/anytime-goalscorer`;

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
    images: [{ url: "/og.png", width: 1200, height: 630, alt: "Il Margine - Anytime Goalscorer" }],
  },
  twitter: {
    card: "summary_large_image",
    title,
    description,
    images: ["/og.png"],
  },
};

export default function AnytimeGoalscorerLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return <>{children}</>;
}
