import type { Metadata } from "next";
import { BASE_URL } from "@/lib/config";

const title = "Football Player Props | Il Margine";
const description = "Football player-prop picks, posted prices and publicly settled results from Il Margine.";
const url = `${BASE_URL}/player-props`;

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
    images: [{ url: "/og.png", width: 1200, height: 630, alt: "Il Margine - Football Player Props" }],
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
