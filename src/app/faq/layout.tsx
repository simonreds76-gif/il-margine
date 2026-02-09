import type { Metadata } from "next";
import { BASE_URL } from "@/lib/config";

export const metadata: Metadata = {
  title: "FAQ",
  description: "Frequently asked questions about Il Margine: betting tips, Telegram, player props, tennis, ROI, bookmakers, bankroll management, and more.",
  alternates: {
    canonical: `${BASE_URL}/faq`,
  },
  robots: "index, follow",
};

export default function FaqLayout({ children }: { children: React.ReactNode }) {
  return children;
}
