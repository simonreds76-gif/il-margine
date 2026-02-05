import type { Metadata } from "next";

const siteUrl = process.env.NEXT_PUBLIC_SITE_URL || 'https://ilmargine.bet';

export const metadata: Metadata = {
  title: "Anytime Goalscorer Betting Tips & Analysis",
  description: "Anytime goalscorer betting tips with analytical breakdowns based on roles, xG data and match context.",
  alternates: {
    canonical: `${siteUrl}/anytime-goalscorer`,
  },
};

export default function AnytimeGoalscorerLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return <>{children}</>;
}
