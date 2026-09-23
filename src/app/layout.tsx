import PublicSiteFrame from "@/components/PublicSiteFrame";
import type { Metadata, Viewport } from "next";
import { Inter } from "next/font/google";
import { Analytics } from "@vercel/analytics/next";
import "./globals.css";
import GlobalNav from "@/components/GlobalNav";
import StructuredData from "@/components/StructuredData";
import CookieBanner from "@/components/CookieBanner";
import SpeedInsightsClient from "@/components/SpeedInsightsClient";
import RouteScopedOverlays from "@/components/RouteScopedOverlays";
import { BASE_URL, GA_MEASUREMENT_ID } from "@/lib/config";

const inter = Inter({ subsets: ["latin"] });
const DEFAULT_SOCIAL_IMAGE = `${BASE_URL}/brand/20260913/social.png`;

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  viewportFit: "cover",
};

export const metadata: Metadata = {
  metadataBase: new URL(BASE_URL),
  icons: {
    icon: [
      { url: "/brand/20260913/icon-32.png", sizes: "32x32", type: "image/png" },
      { url: "/brand/20260913/icon-192.png", sizes: "192x192", type: "image/png" },
      { url: "/brand/20260913/icon-512.png", sizes: "512x512", type: "image/png" },
    ],
    apple: [{ url: "/brand/20260913/icon-180.png", sizes: "180x180", type: "image/png" }],
  },
  title: {
    default: "Il Margine | Independent Betting Analysis",
    template: "%s | Il Margine",
  },
  description: "Independent betting analysis for football player props and tennis. Compare fair odds, explore our methodology and review published picks and results.",
  alternates: {
    canonical: BASE_URL,
  },
  openGraph: {
    type: "website",
    locale: "en_GB",
    url: BASE_URL,
    siteName: "Il Margine",
    title: "Independent Betting Analysis | Tennis and Football Player Props",
    description: "Independent analysis of tennis and football player props, with fair odds, published selections and a transparent results record.",
    images: [
      {
        url: DEFAULT_SOCIAL_IMAGE,
        width: 1200,
        height: 630,
        alt: "Il Margine betting with mathematical edge",
        type: "image/png",
      },
    ],
  },
  twitter: {
    card: "summary_large_image",
    title: "Independent Betting Analysis | Tennis and Football Player Props",
    description: "Independent analysis of tennis and football player props, with fair odds, published selections and a transparent results record.",
    images: [DEFAULT_SOCIAL_IMAGE],
  },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <head>
        <link rel="preconnect" href="https://www.googletagmanager.com" />
        <link rel="dns-prefetch" href="https://www.googletagmanager.com" />
        <meta name="msvalidate.01" content="FD4A9F8A7202C71E5465E6A51F6B8F62" />
      </head>
      <body className={inter.className}>
        <CookieBanner measurementId={GA_MEASUREMENT_ID} />
        <SpeedInsightsClient />
        <Analytics />
        <StructuredData />
        <GlobalNav />
        <PublicSiteFrame>{children}</PublicSiteFrame>
        <RouteScopedOverlays />
      </body>
    </html>
  );
}
