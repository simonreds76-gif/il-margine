"use client";

import { useState } from "react";
import Link from "next/link";
import Image from "next/image";
import BookmakerLogo from "@/components/BookmakerLogo";
import { supabase, Bookmaker } from "@/lib/supabase";
import { useEffect } from "react";
import { TELEGRAM_CHANNEL_URL } from "@/lib/config";

interface BookmakerRecommendation {
  id: string;
  name: string;
  short_name: string;
  bestFor: string[];
  pros: string[];
  cons?: string[];
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
  expiry?: string;
}

export default function Bookmakers() {
  const [bookmakers, setBookmakers] = useState<Bookmaker[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchBookmakers();
  }, []);

  const fetchBookmakers = async () => {
    const { data, error } = await supabase
      .from("bookmakers")
      .select("*")
      .eq("active", true)
      .order("name");
    
    if (data) setBookmakers(data);
    if (error) console.error("Error fetching bookmakers:", error);
    setLoading(false);
  };

  // Recommendations based on bet type
  const recommendations: Record<string, BookmakerRecommendation[]> = {
    props: [
      {
        id: "bet365",
        name: "bet365",
        short_name: "bet365",
        bestFor: ["Player Props", "Wide Market Coverage", "Competitive Odds"],
        pros: [
          "Extensive player prop markets across all major leagues",
          "Competitive odds on props, often better than match odds",
          "High betting limits for props",
          "Excellent live betting options",
        ],
        cons: ["Can be restrictive for winning accounts"],
        rating: 5,
        notes: "Best overall for player props. Wide coverage of Serie A, Premier League, and Champions League.",
      },
      {
        id: "betfair",
        name: "Betfair",
        short_name: "Betfair",
        bestFor: ["Exchange Odds", "No Restrictions", "Best Prices"],
        pros: [
          "Exchange often offers better odds than traditional bookmakers",
          "No account restrictions regardless of profitability",
          "Can lay bets (bet against outcomes)",
          "Transparent commission structure",
        ],
        cons: ["Requires understanding of exchange mechanics", "Commission on winnings"],
        rating: 5,
        notes: "Essential for serious bettors. Exchange odds often beat traditional bookmakers.",
      },
      {
        id: "pinnacle",
        name: "Pinnacle",
        short_name: "Pinnacle",
        bestFor: ["CLV Reference", "Sharp Odds", "No Limits", "Professional Bettors"],
        pros: [
          "Sharpest odds in the industry - used as closing line value (CLV) reference",
          "No betting limits or restrictions",
          "Welcomes winning players",
          "Low margins",
          "Essential for odds comparison and value identification",
        ],
        cons: ["Not directly available in UK (accessible via brokers)", "Limited prop markets compared to bet365", "Requires larger stakes for value"],
        rating: 5,
        notes: "Pinnacle odds are the industry benchmark for closing line value. While not directly available in the UK, many bettors access Pinnacle through brokers. We use Pinnacle odds as our reference point for identifying value at other bookmakers.",
      },
    ],
    tennis: [
      {
        id: "bet365",
        name: "bet365",
        short_name: "bet365",
        bestFor: ["Tennis Markets", "Live Betting", "Game Handicaps"],
        pros: [
          "Extensive pre-match and live tennis markets",
          "Competitive odds on game handicaps and totals",
          "Excellent live streaming",
          "Good coverage of ATP, Challenger, and Grand Slams",
        ],
        cons: ["Can restrict accounts after consistent wins"],
        rating: 5,
        notes: "Best overall for tennis betting. Excellent market depth and competitive pricing.",
      },
      {
        id: "pinnacle",
        name: "Pinnacle",
        short_name: "Pinnacle",
        bestFor: ["CLV Reference", "Sharp Odds", "No Restrictions", "Professional Play"],
        pros: [
          "Sharpest tennis odds available - used as closing line value (CLV) reference",
          "No account restrictions",
          "Welcomes professional bettors",
          "Low margins on all markets",
          "Essential for odds comparison and value identification",
        ],
        cons: ["Not directly available in UK (accessible via brokers)", "Limited live betting options", "Requires larger stakes"],
        rating: 5,
        notes: "Pinnacle odds are the industry benchmark for closing line value in tennis. While not directly available in the UK, many bettors access Pinnacle through brokers. We use Pinnacle odds as our reference point for identifying value at other bookmakers.",
      },
      {
        id: "betfair",
        name: "Betfair",
        short_name: "Betfair",
        bestFor: ["Exchange Odds", "Lay Betting", "Best Prices"],
        pros: [
          "Exchange often beats traditional bookmaker odds",
          "Can lay bets (bet against players)",
          "No restrictions on winning accounts",
          "Good liquidity on major tournaments",
        ],
        cons: ["Commission on winnings", "Lower liquidity on smaller tournaments"],
        rating: 4,
        notes: "Exchange odds often superior, especially for favorites. Essential tool.",
      },
    ],
    betbuilders: [
      {
        id: "bet365",
        name: "bet365",
        short_name: "bet365",
        bestFor: ["Bet Builders", "Same Game Combos", "Flexible Builders"],
        pros: [
          "Industry-leading bet builder interface",
          "Wide selection of markets for builders",
          "Competitive odds on combinations",
          "Easy to use builder tool",
        ],
        cons: ["Can restrict accounts"],
        rating: 5,
        notes: "The best bet builder in the industry. Unmatched market selection and interface.",
      },
      {
        id: "skybet",
        name: "Sky Bet",
        short_name: "SkyBet",
        bestFor: ["Request a Bet", "Custom Builders", "Flexible Options"],
        pros: [
          "Request a Bet feature for custom combinations",
          "Good odds on requested bets",
          "Wide market coverage",
        ],
        cons: ["Not all requests accepted", "Can be slower to process"],
        rating: 4,
        notes: "Request a Bet feature allows custom combinations. Good alternative to bet365.",
      },
    ],
  };

  const getBookmakerFromDb = (shortName: string): Bookmaker | undefined => {
    return bookmakers.find(b => 
      b.short_name.toLowerCase() === shortName.toLowerCase() || 
      b.name.toLowerCase() === shortName.toLowerCase()
    );
  };

  return (
    <div className="min-h-screen bg-[#0f1117] text-slate-100">
      {/* KEY CONCEPTS — A PUNTER'S GLOSSARY */}
      <section className="py-12 md:py-16 border-b border-slate-800/50 bg-slate-900/30">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <h2 className="text-2xl sm:text-3xl font-bold mb-6 flex items-center gap-2">
            <span className="text-xs font-mono text-emerald-400 tracking-wider">KEY CONCEPTS</span>
            <span className="text-slate-500">—</span>
            <span>A Punter&apos;s Glossary</span>
          </h2>
          <p className="text-slate-400 mb-6 max-w-3xl">
            Essential terms every bettor should know before comparing bookmakers and placing bets.
          </p>
          <dl className="grid sm:grid-cols-2 lg:grid-cols-3 gap-4 sm:gap-6">
            <div>
              <dt className="font-semibold text-emerald-400 mb-1">Value</dt>
              <dd className="text-sm text-slate-400">When the odds offered imply a lower probability than your estimate of the true chance. Betting when you have value is the edge that drives long-term profit.</dd>
            </div>
            <div>
              <dt className="font-semibold text-emerald-400 mb-1">Closing Line Value (CLV)</dt>
              <dd className="text-sm text-slate-400">How your bet price compares to the final market odds. Beating the closing line consistently is a strong indicator of genuine edge.</dd>
            </div>
            <div>
              <dt className="font-semibold text-emerald-400 mb-1">Odds</dt>
              <dd className="text-sm text-slate-400">The price a bookmaker offers. Decimal odds (e.g. 2.10) show your total return per unit staked; fractional (e.g. 11/10) is traditional in the UK.</dd>
            </div>
            <div>
              <dt className="font-semibold text-emerald-400 mb-1">Stake / Unit</dt>
              <dd className="text-sm text-slate-400">The amount you risk on a bet. Many punters use a fixed unit (e.g. 1% of bankroll) to manage risk and compare returns.</dd>
            </div>
            <div>
              <dt className="font-semibold text-emerald-400 mb-1">Margin (Overround)</dt>
              <dd className="text-sm text-slate-400">The bookmaker&apos;s built-in profit across a market. Lower margins usually mean fairer odds for the punter.</dd>
            </div>
            <div>
              <dt className="font-semibold text-emerald-400 mb-1">Edge</dt>
              <dd className="text-sm text-slate-400">A consistent advantage over the market—from better information, modelling, or discipline. Without edge, betting is negative expectation.</dd>
            </div>
          </dl>
        </div>
      </section>

      {/* Hero */}
      <section className="py-12 md:py-20 border-b border-slate-800/50">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex items-center gap-2 mb-4">
            <Link href="/" className="text-sm text-slate-500 hover:text-slate-300">Home</Link>
            <span className="text-slate-600">/</span>
            <span className="text-sm text-emerald-400">Bookmakers</span>
          </div>
          
          <h1 className="text-3xl sm:text-4xl md:text-5xl font-bold mb-4 sm:mb-6">Recommended Bookmakers</h1>
          <p className="text-base sm:text-lg text-slate-300 max-w-3xl leading-relaxed">
            Where to place your bets. We recommend bookmakers based on market coverage, odds quality, betting limits, and account management. These are the bookmakers we use ourselves.
          </p>
        </div>
      </section>

      {/* Player Props Recommendations */}
      <section className="py-16 border-b border-slate-800/50">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex items-center gap-2 mb-6">
            <span className="text-xs font-mono text-emerald-400 tracking-wider">PLAYER PROPS</span>
          </div>
          
          <h2 className="text-2xl sm:text-3xl font-bold mb-4 sm:mb-6 flex items-center gap-3">
            <span className="text-3xl sm:text-4xl">⚽</span>
            Best Bookmakers for Player Props
          </h2>
          <p className="text-base text-slate-300 mb-8 sm:mb-10 max-w-2xl">
            Player props require bookmakers with wide market coverage and competitive odds. These are our top recommendations.
          </p>

          <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-6">
            {recommendations.props.map((rec) => {
              const dbBookmaker = getBookmakerFromDb(rec.short_name);
              return (
                <div key={rec.id} className="bg-slate-900/60 rounded-xl border border-slate-800/50 p-6 hover:border-slate-700 transition-all">
                  <div className="flex items-center justify-between mb-4">
                    <div className="flex items-center gap-3">
                      <BookmakerLogo 
                        bookmaker={dbBookmaker || { id: 0, name: rec.name, short_name: rec.short_name, affiliate_link: null, active: true }}
                        size="md"
                      />
                      <h3 className="font-semibold text-lg">{rec.name}</h3>
                    </div>
                    <div className="flex items-center gap-1">
                      {[...Array(5)].map((_, i) => (
                        <svg key={i} className={`w-4 h-4 ${i < rec.rating ? 'text-emerald-400' : 'text-slate-700'}`} fill="currentColor" viewBox="0 0 20 20">
                          <path d="M9.049 2.927c.3-.921 1.603-.921 1.902 0l1.07 3.292a1 1 0 00.95.69h3.462c.969 0 1.371 1.24.588 1.81l-2.8 2.034a1 1 0 00-.364 1.118l1.07 3.292c.3.921-.755 1.688-1.54 1.118l-2.8-2.034a1 1 0 00-1.175 0l-2.8 2.034c-.784.57-1.838-.197-1.539-1.118l1.07-3.292a1 1 0 00-.364-1.118L2.98 8.72c-.783-.57-.38-1.81.588-1.81h3.461a1 1 0 00.951-.69l1.07-3.292z" />
                        </svg>
                      ))}
                    </div>
                  </div>
                  
                  <div className="mb-4">
                    <span className="text-xs font-mono text-emerald-400 mb-2 block">BEST FOR</span>
                    <div className="flex flex-wrap gap-2">
                      {rec.bestFor.map((item, i) => (
                        <span key={i} className="text-xs bg-emerald-500/10 text-emerald-400 px-2 py-1 rounded border border-emerald-500/20">
                          {item}
                        </span>
                      ))}
                    </div>
                  </div>

                  <div className="space-y-3 mb-4">
                    <div>
                      <span className="text-xs text-slate-500 mb-1 block">Pros</span>
                      <ul className="space-y-1">
                        {rec.pros.map((pro, i) => (
                          <li key={i} className="text-sm text-slate-300 flex items-start gap-2">
                            <span className="text-emerald-400 mt-1">✓</span>
                            <span>{pro}</span>
                          </li>
                        ))}
                      </ul>
                    </div>
                    {rec.cons && rec.cons.length > 0 && (
                      <div>
                        <span className="text-xs text-slate-500 mb-1 block">Cons</span>
                        <ul className="space-y-1">
                          {rec.cons.map((con, i) => (
                            <li key={i} className="text-sm text-slate-400 flex items-start gap-2">
                              <span className="text-red-400 mt-1">×</span>
                              <span>{con}</span>
                            </li>
                          ))}
                        </ul>
                      </div>
                    )}
                  </div>

                  {rec.notes && (
                    <div className="mt-4 pt-4 border-t border-slate-800/50">
                      <p className="text-xs text-slate-400 italic">{rec.notes}</p>
                    </div>
                  )}

                  {dbBookmaker?.affiliate_link && (
                    <a
                      href={dbBookmaker.affiliate_link}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="mt-4 block w-full bg-emerald-500 hover:bg-emerald-400 text-black font-medium px-4 py-2.5 rounded-lg text-center transition-colors"
                    >
                      Visit {rec.name}
                    </a>
                  )}
                </div>
              );
            })}
          </div>
        </div>
      </section>

      {/* Tennis Recommendations */}
      <section className="py-16 border-b border-slate-800/50">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex items-center gap-2 mb-6">
            <span className="text-xs font-mono text-emerald-400 tracking-wider">TENNIS</span>
          </div>
          
          <h2 className="text-2xl sm:text-3xl font-bold mb-4 sm:mb-6 flex items-center gap-3">
            <span className="text-3xl sm:text-4xl">🎾</span>
            Best Bookmakers for Tennis
          </h2>
          <p className="text-base text-slate-300 mb-8 sm:mb-10 max-w-2xl">
            Tennis betting requires sharp odds and good market depth. These bookmakers excel in tennis markets.
          </p>

          <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-6">
            {recommendations.tennis.map((rec) => {
              const dbBookmaker = getBookmakerFromDb(rec.short_name);
              return (
                <div key={rec.id} className="bg-slate-900/60 rounded-xl border border-slate-800/50 p-6 hover:border-slate-700 transition-all">
                  <div className="flex items-center justify-between mb-4">
                    <div className="flex items-center gap-3">
                      <BookmakerLogo 
                        bookmaker={dbBookmaker || { id: 0, name: rec.name, short_name: rec.short_name, affiliate_link: null, active: true }}
                        size="md"
                      />
                      <h3 className="font-semibold text-lg">{rec.name}</h3>
                    </div>
                    <div className="flex items-center gap-1">
                      {[...Array(5)].map((_, i) => (
                        <svg key={i} className={`w-4 h-4 ${i < rec.rating ? 'text-emerald-400' : 'text-slate-700'}`} fill="currentColor" viewBox="0 0 20 20">
                          <path d="M9.049 2.927c.3-.921 1.603-.921 1.902 0l1.07 3.292a1 1 0 00.95.69h3.462c.969 0 1.371 1.24.588 1.81l-2.8 2.034a1 1 0 00-.364 1.118l1.07 3.292c.3.921-.755 1.688-1.54 1.118l-2.8-2.034a1 1 0 00-1.175 0l-2.8 2.034c-.784.57-1.838-.197-1.539-1.118l1.07-3.292a1 1 0 00-.364-1.118L2.98 8.72c-.783-.57-.38-1.81.588-1.81h3.461a1 1 0 00.951-.69l1.07-3.292z" />
                        </svg>
                      ))}
                    </div>
                  </div>
                  
                  <div className="mb-4">
                    <span className="text-xs font-mono text-emerald-400 mb-2 block">BEST FOR</span>
                    <div className="flex flex-wrap gap-2">
                      {rec.bestFor.map((item, i) => (
                        <span key={i} className="text-xs bg-emerald-500/10 text-emerald-400 px-2 py-1 rounded border border-emerald-500/20">
                          {item}
                        </span>
                      ))}
                    </div>
                  </div>

                  <div className="space-y-3 mb-4">
                    <div>
                      <span className="text-xs text-slate-500 mb-1 block">Pros</span>
                      <ul className="space-y-1">
                        {rec.pros.map((pro, i) => (
                          <li key={i} className="text-sm text-slate-300 flex items-start gap-2">
                            <span className="text-emerald-400 mt-1">✓</span>
                            <span>{pro}</span>
                          </li>
                        ))}
                      </ul>
                    </div>
                    {rec.cons && rec.cons.length > 0 && (
                      <div>
                        <span className="text-xs text-slate-500 mb-1 block">Cons</span>
                        <ul className="space-y-1">
                          {rec.cons.map((con, i) => (
                            <li key={i} className="text-sm text-slate-400 flex items-start gap-2">
                              <span className="text-red-400 mt-1">×</span>
                              <span>{con}</span>
                            </li>
                          ))}
                        </ul>
                      </div>
                    )}
                  </div>

                  {rec.notes && (
                    <div className="mt-4 pt-4 border-t border-slate-800/50">
                      <p className="text-xs text-slate-400 italic">{rec.notes}</p>
                    </div>
                  )}

                  {dbBookmaker?.affiliate_link && (
                    <a
                      href={dbBookmaker.affiliate_link}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="mt-4 block w-full bg-emerald-500 hover:bg-emerald-400 text-black font-medium px-4 py-2.5 rounded-lg text-center transition-colors"
                    >
                      Visit {rec.name}
                    </a>
                  )}
                </div>
              );
            })}
          </div>
        </div>
      </section>

      {/* New Account Offers Section */}
      <section className="py-16 border-b border-slate-800/50 bg-slate-900/20">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex items-center gap-2 mb-6">
            <span className="text-xs font-mono text-emerald-400 tracking-wider">NEW ACCOUNTS</span>
          </div>
          
          <h2 className="text-2xl sm:text-3xl font-bold mb-4 sm:mb-6 flex items-center gap-3">
            <span className="text-3xl sm:text-4xl">💰</span>
            New Account Offers
          </h2>
          <p className="text-base text-slate-300 mb-8 sm:mb-10 max-w-2xl">
            Opening a new betting account? Check the latest welcome offers and promotions from our recommended bookmakers.
          </p>

          <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-6">
            {(() => {
              const offers: NewAccountOffer[] = [
                {
                  id: "bet365",
                  bookmaker: "bet365",
                  short_name: "bet365",
                  offer: "Bet £10 Get £30",
                  description: "New customers only. Place a qualifying bet of £10 to receive £30 in free bets. Free bets credited as 3x £10 bets.",
                  terms: "18+. New customers only. Min deposit £5. Bet credits available for use upon settlement of bets to value of qualifying deposit. Min odds, bet and payment method exclusions apply. Returns exclude Bet Credits stake. T&Cs, time limits & exclusions apply.",
                },
                {
                  id: "betfair",
                  bookmaker: "Betfair",
                  short_name: "Betfair",
                  offer: "Up to £100 in Free Bets",
                  description: "New customers only. Get up to £100 in free bets when you place your first bet. Free bets credited based on stake amount.",
                  terms: "18+. New customers only. Min deposit £10. Free bets credited as bet credits. Min odds apply. T&Cs apply.",
                },
                {
                  id: "paddypower",
                  bookmaker: "Paddy Power",
                  short_name: "Paddy",
                  offer: "£20 Risk-Free Bet",
                  description: "New customers only. Place your first bet and if it loses, get your stake back as a free bet up to £20.",
                  terms: "18+. New customers only. Place your first bet on sportsbook markets and if it loses, get your stake back as a free bet. Max £20. T&Cs apply.",
                },
                {
                  id: "williamhill",
                  bookmaker: "William Hill",
                  short_name: "WH",
                  offer: "Bet £10 Get £40",
                  description: "New customers only. Place a qualifying bet of £10 to receive £40 in free bets. Free bets split as £30 sportsbook + £10 casino.",
                  terms: "18+. New customers only. Min deposit £10. Qualifying bet must be placed at odds of 1/1 or greater. Free bets credited as 2x £15 sportsbook + £10 casino. T&Cs apply.",
                },
                {
                  id: "skybet",
                  bookmaker: "Sky Bet",
                  short_name: "SkyBet",
                  offer: "Bet £5 Get £20",
                  description: "New customers only. Place a qualifying bet of £5 to receive £20 in free bets. No wagering requirements on free bets.",
                  terms: "18+. New customers only. Min deposit £5. Qualifying bet must be placed at odds of 1/1 or greater. Free bets credited as 4x £5 bets. T&Cs apply.",
                },
                {
                  id: "unibet",
                  bookmaker: "Unibet",
                  short_name: "Unibet",
                  offer: "£40 Welcome Bonus",
                  description: "New customers only. Get £40 in free bets when you deposit and bet £10. Free bets credited as 2x £20 bets.",
                  terms: "18+. New customers only. Min deposit £10. Qualifying bet must be placed at odds of 1/1 or greater. Free bets credited as 2x £20. T&Cs apply.",
                },
              ];

              return offers.map((offer) => {
                const dbBookmaker = getBookmakerFromDb(offer.short_name);
                return (
                  <div key={offer.id} className="bg-gradient-to-br from-slate-900/80 to-slate-800/60 rounded-xl border-2 border-emerald-500/30 p-6 hover:border-emerald-500/60 transition-all relative overflow-hidden">
                    {/* Decorative background elements */}
                    <div className="absolute top-0 right-0 w-32 h-32 bg-emerald-500/5 rounded-full blur-3xl -mr-16 -mt-16"></div>
                    <div className="absolute bottom-0 left-0 w-24 h-24 bg-amber-500/5 rounded-full blur-2xl -ml-12 -mb-12"></div>
                    
                    <div className="relative z-10">
                      <div className="flex items-center justify-between mb-4">
                        <div className="flex items-center gap-3">
                          <BookmakerLogo 
                            bookmaker={dbBookmaker || { id: 0, name: offer.bookmaker, short_name: offer.short_name, affiliate_link: null, active: true }}
                            size="md"
                          />
                          <h3 className="font-semibold text-lg">{offer.bookmaker}</h3>
                        </div>
                        <div className="text-3xl">🎁</div>
                      </div>
                      
                      <div className="mb-4">
                        <div className="flex items-center gap-2 mb-2">
                          <span className="text-2xl">💵</span>
                          <div className="text-2xl font-bold text-emerald-400">{offer.offer}</div>
                        </div>
                        <p className="text-sm text-slate-300 leading-relaxed">{offer.description}</p>
                      </div>

                      {offer.terms && (
                        <div className="mt-4 pt-4 border-t border-slate-800/50">
                          <p className="text-xs text-slate-500 leading-relaxed">{offer.terms}</p>
                        </div>
                      )}

                      {dbBookmaker?.affiliate_link ? (
                        <a
                          href={dbBookmaker.affiliate_link}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="mt-4 block w-full bg-gradient-to-r from-emerald-500 to-emerald-600 hover:from-emerald-400 hover:to-emerald-500 text-black font-bold px-4 py-3 rounded-lg text-center transition-all shadow-lg shadow-emerald-500/20 hover:shadow-emerald-500/40 flex items-center justify-center gap-2"
                        >
                          <span>🎉</span>
                          Claim Offer Now
                        </a>
                      ) : (
                        <button
                          disabled
                          className="mt-4 w-full bg-slate-800 text-slate-500 font-medium px-4 py-2.5 rounded-lg text-center cursor-not-allowed"
                        >
                          Offer Available
                        </button>
                      )}
                    </div>
                  </div>
                );
              });
            })()}
          </div>
        </div>
      </section>

      {/* Bet Builders Section */}
      <section className="py-16">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex items-center gap-2 mb-6">
            <span className="text-xs font-mono text-emerald-400 tracking-wider">BET BUILDERS</span>
          </div>
          
          <h2 className="text-2xl sm:text-3xl font-bold mb-4 sm:mb-6 flex items-center gap-3">
            <span className="text-3xl sm:text-4xl">🎯</span>
            Best Bookmakers for Bet Builders
          </h2>
          <p className="text-base text-slate-300 mb-8 sm:mb-10 max-w-2xl">
            Same-game combinations require flexible bet builder tools. These bookmakers offer the best builder interfaces.
          </p>

          <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-6">
            {recommendations.betbuilders.map((rec) => {
              const dbBookmaker = getBookmakerFromDb(rec.short_name);
              return (
                <div key={rec.id} className="bg-slate-900/60 rounded-xl border border-slate-800/50 p-6 hover:border-slate-700 transition-all">
                  <div className="flex items-center justify-between mb-4">
                    <div className="flex items-center gap-3">
                      <BookmakerLogo 
                        bookmaker={dbBookmaker || { id: 0, name: rec.name, short_name: rec.short_name, affiliate_link: null, active: true }}
                        size="md"
                      />
                      <h3 className="font-semibold text-lg">{rec.name}</h3>
                    </div>
                    <div className="flex items-center gap-1">
                      {[...Array(5)].map((_, i) => (
                        <svg key={i} className={`w-4 h-4 ${i < rec.rating ? 'text-emerald-400' : 'text-slate-700'}`} fill="currentColor" viewBox="0 0 20 20">
                          <path d="M9.049 2.927c.3-.921 1.603-.921 1.902 0l1.07 3.292a1 1 0 00.95.69h3.462c.969 0 1.371 1.24.588 1.81l-2.8 2.034a1 1 0 00-.364 1.118l1.07 3.292c.3.921-.755 1.688-1.54 1.118l-2.8-2.034a1 1 0 00-1.175 0l-2.8 2.034c-.784.57-1.838-.197-1.539-1.118l1.07-3.292a1 1 0 00-.364-1.118L2.98 8.72c-.783-.57-.38-1.81.588-1.81h3.461a1 1 0 00.951-.69l1.07-3.292z" />
                        </svg>
                      ))}
                    </div>
                  </div>
                  
                  <div className="mb-4">
                    <span className="text-xs font-mono text-emerald-400 mb-2 block">BEST FOR</span>
                    <div className="flex flex-wrap gap-2">
                      {rec.bestFor.map((item, i) => (
                        <span key={i} className="text-xs bg-emerald-500/10 text-emerald-400 px-2 py-1 rounded border border-emerald-500/20">
                          {item}
                        </span>
                      ))}
                    </div>
                  </div>

                  <div className="space-y-3 mb-4">
                    <div>
                      <span className="text-xs text-slate-500 mb-1 block">Pros</span>
                      <ul className="space-y-1">
                        {rec.pros.map((pro, i) => (
                          <li key={i} className="text-sm text-slate-300 flex items-start gap-2">
                            <span className="text-emerald-400 mt-1">✓</span>
                            <span>{pro}</span>
                          </li>
                        ))}
                      </ul>
                    </div>
                    {rec.cons && rec.cons.length > 0 && (
                      <div>
                        <span className="text-xs text-slate-500 mb-1 block">Cons</span>
                        <ul className="space-y-1">
                          {rec.cons.map((con, i) => (
                            <li key={i} className="text-sm text-slate-400 flex items-start gap-2">
                              <span className="text-red-400 mt-1">×</span>
                              <span>{con}</span>
                            </li>
                          ))}
                        </ul>
                      </div>
                    )}
                  </div>

                  {rec.notes && (
                    <div className="mt-4 pt-4 border-t border-slate-800/50">
                      <p className="text-xs text-slate-400 italic">{rec.notes}</p>
                    </div>
                  )}

                  {dbBookmaker?.affiliate_link && (
                    <a
                      href={dbBookmaker.affiliate_link}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="mt-4 block w-full bg-emerald-500 hover:bg-emerald-400 text-black font-medium px-4 py-2.5 rounded-lg text-center transition-colors"
                    >
                      Visit {rec.name}
                    </a>
                  )}
                </div>
              );
            })}
          </div>
        </div>
      </section>
    </div>
  );
}
