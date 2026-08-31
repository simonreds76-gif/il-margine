import Link from "next/link";
import Footer from "@/components/Footer";
import BookmakerLogo from "@/components/BookmakerLogo";
import MarginExplorer from "@/components/bookmakers/MarginExplorer";
import PageHomeLink from "@/components/PageHomeLink";
import {
  NOT_MEASURED_MARKETS,
  type BookmakerMarginIndex,
} from "@/lib/bookmakers/margin-index";
import marginIndexJson from "../../../data/bookmakers/margin-index.json";

const MARGIN_INDEX = marginIndexJson as BookmakerMarginIndex;

type BookmakerReview = {
  id: string;
  name: string;
  stars: string;
  rating: string;
  propsScore: string;
  tennisScore: string;
  strengths: string[];
  weaknesses: string[];
  usageTips: string;
  bestFor: string;
  welcomeOffer?: string;
  welcomeTerms?: string;
  offerUrl?: string;
};

const PARTNER_IDS = new Set(["william-hill", "bwin", "betway"]);

function isPartner(
  bookmaker: BookmakerReview,
): bookmaker is BookmakerReview & Required<Pick<BookmakerReview, "welcomeOffer" | "welcomeTerms" | "offerUrl">> {
  return (
    PARTNER_IDS.has(bookmaker.id) &&
    Boolean(bookmaker.welcomeOffer && bookmaker.welcomeTerms && bookmaker.offerUrl)
  );
}

