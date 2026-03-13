import type { Metadata } from "next";
import { BASE_URL } from "@/lib/config";

const title = "Model Monitor";
const description = "Internal monitor for strict policy, shadow policy, CLV audit coverage, and historical profile backtests.";
const url = `${BASE_URL}/model-monitor`;

export const metadata: Metadata = {
  title,
  description,
  alternates: { canonical: url },
  robots: { index: false, follow: false },
};

export default function ModelMonitorLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return <>{children}</>;
}
