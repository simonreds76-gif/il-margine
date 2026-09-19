import type { Metadata } from "next";
import { BASE_URL } from "@/lib/config";
import { BreadcrumbSchema } from "@/components/BreadcrumbSchema";

const title = "Track Record | Verified Betting Results";
const description =
  "Explore the Il Margine betting record: recorded stakes, ROI and settled results across football player props and tennis, including the historical baseline.";
const url = `${BASE_URL}/track-record`;

export const metadata: Metadata = {
  title,
  description,
  alternates: {
    canonical: url,
  },
  robots: "index, follow",
  openGraph: {
    type: "website",
    locale: "en_GB",
    siteName: "Il Margine",
    url,
    title: "Verified Betting Track Record - Player Props & ATP Tennis | Il Margine",
    description,
    images: [{ url: "/brand/20260913/social.png", width: 1200, height: 630, alt: "Il Margine - Track Record" }],
  },
  twitter: {
    card: "summary_large_image",
    title: "Verified Betting Track Record - Player Props & ATP Tennis | Il Margine",
    description,
    images: ["/brand/20260913/social.png"],
  },
};

export default function TrackRecordLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <>
      <BreadcrumbSchema crumbs={[
        { name: "Home", url: "/" },
        { name: "Track Record", url: "/track-record" },
      ]} />
      {children}
    </>
  );
}
