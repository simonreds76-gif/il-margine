import Link from "next/link";
import Image from "next/image";
import Footer from "@/components/Footer";

const BOOKMAKERS = [
  {
    id: "midnite",
    name: "Midnite",
    stars: "⭐⭐⭐⭐½",
    rating: "4.5/5",
    propsScore: "8/10",
    tennisScore: "7/10",
    welcomeOffer: "Bet £10 Get £20 Free Bets",
    welcomeTerms: "Min odds 1.50, free bets valid 7 days",
    strengths: [
      "Strong player props coverage across major leagues",
      "Competitive odds on shots, fouls, cards markets",
      "Modern, fast platform (built for mobile)",
      "Quick bet placement and settlement",
      "Good lower-league football coverage",
      "Generally longer account lifespan than legacy bookmakers",
      "Responsive customer service",
    ],
    weaknesses: [
      "Limited tennis coverage outside ATP/WTA top events",
      "Fewer niche markets than established competitors",
      "Bet builder available on major matches",
      "Stake limits can be conservative on props (£50-100 typical max)",
      "Less track record for account longevity under sustained winning",
    ],
    usageTips: "Midnite is one of the newer operators worth attention. Built from scratch with modern infrastructure, the platform is fast and intuitive. Best used for Premier League and Championship player props where their odds are often competitive with or better than legacy books. Coverage of shots on target, fouls committed, and cards received is solid. Account longevity appears reasonable based on limited testing, but treat as unproven until you've run a few months of profitable action. Start conservatively and scale if the account survives. Avoid for tennis beyond major tournaments. Stick to football props where they're strongest.",
    bestFor: "Modern platform, major league props",
    offerUrl: "#",
  },
  {
    id: "betvictor",
    name: "BetVictor",
    stars: "⭐⭐⭐⭐",
    rating: "4/5",
    propsScore: "8/10",
    tennisScore: "8/10",
    welcomeOffer: "Bet £10 Get £40 in Bonuses",
    welcomeTerms: "Min odds 2.00, various bonus types, T&Cs apply",
    strengths: [
      "Excellent player props depth across all major leagues",
      "Strong tennis handicap and total markets",
      "Competitive odds on both props and tennis",
      "Good ATP 250/500 tournament coverage",
      "Established operator with reliable platform",
      "Reasonable withdrawal processing (24-48 hours typical)",
      "Accepts larger stakes than many UK books (£200+ props, £500+ tennis)",
      ],
    weaknesses: [
      "Player props margins can be 12-14% (slightly wider than best in class)",
      "Bet builder functionality limited",
      "Live betting interface dated compared to newer operators",
    ],
    usageTips: "BetVictor is a solid all-rounder for both player props and tennis. One of the few UK bookmakers offering genuine depth on both market types. For props: Coverage is comprehensive across Premier League, La Liga, Bundesliga, Serie A. Odds quality is competitive, though you'll find better prices elsewhere 30-40% of the time. Still worth having for comparison and as a secondary account. For tennis: Excellent for ATP 250s and Challengers where other bookmakers thin out their markets. Game handicaps and totals are well-priced here. Often competitive with sharper operators on lower-tier events. Strong option for both prop and tennis bettors. Essential to have in rotation.",
    bestFor: "All-rounder, strong tennis",
    offerUrl: "#",
  },
  {
    id: "unibet",
    name: "Unibet",
    stars: "⭐⭐⭐⭐",
    rating: "4/5",
    propsScore: "7/10",
    tennisScore: "8/10",
    welcomeOffer: "Money Back as Bonus up to £40",
    welcomeTerms: "Min odds 1.40, 3+ selections, T&Cs apply",
    strengths: [
      "Excellent tennis markets across all tiers (ATP, WTA, Challengers)",
      "Competitive odds on tennis handicaps and totals",
      "Part of Kindred Group (solid operational infrastructure)",
      "Good platform stability",
      "Fast withdrawals (often same day to e-wallets)",
    ],
    weaknesses: [
      "Player props margins slightly wider (12-15%)",
      "Fewer prop markets than dedicated prop-focused books",
      "Bet builder limited to major matches only",
      "Welcome offer structure less attractive than competitors",
      "Props stake limits conservative (£50-75 typical)",
    ],
    usageTips: "Unibet's real strength is tennis, particularly at ATP 250/500 level and Challenger events. If you're betting tennis seriously, this account is essential. Game handicaps and totals are well-priced across all surface types. Unibet often has better odds than Bet365 or William Hill on lower-tier ATP events, and sometimes matches Pinnacle on Challengers. For player props, treat as a secondary account. Coverage exists but margins are wider and stake limits are tighter than specialists. Good to have for odds comparison but unlikely to be your primary props book. Essential for tennis bettors. Useful secondary account for props.",
    bestFor: "Tennis specialists, ATP 250s",
    offerUrl: "#",
  },
  {
    id: "coral",
    name: "Coral",
    stars: "⭐⭐⭐⭐",
    rating: "4/5",
    propsScore: "8/10",
    tennisScore: "7/10",
    welcomeOffer: "Bet £10 Get £30 in Free Bets",
    welcomeTerms: "Min odds 1.50, free bets valid 7 days",
    strengths: [
      "Comprehensive player props across all major leagues",
      "Part of Entain (shares pricing with Ladbrokes but separate account)",
      "Solid odds quality on props markets",
      "Good bet builder functionality",
      "High street presence (useful for deposits/withdrawals if needed)",
      "Reasonable tennis coverage on major events",
    ],
    weaknesses: [
      "Same pricing engine as Ladbrokes (no arbitrage between them)",
      "Tennis markets thin out below ATP 250 level",
      "Props margins 10-13%",
      "Stake limits tighten quickly on profitable accounts",
    ],
    usageTips: "Coral is part of the Entain group alongside Ladbrokes. Critically, you can hold accounts with both simultaneously. This creates a tactical opportunity: open both Coral and Ladbrokes. They share the same pricing engine, so odds are identical, but each account is independently managed. Having both gives you dual access to Entain's competitive pricing across props and tennis markets. For props: Coverage is excellent across Premier League, Championship, and major European leagues. Bet builder is solid and occasionally misprices correlation. Worth using. For tennis: Adequate for ATP 250+, but skip for anything below that tier. Other operators have better coverage of Challengers. Always pair Coral with Ladbrokes. Never use one without the other.",
    bestFor: "Pair with Ladbrokes for extended access",
    offerUrl: "#",
  },
  {
    id: "ladbrokes",
    name: "Ladbrokes",
    stars: "⭐⭐⭐⭐",
    rating: "4/5",
    propsScore: "8/10",
    tennisScore: "7/10",
    welcomeOffer: "Bet £5 Get £20 in Free Bets",
    welcomeTerms: "Min odds 1.50, free bets valid 7 days",
    strengths: [
      "Identical strengths to Coral (same pricing engine)",
      "Comprehensive props across major leagues",
      "Solid bet builder markets",
      "Part of established Entain group",
      "Historical brand with long operational track record",
    ],
    weaknesses: [
      "Identical weaknesses to Coral (same pricing engine)",
      "Tennis coverage thins below ATP 250",
      "Props margins 10-13%",
    ],
    usageTips: "Everything said about Coral applies here. Ladbrokes and Coral are operationally the same book with separate account management. The strategy is simple: Open both. Use both. When one restricts you, keep using the other. For props: Excellent coverage, good odds, decent bet builders. Use actively. For tennis: Fine for ATP 250+, skip below that. The only reason to choose Ladbrokes over Coral or vice versa is welcome offer preference. Otherwise, they're functionally identical, so having both doubles your access window to Entain pricing. This pairing is non-negotiable. If you have one, you must have the other.",
    bestFor: "Pair with Coral for extended access",
    offerUrl: "#",
  },
  {
    id: "betmgm",
    name: "BetMGM",
    stars: "⭐⭐⭐⭐",
    rating: "4/5",
    propsScore: "7/10",
    tennisScore: "6/10",
    welcomeOffer: "Bet £10 Get £40 in Free Bets",
    welcomeTerms: "Min odds 1.50, free bets valid 7 days",
    strengths: [
      "Operates on LeoVegas platform (acquired by MGM), independent pricing from other UK operators",
      "Growing props coverage",
      "Competitive odds on major matches",
      "Modern platform",
      "Good bet builder selection",
      "Fast withdrawals",
    ],
    weaknesses: [
      "Smaller market selection than established operators",
      "Props margins can be wider (12-15%)",
      "Fewer users means less liquidity on niche markets",
      "Smaller UK presence than established operators",
      "Fewer promotional offers than competitors",
    ],
    usageTips: "BetMGM operates on the LeoVegas platform with fully independent pricing. This means odds can differ significantly from other bookmakers, creating valuable line shopping opportunities. For props: Solid coverage on Premier League and major European leagues. Worth checking for price comparison. Sometimes offers better odds than established operators on specific markets. For tennis: Good coverage across ATP 250+ events. Competitive pricing on game handicaps and totals. Stronger tennis offering than many UK books. Definitely check their odds when betting ATP events. Useful as a core account for both props and tennis. The independent pricing makes this essential for line shopping rather than optional.",
    bestFor: "Line shopping, independent pricing",
    offerUrl: "#",
  },
  {
    id: "william-hill",
    name: "William Hill",
    stars: "⭐⭐⭐⭐",
    rating: "4/5",
    propsScore: "8/10",
    tennisScore: "7/10",
    welcomeOffer: "Bet £10 Get £30 in Free Bets",
    welcomeTerms: "Min odds 1.50, free bets valid 30 days",
    strengths: [
      "Comprehensive player props across all major leagues",
      "Competitive odds on props markets",
      "Good lower-league football coverage",
      "Solid tennis markets on ATP 250+",
      "One of the more established UK operators",
      "Reliable platform and withdrawal processing",
      "Good bet builder functionality",
    ],
    weaknesses: [
      "Props margins 10-13%",
      "Tennis coverage drops off below ATP 250",
      "Platform can feel dated compared to newer operators",
      "Stake limits tighten on repeated winning",
    ],
    usageTips: "William Hill is a legacy UK bookmaker with solid props and tennis offerings. Not the sharpest odds, but reliably competent across the board. For props: Strong coverage across Premier League, Championship, La Liga, Bundesliga, Serie A. Odds are competitive roughly 40-50% of the time. When they're best price, take it. When they're not, shop elsewhere. Bet builder markets are decent. Correlation mispricing does occur, particularly on lower-profile matches. For tennis: Good for ATP 250s and above. Game handicaps and totals are competently priced. Often within 2-3% of Pinnacle closing lines on ATP 500s. Solid all-rounder. Worth having in your rotation.",
    bestFor: "Solid all-rounder",
    offerUrl: "#",
  },
  {
    id: "betfred",
    name: "Betfred",
    stars: "⭐⭐⭐⭐",
    rating: "4/5",
    propsScore: "7/10",
    tennisScore: "7/10",
    welcomeOffer: "Bet £10 Get £40 in Bonuses",
    welcomeTerms: "£30 in free bets + £10 casino bonus, min odds 2.00 for sports bets",
    strengths: [
      "Higher welcome offer than most competitors (£40 total)",
      "Good props coverage on major leagues",
      "Decent tennis markets ATP 250+",
      "Fast withdrawals",
      "Good cards markets specifically",
      "Part of Fred Done's independently owned operation (different risk appetite than corporate books)",
    ],
    weaknesses: [
      "Odds quality slightly below best in class",
      "Props margins 11-14%",
      "Platform can be clunky",
      "Fewer bet builder markets than competitors",
    ],
    usageTips: "Betfred's biggest draw is the £40 welcome offer. Being independently owned (not part of a large group), they operate with different risk parameters. For props: Solid coverage on major leagues. Odds are rarely best-in-class but occasionally competitive. Check them alongside others for line shopping. Cards markets (yellow/red) are often better priced here than elsewhere. If you're targeting card markets specifically, Betfred is worth priority consideration. For tennis: Adequate for ATP 250+. Not exceptional, but functional. Good as a third or fourth props account. Essential if targeting cards markets.",
    bestFor: "Cards markets, higher welcome offer",
    offerUrl: "#",
  },
];

