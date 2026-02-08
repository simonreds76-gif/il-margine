import type { Metadata } from "next";
import { BASE_URL } from "@/lib/config";

export const metadata: Metadata = {
  title: "Track Record",
  description: "Transparent betting results: Player Props and ATP Tennis. Verified track record, ROI, win rate.",
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
