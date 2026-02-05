import type { Metadata } from "next";

const siteUrl = process.env.NEXT_PUBLIC_SITE_URL || 'https://ilmargine.bet';

export const metadata: Metadata = {
  title: "Football Bet Builder Tips | Same Game Combo Analysis",
  description: "Football bet builder tips and same game combo analysis, focusing on structure, correlation and risk control.",
  alternates: {
    canonical: `${siteUrl}/bet-builders`,
  },
};

export default function BetBuildersLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return <>{children}</>;
}
