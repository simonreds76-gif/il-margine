import type { Metadata } from "next";
import Link from "next/link";
import Footer from "@/components/Footer";
import MarginLab from "@/components/calculator/MarginLab";
import { BASE_URL } from "@/lib/config";

export const dynamic = "force-static";

const title = "No-Vig Fair Odds Calculator for Sports Betting";
const description = "Remove the bookmaker’s margin from two-way or three-way decimal odds, or compare Yes and No buy prices on a prediction market. See fair odds and probabilities derived from the prices you enter.";
const url = `${BASE_URL}/calculator/no-vig`;

export const metadata: Metadata = {
  title: { absolute: title },
  description,
  alternates: { canonical: url },
  openGraph: { type: "website", title, description, url, images: ["/brand/20260913/social.png"] },
  twitter: { card: "summary_large_image", title, description, images: ["/brand/20260913/social.png"] },
};

export default function FairOddsCalculatorPage() {
  return (
    <div className="calc-page">
      <main className="site-container">
        <header className="nv-page-head">
          <nav aria-label="Breadcrumb">
            <ol className="nv-crumbs">
              <li><Link href="/">Home</Link></li>
              <li><Link href="/tools">Betting tools</Link></li>
              <li aria-current="page">Devig</li>
            </ol>
          </nav>
          <h1 className="nv-page-title">Devig</h1>
          <p className="nv-page-intro">
            Turn each of a bookmaker’s prices into a chance and the chances usually add up to more than 100%. <strong>The surplus is the margin.</strong> Remove it to see the chance the market itself gives each outcome. Every figure comes from the prices you enter, not from a forecast of ours.
          </p>
        </header>
        <MarginLab standalone />
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
