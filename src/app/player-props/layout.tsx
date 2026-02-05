import type { Metadata } from "next";
import { BASE_URL } from "@/lib/config";

const title = "Player Props Betting Tips | Fouls, Shots, Cards & Value Markets";
const description =
  "Player props betting tips covering fouls committed, fouls won, shots, shots on target, tackles, yellow cards and situational angles such as super subs.";
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
    images: [{ url: "/og.png", width: 1200, height: 630, alt: "Il Margine - Player Props" }],
  },
  twitter: {
    card: "summary_large_image",
    title,
    description,
    images: ["/og.png"],
  },
};

export default function PlayerPropsLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return <>{children}</>;
}
