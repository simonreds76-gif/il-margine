import Link from "next/link";
import Footer from "@/components/Footer";
import BookmakerLogo from "@/components/BookmakerLogo";
import PageHomeLink from "@/components/PageHomeLink";
import marginIndexJson from "../../../data/bookmakers/margin-index.json";

type MarginOperator = {
  rank: number;
  name: string;
  raw_overround_pct: number;
  normalized_hold_pct: number;
  samples: number;
  market_families: string[];
  coverage_pct: number;
};

type MarginSegmentOperator = Pick<
  MarginOperator,
  "rank" | "name" | "raw_overround_pct" | "normalized_hold_pct" | "samples"
>;

type MarginSegment = {
  sport: string;
  sport_slug: string;
  market_family: string;
  events: number;
  observations: number;
  status: string;
  operators: MarginSegmentOperator[];
};

type BookmakerMarginIndex = {
  generated_at: string | null;
  status: string;
  capture_mode?: string;
  methodology: { minimum_publish_gate: string };
  summary: {
    operators: number;
    diagnostic_operators?: number;
    sports?: string[];
    events: number;
    market_families: string[];
    observations: number;
  };
  synthetic_best_price: {
    raw_overround_pct: number | null;
    normalized_hold_pct: number | null;
    samples: number;
  };
  operators: MarginOperator[];
  segments?: MarginSegment[];
};

const MARGIN_INDEX = marginIndexJson as BookmakerMarginIndex;

function marginPct(value: number | null) {
  return value === null ? "-" : `${value >= 0 ? "+" : ""}${value.toFixed(2)}%`;
}

