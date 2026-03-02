import type { Metadata } from "next";
import { BASE_URL } from "@/lib/config";

export const metadata: Metadata = {
  title: "Track Record",
  description: "Performance data across betting markets. Player props and tennis tips posted on site. Results logged as they settle.",
  alternates: {
    canonical: `${BASE_URL}/track-record`,
  },
  robots: "index, follow",
};

export default function TrackRecordLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return children;
}
