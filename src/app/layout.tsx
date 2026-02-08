import type { Metadata } from "next";
import Script from "next/script";
import { Inter } from "next/font/google";
import { SpeedInsights } from "@vercel/speed-insights/next";
import "./globals.css";
import GlobalNav from "@/components/GlobalNav";
import StructuredData from "@/components/StructuredData";
import GoogleAnalytics from "@/components/GoogleAnalytics";
import { BASE_URL } from "@/lib/config";

const GA_MEASUREMENT_ID = process.env.NEXT_PUBLIC_GA_MEASUREMENT_ID;

const inter = Inter({ subsets: ["latin"] });

export const metadata: Metadata = {
  metadataBase: new URL(BASE_URL),
  title: {
    default: "Smart Betting Tips & Analysis | Tennis, Props & Football",
    template: "%s | Il Margine",
  },
  description: "Independent betting tips and analysis across tennis, player props and football markets, with a disciplined and data-driven approach.",
  alternates: {
    canonical: BASE_URL,
  },
  openGraph: {
    type: "website",
    locale: "en_GB",
    url: BASE_URL,
    siteName: "Il Margine",
    title: "Smart Betting Tips & Analysis | Tennis, Props & Football",
    description: "Independent betting tips and analysis across tennis, player props and football markets, with a disciplined and data-driven approach.",
    images: [
      {
        url: "/og.png",
        width: 1200,
        height: 630,
        alt: "Il Margine - Smart Betting Tips & Analysis",
      },
    ],
  },
  twitter: {
    card: "summary_large_image",
    title: "Smart Betting Tips & Analysis | Tennis, Props & Football",
    description: "Independent betting tips and analysis across tennis, player props and football markets, with a disciplined and data-driven approach.",
    images: ["/og.png"],
  },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body className={inter.className}>
        {GA_MEASUREMENT_ID ? (
          <>
            <Script
              src={`https://www.googletagmanager.com/gtag/js?id=${GA_MEASUREMENT_ID}`}
              strategy="afterInteractive"
            />
            <Script id="ga4-config" strategy="afterInteractive">
              {`window.dataLayer = window.dataLayer || []; function gtag(){dataLayer.push(arguments);} gtag('js', new Date()); gtag('config', '${GA_MEASUREMENT_ID}');`}
            </Script>
            <GoogleAnalytics measurementId={GA_MEASUREMENT_ID} />
          </>
        ) : null}
        <StructuredData />
        <GlobalNav />
        {children}
        <SpeedInsights />
      </body>
    </html>
  );
}
