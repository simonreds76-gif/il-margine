import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Il Margine | Mathematical Edge Betting",
  description: "Mathematical edge betting with 25 years of odds compilation experience. Professional betting methodology, singles only, transparent results. Join our free Telegram channel for value-driven selections.",
  icons: {
    icon: [
      { url: "/favicon.png", sizes: "64x64", type: "image/png" },
      { url: "/favicon-128.png", sizes: "128x128", type: "image/png" },
      { url: "/favicon-256.png", sizes: "256x256", type: "image/png" },
    ],
    apple: "/favicon-256.png",
  },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body className="antialiased">
        {children}
      </body>
    </html>
  );
}