function capturedLabel(value: string | null) {
  if (!value) return "No verified capture yet";
  return new Intl.DateTimeFormat("en-GB", {
    day: "numeric",
    month: "short",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    timeZone: "UTC",
    timeZoneName: "short",
  }).format(new Date(value));
}

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
    stars: "⭐⭐⭐½",
    rating: "3.5/5",
    propsScore: "8/10",
    tennisScore: "7/10",
    welcomeOffer: "Bet £10 Get £40 in Bonuses",
    welcomeTerms: "Min odds 2.00, various bonus types, T&Cs apply",
    strengths: [
      "Still offers solid player-props depth across the major leagues",
      "Historically useful tennis handicap and totals book on ATP events",
      "Can still show competitive prices when you line-shop properly",
      "Reasonable ATP 250/500 coverage",
      "Established operator with a familiar, stable platform",
    ],
    weaknesses: [
      "No longer one of the first books we'd build around",
      "Prices are not consistently strong enough to justify blind loyalty",
      "Bet builder functionality is limited",
      "Live betting interface feels dated next to newer books",
    ],
    usageTips: "We would treat BetVictor as a comparison account now rather than a core one. For props: it is still worth checking because it can occasionally hang a strong number, but we would not rely on it as heavily as the better books on the page. For tennis: it remains more interesting on ATP events than on lower tiers, and it can still throw up a playable handicap or totals price from time to time. Useful to keep open, but not one we’d prioritise first.",
    bestFor: "Secondary all-rounder, still worth checking",
    offerUrl: "#",
  },
  {
    id: "william-hill",
    name: "William Hill",
    stars: "⭐⭐⭐⭐",
    rating: "4/5",
    propsScore: "8/10",
    tennisScore: "7/10",
    welcomeOffer: "Bet £10 Get £40 in Free Bets",
    welcomeTerms: "New UK customers, promo code G40. Deposit & place £10 cash single bet (min odds 1/2) on sportsbook (excl. Virtuals). Get £40 in Free Bets (4x£10), valid 7 days, must use in full (£10 each). Not valid via PayPal, Neosurf, Paysafe, Apple Pay, NETELLER, Skrill, ecoPayz, Kalibra/Postpay or WH PLUS Card. One per customer. Full T&Cs apply.",
    strengths: [
      "Must-have in our rotation — we use it regularly for props and tennis",
      "Stake limits hold up better than many UK books we've tested",
      "Comprehensive player props across Premier League, Championship, major European leagues",
      "Solid tennis markets on ATP 250+; game handicaps and totals competently priced",
      "Reliable platform, withdrawal processing and liquidity",
      "Good bet builder; correlation mispricing appears on lower-profile matches",
      "Established operator — one of the books we rely on most",
    ],
    weaknesses: [
      "Props margins 10-13% (in line with market)",
      "Tennis coverage drops off below ATP 250",
      "Platform can feel dated next to newer apps",
    ],
    usageTips: "William Hill is a must-have. We use it regularly for both player props and tennis. Limits have held up better than at several other UK books in our experience — we still get meaningful stakes on props and tennis months in. For props: strong coverage across Premier League, Championship, La Liga, Bundesliga, Serie A. Odds are competitive often enough that we always check them when line shopping. Bet builder markets are decent and correlation mispricing does appear, especially on lower-profile matches. For tennis: solid for ATP 250 and above; game handicaps and totals are competently priced and often within a few percent of sharp closing lines. Withdrawal processing is reliable. Open this account early and keep it in your core set. One of the books we'd replace last.",
    bestFor: "Must-have — we use it often, limits hold up",
    offerUrl: "/api/go/william-hill",
  },
  {
    id: "bwin",
    name: "Bwin",
    stars: "⭐⭐⭐⭐",
    rating: "4/5",
    propsScore: "8/10",
    tennisScore: "7/10",
    welcomeOffer: "Bet £5 Get £20 in Free Bets",
    welcomeTerms: "Min £5 bet on sports at odds 1/2+. 4×£5 free bets, valid 7 days, stake not returned. T&Cs apply.",
    strengths: [
      "Comprehensive player props across all major leagues",
      "Part of Entain (shares group with Coral, Ladbrokes – separate account)",
      "Solid odds quality on props markets",
      "Good bet builder functionality",
      "Modern online platform",
      "Reasonable tennis coverage on major events",
    ],
    weaknesses: [
      "Same pricing engine as other Entain brands (no arbitrage between Bwin, Coral, Ladbrokes)",
      "Tennis markets thin out below ATP 250 level",
      "Props margins 10-13%",
      "Stake limits tighten quickly on profitable accounts",
    ],
    usageTips: "Bwin is part of the Entain group alongside Coral and Ladbrokes. You can hold accounts with all three simultaneously. Each is independently managed despite shared pricing, so having Bwin plus Coral and Ladbrokes extends your access window to Entain's competitive odds. For props: Coverage is excellent across Premier League, Championship, and major European leagues. Bet builder is solid. For tennis: Adequate for ATP 250+. Worth pairing with Coral and Ladbrokes for maximum Entain access.",
    bestFor: "Pair with Coral and Ladbrokes for extended access",
    offerUrl: "/api/go/bwin",
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
    propsScore: "8/10",
    tennisScore: "7/10",
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
    bestFor: "Player props & tennis, independent pricing for line shopping",
    offerUrl: "#",
  },
  {
    id: "betway",
    name: "Betway",
    stars: "⭐⭐⭐⭐",
    rating: "4/5",
    propsScore: "8/10",
    tennisScore: "6/10",
    welcomeOffer: "Bet £10 Get £40 in Free Bets",
    welcomeTerms: "New UK customers. Min £10 qualifying bet at odds 2.0+. Four £10 free bet tokens on settlement, 7-day expiry. Debit card deposits only. Token restrictions apply.",
    strengths: [
      "Established UK sportsbook with real depth on mainstream football markets",
      "Props can be genuinely competitive and sometimes top-of-market on selected football lines",
      "Cash Out is available across a wide range of pre-match and in-play bets",
      "Strong mobile-first product and plenty of in-play focus",
      "Good mainstream football coverage and promotional visibility",
      "Tennis is covered well enough on ATP/WTA headline events",
      "Useful extra line-shopping account even if you already have the core books",
    ],
    weaknesses: [
      "The £10 → £40 welcome offer is less flexible than it first looks once you read the token rules",
      "Free-bet tokens are tied to bet builders/accas with extra conditions",
      "Not one of our first books for lower-tier tennis or Challenger work",
      "Prices still need line-shopping rather than blind trust",
      "Like most recreational books, it is not built to be a forever home for winning accounts",
    ],
    usageTips: "Betway is better than the first draft made it sound. For props: it absolutely deserves to be checked, because on selected football markets the price can be right there with the best of the softer books and sometimes even top the screen. That alone makes it worth having in the rotation. For tennis: we still see it as a mainstream-events book rather than a specialist one, so we would use it more for ATP/WTA headline matches than for deeper lower-tier work. Overall, this is a strong football/mobile sportsbook with enough pricing quality to matter. The one thing to keep in proportion is the welcome offer: the headline is good, but the token rules are tighter than the cleaner sportsbook offers elsewhere.",
    bestFor: "Football props, mobile betting, worthwhile line shopping",
    offerUrl: "/api/go/betway",
  },
];

