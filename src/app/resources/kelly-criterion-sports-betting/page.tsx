import type { Metadata } from "next";
import Link from "next/link";
import Image from "next/image";
import Footer from "@/components/Footer";
import { BASE_URL } from "@/lib/config";

export const metadata: Metadata = {
  title: "The Kelly Criterion for Sports Betting: Complete Guide | Il Margine",
  description:
    "Master the Kelly Criterion for optimal bet sizing in sports betting. Learn the mathematics, fractional Kelly strategies, and how to apply it to player props and tennis betting.",
  alternates: {
    canonical: `${BASE_URL}/resources/kelly-criterion-sports-betting`,
  },
  robots: "index, follow",
};

const ARTICLE_SCHEMA = {
  "@context": "https://schema.org",
  "@type": "Article",
  headline: "The Kelly Criterion for Sports Betting: Complete Guide",
  author: {
    "@type": "Organization",
    name: "Il Margine",
  },
  publisher: {
    "@type": "Organization",
    name: "Il Margine",
    logo: {
      "@type": "ImageObject",
      url: `${BASE_URL}/logo.png`,
    },
  },
  datePublished: "2026-02-12",
  description:
    "Master the Kelly Criterion for optimal bet sizing in sports betting. Learn the mathematics, fractional Kelly strategies, and how to apply it to player props and tennis betting.",
};

const TOC_ITEMS = [
  { id: "introduction", label: "Introduction" },
  { id: "mathematics", label: "The Mathematics Explained" },
  { id: "practice", label: "Kelly in Practice — Player Props & Tennis" },
  { id: "limitations", label: "The Critical Limitations" },
  { id: "fractional", label: "Fractional Kelly — Which Multiple to Use" },
  { id: "implementation", label: "Practical Implementation" },
  { id: "comparison", label: "Kelly vs Other Staking Plans" },
  { id: "conclusion", label: "Conclusion" },
];

