import type { Metadata } from "next";
import { BASE_URL } from "@/lib/config";

export const metadata: Metadata = {
  title: "Sports Betting Resources & Guides",
  description:
    "Practical sports betting guides covering closing line value, Kelly staking, ROI, bankroll management, tennis models and football player props.",
  alternates: {
    canonical: `${BASE_URL}/resources`,
  },
  robots: "index, follow",
  openGraph: {
    type: "website",
    url: `${BASE_URL}/resources`,
    title: "Sports Betting Resources & Guides",
    description:
      "Practical guides to closing line value, Kelly staking, betting records, tennis models and fair odds.",
    images: [`${BASE_URL}/og-social-20260629.png`],
  },
  twitter: {
    card: "summary_large_image",
    title: "Sports Betting Resources & Guides",
    description:
      "Practical guides to closing line value, Kelly staking, betting records, tennis models and fair odds.",
    images: [`${BASE_URL}/og-social-20260629.png`],
  },
};

export default function ResourcesLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return children;
}