const COMPARISON_ROWS = [
  { name: "Midnite", props: "8/10", tennis: "7/10", offer: "£20 free bets", bestFor: "Modern platform, major league props" },
  { name: "BetVictor", props: "8/10", tennis: "7/10", offer: "£40 bonuses", bestFor: "Secondary all-rounder, still worth checking" },
  { name: "William Hill", props: "8/10", tennis: "7/10", offer: "£40 free bets", bestFor: "Must-have — we use it often, limits hold up" },
  { name: "Bwin", props: "8/10", tennis: "7/10", offer: "£5 → £20 free bets", bestFor: "Pair with Coral and Ladbrokes for extended access" },
  { name: "Coral", props: "8/10", tennis: "7/10", offer: "£30 free bets", bestFor: "Pair with Ladbrokes for extended access" },
  { name: "Ladbrokes", props: "8/10", tennis: "7/10", offer: "£20 free bets", bestFor: "Pair with Coral for extended access" },
  { name: "BetMGM", props: "8/10", tennis: "7/10", offer: "£40 free bets", bestFor: "Player props & tennis, independent pricing for line shopping" },
  { name: "Betway", props: "8/10", tennis: "6/10", offer: "£40 free bets", bestFor: "Football props, mobile betting, worthwhile line shopping" },
];

function BookmakerCard({ bm }: { bm: (typeof BOOKMAKERS)[0] }) {
  return (
    <article className="bg-[#1a1d24] rounded-xl border border-slate-800 overflow-hidden">
      {/* Conversion block: always visible */}
      <div className="p-5 md:p-6">
        <div className="flex flex-wrap items-center gap-3 mb-3">
          <BookmakerLogo bookmaker={{ id: 0, name: bm.name, short_name: bm.name, affiliate_link: bm.offerUrl !== "#" ? bm.offerUrl : null, active: true }} size="md" />
          <div>
            <h3 className="font-semibold text-slate-100">{bm.name}</h3>
            <span className="text-xs text-slate-500">{bm.stars} · Props {bm.propsScore} · Tennis {bm.tennisScore}</span>
          </div>
          <span className="sm:ml-auto text-[10px] font-medium px-2 py-0.5 rounded bg-slate-800 text-slate-400 shrink-0 max-w-full sm:max-w-[200px] truncate" title={bm.bestFor}>{bm.bestFor}</span>
        </div>
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 pt-3 border-t border-slate-800">
          <div className="flex items-baseline gap-2 flex-wrap">
            <span className="text-[11px] font-semibold uppercase tracking-wider text-emerald-400">New customers</span>
            <span className="text-slate-500">·</span>
            <span className="text-sm font-semibold text-slate-100">{bm.welcomeOffer}</span>
          </div>
          <a
            href={bm.offerUrl}
            target={bm.offerUrl !== "#" ? "_blank" : undefined}
            rel={bm.offerUrl !== "#" ? "noopener noreferrer nofollow" : undefined}
            className="inline-block w-full sm:w-auto text-center bg-emerald-500 hover:bg-emerald-400 text-white text-sm font-semibold px-5 py-2.5 rounded-lg transition-colors shrink-0"
          >
            Claim {bm.name} Offer →
          </a>
        </div>
      </div>
      {/* Expandable details */}
      <details className="group border-t border-slate-800">
        <summary className="flex cursor-pointer list-none items-center justify-between gap-2 px-5 md:px-6 py-3.5 text-sm rounded-b-xl hover:bg-slate-800/50 transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-emerald-400/50">
          <span className="text-slate-300 font-medium">Read full review — click to expand</span>
          <span className="text-emerald-400 shrink-0 transition-transform group-open:rotate-180" aria-hidden>
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" /></svg>
          </span>
        </summary>
        <div className="px-5 md:px-6 pb-5 pt-0 space-y-4">
          <div className="rounded-lg border border-slate-700/80 bg-slate-800/40 px-3 py-2">
            <p className="text-[11px] text-slate-500">{bm.welcomeTerms}</p>
          </div>
          <div className="grid sm:grid-cols-2 gap-4">
            <div>
              <p className="text-[11px] font-semibold uppercase tracking-wider text-emerald-400 mb-1.5">Strengths</p>
              <ul className="list-disc pl-4 text-slate-400 text-sm space-y-0.5">
                {bm.strengths.map((s, i) => <li key={i}>{s}</li>)}
              </ul>
            </div>
            <div>
              <p className="text-[11px] font-semibold uppercase tracking-wider text-slate-500 mb-1.5">Weaknesses</p>
              <ul className="list-disc pl-4 text-slate-400 text-sm space-y-0.5">
                {bm.weaknesses.map((w, i) => <li key={i}>{w}</li>)}
              </ul>
            </div>
          </div>
          <p className="text-slate-400 text-sm leading-relaxed">{bm.usageTips}</p>
        </div>
      </details>
    </article>
  );
}

