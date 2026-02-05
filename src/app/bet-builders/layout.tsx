import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Football Bet Builder Tips | Same Game Combo Analysis",
  description: "Football bet builder tips and same game combo analysis, focusing on structure, correlation and risk control.",
};

export default function BetBuildersLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return <>{children}</>;
}
