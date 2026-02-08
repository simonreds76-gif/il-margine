"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import BookmakerLogo from "@/components/BookmakerLogo";
import Footer from "@/components/Footer";
import { supabase, Bookmaker } from "@/lib/supabase";

/**
 * Bookmakers & key concepts (UK-focused)
 * - Honest reviews only for bookmakers we're happy to promote: Midnite, BetVictor, Unibet, Coral, Ladbrokes, BetMGM
 * - Expanded concepts: CLV, gubbing, margin, value, line shopping, Super Sub, etc.
 * - New account offers for recommended bookmakers; Understanding account restrictions (factual).
 */

interface BookmakerReview {
  id: string;
  name: string;
  short_name: string;
  summary: string;
  props: string;
  tennis: string;
  betbuilders: string;
  pros: string[];
  cons: string[];
  rating: number;
  notes?: string;
}

interface NewAccountOffer {
  id: string;
  bookmaker: string;
  short_name: string;
  offer: string;
  description: string;
  terms?: string;
}

export default function BookmakersPage() {
  const [bookmakers, setBookmakers] = useState<Bookmaker[]>([]);
  const [loading, setLoading] = useState(true);
  const [hoveredClaimId, setHoveredClaimId] = useState<string | null>(null);

  useEffect(() => {
    void fetchBookmakers();
  }, []);

  const fetchBookmakers = async () => {
    try {
      const { data, error } = await supabase
        .from("bookmakers")
        .select("*")
        .eq("active", true)
        .order("name");

      if (error) console.error("Error fetching bookmakers:", error);
      if (data) setBookmakers(data);
    } catch (e) {
      console.error("Unexpected error fetching bookmakers:", e);
    } finally {
      setLoading(false);
    }
  };

  const getBookmakerFromDb = (shortName: string): Bookmaker | undefined => {
    return bookmakers.find(
      (b) =>
        b.short_name.toLowerCase() === shortName.toLowerCase() ||
        b.name.toLowerCase() === shortName.toLowerCase()
    );
  };

  // Bookmakers we're happy to promote: honest reviews for props, tennis, bet builders
  const recommendedBookmakers: BookmakerReview[] = useMemo(
    () => [
      {
        id: "midnite",
        name: "Midnite",
        short_name: "Midnite",
        summary: "Esports-first brand expanding into sports with a modern product and competitive odds.",
        props: "Growing player prop coverage on major leagues; worth checking for shots, tackles, cards. Limits can be tighter than established books.",
        tennis: "ATP/WTA and Grand Slams covered; in-play and streaming improving. Good for a second or third account to price-shop.",
        betbuilders: "Bet builder available with decent leg count; no Super Sub, so factor in sub risk for player props in builders.",
        pros: [
          "Modern app and UX",
          "Competitive odds on main markets",
          "No history of aggressive gubbing (so far)",
          "Useful for diversifying accounts",
        ],
        cons: [
          "Player prop depth not at tier-one level yet",
          "No substitution protection on props",
        ],
        rating: 4,
        notes: "Worth having in the mix. Use for odds comparison and to spread action.",
      },
      {
        id: "betvictor",
        name: "BetVictor",
        short_name: "BetVictor",
        summary: "Long-standing UK bookmaker with solid football and tennis coverage and a straightforward product.",
        props: "Decent player prop coverage on Premier League and major European leagues. Build Your Bet style markets available; limits are fair for recreational stakes.",
        tennis: "Good tennis coverage including ATP, WTA, Grand Slams. Live streaming and in-play available. Odds often competitive.",
        betbuilders: "Bet builder with multiple legs; no Super Sub – void rules apply if player doesn't start or is subbed before line.",
        pros: [
          "Reliable, established brand",
          "Competitive odds on football and tennis",
          "Live streaming included",
          "Generally fair limits for casual-to-mid stakes",
        ],
        cons: [
          "No Super Sub on props/builders",
          "Niche leagues and props less deep than market leaders",
        ],
        rating: 4,
        notes: "Solid all-rounder. Good for price shopping and as a main or second account.",
      },
      {
        id: "unibet",
        name: "Unibet",
        short_name: "Unibet",
        summary: "Kindred Group brand with strong tennis, good football coverage, and one of the best bet builder leg limits.",
        props: "Player props on major leagues; coverage is good but not the deepest. Odds often sharp – worth comparing.",
        tennis: "Strong here: 10,000+ events streamed, daily tennis boosts (e.g. 5% on selected tournaments), competitive margins. One of the best second accounts for tennis.",
        betbuilders: "Up to 12 legs per builder – more than most. Interface is clean. No Super Sub, so avoid player-prop legs that depend on full 90.",
        pros: [
          "Excellent tennis streaming and boosts",
          "12-leg bet builder",
          "Competitive odds across sports",
          "Stable, licensed operator",
        ],
        cons: [
          "No Super Sub on player props",
          "Can restrict if you're consistently ahead of the market",
        ],
        rating: 4,
        notes: "A punter favourite for tennis and for builder price comparison.",
      },
      {
        id: "coral",
        name: "Coral",
        short_name: "Coral",
        summary: "Part of Entain (Ladbrokes Coral). Build Your Bet and acca insurance; good for diversifying.",
        props: "Build Your Bet covers player stats and combinations. Main leagues well covered; niche props thinner. Acca Edge on accumulators adds value.",
        tennis: "Tennis available on main tour and Slams; coverage is adequate. Odds and limits are reasonable for recreational play.",
        betbuilders: "Build Your Bet is their builder product – decent market depth and combinations. No Super Sub on player legs.",
        pros: [
          "Build Your Bet with good combination options",
          "Acca Edge insurance on accas",
          "Part of a large, regulated group",
          "Regular promos for existing customers",
        ],
        cons: [
          "Odds can trail sharpest books",
          "Restrictions possible for winning accounts",
        ],
        rating: 4,
        notes: "Use for extra lines and promos; always compare odds.",
      },
      {
        id: "ladbrokes",
        name: "Ladbrokes",
        short_name: "Ladbrokes",
        summary: "Entain brand; same group as Coral. Reliable product with Build Your Bet and strong high-street presence.",
        props: "Player props and stat markets on major football; Build Your Bet for custom combos. Coverage similar to Coral.",
        tennis: "ATP, WTA, Slams covered; streaming and in-play. Odds and limits in line with other Entain brands.",
        betbuilders: "Build Your Bet with multi-leg options. No Super Sub – standard void rules for non-starters/subs.",
        pros: [
          "Trusted UK brand",
          "Build Your Bet and acca offers",
          "Good app and in-shop experience",
          "Reasonable limits for most punters",
        ],
        cons: [
          "No Super Sub",
          "Margins can be higher than sharpest books",
        ],
        rating: 4,
        notes: "Another useful account in the portfolio; compare with Coral for best price.",
      },
      {
        id: "betmgm",
        name: "BetMGM",
        short_name: "BetMGM",
        summary: "Strong on player props with often better odds on shots, fouls and shots on target because they don't offer Super Sub – they carry sub risk.",
        props: "Often best price on shots, fouls, SOT when you're confident on minutes. No Super Sub means the book prices in the sub risk – use for nailed-on starters and set-piece takers.",
        tennis: "Tennis offered on main events; coverage is adequate. Odds competitive; less depth than dedicated tennis leaders.",
        betbuilders: "Bet builder available; no substitution protection. Best when builder legs are match-level or when you're happy with sub risk on props.",
        pros: [
          "Frequently best odds on player props (shots, fouls, SOT) due to no Super Sub",
          "Good for value when you have a strong view on minutes",
          "Solid major-league coverage",
        ],
        cons: [
          "No Super Sub – prop voids only if player doesn't start; if player is subbed and doesn't cover the line, the bet is lost",
          "Must factor rotation and early subs into every prop bet",
        ],
        rating: 4,
        notes: "Void if player doesn't start; lost if subbed and doesn't cover. Essential for props punters who understand minutes. Use when you have an edge on playing time.",
      },
    ],
    []
  );

  const newAccountOffers: NewAccountOffer[] = useMemo(
    () => [
      {
        id: "midnite",
        bookmaker: "Midnite",
        short_name: "Midnite",
        offer: "Bet £10 Get £20 in free bets",
        description: "Min odds 1/1. T&Cs apply.",
        terms: "18+. New customers only. Min deposit £10. T&Cs apply. BeGambleAware.org",
      },
      {
        id: "betvictor",
        bookmaker: "BetVictor",
        short_name: "BetVictor",
        offer: "Bet £10 Get £40 in free bets",
        description: "Min odds 1/2. 4x £10 free bets. T&Cs apply.",
        terms: "18+. New customers only. Min deposit £10. T&Cs apply. BeGambleAware.org",
      },
      {
        id: "unibet",
        bookmaker: "Unibet",
        short_name: "Unibet",
        offer: "Bet £10 Get £40 in bonuses",
        description: "2x £10 free bets + £20 casino. Min odds 1/1. T&Cs apply.",
        terms:
          "18+. New customers only. Min deposit £10. T&Cs apply. BeGambleAware.org",
      },
      {
        id: "coral",
        bookmaker: "Coral",
        short_name: "Coral",
        offer: "Bet £5 Get £20 in free bets",
        description: "Min odds 1/2. 4x £5 free bets. T&Cs apply.",
        terms: "18+. New customers only. Min deposit £5. T&Cs apply. BeGambleAware.org",
      },
      {
        id: "ladbrokes",
        bookmaker: "Ladbrokes",
        short_name: "Ladbrokes",
        offer: "Bet £5 Get £20 in free bets",
        description: "Min odds 1/2. 4x £5 free bets. T&Cs apply.",
        terms: "18+. New customers only. Min deposit £5. T&Cs apply. BeGambleAware.org",
      },
      {
        id: "betmgm",
        bookmaker: "BetMGM",
        short_name: "BetMGM",
        offer: "Bet £10 Get £50 in free bets",
        description: "Min odds 1/1. T&Cs apply.",
        terms: "18+. New customers only. Min deposit £10. T&Cs apply. BeGambleAware.org",
      },
    ],
    []
  );

  return (
    <div className="min-h-screen bg-[#0f1117] text-slate-100">
      <section className="relative pt-4 pb-12 md:pt-6 md:pb-16 border-b border-slate-800/50 overflow-hidden">
        <div className="absolute inset-0 bg-gradient-to-b from-emerald-950/10 via-transparent to-transparent pointer-events-none" aria-hidden />
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 relative">
          <div className="flex items-center gap-2 mb-4">
            <Link href="/" className="text-sm text-slate-500 hover:text-slate-300 transition-colors">
              Home
            </Link>
            <span className="text-slate-600">/</span>
            <span className="text-sm text-emerald-400 font-medium">Bookmakers</span>
          </div>

          <h1 className="text-3xl sm:text-4xl md:text-5xl font-bold mb-4 sm:mb-6">Bookmakers & Key Concepts</h1>
          <p className="text-base sm:text-lg text-slate-300 max-w-3xl leading-relaxed mb-8">
            Straight-talking guidance for punters: where to bet, how to think about odds and your account, and the jargon that matters. No filler. The kind of reference you won&apos;t find in generic affiliate roundups.
          </p>

          <div className="max-w-4xl rounded-2xl border border-emerald-500/30 bg-gradient-to-br from-slate-900/90 via-slate-900/70 to-emerald-950/20 shadow-lg shadow-emerald-500/5 overflow-hidden">
            <div className="border-b border-emerald-500/20 bg-emerald-500/5 px-5 py-3 sm:px-6 sm:py-4">
              <h3 className="text-sm font-mono font-semibold text-emerald-400 tracking-wider">KEY CONCEPTS — A PUNTER&apos;S GLOSSARY</h3>
            </div>
            <div className="divide-y divide-slate-800/80">
              <div className="grid grid-cols-1 sm:grid-cols-[minmax(0,10rem)_1fr] gap-2 sm:gap-6 px-5 py-4 sm:px-6 sm:py-4">
                <span className="font-bold text-emerald-400 text-sm sm:text-base">CLV</span>
                <p className="text-sm sm:text-base text-slate-300 leading-relaxed">
                  Closing Line Value – the difference between your odds and the closing line. Consistently beating the close is a strong predictor of long-term profitability.
                </p>
              </div>
              <div className="grid grid-cols-1 sm:grid-cols-[minmax(0,10rem)_1fr] gap-2 sm:gap-6 px-5 py-4 sm:px-6 sm:py-4">
                <span className="font-bold text-emerald-400 text-sm sm:text-base">Gubbing</span>
                <p className="text-sm sm:text-base text-slate-300 leading-relaxed">
                  Account restrictions: reduced stakes, promotions removed, or account closed. Very common for profitable bettors at soft bookmakers. Plan for it.
                </p>
              </div>
              <div className="grid grid-cols-1 sm:grid-cols-[minmax(0,10rem)_1fr] gap-2 sm:gap-6 px-5 py-4 sm:px-6 sm:py-4">
                <span className="font-bold text-emerald-400 text-sm sm:text-base">Sharp vs Soft</span>
                <p className="text-sm sm:text-base text-slate-300 leading-relaxed">
                  Sharp books (e.g. Pinnacle) set efficient lines and don&apos;t restrict winners. Soft bookmakers have higher margins, more promos, and routinely restrict winning accounts.
                </p>
              </div>
              <div className="grid grid-cols-1 sm:grid-cols-[minmax(0,10rem)_1fr] gap-2 sm:gap-6 px-5 py-4 sm:px-6 sm:py-4">
                <span className="font-bold text-emerald-400 text-sm sm:text-base">Margin / Vig</span>
                <p className="text-sm sm:text-base text-slate-300 leading-relaxed">
                  The bookmaker&apos;s edge built into the odds. Lower margin = fairer prices. Sharp books often have 2–4% margin; soft books can be 6–10%+ on the same market.
                </p>
              </div>
              <div className="grid grid-cols-1 sm:grid-cols-[minmax(0,10rem)_1fr] gap-2 sm:gap-6 px-5 py-4 sm:px-6 sm:py-4">
                <span className="font-bold text-emerald-400 text-sm sm:text-base">Value</span>
                <p className="text-sm sm:text-base text-slate-300 leading-relaxed">
                  When your estimated true probability is higher than the implied probability of the odds. Betting value over the long run is how you make money; entertainment betting is the opposite.
                </p>
              </div>
              <div className="grid grid-cols-1 sm:grid-cols-[minmax(0,10rem)_1fr] gap-2 sm:gap-6 px-5 py-4 sm:px-6 sm:py-4">
                <span className="font-bold text-emerald-400 text-sm sm:text-base">Line shopping</span>
                <p className="text-sm sm:text-base text-slate-300 leading-relaxed">
                  Checking odds at multiple bookmakers before placing a bet. Even 0.1 on the odds compounds over hundreds of bets. Essential habit.
                </p>
              </div>
              <div className="grid grid-cols-1 sm:grid-cols-[minmax(0,10rem)_1fr] gap-2 sm:gap-6 px-5 py-4 sm:px-6 sm:py-4">
                <span className="font-bold text-emerald-400 text-sm sm:text-base">Steam move</span>
                <p className="text-sm sm:text-base text-slate-300 leading-relaxed">
                  A rapid, sharp move in the line (e.g. 2.10 to 1.85) usually caused by sharp or professional money. Often a signal; never the only reason to bet.
                </p>
              </div>
              <div className="grid grid-cols-1 sm:grid-cols-[minmax(0,10rem)_1fr] gap-2 sm:gap-6 px-5 py-4 sm:px-6 sm:py-4">
                <span className="font-bold text-emerald-400 text-sm sm:text-base">Super Sub</span>
                <p className="text-sm sm:text-base text-slate-300 leading-relaxed">
                  Player prop protection when a player is substituted: the replacement can fulfil the bet (e.g. shots on target). Crucial for football props – only 35% of strikers play 90 minutes now.
                </p>
              </div>
              <div className="grid grid-cols-1 sm:grid-cols-[minmax(0,10rem)_1fr] gap-2 sm:gap-6 px-5 py-4 sm:px-6 sm:py-4">
                <span className="font-bold text-emerald-400 text-sm sm:text-base">Void if player doesn&apos;t start</span>
                <p className="text-sm sm:text-base text-slate-300 leading-relaxed">
                  Rule that voids a player prop if the player doesn&apos;t start the match. Protects early bets before lineups are confirmed. Look for it when betting props.
                </p>
              </div>
              <div className="grid grid-cols-1 sm:grid-cols-[minmax(0,10rem)_1fr] gap-2 sm:gap-6 px-5 py-4 sm:px-6 sm:py-4">
                <span className="font-bold text-emerald-400 text-sm sm:text-base">Stake factoring</span>
                <p className="text-sm sm:text-base text-slate-300 leading-relaxed">
                  When a bookmaker reduces your maximum stake (e.g. from £100 to £10) based on your behaviour or results. A form of soft gubbing.
                </p>
              </div>
              <div className="grid grid-cols-1 sm:grid-cols-[minmax(0,10rem)_1fr] gap-2 sm:gap-6 px-5 py-4 sm:px-6 sm:py-4">
                <span className="font-bold text-emerald-400 text-sm sm:text-base">Exchange vs book</span>
                <p className="text-sm sm:text-base text-slate-300 leading-relaxed">
                  Exchanges (e.g. Betfair) match bettors with each other; the operator takes commission. No account restrictions for winning. Traditional books bet against you and can limit or close accounts.
                </p>
              </div>
            </div>
          </div>

          <div className="mt-8 max-w-3xl text-sm text-slate-400">
            Betting involves risk. Past performance does not guarantee future results. Always bet responsibly and within
            your means.
          </div>
        </div>
      </section>

      {/* Bookmakers we recommend — only those we're happy to promote */}
      <section className="py-12 md:py-16 border-b border-slate-800/50 bg-gradient-to-b from-slate-900/30 to-transparent">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex items-center gap-2 mb-6">
            <span className="text-xs font-mono text-amber-400 tracking-wider">RECOMMENDED</span>
          </div>
          <h2 className="text-2xl sm:text-3xl font-bold mb-4 sm:mb-6 flex items-center gap-3 text-slate-100">
            <span className="text-3xl sm:text-4xl" aria-hidden>📋</span>
            Bookmakers We Recommend & New Account Offers
          </h2>
          <p className="text-base text-slate-300 mb-8 sm:mb-10 max-w-3xl">
            We only promote bookmakers we&apos;re comfortable with. Honest reviews for player props, tennis, and bet builders, plus current new account offers. Always check the site for full terms.
          </p>
          <p className="text-sm text-amber-400/95 font-medium mb-8 sm:mb-10 flex items-center gap-2">
            <span className="inline-flex w-1.5 h-1.5 rounded-full bg-amber-400" aria-hidden />
            Used by us. We&apos;ve placed bets, checked limits and withdrawal times at every one.
          </p>

          <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-6">
            {recommendedBookmakers.map((rec) => {
              const dbBookmaker = getBookmakerFromDb(rec.short_name);
              const offer = newAccountOffers.find((o) => o.short_name === rec.short_name);
              return (
                <div key={rec.id} className="rounded-2xl border border-slate-800/60 bg-gradient-to-br from-slate-900/80 to-slate-900/40 p-6 hover:border-amber-500/40 hover:shadow-lg hover:shadow-amber-500/10 transition-all duration-200 flex flex-col h-full">
                  <div className="flex-1 flex flex-col">
                  <div className="flex items-center justify-between mb-4">
                    <div className="flex items-center gap-3">
                      <BookmakerLogo
                        bookmaker={
                          dbBookmaker || {
                            id: 0,
                            name: rec.name,
                            short_name: rec.short_name,
                            affiliate_link: null,
                            active: true,
                          }
                        }
                        size="md"
                      />
                      <h3 className="font-semibold text-lg">{rec.name}</h3>
                    </div>
                    <div className="flex items-center gap-1" aria-label={`${rec.rating} out of 5`}>
                      {Array.from({ length: 5 }).map((_, i) => (
                        <svg key={i} className={`w-4 h-4 ${i < rec.rating ? "text-amber-400" : "text-slate-700"}`} fill="currentColor" viewBox="0 0 20 20">
                          <path d="M9.049 2.927c.3-.921 1.603-.921 1.902 0l1.07 3.292a1 1 0 00.95.69h3.462c.969 0 1.371 1.24.588 1.81l-2.8 2.034a1 1 0 00-.364 1.118l1.07 3.292c.3.921-.755 1.688-1.54 1.118l-2.8-2.034a1 1 0 00-1.175 0l-2.8 2.034c-.784.57-1.838-.197-1.539-1.118l1.07-3.292a1 1 0 00-.364-1.118L2.98 8.72c-.783-.57-.38-1.81.588-1.81h3.461a1 1 0 00.951-.69l1.07-3.292z" />
                        </svg>
                      ))}
                    </div>
                  </div>
                  <p className="text-sm text-slate-400 mb-4">{rec.summary}</p>
                  <div className="space-y-3 mb-4">
                    <div>
                      <span className="text-xs font-mono text-amber-400 mb-1 block">Player props</span>
                      <p className="text-xs text-slate-300">{rec.props}</p>
                    </div>
                    <div>
                      <span className="text-xs font-mono text-amber-400 mb-1 block">Tennis</span>
                      <p className="text-xs text-slate-300">{rec.tennis}</p>
                    </div>
                    <div>
                      <span className="text-xs font-mono text-amber-400 mb-1 block">Bet builders</span>
                      <p className="text-xs text-slate-300">{rec.betbuilders}</p>
                    </div>
                  </div>
                  <div className="space-y-2 mb-4">
                    <ul className="space-y-1">
                      {rec.pros.map((pro, i) => (
                        <li key={i} className="text-sm text-slate-300 flex items-start gap-2">
                          <span className="text-amber-400 mt-0.5">✓</span>
                          <span>{pro}</span>
                        </li>
                      ))}
                    </ul>
                    <ul className="space-y-1">
                      {rec.cons.map((con, i) => (
                        <li key={i} className="text-sm text-slate-400 flex items-start gap-2">
                          <span className="text-red-400 mt-0.5">×</span>
                          <span>{con}</span>
                        </li>
                      ))}
                    </ul>
                  </div>
                  {rec.notes && (
                    <div className="mt-4 pt-4 border-t border-slate-800/50">
                      <p className="text-xs text-slate-400 italic">{rec.notes}</p>
                    </div>
                  )}
                  </div>
                  {offer && (
                    <div className="mt-auto pt-4">
                      <div className="p-3 rounded-lg bg-orange-500/15 border border-orange-500/40">
                        <span className="text-xs font-mono text-orange-400 tracking-wider block mb-1.5 flex items-center gap-1.5">
                          New account offer
                          <span className="inline-flex items-center justify-center w-8 h-8 rounded-full bg-emerald-500/25 border-2 border-emerald-500/60 text-2xl shadow-inner" aria-hidden title="Offer">💰</span>
                        </span>
                        <p className="text-base sm:text-lg font-bold text-amber-400 mb-0.5">{offer.offer}</p>
                        <p className="text-xs text-slate-500">{offer.description}</p>
                      </div>
                      <div className="mt-3 w-full flex justify-center sm:justify-center">
                        <a
                          href={dbBookmaker?.affiliate_link || "#"}
                          target="_blank"
                          rel="noopener noreferrer"
                          onMouseEnter={() => setHoveredClaimId(rec.id)}
                          onMouseLeave={() => setHoveredClaimId(null)}
                          style={{
                            backgroundColor: hoveredClaimId === rec.id ? "#ef4444" : "#ea580c",
                            borderColor: hoveredClaimId === rec.id ? "#f87171" : "#f97316",
                            boxShadow: hoveredClaimId === rec.id ? "0 0 24px rgba(239, 68, 68, 0.5)" : "0 4px 14px rgba(234, 88, 12, 0.35)",
                            transform: hoveredClaimId === rec.id ? "scale(1.05)" : "scale(1)",
                          }}
                          className="inline-flex items-center justify-center w-full sm:w-auto sm:min-w-[180px] px-6 py-3 rounded-full text-black font-bold text-sm uppercase tracking-wider border-2 cursor-pointer transition-all duration-200 ease-out focus:outline-none focus:ring-2 focus:ring-red-400 focus:ring-offset-2 focus:ring-offset-slate-900"
                        >
                          Claim offer
                        </a>
                      </div>
                    </div>
                  )}
                  {!offer && dbBookmaker?.affiliate_link && (
                    <a href={dbBookmaker.affiliate_link} target="_blank" rel="noopener noreferrer" className="mt-auto pt-4 inline-flex items-center justify-center w-full sm:w-auto px-6 py-3 rounded-full bg-orange-500 text-black font-bold text-sm uppercase border-2 border-orange-400/50">
                      Visit {rec.name}
                    </a>
                  )}
                </div>
              );
            })}
          </div>
          {loading && <p className="mt-6 text-sm text-slate-500">Loading affiliate links…</p>}
        </div>
      </section>

      <section className="py-12 md:py-16 border-t border-slate-800/50 bg-gradient-to-b from-slate-900/30 to-slate-900/50">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex items-center gap-2 mb-6">
            <span className="text-xs font-mono text-amber-400 tracking-wider">IMPORTANT</span>
          </div>

          <h2 className="text-2xl sm:text-3xl font-bold mb-4 sm:mb-6 flex items-center gap-3 text-slate-100">
            <span className="text-3xl sm:text-4xl" aria-hidden>⚠️</span>
            Understanding Account Restrictions
          </h2>

          <p className="text-base text-slate-300 mb-8 max-w-3xl">
            A UK Gambling Commission study found over 640,000 accounts had restrictions placed on them; nearly half were profitable. Many of the biggest names in UK betting – including Bet365, Paddy Power, and Sky Bet – are widely reported by punters and in the press to restrict or limit winning accounts. We don&apos;t promote them here; below is what you need to know about restrictions in general.
          </p>

          <div className="grid md:grid-cols-2 gap-8">
            <div className="rounded-2xl border border-amber-500/20 bg-gradient-to-br from-slate-900/80 to-slate-900/40 p-6 hover:border-amber-500/30 transition-colors">
              <h3 className="font-semibold text-lg mb-4 text-amber-400">Why Accounts Get Restricted</h3>
              <ul className="space-y-3 text-sm text-slate-300">
                <li className="flex items-start gap-2">
                  <span className="text-amber-400">•</span>
                  <span>
                    <strong>Consistent CLV:</strong> Regularly beating closing lines signals sharp betting
                  </span>
                </li>
                <li className="flex items-start gap-2">
                  <span className="text-amber-400">•</span>
                  <span>
                    <strong>Bonus exploitation:</strong> Only using accounts for promotions
                  </span>
                </li>
                <li className="flex items-start gap-2">
                  <span className="text-amber-400">•</span>
                  <span>
                    <strong>Arbitrage patterns:</strong> Precise stakes and cross-bookie activity
                  </span>
                </li>
                <li className="flex items-start gap-2">
                  <span className="text-amber-400">•</span>
                  <span>
                    <strong>Niche markets:</strong> Betting on low-liquidity leagues/events
                  </span>
                </li>
                <li className="flex items-start gap-2">
                  <span className="text-amber-400">•</span>
                  <span>
                    <strong>Quick withdrawals:</strong> Immediately withdrawing after winning
                  </span>
                </li>
              </ul>
            </div>

            <div className="rounded-2xl border border-emerald-500/20 bg-gradient-to-br from-slate-900/80 to-slate-900/40 p-6 hover:border-emerald-500/30 transition-colors">
              <h3 className="font-semibold text-lg mb-4 text-emerald-400">Mitigation Strategies</h3>
              <ul className="space-y-3 text-sm text-slate-300">
                <li className="flex items-start gap-2">
                  <span className="text-emerald-400">•</span>
                  <span>
                    <strong>Use exchanges:</strong> Betfair (and other exchanges) never restrict winners
                  </span>
                </li>
                <li className="flex items-start gap-2">
                  <span className="text-emerald-400">•</span>
                  <span>
                    <strong>Pinnacle:</strong> Sharp bookmaker that doesn&apos;t restrict winners; in many regions (e.g. UK) it&apos;s only available via brokers, not directly
                  </span>
                </li>
                <li className="flex items-start gap-2">
                  <span className="text-emerald-400">•</span>
                  <span>
                    <strong>Diversify accounts:</strong> Spread action across multiple bookmakers
                  </span>
                </li>
                <li className="flex items-start gap-2">
                  <span className="text-emerald-400">•</span>
                  <span>
                    <strong>Round stakes:</strong> Bet £40 not £39.87 - avoid arb signals
                  </span>
                </li>
                <li className="flex items-start gap-2">
                  <span className="text-emerald-400">•</span>
                  <span>
                    <strong>Bet popular markets:</strong> Premier League over Chinese Division 2
                  </span>
                </li>
                <li className="flex items-start gap-2">
                  <span className="text-emerald-400">•</span>
                  <span>
                    <strong>Accept restrictions:</strong> Plan for account lifecycle - it&apos;s part of the game
                  </span>
                </li>
              </ul>
            </div>
          </div>

          <div className="mt-8 p-6 bg-emerald-500/10 border border-emerald-500/30 rounded-2xl shadow-lg shadow-emerald-500/5">
            <p className="text-sm text-slate-300">
              <strong className="text-emerald-400">Pro Tip:</strong> If you win consistently, some bookmakers may apply
              restrictions. Diversify across multiple accounts, use the Exchange where it adds value (hedging, best price),
              and always price-shop. UK bookmakers are essential for player props and bet builders; plan for the
              possibility of limits and spread your action.
            </p>
          </div>
        </div>
      </section>

      <Footer />
    </div>
  );
}