const FAQ_ITEMS = [
  { q: "Should I open all eight accounts at once?", a: "Yes. Welcome offers alone provide £250+ value. More importantly, having eight accounts active extends your operational window to 18-24 months before restrictions become severe across all platforms. Open them all, claim all offers, use them strategically." },
  { q: "What if odds are better elsewhere?", a: "Always take best price. Line shop across all eight before placing any bet. Over 100 bets, even 2-3% better average odds compounds significantly. Never settle for worse odds out of loyalty or convenience." },
  { q: "Do affiliate links affect your recommendations?", a: "No. These bookmakers were selected through months of real-money testing before any affiliate discussions began. We sought partnerships with books we already used, not vice versa. If a bookmaker deteriorates in quality or changes practices, we'll remove them regardless of commercial arrangements." },
  { q: "Are welcome bonuses worth it?", a: "Absolutely. Combined, these eight offer £250+ in bonuses. Even accounting for rollover requirements, expected value is positive. Claim all of them. Use them on +EV opportunities where possible, or on lower-variance markets if rollover requirements demand it." },
  { q: "Can I use Ladbrokes, Coral, and Bwin together?", a: "Yes, and you should. They're part of the same group (Entain) and share identical pricing, but account management is separate. Opening all three extends your access window to Entain odds significantly. This trio is essential if you're serious about line shopping." },
  { q: "What happens when I get restricted?", a: "Stake limits reduce gradually, eventually hitting £5-20 maximum. The account remains active but becomes operationally useless for serious betting. This is inevitable for winning accounts. Plan for it by having multiple accounts active. When one restricts, continue with others.", linkToFaq: true },
];

