import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Recommended Bookmakers | Best Betting Sites for Tips",
  description: "Where to place your bets. We recommend bookmakers based on market coverage, odds quality, betting limits, and account management.",
};

export default function BookmakersLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return <>{children}</>;
}
