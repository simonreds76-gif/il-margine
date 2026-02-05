import type { Metadata } from "next";

const siteUrl = process.env.NEXT_PUBLIC_SITE_URL || 'https://ilmargine.bet';

export const metadata: Metadata = {
  title: "Recommended Bookmakers | Best Betting Sites for Tips",
  description: "Where to place your bets. We recommend bookmakers based on market coverage, odds quality, betting limits, and account management.",
  alternates: {
    canonical: `${siteUrl}/bookmakers`,
  },
};

export default function BookmakersLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return <>{children}</>;
}