export default function BookmakersPage() {
  const publishableSegments = (MARGIN_INDEX.segments ?? []).filter(
    (segment) => segment.status === "PASS" && segment.operators.length >= 3,
  );
  const hasOverallRanking = MARGIN_INDEX.operators.length >= 4;
  const publishable =
    MARGIN_INDEX.status === "PASS" &&
    (hasOverallRanking || publishableSegments.length > 0);

  return (
    <div className="min-h-screen bg-[#0f1117] text-slate-100">
      <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 pt-6 pb-8 md:pb-12">
        <PageHomeLink className="mb-8" />

        {/* Hero */}
        <section className="mb-10 md:mb-12">
          <span className="text-xs font-mono text-emerald-400 mb-3 block tracking-wider">BOOKMAKERS</span>
          <h1 className="text-3xl sm:text-4xl font-semibold text-slate-100 mb-2">
            £250+ in Welcome Offers
          </h1>
          <p className="text-lg text-slate-300 max-w-2xl mb-4">
            Eight bookmakers. One strategy. Field tested for props and tennis. We bet here and we&apos;re honest about restrictions.
          </p>
          <p className="text-slate-400 text-sm mb-4 max-w-2xl">
            Independent reviews based on real money testing. Affiliate links are used where we have partnerships. Recommendations are unchanged regardless.
          </p>
          <p className="text-slate-500 text-sm max-w-3xl">
            18+ only. Gamble responsibly. <a href="https://www.begambleaware.org" target="_blank" rel="noopener noreferrer" className="text-emerald-400/80 hover:text-emerald-300 underline">begambleaware.org</a>
          </p>
        </section>

        <section className="mb-10 overflow-hidden rounded-2xl border border-cyan-400/20 bg-[radial-gradient(circle_at_top_right,rgba(34,211,238,0.10),transparent_42%),linear-gradient(145deg,rgba(15,23,42,0.96),rgba(2,6,23,0.96))] shadow-[0_24px_70px_rgba(2,6,23,0.35)]">
          <div className="border-b border-slate-800/80 px-5 py-5 sm:px-7">
            <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
              <div>
                <span className="text-[11px] font-semibold uppercase tracking-[0.2em] text-cyan-300">Price intelligence</span>
                <h2 className="mt-2 text-2xl font-semibold text-white">UK bookmaker margin index</h2>
                <p className="mt-2 max-w-3xl text-sm leading-6 text-slate-300">
                  A dated, like-for-like snapshot of the margin built into complete football and tennis markets. Lower hold is better for the bettor.
                </p>
              </div>
              <div className="shrink-0 rounded-full border border-slate-700 bg-slate-950/70 px-3 py-1.5 text-xs text-slate-400">
                Sampled {capturedLabel(MARGIN_INDEX.generated_at)}
              </div>
            </div>
          </div>

          {publishable ? (
            <div>
              <div className="grid gap-px bg-slate-800/80 sm:grid-cols-4">
                {[
                  ["Operators", String(MARGIN_INDEX.summary.diagnostic_operators ?? MARGIN_INDEX.summary.operators)],
                  ["Sports", String(MARGIN_INDEX.summary.sports?.length ?? 0)],
                  ["Events", String(MARGIN_INDEX.summary.events)],
                  ["Market families", String(MARGIN_INDEX.summary.market_families.length)],
                ].map(([label, value]) => (
                  <div key={label} className="bg-slate-950/80 px-5 py-4">
                    <p className="text-[10px] font-semibold uppercase tracking-[0.16em] text-slate-500">{label}</p>
                    <p className="mt-1 font-mono text-xl font-semibold tabular-nums text-white">{value}</p>
                  </div>
                ))}
              </div>

              {publishableSegments.length > 0 && (
                <div className="border-t border-slate-800/80 px-5 py-6 sm:px-7">
                  <div className="mb-4">
                    <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-cyan-300">Sport and market breakdown</p>
                    <p className="mt-1 text-sm text-slate-400">
                      Each table is ranked only against operators quoting the same complete market in this snapshot.
                    </p>
                  </div>
                  <div className="grid gap-4 lg:grid-cols-2">
                    {publishableSegments.map((segment) => (
                      <article key={`${segment.sport_slug}-${segment.market_family}`} className="overflow-hidden rounded-xl border border-slate-800 bg-slate-950/45">
                        <div className="flex items-start justify-between gap-3 border-b border-slate-800 px-4 py-3">
                          <div>
                            <p className="text-[10px] font-semibold uppercase tracking-[0.16em] text-slate-500">{segment.sport}</p>
                            <h3 className="mt-1 font-semibold text-slate-100">{segment.market_family}</h3>
                          </div>
                          <span className="rounded-full border border-slate-700 px-2.5 py-1 font-mono text-[10px] text-slate-400">
                            n={segment.observations}
                          </span>
                        </div>
                        <div className="divide-y divide-slate-800/80">
                          {segment.operators.slice(0, 6).map((operator) => (
                            <div key={operator.name} className="grid grid-cols-[2rem_minmax(0,1fr)_auto_auto] items-center gap-3 px-4 py-3 text-sm">
                              <span className="font-mono text-xs text-slate-600">#{operator.rank}</span>
                              <span className="truncate font-medium text-slate-200">{operator.name}</span>
                              <span className="font-mono tabular-nums text-cyan-300">{marginPct(operator.normalized_hold_pct)}</span>
                              <span className="font-mono text-xs tabular-nums text-slate-500">n={operator.samples}</span>
                            </div>
                          ))}
                        </div>
                      </article>
                    ))}
                  </div>
                </div>
              )}

              {hasOverallRanking && <div className="overflow-x-auto">
                <table className="min-w-[780px] w-full text-left text-sm">
                  <thead className="border-b border-slate-800 bg-slate-950/55 text-[10px] uppercase tracking-[0.14em] text-slate-500">
                    <tr>
                      <th className="px-5 py-3 font-semibold">Rank</th>
                      <th className="px-5 py-3 font-semibold">Operator</th>
                      <th className="px-5 py-3 font-semibold">Normalized hold</th>
                      <th className="px-5 py-3 font-semibold">Raw overround</th>
                      <th className="px-5 py-3 font-semibold">Markets</th>
                      <th className="px-5 py-3 font-semibold">Samples</th>
                      <th className="px-5 py-3 font-semibold">Coverage</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-800/80">
                    {MARGIN_INDEX.operators.map((operator) => (
                      <tr key={operator.name} className="bg-slate-950/20 transition-colors hover:bg-cyan-400/[0.04]">
                        <td className="px-5 py-4 font-mono text-slate-500">#{operator.rank}</td>
                        <td className="px-5 py-4">
                          <div className="flex items-center gap-3">
                            <BookmakerLogo bookmaker={{ id: 0, name: operator.name, short_name: operator.name, affiliate_link: null, active: true }} size="sm" />
                            <span className="font-semibold text-slate-100">{operator.name}</span>
                          </div>
                        </td>
                        <td className="px-5 py-4 font-mono font-semibold tabular-nums text-cyan-300">{marginPct(operator.normalized_hold_pct)}</td>
                        <td className="px-5 py-4 font-mono tabular-nums text-slate-300">{marginPct(operator.raw_overround_pct)}</td>
                        <td className="px-5 py-4 text-xs text-slate-400">{operator.market_families.join(" · ")}</td>
                        <td className="px-5 py-4 font-mono tabular-nums text-slate-300">{operator.samples}</td>
                        <td className="px-5 py-4 font-mono tabular-nums text-slate-300">{operator.coverage_pct.toFixed(1)}%</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>}

              <div className="grid gap-4 border-t border-slate-800/80 px-5 py-5 sm:grid-cols-[minmax(0,1fr)_auto] sm:px-7">
                <div>
                  <p className="text-xs font-semibold uppercase tracking-[0.16em] text-emerald-300">Best-price market</p>
                  <p className="mt-1 text-sm leading-6 text-slate-400">
                    Synthetic line-shopping benchmark built from the best price for each outcome across operators. It is not one bookmaker&apos;s margin.
                  </p>
                </div>
                <div className="flex gap-6 rounded-xl border border-emerald-500/20 bg-emerald-500/[0.06] px-5 py-3">
                  <div>
                    <p className="text-[10px] uppercase tracking-[0.14em] text-slate-500">Normalized</p>
                    <p className="mt-1 font-mono text-lg font-semibold text-emerald-300">{marginPct(MARGIN_INDEX.synthetic_best_price.normalized_hold_pct)}</p>
                  </div>
                  <div>
                    <p className="text-[10px] uppercase tracking-[0.14em] text-slate-500">Samples</p>
                    <p className="mt-1 font-mono text-lg font-semibold text-white">{MARGIN_INDEX.synthetic_best_price.samples}</p>
                  </div>
                </div>
              </div>
            </div>
          ) : (
            <div className="px-5 py-6 sm:px-7">
              <div className="rounded-xl border border-amber-400/20 bg-amber-400/[0.06] px-4 py-4">
                <p className="font-semibold text-amber-200">Awaiting a verified comparison sample</p>
                <p className="mt-2 text-sm leading-6 text-slate-300">
                  No ranking is shown until the capture contains at least four qualified operators, three market families and twenty comparable operator/event/market observations.
                </p>
                <p className="mt-2 text-xs text-slate-500">
                  Current diagnostic coverage: {MARGIN_INDEX.summary.operators} qualified operators · {MARGIN_INDEX.summary.market_families.length} market families · {MARGIN_INDEX.summary.observations} observations.
                </p>
              </div>
            </div>
          )}

          <div className="border-t border-slate-800/80 bg-slate-950/45 px-5 py-4 text-xs leading-5 text-slate-500 sm:px-7">
            Manual one-off snapshot, not a live or weekly feed. Raw overround is Σ(1/decimal odds) − 1. Normalized hold is 1 − 1/Σ(1/decimal odds). Alternate lines are collapsed before operators are compared, so books with more lines do not receive extra weight.
          </div>
        </section>

        {/* Quick-offer strip: scan & convert */}
        <section className="mb-10">
          <h2 className="text-sm font-semibold text-slate-400 mb-4">Offers at a glance</h2>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
            {BOOKMAKERS.map((bm) => (
              <div key={bm.id} className="rounded-lg border border-slate-700/80 bg-slate-800/40 p-3 flex flex-col gap-2">
                <div className="flex items-center gap-2">
                  <BookmakerLogo bookmaker={{ id: 0, name: bm.name, short_name: bm.name, affiliate_link: bm.offerUrl !== "#" ? bm.offerUrl : null, active: true }} size="sm" />
                  <span className="font-medium text-slate-200 text-sm">{bm.name}</span>
                </div>
                <p className="text-xs font-medium text-slate-100">{bm.welcomeOffer}</p>
                <p className="text-[10px] text-slate-500 line-clamp-1">{bm.bestFor}</p>
                <a
                  href={bm.offerUrl}
                  target={bm.offerUrl !== "#" ? "_blank" : undefined}
                  rel={bm.offerUrl !== "#" ? "noopener noreferrer nofollow" : undefined}
                  className="mt-auto text-xs font-semibold text-emerald-400 hover:text-emerald-300"
                >
                  {bm.offerUrl !== "#" ? "Claim offer →" : "View offer"}
                </a>
              </div>
            ))}
          </div>
        </section>

        {/* Full reviews */}
        <section className="mb-12">
          <h2 className="text-sm font-semibold text-slate-400 mb-4">Full reviews</h2>
          <p className="text-slate-500 text-sm mb-6">Click &quot;Read full review&quot; on each card for strengths, weaknesses, terms and how we use each book.</p>

          {/* Must-have: William Hill first */}
          <div className="mb-6">
            <p className="text-xs font-semibold uppercase tracking-wider text-emerald-400/80 mb-3">Must-have — we use it often</p>
            <div className="space-y-6">
              {BOOKMAKERS.filter((bm) => bm.id === "william-hill").map((bm) => (
                <BookmakerCard key={bm.id} bm={bm} />
              ))}
            </div>
          </div>

          {/* Entain trio */}
          <div className="mb-6">
            <p className="text-xs font-semibold uppercase tracking-wider text-emerald-400/80 mb-3">The Entain trio (open all three)</p>
            <div className="space-y-6">
              {BOOKMAKERS.filter((bm) => ["bwin", "coral", "ladbrokes"].includes(bm.id)).map((bm) => (
                <BookmakerCard key={bm.id} bm={bm} />
              ))}
            </div>
          </div>

          {/* Rest */}
          <p className="text-xs font-semibold uppercase tracking-wider text-slate-500 mb-3">Other operators</p>
          <div className="space-y-6">
            {BOOKMAKERS.filter((bm) => !["bwin", "coral", "ladbrokes", "william-hill"].includes(bm.id)).map((bm) => (
              <BookmakerCard key={bm.id} bm={bm} />
            ))}
          </div>
        </section>

        {/* Key Concepts - 5 accordions */}
        <section className="mb-10">
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
                  <p><strong className="text-slate-100">Efficient Markets:</strong> Premier League match odds are the clearest example. Teams of traders, real-time monitoring and heavy liquidity make those lines hard to beat consistently.</p>
                  <p><strong className="text-slate-100">Softer Markets:</strong> Player props are the clearest soft market for us: template pricing, lighter oversight and wider margins. Bet builders can also misprice correlation.</p>
                  <p><strong className="text-slate-100">Tennis sits in the middle.</strong> It is generally more efficient than props, but selected ATP and Challenger spots, especially in handicaps and totals, can still be worth betting when our model prices them better than the market.</p>
                  <p>Our approach: we bet wherever we identify genuine edge. Props and selective tennis prices are the main focus, but for different reasons. See <Link href="/the-edge" className="text-emerald-400 hover:text-emerald-300 underline">The Edge</Link> for methodology.</p>
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
                <div className="text-slate-300 text-sm leading-relaxed space-y-4">
                  <p>Bookmakers flag accounts that only take value. Blending typical punters&apos; behaviour can extend lifespan:</p>
                  <ul className="list-disc pl-5 space-y-1">
                    <li><strong className="text-slate-100">Mix in recreational bets:</strong> For every 3–4 value bets, place one bet at standard odds (e.g. match winner, favourite). Don&apos;t only bet when you spot edge.</li>
                    <li><strong className="text-slate-100">Stick to popular markets:</strong> Premier League, Champions League, major events. Avoid obscure leagues unless you bet there regularly anyway.</li>
                    <li><strong className="text-slate-100">Bet at normal times:</strong> Weekends, before kick-off. Avoid only betting during sharp odds moves.</li>
                    <li><strong className="text-slate-100">Vary stakes:</strong> Use rounded amounts (10, 20, 25). Avoid odd decimals or constant max stakes.</li>
                    <li><strong className="text-slate-100">Use bet builders and accas occasionally:</strong> Popular with casual punters. Small acca or correlated builder now and then helps.</li>
                    <li><strong className="text-slate-100">Occasional in-play:</strong> Small random in-play bets mirror typical betting habits.</li>
                  </ul>
                  <p>Also: Deposit regularly. Delay withdrawals 2–3 weeks. Avoid patterns (same time, same league only). These tactics extend lifespan by 20–40%, not indefinitely. Restrictions are inevitable; plan rollover to new accounts.</p>
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
                  <p>Most bookmakers use template pricing for player props, and far more generic automation on parts of the tennis board than the average bettor realises. Example: bookmaker pulls a player&apos;s last 10 matches, calculates an average, applies margin, and pushes out a number. What those shortcuts miss: opponent-specific factors, tactical matchups, referee tendencies, venue context, surface effects, and scheduling pressure. When your analysis captures those things and the template doesn&apos;t, price and true probability drift apart. That&apos;s where we operate. See <Link href="/the-edge" className="text-emerald-400 hover:text-emerald-300 underline">The Edge</Link>.</p>
                </div>
              </div>
            </details>
          </div>
        </section>

        {/* Comparison Table */}
        <section className="mb-10">
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
        <section className="bg-[#1a1d24] rounded-xl border border-slate-800 p-6 md:p-8 mb-10">
          <h2 className="text-xl font-semibold text-emerald-400 mb-4">Recommended Approach</h2>
          <div className="text-slate-300 text-sm leading-relaxed space-y-4">
            <p><strong className="text-slate-100">Account opening sequence:</strong></p>
            <ol className="list-decimal pl-6 space-y-2">
              <li>Open all eight accounts — welcome offers alone provide £250+ value</li>
              <li>Prioritise by market focus: Props primary: BetVictor, Midnite, William Hill, Coral, Ladbrokes, Bwin. Tennis primary: BetVictor, William Hill. Mixed: all eight for line shopping</li>
              <li>Always open Coral AND Ladbrokes — never one without the other</li>
              <li>Use BetMGM for line shopping — independent pricing often differs from other UK operators</li>
            </ol>
            <p><strong className="text-slate-100">Line shopping workflow:</strong> Before placing any bet: check odds across all eight, identify best price, place at bookmaker offering highest odds, track which books consistently offer best price, adjust priority accordingly.</p>
            <p>Over time, accounts will restrict at different rates. By opening all eight, you extend total operational window to 18-24 months before severe restrictions across all accounts. See <Link href="/track-record" className="text-emerald-400 hover:text-emerald-300 underline">Track Record</Link> for our performance context.</p>
          </div>
        </section>

        {/* Betting Glossary - 8 categories */}
        <section className="mb-10">
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
        <section className="bg-[#1a1d24] rounded-xl border border-slate-800 overflow-hidden mb-10">
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
        <section className="bg-amber-500/10 border border-amber-500/30 rounded-xl p-6 md:p-8 mb-10">
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

