import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Anytime Goalscorer Betting Tips & Analysis",
  description: "Anytime goalscorer betting tips with analytical breakdowns based on roles, xG data and match context.",
};

export default function AnytimeGoalscorerLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return <>{children}</>;
}
