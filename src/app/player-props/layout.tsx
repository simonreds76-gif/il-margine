import type { Metadata } from "next";
import { BASE_URL } from "@/lib/config";
import { BreadcrumbSchema } from "@/components/BreadcrumbSchema";

const title = "Player Props Betting Tips | Fouls, Shots, Cards & Value Markets";
const description =
  "Independent football player props tips: shots, fouls, tackles and cards. Browse match picks, recorded bookmaker odds, analysis and tracked results.";
const url = `${BASE_URL}/player-props`;

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
    images: [{ url: "/brand/20260913/social.png", width: 1200, height: 630, alt: "Il Margine - Player Props" }],
  },
  twitter: {
    card: "summary_large_image",
    title,
    description,
    images: ["/brand/20260913/social.png"],
  },
};

export default function PlayerPropsLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <>
      <BreadcrumbSchema crumbs={[
        { name: "Home", url: "/" },
        { name: "Player Props", url: "/player-props" },
      ]} />
      {children}
    </>
  );
}
