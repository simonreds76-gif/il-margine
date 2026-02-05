import type { Metadata } from "next";

const siteUrl = process.env.NEXT_PUBLIC_SITE_URL || 'https://ilmargine.bet';

export const metadata: Metadata = {
  title: "Tennis Betting Tips Today | ATP, Challenger & Grand Slams",
  description: "Daily tennis betting tips covering ATP, Challenger and Grand Slam matches, with analytical previews and disciplined staking.",
  alternates: {
    canonical: `${siteUrl}/tennis-tips`,
  },
};

export default function TennisTipsLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return <>{children}</>;
}
