import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Tennis Betting Tips Today | ATP, Challenger & Grand Slams",
  description: "Daily tennis betting tips covering ATP, Challenger and Grand Slam matches, with analytical previews and disciplined staking.",
};

export default function TennisTipsLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return <>{children}</>;
}
