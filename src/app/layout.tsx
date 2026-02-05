import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css";
import GlobalNav from "@/components/GlobalNav";

const inter = Inter({ subsets: ["latin"] });

export const metadata: Metadata = {
  title: "Smart Betting Tips & Analysis | Tennis, Props & Football",
  description: "Independent betting tips and analysis across tennis, player props and football markets, with a disciplined and data-driven approach.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body className={inter.className}>
        <GlobalNav />
        {children}
      </body>
    </html>
  );
}
