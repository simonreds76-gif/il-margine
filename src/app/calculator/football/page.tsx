import type { Metadata } from "next";
import Link from "next/link";
import Footer from "@/components/Footer";
import PageHomeLink from "@/components/PageHomeLink";
import FootballPrices from "@/components/calculator/FootballPrices";
import { BASE_URL } from "@/lib/config";
import "./football-prices.css";

export const dynamic = "force-static";
const title = "Double Chance & Draw No Bet Fair Odds Calculator";
const description = "Calculate football double-chance and draw-no-bet fair odds from a 1X2 market. Compare margin-removal methods and test a bookmaker price with draws refunded correctly.";
export const metadata: Metadata = {
  title: { absolute: `${title} | Il Margine` }, description, alternates: { canonical: `${BASE_URL}/calculator/football` }, robots: { index: true, follow: true },
  openGraph: { title, description, url: `${BASE_URL}/calculator/football`, type: "website", images: ["/brand/20260913/social.png"] },
  twitter: { card: "summary_large_image", title, description, images: ["/brand/20260913/social.png"] },
};
export default function FootballCalculatorPage() {
  return <div className="calc-page"><main className="site-container">
    <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: JSON.stringify([
      { "@context": "https://schema.org", "@type": "WebApplication", name: title, description, url: `${BASE_URL}/calculator/football`, applicationCategory: "SportsApplication", operatingSystem: "Web", isAccessibleForFree: true },
      { "@context": "https://schema.org", "@type": "BreadcrumbList", itemListElement: [{ "@type": "ListItem", position: 1, name: "Home", item: BASE_URL }, { "@type": "ListItem", position: 2, name: "Tools", item: `${BASE_URL}/tools` }, { "@type": "ListItem", position: 3, name: "Football fair odds", item: `${BASE_URL}/calculator/football` }] },
    ]) }} />
    <header className="page-heading calc-heading"><PageHomeLink /><p className="site-eyebrow">Football pricing tools</p><h1>Double chance.<br />Draw no bet. Fair prices.</h1><div className="page-intro"><p>See how including or refunding the draw changes a football price. Start with a complete 1X2 market, then compare an available quote with the calculated benchmark.</p></div><nav className="football-calculator-links" aria-label="Related tools"><Link prefetch={false} href="/tools">← All betting tools</Link><Link prefetch={false} href="/calculator">Returns, Kelly & fair odds →</Link><Link prefetch={false} href="/football-atlas">Football Return Atlas →</Link></nav></header>
    <FootballPrices />
    <section className="calc-section"><p className="site-eyebrow">A worked example</p><h2>Same match. Different treatment of the draw.</h2><div className="calc-howto"><article className="site-card"><h3>Double chance: the draw can win</h3><p className="calc-lede">At fair probabilities of 50% home, 30% draw and 20% away, home or draw wins 80% of the time. Its fair decimal price is 1 ÷ 0.80 = <strong>1.25</strong>.</p><p className="calc-note">1X means home or draw. X2 means draw or away. 12 means either team wins; a draw loses.</p></article><article className="site-card"><h3>Draw no bet: the draw is a refund</h3><p className="calc-lede">With those same probabilities, home DNB wins 50%, refunds 30% and loses 20%. Its fair price is (0.50 + 0.20) ÷ 0.50 = <strong>1.40</strong>.</p><p className="calc-note">At offered odds of 1.50, a £10 stake has expected net profit of 0.50 × £5 − 0.20 × £10 = £0.50. The expected value is +5%, with no profit or loss on a draw.</p></article></div></section>
    <section className="calc-section"><p className="site-eyebrow">Using the answer</p><h2>A benchmark to compare, not a historical quote.</h2><div className="calc-prose"><p>Use home, draw and away prices for the same match, timestamp and settlement rules. This calculator assumes 90 minutes plus stoppage time, excluding extra time and penalties. Margin removal estimates probabilities; it cannot prove that the market is right.</p><p>A team +0.5 handicap and double chance on that team settle alike, as do a zero handicap and draw no bet under matching rules. Their offered prices can differ. Football Return Atlas uses recorded prices for the markets it shows; these calculated odds do not create an executable historical DNB or double-chance record.</p><p><Link className="site-text-link" href="/resources/odds-value-stakes">Work through probability, value and staking →</Link></p></div></section>
    </main><Footer /></div>;
}
