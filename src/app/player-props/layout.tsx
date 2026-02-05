import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Player Props Betting Tips | Fouls, Shots, Cards & Value Markets",
  description: "Player props betting tips covering fouls committed, fouls won, shots, shots on target, tackles, yellow cards and situational angles such as super subs.",
};

export default function PlayerPropsLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return <>{children}</>;
}