const BOOKMAKERS: BookmakerReview[] = [
  {
    id: "midnite",
    name: "Midnite",
    stars: "⭐⭐⭐⭐½",
    rating: "4.5/5",
    propsScore: "8/10",
    tennisScore: "7/10",
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
  },
  {
    id: "betvictor",
    name: "BetVictor",
    stars: "⭐⭐⭐½",
    rating: "3.5/5",
    propsScore: "8/10",
    tennisScore: "7/10",
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
  },
  {
    id: "ladbrokes",
    name: "Ladbrokes",
    stars: "⭐⭐⭐⭐",
    rating: "4/5",
    propsScore: "8/10",
    tennisScore: "7/10",
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
  },
  {
    id: "betmgm",
    name: "BetMGM",
    stars: "⭐⭐⭐⭐",
    rating: "4/5",
    propsScore: "8/10",
    tennisScore: "7/10",
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
  { name: "Midnite", props: "8/10", tennis: "7/10", offer: "Editorial only", bestFor: "Modern platform, major league props" },
  { name: "BetVictor", props: "8/10", tennis: "7/10", offer: "Editorial only", bestFor: "Secondary all-rounder, still worth checking" },
  { name: "William Hill", props: "8/10", tennis: "7/10", offer: "£40 free bets", bestFor: "Must-have — we use it often, limits hold up" },
  { name: "Bwin", props: "8/10", tennis: "7/10", offer: "£5 → £20 free bets", bestFor: "Pair with Coral and Ladbrokes for extended access" },
  { name: "Coral", props: "8/10", tennis: "7/10", offer: "Editorial only", bestFor: "Pair with Ladbrokes for extended access" },
  { name: "Ladbrokes", props: "8/10", tennis: "7/10", offer: "Editorial only", bestFor: "Pair with Coral for extended access" },
  { name: "BetMGM", props: "8/10", tennis: "7/10", offer: "Editorial only", bestFor: "Player props & tennis, independent pricing for line shopping" },
  { name: "Betway", props: "8/10", tennis: "6/10", offer: "£40 free bets", bestFor: "Football props, mobile betting, worthwhile line shopping" },
];

function BookmakerCard({ bm }: { bm: BookmakerReview }) {
  const partner = isPartner(bm);

  return (
    <article className="bg-[#1a1d24] rounded-xl border border-slate-800 overflow-hidden">
      <div className="p-5 md:p-6">
        <div className="flex flex-wrap items-center gap-3 mb-3">
          <BookmakerLogo bookmaker={{ id: 0, name: bm.name, short_name: bm.name, affiliate_link: partner ? bm.offerUrl : null, active: true }} size="md" />
          <div>
            <h3 className="font-semibold text-slate-100">{bm.name}</h3>
            <span className="text-xs text-slate-500">{bm.stars} · Props {bm.propsScore} · Tennis {bm.tennisScore}</span>
          </div>
          <span className={`sm:ml-auto rounded-full border px-2.5 py-1 text-[9px] font-semibold uppercase tracking-[0.14em] ${partner ? "border-emerald-400/20 bg-emerald-400/[0.08] text-emerald-300" : "border-slate-700 bg-slate-900 text-slate-500"}`}>
            {partner ? "Affiliate partner" : "Independent review"}
          </span>
        </div>
        {partner ? (
          <div className="flex flex-col gap-3 border-t border-slate-800 pt-4 sm:flex-row sm:items-center sm:justify-between">
            <div>
              <span className="text-[10px] font-semibold uppercase tracking-[0.16em] text-emerald-400">New UK customers</span>
              <p className="mt-1 text-sm font-semibold text-slate-100">{bm.welcomeOffer}</p>
            </div>
            <a
              href={bm.offerUrl}
              target="_blank"
              rel="sponsored nofollow noopener noreferrer"
              className="inline-flex w-full items-center justify-center rounded-lg bg-emerald-500 px-5 py-2.5 text-sm font-semibold text-white transition-colors hover:bg-emerald-400 sm:w-auto"
            >
              View {bm.name} offer →
            </a>
          </div>
        ) : (
          <div className="border-t border-slate-800 pt-4">
            <p className="text-sm text-slate-400">No paid link. Included for independent comparison and line-shopping context.</p>
          </div>
        )}
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
          {partner && (
            <div className="rounded-lg border border-slate-700/80 bg-slate-800/40 px-3 py-2">
              <p className="text-[11px] leading-5 text-slate-500">{bm.welcomeTerms}</p>
            </div>
          )}
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
  { q: "Is the margin index live?", a: "No. It is a dated, one-off snapshot. We publish the capture time and sample size so the comparison is not mistaken for a live odds screen." },
  { q: "Why are some prop markets not measured?", a: "A bookmaker margin needs every mutually exclusive outcome from the same bookmaker at the same line. An over-only player-prop price cannot produce a defensible margin, so we label it not measured rather than inventing one." },
  { q: "What if odds are better elsewhere?", a: "Take the best available price after checking that the market, line and settlement rules are identical. Small price improvements compound materially over a large sample." },
  { q: "Do affiliate links affect the margin ranking?", a: "No. William Hill, Bwin and Betway are our only affiliate partners on this page. The margin snapshot is computed independently from captured prices, and the measured Bet365 and BetMGM rows are not paid placements." },
  { q: "Are welcome offers guaranteed value?", a: "No. Terms, qualifying odds, expiry and withdrawal conditions matter. Read the current operator terms and never place a poor-value bet solely to unlock a promotion." },
  { q: "What happens when I get restricted?", a: "Stake limits reduce gradually, eventually hitting £5-20 maximum. The account remains active but becomes operationally useless for serious betting. This is inevitable for winning accounts. Plan for it by having multiple accounts active. When one restricts, continue with others.", linkToFaq: true },
];

export default function BookmakersPage() {
  const measuredSegments = (MARGIN_INDEX.segments ?? []).filter(
    (segment) => segment.operators.length > 0,
  );
  const partnerBookmakers = BOOKMAKERS.filter(isPartner);
  const editorialBookmakers = BOOKMAKERS.filter((bookmaker) => !isPartner(bookmaker));

  return (
    <div className="min-h-screen bg-[#0f1117] text-slate-100">
      <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 pt-6 pb-8 md:pb-12">
        <PageHomeLink className="mb-8" />

        {/* Hero */}
        <section className="mb-10 md:mb-12">
          <span className="text-xs font-mono text-emerald-400 mb-3 block tracking-wider">BOOKMAKERS</span>
          <h1 className="max-w-4xl text-4xl font-semibold tracking-[-0.035em] text-white sm:text-5xl lg:text-6xl">
            UK Bookmaker Margin Index
          </h1>
          <p className="mt-5 max-w-3xl text-lg leading-8 text-slate-300">
            Which UK bookmaker is cheapest, market by market. Measured from complete prices captured in a single snapshot — not estimates and not a live feed.
          </p>
          <p className="mt-4 max-w-3xl text-sm leading-6 text-slate-500">
            The independent index covers every operator present in the verified capture. Promotional links appear only for our three partners: William Hill, Bwin and Betway.
          </p>
          <p className="mt-4 text-sm text-slate-500">
            18+ only. Gamble responsibly. <a href="https://www.begambleaware.org" target="_blank" rel="noopener noreferrer" className="text-emerald-400/80 hover:text-emerald-300 underline">begambleaware.org</a>
          </p>
        </section>

        <MarginExplorer
          generatedAt={MARGIN_INDEX.generated_at}
          segments={measuredSegments}
          notMeasured={NOT_MEASURED_MARKETS}
        />

        <section className="mb-12 grid gap-4 md:grid-cols-3">
          <article className="rounded-2xl border border-slate-800 bg-[#141820] p-5">
            <p className="text-[10px] font-semibold uppercase tracking-[0.18em] text-cyan-300">Complete markets only</p>
            <h2 className="mt-2 text-lg font-semibold text-white">No over-only shortcuts</h2>
            <p className="mt-2 text-sm leading-6 text-slate-400">We calculate margin only when every mutually exclusive outcome is available from the same bookmaker at the identical line.</p>
          </article>
          <article className="rounded-2xl border border-slate-800 bg-[#141820] p-5">
            <p className="text-[10px] font-semibold uppercase tracking-[0.18em] text-emerald-300">One dated capture</p>
            <h2 className="mt-2 text-lg font-semibold text-white">Comparable, not live</h2>
            <p className="mt-2 text-sm leading-6 text-slate-400">Alternate lines are collapsed before comparison, so a bookmaker with more lines cannot gain artificial weight.</p>
          </article>
          <article className="rounded-2xl border border-slate-800 bg-[#141820] p-5">
            <p className="text-[10px] font-semibold uppercase tracking-[0.18em] text-amber-300">Read the evidence</p>
            <h2 className="mt-2 text-lg font-semibold text-white">Samples stay visible</h2>
            <p className="mt-2 text-sm leading-6 text-slate-400">Every panel shows event and quote counts. Thin markets remain labelled instead of being blended into a misleading global league table.</p>
          </article>
        </section>

        {/* Partner offers */}
        <section className="mb-12 rounded-[2rem] border border-emerald-300/15 bg-[linear-gradient(145deg,rgba(16,185,129,0.06),rgba(15,17,23,0.9)_44%)] p-5 sm:p-7">
          <div className="mb-5 max-w-3xl">
            <p className="text-[10px] font-semibold uppercase tracking-[0.2em] text-emerald-300">Commercial relationships</p>
            <h2 className="mt-2 text-2xl font-semibold text-white">Our partner offers</h2>
            <p className="mt-2 text-sm leading-6 text-slate-400">Only these three cards contain paid links. The independent margin explorer above is calculated without regard to affiliate status.</p>
          </div>
          <div className="grid gap-3 md:grid-cols-3">
            {partnerBookmakers.map((bm) => (
              <article key={bm.id} className="flex flex-col rounded-2xl border border-slate-700/80 bg-[#11151c] p-4 shadow-[0_14px_40px_rgba(0,0,0,0.2)]">
                <div className="flex items-center gap-3">
                  <BookmakerLogo bookmaker={{ id: 0, name: bm.name, short_name: bm.name, affiliate_link: bm.offerUrl, active: true }} size="sm" />
                  <div>
                    <p className="font-semibold text-slate-100">{bm.name}</p>
                    <p className="text-[9px] font-semibold uppercase tracking-[0.14em] text-emerald-400">Affiliate partner</p>
                  </div>
                </div>
                <p className="mt-4 text-sm font-semibold text-white">{bm.welcomeOffer}</p>
                <p className="mt-1 text-xs leading-5 text-slate-500">New UK customers. Full operator terms apply.</p>
                <a
                  href={bm.offerUrl}
                  target="_blank"
                  rel="sponsored nofollow noopener noreferrer"
                  className="mt-4 inline-flex items-center justify-center rounded-xl border border-emerald-400/25 bg-emerald-400/[0.09] px-4 py-2.5 text-sm font-semibold text-emerald-200 transition-colors hover:bg-emerald-400/[0.16]"
                >
                  View offer →
                </a>
              </article>
            ))}
          </div>
        </section>

        {/* Full reviews */}
        <section className="mb-12">
          <h2 className="text-2xl font-semibold text-white">Independent bookmaker reviews</h2>
          <p className="mb-7 mt-2 max-w-3xl text-sm leading-6 text-slate-500">All eight operators remain in the editorial comparison. Paid relationships are labelled on every relevant card; the remaining reviews contain no signup link.</p>

          <div className="mb-6">
            <p className="mb-3 text-xs font-semibold uppercase tracking-[0.18em] text-emerald-400/80">Affiliate partners</p>
            <div className="space-y-6">
              {partnerBookmakers.map((bm) => (
                <BookmakerCard key={bm.id} bm={bm} />
              ))}
            </div>
          </div>

          <p className="mb-3 text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">Editorial only · no paid link</p>
          <div className="space-y-6">
            {editorialBookmakers.map((bm) => (
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

        {/* Responsive comparison */}
        <section className="mb-10">
          <h2 className="text-xl font-semibold text-emerald-400">Quick Comparison</h2>
          <p className="mt-2 text-sm text-slate-500">Editorial ratings are relative to the UK recreational-bookmaker market. Offer labels appear only for partners.</p>
          <div className="mt-5 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            {COMPARISON_ROWS.map((row) => (
              <article key={row.name} className="rounded-2xl border border-slate-800 bg-[#141820] p-4">
                <div className="flex items-center gap-3">
                  <BookmakerLogo bookmaker={{ id: 0, name: row.name, short_name: row.name, affiliate_link: null, active: true }} size="sm" />
                  <h3 className="font-semibold text-white">{row.name}</h3>
                </div>
                <dl className="mt-4 grid grid-cols-2 gap-2 text-xs">
                  <div className="rounded-lg bg-black/20 p-2.5">
                    <dt className="text-slate-600">Player props</dt>
                    <dd className="mt-1 font-mono font-semibold text-slate-200">{row.props}</dd>
                  </div>
                  <div className="rounded-lg bg-black/20 p-2.5">
                    <dt className="text-slate-600">Tennis</dt>
                    <dd className="mt-1 font-mono font-semibold text-slate-200">{row.tennis}</dd>
                  </div>
                </dl>
                <p className="mt-3 text-[10px] font-semibold uppercase tracking-[0.14em] text-emerald-400/80">{row.offer}</p>
                <p className="mt-2 text-xs leading-5 text-slate-500">{row.bestFor}</p>
              </article>
            ))}
          </div>
        </section>

        {/* Account Strategy */}
        <section className="bg-[#1a1d24] rounded-xl border border-slate-800 p-6 md:p-8 mb-10">
          <h2 className="text-xl font-semibold text-emerald-400 mb-4">Recommended Approach</h2>
          <div className="text-slate-300 text-sm leading-relaxed space-y-4">
            <p><strong className="text-slate-100">Use the index as evidence, not a signup ranking.</strong> Choose the sport and exact market you intend to bet, compare complete prices, then check the current live line and settlement rules directly with the operator.</p>
            <ol className="list-decimal pl-6 space-y-2">
              <li>Match the same market and line across bookmakers.</li>
              <li>Prefer the best price, not the bookmaker with the strongest promotion.</li>
              <li>Treat thin samples as directional evidence only.</li>
              <li>Keep stakes tied to bankroll and verified edge, never to bonus size.</li>
            </ol>
            <p>Reviews cover eight operators because line shopping benefits from breadth. Only William Hill, Bwin and Betway are commercial partners. See our <Link href="/track-record" className="text-emerald-400 hover:text-emerald-300 underline">Track Record</Link> for performance context.</p>
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
          <p className="text-slate-300 text-sm leading-relaxed mb-3">William Hill, Bwin and Betway are our only affiliate partners on this page. Their cards and links are explicitly labelled. We may receive a commission if an eligible user opens an account through one of those links, at no extra cost to the user.</p>
          <p className="text-slate-300 text-sm leading-relaxed mb-3">Midnite, BetVictor, Coral, Ladbrokes and BetMGM are included as editorial reviews only and have no signup link here. Bet365 and BetMGM appear in the current margin snapshot because prices were captured for comparison; neither paid for that placement.</p>
          <p className="text-slate-300 text-sm leading-relaxed">Affiliate status never changes the margin calculation. The index uses complete captured outcome sets, publishes its timestamp and sample size, and labels unsupported markets as not measured.</p>
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
