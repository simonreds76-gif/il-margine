import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Returns Calculator | Potential Winnings Calculator",
  description: "Calculate your potential returns based on our historical performance. All calculations are based on our verified track record and assume you follow our unit recommendations.",
};

export default function CalculatorLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return <>{children}</>;
}
