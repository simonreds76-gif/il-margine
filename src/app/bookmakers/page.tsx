"use client";

import { useState } from "react";
import Link from "next/link";
import Image from "next/image";
import BookmakerLogo from "@/components/BookmakerLogo";
import { supabase, Bookmaker } from "@/lib/supabase";
import { useEffect } from "react";

interface BookmakerRecommendation {
  id: string;
  name: string;
  short_name: string;
  bestFor: string[];
  pros: string[];
  cons?: string[];
  rating: number;
  minOdds?: string;
  maxStake?: string;
  notes?: string;
}

export default function Bookmakers() {
  const [bookmakers, setBookmakers] = useState<Bookmaker[]>([]);
  const [loading, setLoading] = useState(true);
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);

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
        minOdds: "1.50",
        maxStake: "High",
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
        minOdds: "1.01",
        maxStake: "Market dependent",
        notes: "Essential for serious bettors. Exchange odds often beat traditional bookmakers.",
      },
      {
        id: "pinnacle",
        name: "Pinnacle",
        short_name: "Pinnacle",
        bestFor: ["Sharp Odds", "No Limits", "Professional Bettors"],
        pros: [
          "Sharpest odds in the industry",
          "No betting limits or restrictions",
          "Welcomes winning players",
          "Low margins",
        ],
        cons: ["Limited prop markets compared to bet365", "Requires larger stakes for value"],
        rating: 5,
        minOdds: "1.74",
        maxStake: "Unlimited",
        notes: "The sharpest bookmaker. Essential for serious players, though prop coverage is limited.",
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
        minOdds: "1.50",
        maxStake: "High",
        notes: "Best overall for tennis betting. Excellent market depth and competitive pricing.",
      },
      {
        id: "pinnacle",
        name: "Pinnacle",
        short_name: "Pinnacle",
        bestFor: ["Sharp Odds", "No Restrictions", "Professional Play"],
        pros: [
          "Sharpest tennis odds available",
          "No account restrictions",
          "Welcomes professional bettors",
          "Low margins on all markets",
        ],
        cons: ["Limited live betting options", "Requires larger stakes"],
        rating: 5,
        minOdds: "1.74",
        maxStake: "Unlimited",
        notes: "Essential for serious tennis bettors. Sharpest odds, no restrictions.",
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
        minOdds: "1.01",
        maxStake: "Market dependent",
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
      {/* Nav */}
      <nav className="border-b border-slate-800/80 sticky top-0 z-50 bg-[#0f1117]/95 backdrop-blur-sm">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex items-center justify-between h-16">
            <Link href="/" className="flex items-center">
              <Image src="/logo.png" alt="Il Margine" width={180} height={50} className="h-11 md:h-12 w-auto" style={{ background: 'transparent' }} />
            </Link>
            
            <button
              onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
              className="md:hidden p-2 text-slate-400 hover:text-slate-100 transition-colors"
              aria-label="Toggle menu"
            >
              <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                {mobileMenuOpen ? (
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                ) : (
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 12h16M4 18h16" />
                )}
              </svg>
            </button>
            
            <div className="hidden md:flex items-center gap-6">
              <Link href="/" className="text-sm text-slate-400 hover:text-slate-100 transition-colors">Home</Link>
              <Link href="/player-props" className="text-sm text-slate-400 hover:text-slate-100 transition-colors">Player Props</Link>
              <Link href="/atp-tennis" className="text-sm text-slate-400 hover:text-slate-100 transition-colors">ATP Tennis</Link>
              <Link href="/bookmakers" className="text-sm text-emerald-400 font-medium">Bookmakers</Link>
              <Link href="/calculator" className="text-sm text-slate-400 hover:text-slate-100 transition-colors">Calculator</Link>
            </div>
          </div>
          
          {mobileMenuOpen && (
            <div className="md:hidden border-t border-slate-800/50 py-4 space-y-3">
              <Link href="/" className="block px-4 py-2 text-sm text-slate-300 hover:text-emerald-400 hover:bg-emerald-500/10 rounded transition-colors">Home</Link>
              <Link href="/player-props" className="block px-4 py-2 text-sm text-slate-300 hover:text-emerald-400 hover:bg-emerald-500/10 rounded transition-colors">Player Props</Link>
              <Link href="/atp-tennis" className="block px-4 py-2 text-sm text-slate-300 hover:text-emerald-400 hover:bg-emerald-500/10 rounded transition-colors">ATP Tennis</Link>
              <Link href="/bookmakers" className="block px-4 py-2 text-sm text-emerald-400 font-medium hover:bg-emerald-500/10 rounded transition-colors">Bookmakers</Link>
              <Link href="/calculator" className="block px-4 py-2 text-sm text-slate-300 hover:text-emerald-400 hover:bg-emerald-500/10 rounded transition-colors">Calculator</Link>
            </div>
          )}
        </div>
      </nav>

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
          
          <h2 className="text-2xl sm:text-3xl font-bold mb-4 sm:mb-6">Best Bookmakers for Player Props</h2>
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

                  {rec.minOdds && rec.maxStake && (
                    <div className="mt-4 pt-4 border-t border-slate-800/50 flex gap-4 text-xs">
                      <div>
                        <span className="text-slate-500">Min Odds:</span>
                        <span className="text-slate-300 ml-2 font-mono">{rec.minOdds}</span>
                      </div>
                      <div>
                        <span className="text-slate-500">Max Stake:</span>
                        <span className="text-slate-300 ml-2">{rec.maxStake}</span>
                      </div>
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
          
          <h2 className="text-2xl sm:text-3xl font-bold mb-4 sm:mb-6">Best Bookmakers for Tennis</h2>
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

                  {rec.minOdds && rec.maxStake && (
                    <div className="mt-4 pt-4 border-t border-slate-800/50 flex gap-4 text-xs">
                      <div>
                        <span className="text-slate-500">Min Odds:</span>
                        <span className="text-slate-300 ml-2 font-mono">{rec.minOdds}</span>
                      </div>
                      <div>
                        <span className="text-slate-500">Max Stake:</span>
                        <span className="text-slate-300 ml-2">{rec.maxStake}</span>
                      </div>
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

      {/* Bet Builders Section */}
      <section className="py-16">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex items-center gap-2 mb-6">
            <span className="text-xs font-mono text-emerald-400 tracking-wider">BET BUILDERS</span>
          </div>
          
          <h2 className="text-2xl sm:text-3xl font-bold mb-4 sm:mb-6">Best Bookmakers for Bet Builders</h2>
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
