import type { Metadata } from "next";

const siteUrl = process.env.NEXT_PUBLIC_SITE_URL || 'https://ilmargine.bet';

export const metadata: Metadata = {
  title: "Player Props Betting Tips | Fouls, Shots, Cards & Value Markets",
  description: "Player props betting tips covering fouls committed, fouls won, shots, shots on target, tackles, yellow cards and situational angles such as super subs.",
  alternates: {
    canonical: `${siteUrl}/player-props`,
  },
};

export default function PlayerPropsLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return <>{children}</>;
}