export default function KellyCriterionPage() {
  return (
    <div className="min-h-screen bg-[#0f1117] text-slate-100">
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: JSON.stringify(ARTICLE_SCHEMA) }}
      />

      {/* Header */}
      <section className="pt-6 pb-8 md:pt-6 md:pb-10 border-b border-slate-800/50">
        <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8">
          <Link
            href="/"
            className="inline-flex items-center gap-2 text-sm text-slate-500 hover:text-slate-300 mb-6"
          >
            <Image
              src="/favicon.png"
              alt=""
              width={40}
              height={40}
              className="h-10 w-10 object-contain shrink-0"
            />
            <span>← Home</span>
          </Link>
          <nav className="flex items-center gap-2 text-sm text-slate-500 mb-6">
            <Link href="/" className="hover:text-slate-300">
              Home
            </Link>
            <span>/</span>
            <Link href="/resources" className="hover:text-slate-300">
              Resources
            </Link>
            <span>/</span>
            <span className="text-slate-300">Kelly Criterion</span>
          </nav>
          <span className="text-xs font-mono text-emerald-400 tracking-wider mb-2 block">
            BETTING STRATEGY
          </span>
          <h1 className="text-3xl sm:text-4xl font-semibold text-slate-100 mb-4">
            The Kelly Criterion for Sports Betting
          </h1>
          <p className="text-base sm:text-lg text-slate-300 mb-8 max-w-3xl leading-relaxed">
            Master the mathematics of optimal bet sizing. Learn how professional bettors
            use the Kelly Criterion to maximize bankroll growth while controlling risk.
          </p>
        </div>
      </section>

      {/* Main content with TOC sidebar */}
      <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 py-12 md:py-16">
        <div className="lg:grid lg:grid-cols-[240px_1fr] lg:gap-16">
          {/* Table of Contents - sticky on desktop */}
          <aside className="lg:sticky lg:top-24 lg:self-start mb-10 lg:mb-0">
            <div className="bg-slate-900/50 border border-slate-800 rounded-lg p-5">
              <h3 className="text-xs font-mono text-slate-500 uppercase tracking-wider mb-4">
                CONTENTS
              </h3>
              <nav className="space-y-2">
                {TOC_ITEMS.map((item, i) => (
                  <a
                    key={item.id}
                    href={`#${item.id}`}
                    className="block text-sm text-slate-400 hover:text-emerald-400 transition-colors"
                  >
                    {i + 1}. {item.label}
                  </a>
                ))}
              </nav>
            </div>
          </aside>

          {/* Article content */}
          <article className="prose prose-invert max-w-none">
            <div className="text-base text-slate-300 leading-relaxed space-y-6">
              {/* Section 1: Introduction */}
              <section id="introduction">
                <h2 className="text-2xl sm:text-3xl font-semibold text-slate-100 mb-6 mt-12 first:mt-0">
                  Introduction
                </h2>
                <p className="mb-4">
                  The difference between profitable bettors and losing punters often
                  comes down to one critical factor: stake sizing. You can identify
                  value in the market, build a data-driven selection process, and
                  maintain discipline — but if you bet too much on any single outcome,
                  variance will eventually destroy your bankroll. Bet too little, and
                  you leave profit on the table.
                </p>
                <p className="mb-4">
                  This is where the Kelly Criterion comes in.
                </p>
                <p className="mb-4">
                  Originally developed in 1956 by John Kelly Jr., a researcher at Bell
                  Labs working on telephone signal noise, the Kelly Criterion is a
                  mathematical formula that calculates the optimal bet size to maximize
                  long-term bankroll growth while minimizing the risk of ruin. What
                  began as a solution to telecommunications problems quickly became
                  recognized by gamblers and investors as the gold standard for
                  bankroll management.
                </p>
                <p className="mb-4">
                  The Kelly Criterion answers a simple question:{" "}
                  <em>How much should I stake when I have an edge?</em>
                </p>
                <p className="mb-4">
                  In this guide, we&apos;ll break down the mathematics behind Kelly,
                  explain how to apply it to football player props and tennis betting,
                  address its limitations, and show you why most professional bettors
                  use a modified version called &quot;fractional Kelly&quot; rather than
                  the full formula.
                </p>
              </section>

              {/* Section 2: Mathematics */}
              <section id="mathematics">
                <h2 className="text-2xl sm:text-3xl font-semibold text-slate-100 mb-6 mt-12">
                  The Mathematics Explained
                </h2>

                <h3 className="text-xl font-semibold text-slate-100 mb-4 mt-8">
                  The Kelly Formula
                </h3>
                <p className="mb-4">
                  The Kelly Criterion calculates the optimal fraction of your bankroll
                  to wager using this formula:
                </p>
                <p className="mb-4">
                  <code className="text-emerald-400 bg-slate-900 px-2 py-1 rounded font-mono">
                    f* = (bp - q) / b
                  </code>
                </p>
                <p className="mb-4">Where:</p>
                <ul className="list-disc pl-6 mb-4 space-y-2">
                  <li>
                    <strong className="text-slate-200">f*</strong> = the fraction of
                    your bankroll to bet (the Kelly percentage)
                  </li>
                  <li>
                    <strong className="text-slate-200">b</strong> = the net odds
                    received on the wager (decimal odds minus 1)
                  </li>
                  <li>
                    <strong className="text-slate-200">p</strong> = your estimated
                    probability of winning
                  </li>
                  <li>
                    <strong className="text-slate-200">q</strong> = probability of
                    losing (1 - p)
                  </li>
                </ul>

                <h3 className="text-xl font-semibold text-slate-100 mb-4 mt-8">
                  Breaking It Down With an Example
                </h3>
                <p className="mb-4">
                  Let&apos;s say you&apos;re betting on a player props market:
                </p>
                <ul className="list-disc pl-6 mb-4 space-y-2">
                  <li>
                    <strong className="text-slate-200">Your assessment:</strong> A
                    player has a 55% chance of 2+ shots on target
                  </li>
                  <li>
                    <strong className="text-slate-200">Bookmaker odds:</strong> 1.91
                    (decimal) or -110 (American)
                  </li>
                  <li>
                    <strong className="text-slate-200">Your bankroll:</strong> £1,000
                  </li>
                </ul>
                <p className="mb-4">First, calculate the variables:</p>
                <ul className="list-disc pl-6 mb-4 space-y-2">
                  <li>
                    <strong className="text-slate-200">b</strong> = 1.91 - 1 = 0.91
                  </li>
                  <li>
                    <strong className="text-slate-200">p</strong> = 0.55 (55%)
                  </li>
                  <li>
                    <strong className="text-slate-200">q</strong> = 0.45 (45%)
                  </li>
                </ul>
                <p className="mb-4">Now apply the formula:</p>
                <p className="mb-4 font-mono text-emerald-400">
                  f* = (0.91 × 0.55 - 0.45) / 0.91
                  <br />
                  f* = (0.5005 - 0.45) / 0.91
                  <br />
                  f* = 0.0505 / 0.91
                  <br />
                  f* = 0.055 or 5.5%
                </p>
                <p className="mb-4">
                  The Kelly Criterion recommends staking{" "}
                  <strong className="text-slate-200">5.5% of your bankroll</strong>,
                  which equals <strong className="text-slate-200">£55</strong> on this
                  bet.
                </p>

                <h3 className="text-xl font-semibold text-slate-100 mb-4 mt-8">
                  Why This Works
                </h3>
                <p className="mb-4">
                  The Kelly Criterion maximizes the geometric growth rate of your
                  bankroll over time. Unlike arithmetic approaches (flat staking), Kelly
                  accounts for the compounding effect of wins and the devastating
                  impact of losses.
                </p>
                <p className="mb-4">
                  The formula effectively balances two competing forces:
                </p>
                <ol className="list-decimal pl-6 mb-4 space-y-2">
                  <li>
                    <strong className="text-slate-200">Betting enough</strong> to
                    capitalize on your edge
                  </li>
                  <li>
                    <strong className="text-slate-200">Betting conservatively
                    enough</strong> to survive inevitable losing runs
                  </li>
                </ol>
                <p className="mb-4">
                  Crucially, if the Kelly formula returns zero or a negative number,
                  it tells you not to bet — the odds don&apos;t justify the risk. This
                  built-in safeguard prevents you from placing wagers where you
                  don&apos;t have a genuine edge.
                </p>

                <h3 className="text-xl font-semibold text-slate-100 mb-4 mt-8">
                  Understanding the Relationship
                </h3>
                <p className="mb-4">
                  Key insight: Kelly bet size increases with:
                </p>
                <ul className="list-disc pl-6 mb-4 space-y-2">
                  <li>Larger edges (higher p relative to implied probability)</li>
                  <li>Higher odds (more b)</li>
                </ul>
                <p className="mb-4">Kelly bet size decreases with:</p>
                <ul className="list-disc pl-6 mb-4 space-y-2">
                  <li>Smaller edges</li>
                  <li>Lower odds (less b)</li>
                </ul>
                <p className="mb-4">
                  This makes intuitive sense: you should bet more when you have a
                  significant advantage at favorable odds, and less when your edge is
                  marginal.
                </p>

                <div className="bg-emerald-500/10 border border-emerald-500/30 rounded-lg p-6 my-6">
                  <h4 className="text-emerald-400 font-semibold mb-3">
                    Kelly Criterion Quick Summary
                  </h4>
                  <ul className="text-slate-300 text-sm space-y-2 list-none">
                    <li>• Calculates optimal bet size based on your edge</li>
                    <li>
                      • Formula:{" "}
                      <code className="text-emerald-400 font-mono">f* = (bp - q) / b</code>
                    </li>
                    <li>• Use fractional Kelly (one-tenth for props, quarter for tennis)</li>
                    <li>• Never bet more than 5% of bankroll on single bet</li>
                    <li>• Only works if you have a genuine edge</li>
                  </ul>
                </div>
              </section>

              {/* Section 3: Practice */}
              <section id="practice">
                <h2 className="text-2xl sm:text-3xl font-semibold text-slate-100 mb-6 mt-12">
                  Kelly in Practice — Player Props & Tennis
                </h2>

                <h3 className="text-xl font-semibold text-slate-100 mb-4 mt-8">
                  Applying Kelly to Football Player Props
                </h3>
                <p className="mb-4">
                  Player props markets — shots on target, fouls committed, tackles
                  won — are where bookmakers often misprice individual player
                  performance. Here&apos;s how Kelly applies:
                </p>

                <div className="bg-slate-900/50 border border-slate-800 rounded-lg p-6 my-6">
                  <h4 className="text-slate-100 font-semibold mb-3">
                    Example: Player Props Calculation
                  </h4>
                  <p className="text-slate-300 mb-4">
                    <strong className="text-slate-200">Scenario:</strong> Declan
                    Rice 2+ tackles won vs Aston Villa
                  </p>
                  <ul className="text-slate-300 text-sm space-y-2 mb-4">
                    <li>• Rice averages 2.3 tackles per game in the Premier League</li>
                    <li>• Villa&apos;s midfield tends to give up tackle opportunities</li>
                    <li>• Your matchup analysis suggests 58% probability of 2+ tackles won</li>
                    <li>• Bookmaker offers 2.00 (decimal)</li>
                  </ul>
                  <p className="text-slate-300 mb-2">Kelly calculation:</p>
                  <p className="text-slate-300 mb-0">
                    b = 1.00, p = 0.58, q = 0.42 →{" "}
                    <code className="text-emerald-400 font-mono">f* = 16%</code>
                  </p>
                </div>

                <p className="mb-4">
                  Full Kelly suggests staking 16% of your bankroll. On £1,000 that&apos;s
                  £160 on a single prop bet. One bad result and you&apos;ve lost a big
                  chunk. Player props are more volatile than match outcomes (individual
                  performance swings harder), and probability estimates are less reliable
                  than in liquid tennis markets. That&apos;s too aggressive. This is why
                  many professionals use{" "}
                  <strong className="text-slate-200">fractional Kelly</strong>, often
                  one-tenth or quarter Kelly for props.
                </p>

                <h3 className="text-xl font-semibold text-slate-100 mb-4 mt-8">
                  Fractional Kelly: The Professional Approach
                </h3>
                <p className="mb-4">
                  Rather than betting the full Kelly percentage, most sharp bettors
                  use a fraction:
                </p>
                <ul className="list-disc pl-6 mb-4 space-y-2">
                  <li>
                    <strong className="text-slate-200">One-Tenth Kelly (0.1x):</strong>{" "}
                    Bet 10% of the Kelly recommendation. Advised for prop bets because
                    they are more volatile than match outcomes: individual player
                    performance swings harder, and probability estimates are less reliable.
                  </li>
                  <li>
                    <strong className="text-slate-200">Quarter Kelly (0.25x):</strong>{" "}
                    Bet 25% of the Kelly recommendation
                  </li>
                  <li>
                    <strong className="text-slate-200">Half Kelly (0.5x):</strong> Bet
                    50% of the Kelly recommendation
                  </li>
                </ul>
                <p className="mb-4">
                  Using our Rice example with{" "}
                  <strong className="text-slate-200">one-tenth Kelly</strong>:
                </p>
                <p className="mb-4">
                  Full Kelly: 16% → One-tenth Kelly: 16% × 0.1 ={" "}
                  <strong className="text-slate-200">1.6%</strong> of bankroll
                </p>
                <p className="mb-4">
                  On a £1,000 bankroll, that&apos;s{" "}
                  <strong className="text-slate-200">£16</strong> instead of £160.
                </p>

                <h3 className="text-xl font-semibold text-slate-100 mb-4 mt-8">
                  Why Fractional Kelly?
                </h3>
                <p className="mb-4">
                  Three critical reasons:
                </p>
                <p className="mb-4">
                  <strong className="text-slate-200">1. Probability Estimation
                  Error</strong> — You&apos;re never 100% certain of your assessed
                  probability. Fractional Kelly provides a safety buffer.
                </p>
                <p className="mb-4">
                  <strong className="text-slate-200">2. Variance Tolerance</strong> —
                  Full Kelly produces violent bankroll swings. Half Kelly reduces
                  volatility dramatically while sacrificing only 25% of long-term
                  growth rate.
                </p>
                <p className="mb-4">
                  <strong className="text-slate-200">3. Multiple Simultaneous
                  Bets</strong> — If you&apos;re betting 20-30 props per week, full
                  Kelly on each bet would have you massively overexposed. Fractional
                  Kelly allows you to spread risk across a portfolio of bets.
                </p>

                <h3 className="text-xl font-semibold text-slate-100 mb-4 mt-8">
                  Applying Kelly to ATP Tennis
                </h3>
                <p className="mb-4">
                  Tennis markets operate similarly, but with different characteristics:
                </p>
                <div className="bg-slate-900/50 border border-slate-800 rounded-lg p-6 my-6">
                  <h4 className="text-slate-100 font-semibold mb-3">
                    Example: ATP Tennis
                  </h4>
                  <p className="text-slate-300 mb-4">
                    <strong className="text-slate-200">Scenario:</strong> ATP 250 first
                    set winner
                  </p>
                  <ul className="text-slate-300 text-sm space-y-2 mb-4">
                    <li>• Your model: Player A has 58% chance to win first set</li>
                    <li>• Pinnacle (closing line): 1.85 (implies 54% probability)</li>
                    <li>• You&apos;ve found a 4% edge</li>
                  </ul>
                  <p className="text-slate-300 mb-2">Kelly: f* = 6.95%. With quarter Kelly: 1.74%</p>
                  <p className="text-slate-300 mb-0">
                    On £2,000 bankroll: <strong className="text-slate-200">£34.80</strong> stake
                  </p>
                </div>
                <p className="mb-4">
                  This aligns with our staking range of 0.5u to 2u (where 1 unit = 1-2%
                  of bankroll).
                </p>

                <h3 className="text-xl font-semibold text-slate-100 mb-4 mt-8">
                  Kelly Across Different Markets
                </h3>
                <p className="mb-4">
                  The beauty of Kelly is it automatically scales your stake based on:
                </p>
                <ul className="list-disc pl-6 mb-4 space-y-2">
                  <li>
                    <strong className="text-slate-200">Edge size:</strong> Bigger edge
                    = larger stake
                  </li>
                  <li>
                    <strong className="text-slate-200">Odds:</strong> Kelly accounts
                    for risk/reward relationship
                  </li>
                  <li>
                    <strong className="text-slate-200">Bankroll:</strong> Stakes grow
                    as bankroll grows, shrink as it shrinks
                  </li>
                </ul>
                <p className="mb-4">
                  This dynamic sizing is far superior to flat staking, which treats all
                  bets identically regardless of edge or context.
                </p>
              </section>

              {/* Section 4: Limitations */}
              <section id="limitations">
                <h2 className="text-2xl sm:text-3xl font-semibold text-slate-100 mb-6 mt-12">
                  The Critical Limitations
                </h2>

                <h3 className="text-xl font-semibold text-slate-100 mb-4 mt-8">
                  The Kelly Criterion Is Not Perfect
                </h3>
                <p className="mb-4">
                  Before you rush to implement Kelly, understand its weaknesses.
                  Professional bettors know these limitations intimately:
                </p>

                <h3 className="text-xl font-semibold text-slate-100 mb-4 mt-8">
                  1. Extreme Sensitivity to Probability Errors
                </h3>
                <p className="mb-4">
                  The Kelly Criterion&apos;s greatest flaw: it assumes you know the
                  true probability. You don&apos;t. You never do.
                </p>
                <p className="mb-4">
                  <strong className="text-slate-200">Real-world example:</strong> You
                  estimate 60% win probability, but true probability is 55%. Full
                  Kelly recommends 8.2% of bankroll; correct Kelly (if you knew true
                  odds) is 2.1%. You&apos;re betting nearly 4x too much due to a
                  5-point estimation error.
                </p>
                <p className="mb-4">
                  The mathematics are unforgiving: if you bet twice the optimal Kelly
                  amount, your long-term growth rate becomes zero. Bet more than 2x
                  Kelly, and you&apos;ll lose money over time despite having an edge.
                </p>

                <div className="bg-amber-500/10 border border-amber-500/30 rounded-lg p-6 my-6">
                  <h4 className="text-amber-400 font-semibold mb-3">
                    ⚠️ The Danger of Overconfidence
                  </h4>
                  <p className="text-slate-300 mb-0">
                    If you estimate 60% win probability but true probability is 55%,
                    you&apos;ll bet nearly 4x too much. This is why professionals use
                    fractional Kelly (one-tenth or quarter) — it provides a safety margin
                    against estimation errors.
                  </p>
                </div>

                <h3 className="text-xl font-semibold text-slate-100 mb-4 mt-8">
                  2. Assumes Accurate Odds Assessment
                </h3>
                <p className="mb-4">
                  Kelly requires you to accurately quantify your edge. For player
                  props, this means collecting season-long data, adjusting for
                  opponent tendencies, accounting for injuries, motivation, form, and
                  understanding bookmaker pricing patterns. If your analysis is
                  flawed, Kelly will magnify those errors.
                </p>

                <h3 className="text-xl font-semibold text-slate-100 mb-4 mt-8">
                  3. Bankroll Volatility
                </h3>
                <p className="mb-4">
                  Full Kelly: 50% chance of 50% drawdown, 10% chance of 75% drawdown.
                  Most bettors cannot psychologically handle this. Quarter Kelly
                  reduces these swings dramatically.
                </p>

                <h3 className="text-xl font-semibold text-slate-100 mb-4 mt-8">
                  4. Transaction Costs & Liquidity
                </h3>
                <p className="mb-4">
                  Kelly assumes zero transaction costs, infinite liquidity, ability to
                  bet any amount. Real-world: bookmakers limit stakes, you face
                  restrictions after winning, minimum bet sizes exist.
                </p>

                <h3 className="text-xl font-semibold text-slate-100 mb-4 mt-8">
                  5. The Multiple Bets Problem
                </h3>
                <p className="mb-4">
                  Kelly was designed for sequential, single bets. But profitable
                  strategies generate multiple simultaneous opportunities. If you&apos;re
                  betting 30 props across a weekend, each at 2% Kelly, you&apos;re
                  effectively 60% leveraged on correlated outcomes.
                </p>

                <h3 className="text-xl font-semibold text-slate-100 mb-4 mt-8">
                  6. Requires Discipline
                </h3>
                <p className="mb-4">
                  Kelly tells you to bet more after wins and less after losses. Most
                  bettors do the opposite. Kelly demands you ignore emotional impulses.
                </p>

                <h3 className="text-xl font-semibold text-slate-100 mb-4 mt-8">
                  7. No Edge? Don&apos;t Bet
                </h3>
                <p className="mb-4">
                  If Kelly returns zero or negative, you don&apos;t have an edge — regardless
                  of how confident you feel. The formula is brutally honest.
                </p>

                <h3 className="text-xl font-semibold text-slate-100 mb-4 mt-8">
                  When Kelly Fails Completely
                </h3>
                <p className="mb-4">
                  Kelly assumes: genuine edge, accurate probability estimates,
                  sufficient bankroll, ability to handle volatility, long-term
                  perspective (hundreds of bets minimum). If any aren&apos;t met, Kelly
                  is the wrong tool. Recreational bettors with small bankrolls should
                  use fixed small stakes instead.
                </p>
              </section>

              {/* Section 5: Fractional Kelly */}
              <section id="fractional">
                <h2 className="text-2xl sm:text-3xl font-semibold text-slate-100 mb-6 mt-12">
                  Fractional Kelly — Which Multiple to Use
                </h2>

                <p className="mb-4">
                  Professional bettors rarely use full Kelly. The question isn&apos;t
                  whether to use a fraction, but which fraction.
                </p>

                <div className="bg-slate-900/50 border border-slate-800 rounded-lg p-6 my-6 overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="border-b border-slate-700 text-xs text-slate-500 uppercase">
                        <th className="text-left py-3 pr-4">Kelly Fraction</th>
                        <th className="text-left py-3 pr-4">Volatility</th>
                        <th className="text-left py-3 pr-4">Growth Rate</th>
                        <th className="text-left py-3">Best For</th>
                      </tr>
                    </thead>
                    <tbody className="text-slate-300">
                      <tr className="border-b border-slate-800/50">
                        <td className="py-3 pr-4">Full Kelly (1x)</td>
                        <td className="py-3 pr-4">Extreme</td>
                        <td className="py-3 pr-4">100%</td>
                        <td className="py-3">Almost nobody</td>
                      </tr>
                      <tr className="border-b border-slate-800/50">
                        <td className="py-3 pr-4">Half Kelly (0.5x)</td>
                        <td className="py-3 pr-4">High</td>
                        <td className="py-3 pr-4">75%</td>
                        <td className="py-3">Aggressive pros</td>
                      </tr>
                      <tr className="border-b border-slate-800/50">
                        <td className="py-3 pr-4">Quarter Kelly (0.25x)</td>
                        <td className="py-3 pr-4">Moderate</td>
                        <td className="py-3 pr-4">56%</td>
                        <td className="py-3">Tennis / match markets (liquid)</td>
                      </tr>
                      <tr className="border-b border-slate-800/50">
                        <td className="py-3 pr-4">One-Tenth Kelly (0.1x)</td>
                        <td className="py-3 pr-4">Low</td>
                        <td className="py-3 pr-4">19%</td>
                        <td className="py-3">Prop bets / conservative (most pros)</td>
                      </tr>
                    </tbody>
                  </table>
                </div>

                <div className="bg-emerald-500/10 border border-emerald-500/30 rounded-lg p-6 my-6">
                  <h3 className="text-xl font-semibold text-emerald-400 mb-4">
                    How Il Margine Approaches It
                  </h3>
                  <p className="text-slate-300 mb-4">
                    We use <strong className="text-slate-200">one-tenth Kelly for prop bets</strong> — they&apos;re more volatile and our probability estimates are less reliable. For tennis (match / first set markets), where edges are easier to quantify and markets are more liquid, we use <strong className="text-slate-200">quarter Kelly</strong>.
                  </p>
                  <p className="text-slate-300 mb-4">
                    Our stake range is generally <strong className="text-slate-200">0.5u to 2u</strong>, where 1 unit ≈ 1% of bankroll. That means:
                  </p>
                  <ul className="text-slate-300 text-sm space-y-2 list-none mb-4">
                    <li>• <strong className="text-slate-200">Minimum:</strong> ~0.5% of bankroll</li>
                    <li>• <strong className="text-slate-200">Maximum:</strong> ~2% of bankroll</li>
                    <li>• <strong className="text-slate-200">Typical:</strong> 1u (1% of bankroll)</li>
                  </ul>
                  <p className="text-slate-300 mb-0">
                    We cap at ~2% because of estimation uncertainty, multiple simultaneous bets, and account longevity. Most professionals avoid staking more than 1–2% per bet; 2–4% is aggressive and rarely justified for props.
                  </p>
                </div>

                <h3 className="text-xl font-semibold text-slate-100 mb-4 mt-8">
                  The Ed Thorp Insight
                </h3>
                <p className="mb-4">
                  Legendary mathematician Ed Thorp found that overbetting is worse
                  than underbetting, half Kelly offers insurance against estimation
                  errors, and the cost of reducing from full to half Kelly is only 25%
                  growth. <strong className="text-slate-200">His advice:</strong>{" "}
                  &quot;When in doubt, bet less.&quot;
                </p>
              </section>

              {/* Section 6: Implementation */}
              <section id="implementation">
                <h2 className="text-2xl sm:text-3xl font-semibold text-slate-100 mb-6 mt-12">
                  Practical Implementation
                </h2>

                <h3 className="text-xl font-semibold text-slate-100 mb-4 mt-8">
                  Step-by-Step: Using Kelly for Your Bets
                </h3>
                <ol className="list-decimal pl-6 mb-4 space-y-3">
                  <li>
                    <strong className="text-slate-200">Assess True Probability</strong> —
                    Analyze data, estimate win probability, err conservative
                  </li>
                  <li>
                    <strong className="text-slate-200">Calculate Implied Probability</strong> —
                    Implied probability = 1 / odds
                  </li>
                  <li>
                    <strong className="text-slate-200">Determine Your Edge</strong> —
                    Edge = your probability - implied probability
                  </li>
                  <li>
                    <strong className="text-slate-200">Apply Kelly Formula</strong> —
                    f* = (bp - q) / b
                  </li>
                  <li>
                    <strong className="text-slate-200">Apply Fractional Kelly</strong> —
                    Multiply by 0.1 for props, 0.25 for tennis/match markets
                  </li>
                  <li>
                    <strong className="text-slate-200">Calculate Stake in Currency</strong> —
                    Multiply percentage by bankroll
                  </li>
                  <li>
                    <strong className="text-slate-200">Track & Adjust</strong> —
                    Record bets, recalculate bankroll regularly
                  </li>
                </ol>

                <h3 className="text-xl font-semibold text-slate-100 mb-4 mt-8">
                  Kelly Calculator
                </h3>
                <p className="mb-4">
                  Use our free Kelly calculator at{" "}
                  <Link href="/calculator" className="text-emerald-400 hover:text-emerald-300 underline">
                    /calculator
                  </Link>
                  . Input bankroll, decimal odds, and your win probability estimate, then
                  choose your fractional multiplier (one-tenth or quarter Kelly). The
                  calculator outputs your recommended stake instantly.
                </p>

                <h3 className="text-xl font-semibold text-slate-100 mb-4 mt-8">
                  Golden Rules
                </h3>
                <ol className="list-decimal pl-6 mb-4 space-y-2">
                  <li>Never bet more than 5% of bankroll on a single bet</li>
                  <li>Use one-tenth Kelly for props, quarter Kelly for tennis</li>
                  <li>Recalculate bankroll monthly</li>
                  <li>If Kelly says don&apos;t bet, don&apos;t bet — no exceptions</li>
                  <li>Track everything</li>
                </ol>
              </section>

              {/* Section 7: Comparison */}
              <section id="comparison">
                <h2 className="text-2xl sm:text-3xl font-semibold text-slate-100 mb-6 mt-12">
                  Kelly vs Other Staking Plans
                </h2>

                <p className="mb-4">
                  <strong className="text-slate-200">Flat Staking:</strong> Simple but
                  suboptimal — treats all bets equally.
                </p>
                <p className="mb-4">
                  <strong className="text-slate-200">Percentage Staking:</strong> Better
                  than flat, but doesn&apos;t account for edge size or odds.
                </p>
                <p className="mb-4">
                  <strong className="text-slate-200">Martingale:</strong> Mathematically
                  unsound — guarantees ruin with insufficient bankroll.
                </p>
                <p className="mb-4">
                  <strong className="text-slate-200">Kelly Criterion:</strong> Mathematically
                  optimal for maximizing growth, automatically adjusts to edge and
                  odds. Best long-term approach for value bettors.
                </p>
                <p className="mb-4">
                  <strong className="text-slate-200">The verdict:</strong> For serious
                  bettors with genuine edges, Kelly (fractional) is superior. For
                  recreational bettors or those without proven edges, simple
                  percentage staking is safer.
                </p>
              </section>

              {/* Section 8: Conclusion */}
              <section id="conclusion">
                <h2 className="text-2xl sm:text-3xl font-semibold text-slate-100 mb-6 mt-12">
                  Conclusion
                </h2>
                <p className="mb-4">
                  The Kelly Criterion represents the most mathematically rigorous
                  approach to bankroll management in sports betting. When applied
                  correctly with fractional Kelly, it maximizes long-term growth while
                  controlling risk of ruin.
                </p>
                <p className="mb-4">
                  But Kelly is not a magic formula. It demands accurate probability
                  estimation, honest edge assessment, psychological discipline, and
                  a long-term perspective. Most critically, Kelly cannot create an
                  edge where none exists.
                </p>
                <p className="mb-4">
                  Our approach at Il Margine combines data-driven selection with
                  conservative fractional Kelly staking (one-tenth for props, quarter for tennis).
                  This balance delivers sustainable growth without the volatility that
                  destroys most bettors.
                </p>
                <p className="mb-4">
                  The mathematics are clear: if you have an edge, Kelly tells you how
                  much to bet. If you don&apos;t have an edge, Kelly tells you not to bet
                  at all. That honesty and mathematical discipline is what separates
                  profitable betting from gambling.
                </p>
                <p className="mb-4 font-semibold text-slate-200">
                  Start conservative. Track everything. Let the mathematics guide you.
                </p>
              </section>

              {/* Related Resources */}
              <div className="border-t border-slate-800 mt-16 pt-8">
                <h3 className="text-xl font-semibold text-slate-100 mb-4">
                  Related Resources
                </h3>
                <div className="grid sm:grid-cols-2 gap-4">
                  <Link
                    href="/the-edge"
                    className="block p-4 bg-slate-900/50 border border-slate-800 rounded-lg hover:border-emerald-500/30 transition-colors"
                  >
                    <h4 className="text-slate-100 font-semibold mb-2">Our Methodology</h4>
                    <p className="text-sm text-slate-400">
                      Learn how we identify value in player props and tennis markets
                    </p>
                  </Link>
                  <Link
                    href="/calculator"
                    className="block p-4 bg-slate-900/50 border border-slate-800 rounded-lg hover:border-emerald-500/30 transition-colors"
                  >
                    <h4 className="text-slate-100 font-semibold mb-2">Returns Calculator</h4>
                    <p className="text-sm text-slate-400">
                      See how much you would have won following our historical picks at different stake levels
                    </p>
                  </Link>
                </div>
              </div>
            </div>
          </article>
        </div>
      </div>

      <Footer />
    </div>
  );
}
