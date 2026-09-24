import Link from "next/link";
import Image from "next/image";
import Footer from "@/components/Footer";
import PageHomeLink from "@/components/PageHomeLink";
import EditorialIcon from "@/components/EditorialIcon";
import MarginExplorer from "@/components/bookmakers/MarginExplorer";
import BookmakerMark from "@/components/bookmakers/BookmakerMark";
import { NOT_MEASURED_MARKETS, capturedLabel, type BookmakerMarginIndex } from "@/lib/bookmakers/margin-index";
import marginIndexJson from "../../../data/bookmakers/margin-index.json";
import "./bookmakers.css";

const index = marginIndexJson as BookmakerMarginIndex;
const names = Array.from(new Set(index.segments?.flatMap(s => s.operators.map(o => o.name)) ?? []));
const coverage = index.coverage ?? { target_operators: names.length, discovered_operators: names.length, payload_operators: names.length, qualified_operators: names.length, payload_operator_names: names, qualified_operator_names: names };
const segments = coverage.payload_operators >= 10 ? index.segments ?? [] : [];
const FAQ = [
  { q: "Which UK bookmaker has the lowest margin?", a: "It depends on the market and when you look. Choose football or tennis, then a market, to see the measured order. These are dated observations from a small sample, not a permanent ranking of bookmakers. The lowest market margin also does not guarantee the best price on your selection." },
  { q: "What is the difference between overround and margin?", a: "Add 1 divided by each decimal price to get the book total, B. Overround is (B − 1) × 100%. The ranking uses normalised margin, (1 − 1/B) × 100%, which puts that excess on a turnover basis under proportional pricing assumptions. Neither tells you the bookmaker’s actual profit or your personal expected loss." },
  { q: "Are these today’s odds?", a: `No. This is an archived capture from ${capturedLabel(index.generated_at)}. Prices can change substantially. Check the current odds and settlement terms before making any comparison. We do not replace a missing quote with one from an older capture.` },
  { q: "Why can’t every player-prop market be ranked?", a: "An over-only price cannot reveal the full market margin. We need both sides of the same line, from the same bookmaker and capture. Anytime goalscorer selections overlap, so adding their implied probabilities does not produce a valid market overround." },
  { q: "Are exchange prices included?", a: "No. Exchange back and lay prices, available liquidity and commission require a different comparison. This table covers fixed-odds sportsbooks only; it does not treat an exchange as a zero-margin bookmaker." },
  { q: "Do partner links affect the rankings?", a: "No. Rankings are calculated from the recorded prices. Partner links appear separately below and may earn Il Margine a commission. There are no paid positions in the margin table." },
];
const partners = [{ name: "William Hill", url: "/api/go/william-hill" }, { name: "Betway", url: "/api/go/betway" }, { name: "Bwin", url: "/api/go/bwin" }];

