import type { Metadata } from "next";
import { BASE_URL } from "@/lib/config";

const title = "Tennis Betting Tips Today | ATP, Challenger & Grand Slams";
const description =
  "Daily tennis betting tips covering ATP, Challenger and Grand Slam matches, with analytical previews and disciplined staking.";
const url = `${BASE_URL}/tennis-tips`;

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
    images: [{ url: "/og.png", width: 1200, height: 630, alt: "Il Margine - Tennis Tips" }],
  },
  twitter: {
    card: "summary_large_image",
    title,
    description,
    images: ["/og.png"],
  },
};

export default function TennisTipsLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return <>{children}</>;
}
