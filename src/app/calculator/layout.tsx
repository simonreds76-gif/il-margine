import type { Metadata } from "next";
import { BASE_URL } from "@/lib/config";

const title = "Calculator | Potential Winnings Calculator";
const description =
  "Calculate your potential returns based on our historical performance. All calculations are based on our verified track record and assume you follow our unit recommendations.";
const url = `${BASE_URL}/calculator`;

export const metadata: Metadata = {
  title,
  description,
  alternates: { canonical: url },
  openGraph: {
    type: "website",
    locale: "en_GB",
    url,
    siteName: "Il Margine",
    title,
    description,
    images: [{ url: "/og.png", width: 1200, height: 630, alt: "Il Margine - Calculator" }],
  },
  twitter: {
    card: "summary_large_image",
    title,
    description,
    images: ["/og.png"],
  },
};

export default function CalculatorLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return <>{children}</>;
}