export default function BookmakersPage() {
  return <div className="bookmaker-page min-h-screen bg-[#0f1117] text-slate-100">
    <div className="public-hub-heading mx-auto max-w-6xl px-4 pb-12 pt-5 sm:px-6 lg:px-8">
      <PageHomeLink className="mb-8" />
      <header className="bm-hero">
        <div>
          <h1 className="sr-only">UK bookmakers. Mind the margin.</h1>
          <Image className="bm-masthead" src="/brand/mind-the-margin-v1.webp" alt="Mind the Margin — UK bookmaker comparison by Il Margine" width={1440} height={480} priority unoptimized />
          <p className="bm-lead">Same match. Different prices. See which bookmakers built more margin into their football and tennis markets — and what that means when you compare a bet.</p>
          <nav aria-label="Bookmaker page sections" className="bm-jumps">
            <a href="#compare-margins" className="bm-primary"><EditorialIcon name="compare" />Compare bookmakers <span aria-hidden="true">↓</span></a>
            <a href="#understand-margins">Understand the numbers <span aria-hidden="true">↗</span></a>
          </nav>
        </div>
        <aside className="bm-ticket" aria-label="Illustrative two-outcome market">
          <div className="bm-ticket-head"><EditorialIcon name="markets" className="h-10 w-10" /><span>What’s inside the price?<small>Illustration · equally likely outcomes</small></span></div>
          <div className="bm-ticket-prices"><div><small>Fair odds</small><strong>2.00 <span>/</span> 2.00</strong></div><div><small>Bookmaker odds</small><strong>1.90 <span>/</span> 1.90</strong></div></div>
          <div className="bm-ticket-bar"><span>95% priced return</span><b>5%</b></div>
          <p>At a true 50% win chance, a £10 bet at 1.90 returns £9.50 on average, including stake. The expected cost is <strong>50p</strong>.</p>
          <span className="bm-ticket-foot">5.26% overround · 5.00% normalised margin</span>
        </aside>
      </header>
      <section id="compare-margins" className="bm-section" aria-label="Bookmaker margin comparison">
        <div className="bm-capture"><EditorialIcon name="analysis" /><div><strong>Dated evidence, not a live price board</strong><p>{capturedLabel(index.generated_at)} · {index.summary.events} events · {coverage.qualified_operators} bookmakers measured. Small samples show price differences, not lasting superiority.</p></div></div>
        <MarginExplorer generatedAt={index.generated_at} segments={segments} notMeasured={NOT_MEASURED_MARKETS} coverage={coverage} summary={index.summary} />
      </section>
      <section id="understand-margins" className="bm-section">
        <div className="bm-section-title"><EditorialIcon name="guide" className="h-11 w-11" /><div><p className="bm-kicker">Read the price, not the promotion</p><h2>Understand the numbers</h2></div></div>
        <div className="bm-guide-grid">
          <article className="bm-card"><EditorialIcon name="markets" /><h3>Overround</h3><p>Turn every decimal price into an implied probability, then add them. A book totalling 106% has a <strong>6% overround</strong>.</p><code>B = 1/home + 1/draw + 1/away</code></article>
          <article className="bm-card"><EditorialIcon name="analysis" /><h3>The margin we rank</h3><p>Normalising that 106% book gives <strong>5.66%</strong>: 1 − 1/1.06. It is a pricing measure under proportional assumptions, not a report of the bookmaker’s profits.</p><Link href="/calculator">Try the margin calculator →</Link></article>
          <article className="bm-card"><EditorialIcon name="compare" /><h3>Your selection still matters</h3><p>A bookmaker can have a lower overall margin but a shorter price on your team. Compare the exact selection, line and settlement rules before choosing where to bet.</p><Link href="/resources">Learn about fair odds and value →</Link></article>
        </div>
        <div className="bm-price-example">
          <div><p className="bm-kicker">A difference you can count</p><h3>2.00 or 2.10? On £20, that is £2.</h3><p>Same winning selection, same stake: £40 returned at 2.00 or £42 at 2.10. Both include your stake. Shopping for a price improves the payout; it does not make the selection more likely to win.</p></div>
          <div className="bm-receipts"><div><small>£20 at 2.00</small><strong>£40</strong><span>Total return if won</span></div><div><small>£20 at 2.10</small><strong>£42</strong><span>£2 more if won</span></div></div>
        </div>
      </section>
      <section id="margin-method" className="bm-section bm-method">
        <div className="bm-section-title"><EditorialIcon name="method" className="h-11 w-11" /><div><p className="bm-kicker">Behind the comparison</p><h2>How we measure it</h2></div></div>
        <ol className="bm-steps">
          <li><span>01</span><div><h3>Complete markets</h3><p>All mutually exclusive outcomes must be present from one bookmaker at the same line. Incomplete prices and exchange markets are excluded.</p></div></li>
          <li><span>02</span><div><h3>One contribution per event</h3><p>We take the median across each bookmaker’s available alternate lines, then average events equally within each market. Extra lines do not add extra event weight.</p></div></li>
          <li><span>03</span><div><h3>Show the limits</h3><p>Available line menus can differ between bookmakers. These market-family summaries are not a matched-line betting test. Each row shows its sample count; close positions in this small capture should not be overinterpreted.</p></div></li>
        </ol>
      </section>
      <section className="bm-section" aria-labelledby="bm-faq"><div className="bm-section-title"><EditorialIcon name="about" className="h-11 w-11" /><h2 id="bm-faq">Before you compare</h2></div><div className="bm-faq">{FAQ.map(item => <details key={item.q}><summary>{item.q}<span aria-hidden="true">+</span></summary><p>{item.a}</p></details>)}</div></section>
      <aside className="bm-partners" aria-label="Commercial partner links">
        <div><p className="bm-kicker">Commercial links · separate from the rankings</p><h2>Partner bookmakers</h2><p>These links may earn Il Margine a commission. They do not affect the measured order above. Offers, eligibility and terms are set by the operator; check them on the destination site.</p></div>
        <div className="bm-partner-links">{partners.map(p => <a key={p.name} href={p.url} rel="sponsored nofollow"><BookmakerMark name={p.name} /><span>{p.name}<small>Visit operator ↗</small></span></a>)}</div>
      </aside>
    </div>
    <Footer />
  </div>;
}