const COMPARISON_ROWS = [
  { name: "Midnite", props: "8/10", tennis: "7/10", offer: "£20 free bets", bestFor: "Modern platform, major league props" },
  { name: "BetVictor", props: "8/10", tennis: "8/10", offer: "£40 bonuses", bestFor: "All-rounder, strong tennis" },
  { name: "Unibet", props: "7/10", tennis: "8/10", offer: "£40 money back", bestFor: "Tennis specialists, ATP 250s" },
  { name: "Coral", props: "8/10", tennis: "7/10", offer: "£30 free bets", bestFor: "Pair with Ladbrokes for extended access" },
  { name: "Ladbrokes", props: "8/10", tennis: "7/10", offer: "£20 free bets", bestFor: "Pair with Coral for extended access" },
  { name: "BetMGM", props: "7/10", tennis: "6/10", offer: "£40 free bets", bestFor: "Line shopping, independent pricing" },
  { name: "William Hill", props: "8/10", tennis: "7/10", offer: "£30 free bets", bestFor: "Solid all-rounder" },
  { name: "Betfred", props: "7/10", tennis: "7/10", offer: "£40 bonuses", bestFor: "Cards markets, higher welcome offer" },
];

const FAQ_ITEMS = [
  { q: "Should I open all eight accounts at once?", a: "Yes. Welcome offers alone provide £250+ value. More importantly, having eight accounts active extends your operational window to 18-24 months before restrictions become severe across all platforms. Open them all, claim all offers, use them strategically." },
  { q: "What if odds are better elsewhere?", a: "Always take best price. Line shop across all eight before placing any bet. Over 100 bets, even 2-3% better average odds compounds significantly. Never settle for worse odds out of loyalty or convenience." },
  { q: "Do affiliate links affect your recommendations?", a: "No. These bookmakers were selected through months of real-money testing before any affiliate discussions began. We sought partnerships with books we already used, not vice versa. If a bookmaker deteriorates in quality or changes practices, we'll remove them regardless of commercial arrangements." },
  { q: "Are welcome bonuses worth it?", a: "Absolutely. Combined, these eight offer £250+ in bonuses. Even accounting for rollover requirements, expected value is positive. Claim all of them. Use them on +EV opportunities where possible, or on lower-variance markets if rollover requirements demand it." },
  { q: "Can I use both Ladbrokes and Coral?", a: "Yes, and you absolutely should. They're part of the same group (Entain) and share identical pricing, but account management is separate. Opening both doubles your access window to Entain odds from 6-9 months to 12-18 months. This pairing is essential." },
  { q: "What happens when I get restricted?", a: "Stake limits reduce gradually, eventually hitting £5-20 maximum. The account remains active but becomes operationally useless for serious betting. This is inevitable for winning accounts. Plan for it by having multiple accounts active. When one restricts, continue with others.", linkToFaq: true },
];

