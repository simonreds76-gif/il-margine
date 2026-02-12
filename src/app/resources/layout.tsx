import type { Metadata } from "next";
import { BASE_URL } from "@/lib/config";

export const metadata: Metadata = {
  title: "Resources | Il Margine",
  description:
    "Betting strategy guides, bankroll management, and educational resources from Il Margine.",
  alternates: {
    canonical: `${BASE_URL}/resources`,
  },
  robots: "index, follow",
};

export default function ResourcesLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return children;
}
