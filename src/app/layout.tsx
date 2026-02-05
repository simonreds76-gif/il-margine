import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css";
import GlobalNav from "@/components/GlobalNav";

const inter = Inter({ subsets: ["latin"] });

const siteUrl = process.env.NEXT_PUBLIC_SITE_URL || 'https://ilmargine.bet';

export const metadata: Metadata = {
  metadataBase: new URL(siteUrl),
  title: {
    default: "Smart Betting Tips & Analysis | Tennis, Props & Football",
    template: "%s | Il Margine",
  },
  description: "Independent betting tips and analysis across tennis, player props and football markets, with a disciplined and data-driven approach.",
  alternates: {
    canonical: siteUrl,
  },
  openGraph: {
    type: "website",
    locale: "en_GB",
    url: siteUrl,
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
  const siteUrl = process.env.NEXT_PUBLIC_SITE_URL || 'https://ilmargine.bet';
  
  return (
    <html lang="en">
      <head>
        <script
          type="application/ld+json"
          dangerouslySetInnerHTML={{
            __html: JSON.stringify({
              "@context": "https://schema.org",
              "@type": "WebSite",
              "name": "Il Margine",
              "url": siteUrl,
              "description": "Independent betting tips and analysis across tennis, player props and football markets, with a disciplined and data-driven approach.",
            }),
          }}
        />
        <script
          type="application/ld+json"
          dangerouslySetInnerHTML={{
            __html: JSON.stringify({
              "@context": "https://schema.org",
              "@type": "Organization",
              "name": "Il Margine",
              "url": siteUrl,
              "logo": `${siteUrl}/logo.png`,
            }),
          }}
        />
      </head>
      <body className={inter.className}>
        <GlobalNav />
        {children}
      </body>
    </html>
  );
}
