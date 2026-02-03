import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Il Margine | Mathematical Edge Betting",
  description: "Kill the bookies. Mathematical edge betting, singles only. Join our free Telegram channel for picks that got us banned from every major UK bookmaker.",
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
