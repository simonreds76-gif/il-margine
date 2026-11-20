import type { Metadata } from "next";
import Link from "next/link";
import Footer from "@/components/Footer";
import PageHeading from "@/components/PageHeading";
import MarginLab from "@/components/calculator/MarginLab";
import { BASE_URL } from "@/lib/config";

export const dynamic = "force-static";

const title = "Devig Calculator | Remove the Bookmaker’s Margin";
const description = "Remove the bookmaker’s margin from two-way or three-way decimal odds, or compare Yes and No prediction market prices in cents. See fair odds and estimated probabilities.";
const url = `${BASE_URL}/calculator/no-vig`;

export const metadata: Metadata = {
  title: { absolute: `${title} | Il Margine` },
  description,
  alternates: { canonical: url },
  openGraph: { type: "website", title, description, url, images: ["/brand/20260913/social.png"] },
  twitter: { card: "summary_large_image", title, description, images: ["/brand/20260913/social.png"] },
};

export default function FairOddsCalculatorPage() {
  return (
    <div className="calc-page">
      <main className="site-container">
        <PageHeading eyebrow="Betting calculator" title="Devig" icon="price" parent={{ href: "/tools", label: "Betting tools" }}>
          <p>Remove the bookmaker’s margin to see what chance the market gives each outcome. Enter decimal odds for all sides, or compare Yes and No buy prices on a prediction market.</p>
        </PageHeading>
        <MarginLab />
        <p className="calc-compliance">
          <Link className="site-text-link" href="/resources/odds-value-stakes#margin">How the bookmaker’s margin works</Link>
          {" · "}
          <Link className="site-text-link" href="/calculator/football">Football double chance and draw no bet</Link>
        </p>
      </main>
      <Footer />
    </div>
  );
}
