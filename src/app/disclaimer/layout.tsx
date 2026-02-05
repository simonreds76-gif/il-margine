import type { Metadata } from "next";
import { BASE_URL } from "@/lib/config";

const title = "Disclaimer | Il Margine";
const url = `${BASE_URL}/disclaimer`;

export const metadata: Metadata = {
  title,
  alternates: { canonical: url },
  robots: { index: true, follow: true },
};

export default function DisclaimerLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return <>{children}</>;
}