export default function BookmakersPage() {
  return (
    <div className="min-h-screen bg-[#0f1117] text-slate-100">
      <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 pt-6 pb-8 md:pb-12">
        <Link href="/" className="inline-flex items-center gap-2 text-sm text-slate-500 hover:text-slate-300 mb-8">
          <Image src="/favicon.png" alt="" width={40} height={40} className="h-10 w-10 object-contain shrink-0" />
          <span>← Home</span>
        </Link>

        {/* Hero */}
        <section className="mb-12 md:mb-16">
          <span className="text-xs font-mono text-emerald-400 mb-3 block tracking-wider">BOOKMAKERS</span>
          <h1 className="text-3xl sm:text-4xl font-semibold text-slate-100 mb-3">Recommended Bookmakers</h1>
          <p className="text-lg text-slate-300 max-w-3xl mb-4">
            Field-tested bookmakers for player props and tennis betting. Affiliate partnerships being established.
          </p>
          <p className="text-slate-300 leading-relaxed mb-4 max-w-3xl">
            Not all bookmakers are created equal. Some offer competitive odds on player props, others restrict winning accounts within weeks. Some process withdrawals in hours, others take days.
          </p>
          <p className="text-slate-300 leading-relaxed mb-4 max-w-3xl">
            This page recommends bookmakers we&apos;ve tested with real stakes across player props and tennis markets. Each has been evaluated for odds quality, market depth, account longevity, and operational reliability.
          </p>
          <ul className="list-disc pl-6 text-slate-300 space-y-1 mb-4 max-w-3xl">
            <li>Eight bookmakers suitable for value betting</li>
            <li>Market-specific strengths for props and tennis</li>
            <li>Realistic account longevity expectations</li>
            <li>Current welcome offers</li>
            <li>Usage tactics for each platform</li>
          </ul>
          <p className="text-slate-400 text-sm max-w-3xl">
            <strong className="text-slate-300">Affiliate disclosure:</strong> We&apos;re establishing affiliate partnerships with these bookmakers. When active, links will be clearly marked. Recommendations remain independent regardless of commercial arrangements.
          </p>
        </section>

        {/* 8 Bookmaker cards */}
        <div className="space-y-8 mb-14">
          {BOOKMAKERS.map((bm) => (
            <article key={bm.id} className="bg-[#1a1d24] rounded-xl border border-slate-800 p-6 md:p-8">
              <h3 className="text-xl font-semibold text-slate-100 mb-2">{bm.name}</h3>
              <p className="text-amber-400/90 text-sm mb-3" aria-label={`Rating ${bm.rating}`}>{bm.stars}</p>
              <div className="flex flex-wrap gap-4 text-sm text-slate-400 mb-4">
                <span>💰 <strong className="text-slate-200">Player Props:</strong> {bm.propsScore}</span>
                <span>🎾 <strong className="text-slate-200">Tennis:</strong> {bm.tennisScore}</span>
              </div>
              <div className="bg-emerald-500/10 border border-emerald-500/20 rounded-lg p-4 mb-4">
                <p className="font-medium text-slate-100">New customers: {bm.welcomeOffer}</p>
                <p className="text-sm text-slate-400 mt-1">Terms: {bm.welcomeTerms}</p>
              </div>
              <div className="grid sm:grid-cols-2 gap-6 mb-4">
                <div>
                  <p className="text-xs font-mono text-emerald-400 mb-2">Strengths</p>
                  <ul className="list-disc pl-5 text-slate-300 text-sm space-y-1">
                    {bm.strengths.map((s, i) => <li key={i}>{s}</li>)}
                  </ul>
                </div>
                <div>
                  <p className="text-xs font-mono text-slate-400 mb-2">Weaknesses</p>
                  <ul className="list-disc pl-5 text-slate-300 text-sm space-y-1">
                    {bm.weaknesses.map((w, i) => <li key={i}>{w}</li>)}
                  </ul>
                </div>
              </div>
              <p className="text-slate-300 text-sm leading-relaxed mb-6">{bm.usageTips}</p>
              <a
                href={bm.offerUrl}
                className="inline-flex items-center gap-2 bg-emerald-500 hover:bg-emerald-400 text-white font-semibold px-6 py-3 rounded-lg transition-colors shadow-lg w-full sm:w-auto justify-center"
              >
                Claim {bm.name} Offer →
              </a>
            </article>
          ))}
        </div>

        {/* Key Concepts - 5 accordions */}
        <section className="mb-14">
          <h2 className="text-xl font-semibold text-emerald-400 mb-6">Understanding Bookmaker Markets</h2>
          <div className="bg-[#1a1d24] rounded-xl border border-slate-800 overflow-hidden divide-y divide-slate-800">
            <details className="group">
              <summary className="flex cursor-pointer list-none items-center justify-between gap-2 px-6 md:px-8 py-4 text-left font-medium text-slate-200 hover:bg-slate-800/30 transition-colors">
                <span>Market Efficiency & Edge Identification</span>
                <span className="text-emerald-400 shrink-0 transition-transform group-open:rotate-180">
                  <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" /></svg>
                </span>
              </summary>
              <div className="px-6 md:px-8 pb-4 pt-0">
                <div className="text-slate-300 text-sm leading-relaxed space-y-3">
                  <p>Not all markets are priced equally. Bookmakers allocate resources based on betting volume and risk exposure.</p>
                  <p><strong className="text-slate-100">Efficient Markets:</strong> Premier League match odds: Teams of traders, real-time monitoring, 3-5% margin. High liquidity + sharp money = minimal edge opportunity.</p>
                  <p><strong className="text-slate-100">Inefficient Markets:</strong> Player props: Template pricing, minimal oversight, 10-15% margin. Lower-tier tennis: Algorithmic pricing, limited trader attention, 8-12% margin. Bet builders: Correlation mispricing common, 10-15% margin.</p>
                  <p>Our approach: We bet across all markets when we identify genuine edge. Player props and tennis handicaps are our primary focus because mispricing is more frequent, but we&apos;ll take value wherever it exists. See <Link href="/the-edge" className="text-emerald-400 hover:text-emerald-300 underline">The Edge</Link> for methodology.</p>
                </div>
              </div>
            </details>
            <details className="group">
              <summary className="flex cursor-pointer list-none items-center justify-between gap-2 px-6 md:px-8 py-4 text-left font-medium text-slate-200 hover:bg-slate-800/30 transition-colors">
                <span>Market Margins</span>
                <span className="text-emerald-400 shrink-0 transition-transform group-open:rotate-180">
                  <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" /></svg>
                </span>
              </summary>
              <div className="px-6 md:px-8 pb-4 pt-0">
                <div className="text-slate-300 text-sm leading-relaxed space-y-3">
                  <p>Understanding margins reveals where value opportunities exist:</p>
                  <div className="overflow-x-auto">
                    <table className="w-full text-sm border-collapse">
                      <thead>
                        <tr className="border-b border-slate-700">
                          <th className="text-left py-2 pr-4 text-emerald-400/90 font-medium">Market Type</th>
                          <th className="text-left py-2 pr-4 text-emerald-400/90 font-medium">Typical Margin</th>
                          <th className="text-left py-2 pr-4 text-emerald-400/90 font-medium">Opportunity</th>
                          <th className="text-left py-2 text-emerald-400/90 font-medium">Focus</th>
                        </tr>
                      </thead>
                      <tbody className="text-slate-300">
                        <tr className="border-b border-slate-800"><td className="py-2 pr-4">Premier League 1X2</td><td className="py-2 pr-4">3-5%</td><td className="py-2 pr-4">Low</td><td className="py-2">Occasionally</td></tr>
                        <tr className="border-b border-slate-800"><td className="py-2 pr-4">Championship 1X2</td><td className="py-2 pr-4">5-7%</td><td className="py-2 pr-4">Low-Moderate</td><td className="py-2">Occasionally</td></tr>
                        <tr className="border-b border-slate-800"><td className="py-2 pr-4">Player Props</td><td className="py-2 pr-4">10-15%</td><td className="py-2 pr-4">High</td><td className="py-2">Yes</td></tr>
                        <tr className="border-b border-slate-800"><td className="py-2 pr-4">Tennis Match Odds</td><td className="py-2 pr-4">4-6%</td><td className="py-2 pr-4">Low</td><td className="py-2">Occasionally (selective)</td></tr>
                        <tr className="border-b border-slate-800"><td className="py-2 pr-4">Tennis Handicaps</td><td className="py-2 pr-4">8-12%</td><td className="py-2 pr-4">Moderate-High</td><td className="py-2">Yes</td></tr>
                        <tr className="border-b border-slate-800"><td className="py-2 pr-4">Bet Builders</td><td className="py-2 pr-4">10-15%</td><td className="py-2 pr-4">High</td><td className="py-2">Yes (coming soon)</td></tr>
                      </tbody>
                    </table>
                  </div>
                  <p>Larger margins don&apos;t guarantee edge, but they create more room for mispricing.</p>
                </div>
              </div>
            </details>
            <details className="group">
              <summary className="flex cursor-pointer list-none items-center justify-between gap-2 px-6 md:px-8 py-4 text-left font-medium text-slate-200 hover:bg-slate-800/30 transition-colors">
                <span>Account Restrictions</span>
                <span className="text-emerald-400 shrink-0 transition-transform group-open:rotate-180">
                  <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" /></svg>
                </span>
              </summary>
              <div className="px-6 md:px-8 pb-4 pt-0">
                <div className="text-slate-300 text-sm leading-relaxed space-y-3">
                  <p>Bookmakers restrict profitable accounts. This is inevitable, not personal.</p>
                  <p>Factors accelerating restrictions: consistent profitability, only betting props/niche markets, only odds ≥2.00, large stakes, withdrawing more than depositing. See <Link href="/faq" className="text-emerald-400 hover:text-emerald-300 underline">FAQ</Link> for guidance.</p>
                </div>
              </div>
            </details>
            <details className="group">
              <summary className="flex cursor-pointer list-none items-center justify-between gap-2 px-6 md:px-8 py-4 text-left font-medium text-slate-200 hover:bg-slate-800/30 transition-colors">
                <span>Account Longevity Tactics</span>
                <span className="text-emerald-400 shrink-0 transition-transform group-open:rotate-180">
                  <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" /></svg>
                </span>
              </summary>
              <div className="px-6 md:px-8 pb-4 pt-0">
                <div className="text-slate-300 text-sm leading-relaxed space-y-3">
                  <p>Practical tactics: Mix recreational action (occasional match odds). Variable staking (0.5u to 3u). Deposit regularly. Use features (bet builders, cash-out, in-play sometimes). Delay withdrawals 2-3 weeks. Avoid patterns (don&apos;t only bet Friday evenings or one league).</p>
                  <p>Advanced: Prioritise accounts with longer historical longevity. Accept restrictions are inevitable and plan rollover to new accounts. These tactics extend lifespan by 20-40%, not indefinitely.</p>
                </div>
              </div>
            </details>
            <details className="group">
              <summary className="flex cursor-pointer list-none items-center justify-between gap-2 px-6 md:px-8 py-4 text-left font-medium text-slate-200 hover:bg-slate-800/30 transition-colors">
                <span>Template Pricing Weakness</span>
                <span className="text-emerald-400 shrink-0 transition-transform group-open:rotate-180">
                  <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" /></svg>
                </span>
              </summary>
              <div className="px-6 md:px-8 pb-4 pt-0">
                <div className="text-slate-300 text-sm leading-relaxed space-y-3">
                  <p>Most bookmakers use template pricing for player props and lower-tier tennis. Example: bookmaker pulls player&apos;s last 10 matches, calculates average (e.g. 2.3 SOT), applies 12% margin, outputs odds. What templates miss: opponent-specific factors, tactical matchups, referee tendencies, venue factors, motivation. When your analysis incorporates these and the template doesn&apos;t, odds diverge from true probability. That&apos;s where we operate. See <Link href="/the-edge" className="text-emerald-400 hover:text-emerald-300 underline">The Edge</Link>.</p>
                </div>
              </div>
            </details>
          </div>
        </section>

        {/* Comparison Table */}
        <section className="mb-14">
          <h2 className="text-xl font-semibold text-emerald-400 mb-4">Quick Comparison</h2>
          <div className="overflow-x-auto rounded-lg border border-slate-700">
            <table className="w-full text-sm border-collapse min-w-[600px]">
              <thead>
                <tr className="bg-slate-800/60 border-b border-slate-700">
                  <th className="text-left py-3 px-4 text-emerald-400/90 font-medium">Bookmaker</th>
                  <th className="text-left py-3 px-4 text-emerald-400/90 font-medium">Player Props</th>
                  <th className="text-left py-3 px-4 text-emerald-400/90 font-medium">Tennis</th>
                  <th className="text-left py-3 px-4 text-emerald-400/90 font-medium">Welcome Offer</th>
                  <th className="text-left py-3 px-4 text-emerald-400/90 font-medium">Best For</th>
                </tr>
              </thead>
              <tbody>
                {COMPARISON_ROWS.map((row) => (
                  <tr key={row.name} className="border-b border-slate-800">
                    <td className="py-3 px-4 font-medium text-slate-200">{row.name}</td>
                    <td className="py-3 px-4 text-slate-300">{row.props}</td>
                    <td className="py-3 px-4 text-slate-300">{row.tennis}</td>
                    <td className="py-3 px-4 text-slate-300">{row.offer}</td>
                    <td className="py-3 px-4 text-slate-300">{row.bestFor}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p className="text-slate-500 text-xs mt-2">All ratings relative to UK bookmaker market, not global operators like Pinnacle.</p>
        </section>

        {/* Account Strategy */}
        <section className="bg-[#1a1d24] rounded-xl border border-slate-800 p-6 md:p-8 mb-14">
          <h2 className="text-xl font-semibold text-emerald-400 mb-4">Recommended Approach</h2>
          <div className="text-slate-300 text-sm leading-relaxed space-y-4">
            <p><strong className="text-slate-100">Account opening sequence:</strong></p>
            <ol className="list-decimal pl-6 space-y-2">
              <li>Open all eight accounts — welcome offers alone provide £250+ value</li>
              <li>Prioritise by market focus: Props primary: BetVictor, Midnite, William Hill, Coral, Ladbrokes. Tennis primary: Unibet, BetVictor, William Hill. Mixed: all eight for line shopping</li>
              <li>Always open Coral AND Ladbrokes — never one without the other</li>
              <li>Use BetMGM for Entain price comparison — often differs from Coral/Ladbrokes</li>
            </ol>
            <p><strong className="text-slate-100">Line shopping workflow:</strong> Before placing any bet: check odds across all eight, identify best price, place at bookmaker offering highest odds, track which books consistently offer best price, adjust priority accordingly.</p>
            <p>Over time, accounts will restrict at different rates. By opening all eight, you extend total operational window to 18-24 months before severe restrictions across all accounts. See <Link href="/track-record" className="text-emerald-400 hover:text-emerald-300 underline">Track Record</Link> for our performance context.</p>
          </div>
        </section>

        {/* Betting Glossary - 8 categories */}
        <section className="mb-14">
          <h2 className="text-xl font-semibold text-emerald-400 mb-6">Industry Terminology You Need To Know</h2>
          <div className="bg-[#1a1d24] rounded-xl border border-slate-800 overflow-hidden divide-y divide-slate-800">
            <details className="group">
              <summary className="flex cursor-pointer list-none items-center justify-between gap-2 px-6 md:px-8 py-4 text-left font-medium text-slate-200 hover:bg-slate-800/30 transition-colors">
                <span>Essential Betting Terms</span>
                <span className="text-emerald-400 shrink-0 transition-transform group-open:rotate-180"><svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" /></svg></span>
              </summary>
              <div className="px-6 md:px-8 pb-4 pt-0">
                <dl className="text-slate-300 text-sm space-y-3">
                  <div><dt className="font-semibold text-emerald-400/90">Gubbing / Getting Gubbed</dt><dd>When a bookmaker restricts your account to minimal stake levels (£5-10 max). The inevitable end-point for consistent winners on recreational bookmakers.</dd></div>
                  <div><dt className="font-semibold text-emerald-400/90">Mug Punter / Recreational Bettor</dt><dd>Casual bettor who uses promotions, backs favourites in accumulators. Bookmakers&apos; ideal customer.</dd></div>
                  <div><dt className="font-semibold text-emerald-400/90">Sharp / Sharp Bettor</dt><dd>Professional or highly profitable bettor with analytical edge. If you&apos;re consistently sharp, you&apos;ll get gubbed.</dd></div>
                  <div><dt className="font-semibold text-emerald-400/90">Stake / Staking</dt><dd>The amount wagered. &quot;Max stake&quot; = maximum bookmaker allows; decreases as you win.</dd></div>
                  <div><dt className="font-semibold text-emerald-400/90">Void / Voided Bet</dt><dd>Bet cancelled with stake returned. Common in player props when player doesn&apos;t start.</dd></div>
                  <div><dt className="font-semibold text-emerald-400/90">Value Bet / +EV</dt><dd>Bet where your calculated probability exceeds the bookmaker&apos;s implied probability. Long-term profitability comes from consistent +EV.</dd></div>
                  <div><dt className="font-semibold text-emerald-400/90">ROI</dt><dd>(Total Profit ÷ Total Staked) × 100. e.g. +20% = £20 profit per £100 wagered.</dd></div>
                  <div><dt className="font-semibold text-emerald-400/90">Units</dt><dd>Standardised bet sizing. 1 unit = your standard stake (typically 1-2% of bankroll).</dd></div>
                  <div><dt className="font-semibold text-emerald-400/90">Closing Line Value (CLV)</dt><dd>Comparing odds you took vs final odds before event. Positive CLV indicates sharp betting.</dd></div>
                  <div><dt className="font-semibold text-emerald-400/90">Bankroll</dt><dd>Total funds dedicated to betting. Recommended: 40-50 units minimum.</dd></div>
                  <div><dt className="font-semibold text-emerald-400/90">Edge</dt><dd>Your advantage over bookmaker&apos;s odds. All profitable betting is edge exploitation.</dd></div>
                </dl>
              </div>
            </details>
            <details className="group">
              <summary className="flex cursor-pointer list-none items-center justify-between gap-2 px-6 md:px-8 py-4 text-left font-medium text-slate-200 hover:bg-slate-800/30 transition-colors">
                <span>Market-Specific Terms</span>
                <span className="text-emerald-400 shrink-0 transition-transform group-open:rotate-180"><svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" /></svg></span>
              </summary>
              <div className="px-6 md:px-8 pb-4 pt-0">
                <dl className="text-slate-300 text-sm space-y-3">
                  <div><dt className="font-semibold text-emerald-400/90">Player Props / Player Specials</dt><dd>Bets on individual player stats: shots on target, fouls, tackles, cards.</dd></div>
                  <div><dt className="font-semibold text-emerald-400/90">Handicap / Spread</dt><dd>Adjusting final score by a margin. e.g. -3.5 games in tennis.</dd></div>
                  <div><dt className="font-semibold text-emerald-400/90">Total / Over-Under</dt><dd>Bet on combined total exceeding or below a number.</dd></div>
                  <div><dt className="font-semibold text-emerald-400/90">Bet Builder / Same Game Parlay</dt><dd>Multiple selections from one match; all must win. Correlation mispricing common.</dd></div>
                  <div><dt className="font-semibold text-emerald-400/90">Anytime Goalscorer (ATG)</dt><dd>Bet on player to score at least one goal during the match.</dd></div>
                </dl>
              </div>
            </details>
            <details className="group">
              <summary className="flex cursor-pointer list-none items-center justify-between gap-2 px-6 md:px-8 py-4 text-left font-medium text-slate-200 hover:bg-slate-800/30 transition-colors">
                <span>Bookmaker-Specific Terms</span>
                <span className="text-emerald-400 shrink-0 transition-transform group-open:rotate-180"><svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" /></svg></span>
              </summary>
              <div className="px-6 md:px-8 pb-4 pt-0">
                <dl className="text-slate-300 text-sm space-y-3">
                  <div><dt className="font-semibold text-emerald-400/90">Enhanced Odds / Price Boost</dt><dd>Promotional odds better than standard. Always calculate true value.</dd></div>
                  <div><dt className="font-semibold text-emerald-400/90">Free Bet / Bonus Bet</dt><dd>Stake provided by bookmaker. &quot;Stake Not Returned&quot; (SNR) = winnings exclude original stake.</dd></div>
                  <div><dt className="font-semibold text-emerald-400/90">Cash Out</dt><dd>Settling bet before event finishes at current odds. Usually -EV but can help account profile.</dd></div>
                  <div><dt className="font-semibold text-emerald-400/90">In-Play / Live Betting</dt><dd>Betting after event starts. Odds update in real-time.</dd></div>
                  <div><dt className="font-semibold text-emerald-400/90">Acca / Accumulator</dt><dd>Multiple bets combined; all must win. Margins compound — we don&apos;t recommend accas.</dd></div>
                  <div><dt className="font-semibold text-emerald-400/90">Each-Way (E/W)</dt><dd>Win + place bet. Common in horse racing.</dd></div>
                </dl>
              </div>
            </details>
            <details className="group">
              <summary className="flex cursor-pointer list-none items-center justify-between gap-2 px-6 md:px-8 py-4 text-left font-medium text-slate-200 hover:bg-slate-800/30 transition-colors">
                <span>UK Betting Slang</span>
                <span className="text-emerald-400 shrink-0 transition-transform group-open:rotate-180"><svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" /></svg></span>
              </summary>
              <div className="px-6 md:px-8 pb-4 pt-0">
                <dl className="text-slate-300 text-sm space-y-3">
                  <div><dt className="font-semibold text-emerald-400/90">Ton / Century</dt><dd>£100 stake.</dd></div>
                  <div><dt className="font-semibold text-emerald-400/90">Pony</dt><dd>£25. Score = £20. Monkey = £500. Grand / K = £1,000.</dd></div>
                  <div><dt className="font-semibold text-emerald-400/90">Drifting</dt><dd>Odds increasing (getting longer).</dd></div>
                  <div><dt className="font-semibold text-emerald-400/90">Shortening / Steaming In</dt><dd>Odds decreasing; usually sharp money.</dd></div>
                  <div><dt className="font-semibold text-emerald-400/90">Nap</dt><dd>Best bet of the day.</dd></div>
                  <div><dt className="font-semibold text-emerald-400/90">Odds On / Odds Against</dt><dd>Odds &lt;2.00 (favourite) vs &gt;2.00 (underdog).</dd></div>
                  <div><dt className="font-semibold text-emerald-400/90">Rag / Jolly</dt><dd>Outsider vs favourite.</dd></div>
                  <div><dt className="font-semibold text-emerald-400/90">Certs / Banker</dt><dd>Perceived sure thing. No such thing — red flag if claimed.</dd></div>
                </dl>
              </div>
            </details>
            <details className="group">
              <summary className="flex cursor-pointer list-none items-center justify-between gap-2 px-6 md:px-8 py-4 text-left font-medium text-slate-200 hover:bg-slate-800/30 transition-colors">
                <span>Advanced / Professional Terms</span>
                <span className="text-emerald-400 shrink-0 transition-transform group-open:rotate-180"><svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" /></svg></span>
              </summary>
              <div className="px-6 md:px-8 pb-4 pt-0">
                <dl className="text-slate-300 text-sm space-y-3">
                  <div><dt className="font-semibold text-emerald-400/90">Bookmaker Margin / Overround</dt><dd>Sum of implied probabilities exceeds 100%. e.g. 105% = 5% margin.</dd></div>
                  <div><dt className="font-semibold text-emerald-400/90">Implied vs True Probability</dt><dd>1 ÷ decimal odds = implied. True probability from your analysis. When true &gt; implied = value.</dd></div>
                  <div><dt className="font-semibold text-emerald-400/90">Expected Value (EV)</dt><dd>Average result if bet repeated. Positive EV = profitable long-term.</dd></div>
                  <div><dt className="font-semibold text-emerald-400/90">Variance / Sample Size</dt><dd>Short-term deviation from expected. Need 100+ bets, preferably 200+, for edge to show.</dd></div>
                  <div><dt className="font-semibold text-emerald-400/90">Kelly Criterion</dt><dd>Staking formula. Most use fractional Kelly (¼ or ½).</dd></div>
                  <div><dt className="font-semibold text-emerald-400/90">Line Shopping</dt><dd>Comparing odds across bookmakers. Essential for maximising edge.</dd></div>
                  <div><dt className="font-semibold text-emerald-400/90">Steam Move / RLM</dt><dd>Sudden sharp odds movement; or odds moving opposite to public %.</dd></div>
                </dl>
              </div>
            </details>
            <details className="group">
              <summary className="flex cursor-pointer list-none items-center justify-between gap-2 px-6 md:px-8 py-4 text-left font-medium text-slate-200 hover:bg-slate-800/30 transition-colors">
                <span>Risk & Bankroll Management</span>
                <span className="text-emerald-400 shrink-0 transition-transform group-open:rotate-180"><svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" /></svg></span>
              </summary>
              <div className="px-6 md:px-8 pb-4 pt-0">
                <dl className="text-slate-300 text-sm space-y-3">
                  <div><dt className="font-semibold text-emerald-400/90">Bankroll Management</dt><dd>Bet sizes relative to total funds. Standard: 1-2% per bet, max 5% on highest confidence.</dd></div>
                  <div><dt className="font-semibold text-emerald-400/90">Unit System</dt><dd>1 unit = 1% of bankroll typically.</dd></div>
                  <div><dt className="font-semibold text-emerald-400/90">Risk of Ruin</dt><dd>Probability of losing entire bankroll. Proper management keeps it near zero.</dd></div>
                </dl>
              </div>
            </details>
            <details className="group">
              <summary className="flex cursor-pointer list-none items-center justify-between gap-2 px-6 md:px-8 py-4 text-left font-medium text-slate-200 hover:bg-slate-800/30 transition-colors">
                <span>Terminology Red Flags</span>
                <span className="text-emerald-400 shrink-0 transition-transform group-open:rotate-180"><svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" /></svg></span>
              </summary>
              <div className="px-6 md:px-8 pb-4 pt-0">
                <p className="text-slate-300 text-sm mb-2">Avoid services using: Lock / Sure Thing, Guaranteed Winner, Insider Information, Fixed Match, &quot;Triple your bankroll in 30 days&quot;. All are red flags.</p>
              </div>
            </details>
            <details className="group">
              <summary className="flex cursor-pointer list-none items-center justify-between gap-2 px-6 md:px-8 py-4 text-left font-medium text-slate-200 hover:bg-slate-800/30 transition-colors">
                <span>Il Margine Preferences</span>
                <span className="text-emerald-400 shrink-0 transition-transform group-open:rotate-180"><svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" /></svg></span>
              </summary>
              <div className="px-6 md:px-8 pb-4 pt-0">
                <p className="text-slate-300 text-sm">We say: player props, edge/value, expected value, long-term profitability, variance, sample size matters, bookmaker margin, account restrictions. We don&apos;t say: locks, sure things, guaranteed winners, can&apos;t lose, insider information.</p>
              </div>
            </details>
          </div>
        </section>

        {/* FAQ */}
        <section className="bg-[#1a1d24] rounded-xl border border-slate-800 overflow-hidden mb-14">
          <h2 className="text-xl font-semibold text-emerald-400 p-6 md:p-8 pb-2">Common Questions</h2>
          <div className="divide-y divide-slate-800">
            {FAQ_ITEMS.map((item, i) => (
              <details key={i} className="group">
                <summary className="flex cursor-pointer list-none items-center justify-between gap-2 px-6 md:px-8 py-4 text-left font-medium text-slate-200 hover:bg-slate-800/30 transition-colors">
                  <span>{item.q}</span>
                  <span className="text-emerald-400 shrink-0 transition-transform group-open:rotate-180">
                    <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" /></svg>
                  </span>
                </summary>
                <div className="px-6 md:px-8 pb-4 pt-0">
                  <p className="text-slate-400 text-sm leading-relaxed">
                    {item.a}
                    {"linkToFaq" in item && item.linkToFaq && (
                      <> See our <Link href="/faq" className="text-emerald-400 hover:text-emerald-300 underline">FAQ page</Link> for detailed guidance on managing restrictions.</>
                    )}
                  </p>
                </div>
              </details>
            ))}
          </div>
        </section>

        {/* Affiliate Disclosure - amber */}
        <section className="bg-amber-500/10 border border-amber-500/30 rounded-xl p-6 md:p-8 mb-14">
          <h2 className="text-lg font-semibold text-amber-400/95 mb-3">Transparency Statement</h2>
          <p className="text-slate-300 text-sm leading-relaxed mb-3">We&apos;re in the process of establishing affiliate partnerships with the bookmakers recommended on this page.</p>
          <p className="text-slate-300 text-sm leading-relaxed mb-3"><strong className="text-slate-200">What this means:</strong> If you click through and open an account, we may receive a commission. This costs you nothing extra. Welcome offers are identical whether you use our links or go direct.</p>
          <p className="text-slate-300 text-sm leading-relaxed">These bookmakers were selected based on our testing and professional use, not commercial arrangements. We only partner with bookmakers we genuinely use and recommend. If our assessment changes, we&apos;ll update this page accordingly.</p>
        </section>

        {/* Responsible Gambling */}
        <section className="mb-10">
          <h2 className="text-xl font-semibold text-emerald-400 mb-4">Betting Responsibly</h2>
          <p className="text-slate-300 text-sm leading-relaxed mb-3">Opening multiple bookmaker accounts is standard for professional bettors, but it requires discipline.</p>
          <p className="text-slate-300 text-sm leading-relaxed mb-3"><strong className="text-slate-200">Guidelines:</strong> Only deposit money you can afford to lose. Set loss limits across all accounts. Never chase losses by opening more accounts. Track total exposure. Be aware that more accounts = more temptation.</p>
          <p className="text-slate-300 text-sm leading-relaxed mb-3"><strong className="text-slate-200">If you&apos;re struggling:</strong> UK: 0808 8020 133 (National Gambling Helpline). BeGambleAware: <a href="https://www.begambleaware.org" target="_blank" rel="noopener noreferrer" className="text-emerald-400 hover:text-emerald-300 underline">begambleaware.org</a>. GamCare: <a href="https://www.gamcare.org.uk" target="_blank" rel="noopener noreferrer" className="text-emerald-400 hover:text-emerald-300 underline">gamcare.org.uk</a>. Self-exclusion: GAMSTOP covers all UK-licensed operators.</p>
          <p className="text-slate-400 text-sm">18+ only. Gamble responsibly.</p>
        </section>
      </div>
      <Footer />
    </div>
  );
}
