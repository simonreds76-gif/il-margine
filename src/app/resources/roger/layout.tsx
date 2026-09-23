import type { Metadata } from "next";
import { BASE_URL } from "@/lib/config";

export const metadata: Metadata = {
  title: "Roger ATP Tennis Stats Chatbot",
  description:
    "Ask Roger specific ATP tennis questions about head-to-head records, tournament history and serve statistics. Learn how to check the sample, surface and dates behind an answer.",
  keywords: [
    "tennis stats chatbot",
    "ATP head to head",
    "tennis H2H",
    "tournament record tennis",
    "player stats tennis",
    "tennis betting stats",
    "serve stats ATP",
    "tennis data betting",
  ],
  alternates: {
    canonical: `${BASE_URL}/resources/roger`,
  },
  openGraph: {
    title: "Roger ATP Tennis Stats Chatbot",
    description:
      "Explore ATP head-to-head records, tournament history and serve statistics with Roger. Practical example questions and checks for understanding the answers.",
    url: `${BASE_URL}/resources/roger`,
    type: "website",
    images: [`${BASE_URL}/brand/20260913/social.png`],
  },
  twitter: {
    card: "summary_large_image",
    title: "Roger ATP Tennis Stats Chatbot",
    description: "Ask Roger about ATP head to head, tournament records, serve stats, and more.",
    images: [`${BASE_URL}/brand/20260913/social.png`],
  },
  robots: "index, follow",
};

export default function RogerLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return children;
}
