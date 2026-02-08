import type { Metadata } from "next";
import { BASE_URL } from "@/lib/config";

export const metadata: Metadata = {
  title: "The Edge",
  description: "Why Il Margine works: 25 years in the betting industry, former odds compiler, proprietary models, mathematical edge only.",
  alternates: {
    canonical: `${BASE_URL}/the-edge`,
  },
  robots: "index, follow",
};

export default function TheEdgeLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return children;
}
