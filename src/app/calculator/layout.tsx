import type { Metadata } from "next";

const siteUrl = process.env.NEXT_PUBLIC_SITE_URL || 'https://ilmargine.bet';

export const metadata: Metadata = {
  title: "Calculator | Potential Winnings Calculator",
  description: "Calculate your potential returns based on our historical performance. All calculations are based on our verified track record and assume you follow our unit recommendations.",
  alternates: {
    canonical: `${siteUrl}/calculator`,
  },
};

export default function CalculatorLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return <>{children}</>;
}
