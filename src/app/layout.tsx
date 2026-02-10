import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css";
import GlobalNav from "@/components/GlobalNav";
import StructuredData from "@/components/StructuredData";
import CookieBanner from "@/components/CookieBanner";
import SpeedInsightsClient from "@/components/SpeedInsightsClient";
import { BASE_URL, GA_MEASUREMENT_ID } from "@/lib/config";

const inter = Inter({ subsets: ["latin"] });

export const metadata: Metadata = {
  metadataBase: new URL(BASE_URL),
  icons: {
    icon: [{ url: "/favicon.png", sizes: "32x32", type: "image/png" }],
    apple: "/favicon.png",
  },
  title: {
    default: "Il Margine | Betting with Mathematical Edge",
    template: "%s | Il Margine",
  },
  description: "Professional betting methodology from a former odds compiler. We identify value where bookmakers misprice markets. Data-driven tips on tennis, player props & football with transparent results.",
  alternates: {
    canonical: BASE_URL,
  },
  openGraph: {
    type: "website",
    locale: "en_GB",
    url: BASE_URL,
    siteName: "Il Margine",
    title: "Betting with Mathematical Edge | Tennis and Football Player Props",
    description: "Professional betting methodology from a former odds compiler. Data driven betting tips on tennis markets and football player props. We identify value where bookmakers misprice markets and publish transparent results.",
    images: [
      {
        url: `${BASE_URL}/banner.png`,
        width: 1200,
        height: 400,
        alt: "Il Margine Smart Betting Tips and Analysis",
        type: "image/png",
      },
    ],
  },
  twitter: {
    card: "summary_large_image",
    title: "Betting with Mathematical Edge | Tennis and Football Player Props",
    description: "Professional betting methodology from a former odds compiler. Data driven betting tips on tennis markets and football player props. We identify value where bookmakers misprice markets and publish transparent results.",
    images: [`${BASE_URL}/banner.png`],
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
        <link rel="icon" href="/favicon.png" sizes="32x32" type="image/png" />
        <link rel="preconnect" href="https://www.googletagmanager.com" />
        <link rel="dns-prefetch" href="https://www.googletagmanager.com" />
      </head>
      <body className={inter.className}>
        <CookieBanner measurementId={GA_MEASUREMENT_ID} />
        <SpeedInsightsClient />
        <StructuredData />
        <GlobalNav />
        <div className="site-content w-full min-h-screen pt-20">
          {children}
        </div>
      </body>
    </html>
  );
}
