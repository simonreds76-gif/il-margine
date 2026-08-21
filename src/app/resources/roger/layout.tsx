import type { Metadata } from "next";
import { BASE_URL } from "@/lib/config";

export const metadata: Metadata = {
  title: "Roger ATP Tennis Stats Chatbot",
  description:
    "Roger is our tennis stats chatbot. Ask about ATP head to head records, tournament history, serve stats, player records at venues, and more. Use tennis data to enhance your betting decisions.",
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
      "Ask Roger about ATP head to head, tournament records, serve stats, and more. Tennis data to enhance your betting.",
    url: `${BASE_URL}/resources/roger`,
    type: "website",
    images: [`${BASE_URL}/og-social-20260629.png`],
  },
  twitter: {
    card: "summary_large_image",
    title: "Roger ATP Tennis Stats Chatbot",
    description: "Ask Roger about ATP head to head, tournament records, serve stats, and more.",
    images: [`${BASE_URL}/og-social-20260629.png`],
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
