"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import Image from "next/image";
import { supabase, MarketStats } from "@/lib/supabase";
import { BASELINE_STATS, calculateROI, calculateWinRate } from "@/lib/baseline";
import { TELEGRAM_CHANNEL_URL } from "@/lib/config";
import BookmakerLogo from "@/components/BookmakerLogo";

interface CombinedMarketStats {
  total_bets: number;
  roi: number;
  win_rate: number;
  avg_odds: number;
  total_profit: number;
}

export default function Home() {
  const [activeMarket, setActiveMarket] = useState("props");
  const [tipsMenuOpen, setTipsMenuOpen] = useState(false);
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const [loading, setLoading] = useState(true);
  const [marketStats, setMarketStats] = useState<MarketStats[]>([]);
  const [recentBets, setRecentBets] = useState<any[]>([]);
  const [combinedStats, setCombinedStats] = useState<{
    props: CombinedMarketStats;
    tennis: CombinedMarketStats;
    overall: CombinedMarketStats;
  } | null>(null);

  // Fetch live data from database
  useEffect(() => {
    fetchData();

    // Set up real-time subscription to update when bets change
    const channel = supabase
      .channel('bets-changes')
      .on(
        'postgres_changes',
        {
          event: '*', // Listen to all events (INSERT, UPDATE, DELETE)
          schema: 'public',
          table: 'bets'
        },
        (payload) => {
          // When any bet is added, updated, or deleted, refresh the data
          console.log('Bet changed:', payload.eventType);
          fetchData();
        }
      )
      .subscribe();

    // Cleanup subscription on unmount
    return () => {
      supabase.removeChannel(channel);
    };
  }, []);

  const fetchData = async () => {
    setLoading(true);
    
    // Fetch market stats
    const { data: stats, error: statsError } = await supabase
      .from("market_stats")
      .select("*");
    
    if (stats) setMarketStats(stats);
    if (statsError) console.error("Error fetching market stats:", statsError);

    // Fetch recent settled bets (last 4-6 for homepage)
    const { data: recent, error: recentError } = await supabase
      .from("bets")
      .select("*, bookmaker:bookmakers(*)")
      .in("status", ["won", "lost"])
      .order("settled_at", { ascending: false })
      .limit(6);
    
    if (recent) setRecentBets(recent);
    if (recentError) console.error("Error fetching recent bets:", recentError);

    // Calculate combined stats - always call this, even if stats is empty
    // It will use baseline values when there's no live data
    calculateCombinedStats(stats || []);
    
    setLoading(false);
  };

  const calculateCombinedStats = (liveStats: MarketStats[]) => {
    const propsLive = liveStats.find(s => s.market === "props");
    const tennisLive = liveStats.find(s => s.market === "tennis");

    // Combine Player Props
    const propsLiveBets = propsLive?.total_bets || 0;
    const propsLiveWins = propsLive?.wins || 0;
    const propsLiveLosses = propsLive?.losses || 0;
    const propsLiveProfit = Number(propsLive?.total_profit) || 0;
    // Estimate stake from bets (assuming avg 1u per bet if no stake data)
    const propsLiveStake = propsLiveBets;
    
    const propsCombined: CombinedMarketStats = {
      total_bets: BASELINE_STATS.props.total_bets + propsLiveBets,
      roi: 0,
      win_rate: 0,
      avg_odds: 0,
      total_profit: 0,
    };
    
    const propsWins = BASELINE_STATS.props.wins + propsLiveWins;
    const propsLosses = BASELINE_STATS.props.losses + propsLiveLosses;
    const propsProfit = BASELINE_STATS.props.total_profit + propsLiveProfit;
    const propsStake = BASELINE_STATS.props.total_stake + (propsLiveStake || propsLiveBets); // Fallback to bet count if no stake data
    
    propsCombined.win_rate = calculateWinRate(propsWins, propsLosses);
    propsCombined.roi = calculateROI(propsProfit, propsStake || 1);
    propsCombined.total_profit = propsProfit;
    
    // Calculate weighted average odds
    if (propsLive?.avg_odds && propsLiveBets > 0) {
      // Baseline doesn't have avg_odds, so we'll use live avg_odds as approximation
      // Or calculate from baseline ROI if we had that data
      propsCombined.avg_odds = Number(propsLive.avg_odds);
    } else {
      // If no live data, we can't calculate combined avg_odds accurately
      // Use a placeholder or estimate from ROI
      propsCombined.avg_odds = 0;
    }

    // Combine ATP Tennis
    const tennisLiveBets = tennisLive?.total_bets || 0;
    const tennisLiveWins = tennisLive?.wins || 0;
    const tennisLiveLosses = tennisLive?.losses || 0;
    const tennisLiveProfit = Number(tennisLive?.total_profit) || 0;
    // Estimate stake from bets (assuming avg 1u per bet if no stake data)
    const tennisLiveStake = tennisLiveBets;
    
    const tennisCombined: CombinedMarketStats = {
      total_bets: BASELINE_STATS.tennis.total_bets + tennisLiveBets,
      roi: 0,
      win_rate: 0,
      avg_odds: 0,
      total_profit: 0,
    };
    
    const tennisWins = BASELINE_STATS.tennis.wins + tennisLiveWins;
    const tennisLosses = BASELINE_STATS.tennis.losses + tennisLiveLosses;
    const tennisProfit = BASELINE_STATS.tennis.total_profit + tennisLiveProfit;
    const tennisStake = BASELINE_STATS.tennis.total_stake + (tennisLiveStake || tennisLiveBets);
    
    tennisCombined.win_rate = calculateWinRate(tennisWins, tennisLosses);
    tennisCombined.roi = calculateROI(tennisProfit, tennisStake || 1);
    tennisCombined.total_profit = tennisProfit;
    
    if (tennisLive?.avg_odds && tennisLiveBets > 0) {
      tennisCombined.avg_odds = Number(tennisLive.avg_odds);
    } else {
      tennisCombined.avg_odds = 0;
    }

    // Combine Overall - Use baseline overall stats directly, then add live data from both markets
    const overallLiveBets = propsLiveBets + tennisLiveBets;
    const overallLiveWins = propsLiveWins + tennisLiveWins;
    const overallLiveLosses = propsLiveLosses + tennisLiveLosses;
    const overallLiveProfit = propsLiveProfit + tennisLiveProfit;
    const overallLiveStake = (propsLiveStake || propsLiveBets) + (tennisLiveStake || tennisLiveBets);
    
    const overallCombined: CombinedMarketStats = {
      total_bets: BASELINE_STATS.overall.total_bets + overallLiveBets,
      roi: 0,
      win_rate: 0,
      avg_odds: 0,
      total_profit: 0,
    };
    
    // Combine baseline overall with live data from both markets
    const overallWins = BASELINE_STATS.overall.wins + overallLiveWins;
    const overallLosses = BASELINE_STATS.overall.losses + overallLiveLosses;
    const overallProfit = BASELINE_STATS.overall.total_profit + overallLiveProfit;
    const overallStake = BASELINE_STATS.overall.total_stake + overallLiveStake;
    
    overallCombined.win_rate = calculateWinRate(overallWins, overallLosses);
    overallCombined.roi = calculateROI(overallProfit, overallStake || 1);
    overallCombined.total_profit = overallProfit;
    
    // Weighted average odds across markets
    if (propsCombined.avg_odds > 0 || tennisCombined.avg_odds > 0) {
      const totalOddsWeight = (propsCombined.avg_odds * propsCombined.total_bets) + 
                             (tennisCombined.avg_odds * tennisCombined.total_bets);
      overallCombined.avg_odds = overallCombined.total_bets > 0 
        ? totalOddsWeight / overallCombined.total_bets
        : 0;
    }

    setCombinedStats({
      props: propsCombined,
      tennis: tennisCombined,
      overall: overallCombined,
    });
  };

  // Calculate last 7 days profit from recent bets
  const last7DaysProfit = recentBets
    .filter(bet => {
      if (!bet.settled_at) return false;
      const settledDate = new Date(bet.settled_at);
      const sevenDaysAgo = new Date();
      sevenDaysAgo.setDate(sevenDaysAgo.getDate() - 7);
      return settledDate >= sevenDaysAgo;
    })
    .reduce((sum, bet) => sum + (Number(bet.profit_loss) || 0), 0);

  const markets = [
    { 
      id: "props", 
      name: "Player Props", 
      description: "Football individual player markets", 
      status: "active", 
      bets: combinedStats ? `${combinedStats.props.total_bets}+` : "780+", 
      profit: combinedStats ? `${combinedStats.props.roi > 0 ? "+" : ""}${combinedStats.props.roi.toFixed(1)}% ROI` : "+25% ROI" 
    },
    { 
      id: "atp", 
      name: "ATP Tennis", 
      description: "Pre-match singles markets", 
      status: "active", 
      bets: combinedStats ? `${combinedStats.tennis.total_bets}` : "447", 
      profit: combinedStats ? `${combinedStats.tennis.roi > 0 ? "+" : ""}${combinedStats.tennis.roi.toFixed(1)}% ROI` : "+8.6% ROI" 
    },
    { id: "builders", name: "Bet Builders", description: "Same-game combinations", status: "coming" },
    { id: "atg", name: "ATG", description: "Anytime goalscorer markets", status: "coming" },
  ];

  return (
    <div className="min-h-screen bg-[#0f1117] text-slate-100">
      {/* Nav */}
      <nav className="border-b border-slate-800/80 sticky top-0 z-50 bg-[#0f1117]/95 backdrop-blur-sm">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex items-center justify-between h-16">
            <Link href="/" className="flex items-center">
              <Image src="/logo.png" alt="Il Margine" width={180} height={50} className="h-11 md:h-12 w-auto" style={{ background: 'transparent' }} />
            </Link>
            
            {/* Mobile Menu Button */}
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
              {/* Tips Dropdown */}
              <div className="relative">
                <button 
                  onClick={() => setTipsMenuOpen(!tipsMenuOpen)}
                  onBlur={() => setTimeout(() => setTipsMenuOpen(false), 150)}
                  className="text-sm text-slate-400 hover:text-slate-100 transition-colors flex items-center gap-1"
                >
                  Tips
                  <svg className={`w-4 h-4 transition-transform ${tipsMenuOpen ? 'rotate-180' : ''}`} fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                  </svg>
                </button>
                
                {tipsMenuOpen && (
                  <div className="absolute top-full left-0 mt-2 w-64 bg-slate-900/95 backdrop-blur-sm border border-slate-800 rounded-xl shadow-2xl overflow-hidden z-50">
                    <Link 
                      href="/player-props" 
                      className="group block px-4 py-4 hover:bg-emerald-500/10 transition-all duration-300 border-b border-slate-800/50"
                    >
                      <div className="flex items-center justify-between">
                        <div>
                          <span className="font-medium text-slate-200 group-hover:text-emerald-400 transition-colors">Player Props</span>
                          <span className="block text-xs text-slate-500 mt-0.5">Football • Shots, Tackles, Fouls</span>
                        </div>
                        <div className="w-12 h-8 relative overflow-hidden">
                          <svg className="w-full h-full" viewBox="0 0 48 32">
                            <path 
                              d="M0 28 L12 20 L24 24 L36 12 L48 8" 
                              fill="none" 
                              stroke="currentColor" 
                              strokeWidth="2"
                              className="text-slate-700 group-hover:text-emerald-500/50 transition-colors duration-300"
                            />
                            <path 
                              d="M0 28 L12 20 L24 24 L36 12 L48 8" 
                              fill="none" 
                              stroke="currentColor" 
                              strokeWidth="2"
                              className="text-transparent group-hover:text-emerald-400 transition-all duration-500"
                              strokeDasharray="100"
                              strokeDashoffset="100"
                              style={{ animation: tipsMenuOpen ? 'none' : 'none' }}
                            />
                            <circle cx="48" cy="8" r="3" className="fill-slate-700 group-hover:fill-emerald-400 transition-colors duration-300" />
                          </svg>
                        </div>
                      </div>
                      <div className="flex items-center gap-3 mt-2">
                        <span className={`text-xs font-mono ${combinedStats ? (combinedStats.props.roi >= 0 ? 'text-emerald-400' : 'text-red-400') : 'text-emerald-400'}`}>
                          {combinedStats ? `${combinedStats.props.roi >= 0 ? "+" : ""}${combinedStats.props.roi.toFixed(1)}% ROI` : "+25% ROI"}
                        </span>
                        <span className="text-xs text-slate-500">
                          {combinedStats ? `${combinedStats.props.total_bets}+ bets` : "780+ bets"}
                        </span>
                        {combinedStats && (
                          <span className={`text-xs font-mono ${combinedStats.props.total_profit >= 0 ? 'text-emerald-400' : 'text-red-400'}`}>
                            {combinedStats.props.total_profit >= 0 ? '+' : ''}{combinedStats.props.total_profit.toFixed(1)}u
                          </span>
                        )}
                      </div>
                    </Link>
                    
                    <Link 
                      href="/tennis-tips" 
                      className="group block px-4 py-4 hover:bg-emerald-500/10 transition-all duration-300 border-b border-slate-800/50"
                    >
                      <div className="flex items-center justify-between">
                        <div>
                          <span className="font-medium text-slate-200 group-hover:text-emerald-400 transition-colors">Tennis Tips</span>
                          <span className="block text-xs text-slate-500 mt-0.5">Pre-match • Handicaps, Totals</span>
                        </div>
                        <div className="w-12 h-8 relative overflow-hidden">
                          <svg className="w-full h-full" viewBox="0 0 48 32">
                            <path 
                              d="M0 24 L16 22 L32 16 L48 10" 
                              fill="none" 
                              stroke="currentColor" 
                              strokeWidth="2"
                              className="text-slate-700 group-hover:text-emerald-500/50 transition-colors duration-300"
                            />
                            <circle cx="48" cy="10" r="3" className="fill-slate-700 group-hover:fill-emerald-400 transition-colors duration-300" />
                          </svg>
                        </div>
                      </div>
                      <div className="flex items-center gap-3 mt-2">
                        <span className={`text-xs font-mono ${combinedStats ? (combinedStats.tennis.roi >= 0 ? 'text-emerald-400' : 'text-red-400') : 'text-emerald-400'}`}>
                          {combinedStats ? `${combinedStats.tennis.roi >= 0 ? "+" : ""}${combinedStats.tennis.roi.toFixed(1)}% ROI` : "+8.6% ROI"}
                        </span>
                        <span className="text-xs text-slate-500">
                          {combinedStats ? `${combinedStats.tennis.total_bets} bets` : "447 bets"}
                        </span>
                        {combinedStats && (
                          <span className={`text-xs font-mono ${combinedStats.tennis.total_profit >= 0 ? 'text-emerald-400' : 'text-red-400'}`}>
                            {combinedStats.tennis.total_profit >= 0 ? '+' : ''}{combinedStats.tennis.total_profit.toFixed(1)}u
                          </span>
                        )}
                      </div>
                    </Link>
                    
                    <Link 
                      href="/anytime-goalscorer" 
                      className="group block px-4 py-4 hover:bg-emerald-500/10 transition-all duration-300 border-b border-slate-800/50"
                    >
                      <div className="flex items-center justify-between">
                        <div>
                          <span className="font-medium text-slate-200 group-hover:text-emerald-400 transition-colors">Anytime Goalscorer</span>
                          <span className="block text-xs text-slate-500 mt-0.5">Scoring markets • xG analysis</span>
                        </div>
                      </div>
                    </Link>
                    
                    <Link 
                      href="/bet-builders" 
                      className="group block px-4 py-4 hover:bg-emerald-500/10 transition-all duration-300"
                    >
                      <div className="flex items-center justify-between">
                        <div>
                          <span className="font-medium text-slate-200 group-hover:text-emerald-400 transition-colors">Bet Builders</span>
                          <span className="block text-xs text-slate-500 mt-0.5">Same-game combos</span>
                        </div>
                      </div>
                    </Link>
                  </div>
                )}
              </div>
              
              <a href="#the-edge" className="text-sm text-slate-400 hover:text-slate-100 transition-colors">The Edge</a>
              <a href="#track-record" className="text-sm text-slate-400 hover:text-slate-100 transition-colors">Track Record</a>
              <Link href="/bookmakers" className="text-sm text-slate-400 hover:text-slate-100 transition-colors">Bookmakers</Link>
              <Link href="/calculator" className="text-sm text-slate-400 hover:text-slate-100 transition-colors">Calculator</Link>
              <a 
                href={TELEGRAM_CHANNEL_URL}
                target="_blank"
                rel="noopener noreferrer"
                className="bg-emerald-500 hover:bg-emerald-400 text-black text-sm font-medium px-4 py-2 rounded transition-colors flex items-center gap-2"
              >
                <svg className="w-4 h-4" viewBox="0 0 24 24" fill="currentColor"><path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm4.64 6.8c-.15 1.58-.8 5.42-1.13 7.19-.14.75-.42 1-.68 1.03-.58.05-1.02-.38-1.58-.75-.88-.58-1.38-.94-2.23-1.5-.99-.65-.35-1.01.22-1.59.15-.15 2.71-2.48 2.76-2.69a.2.2 0 00-.05-.18c-.06-.05-.14-.03-.21-.02-.09.02-1.49.95-4.22 2.79-.4.27-.76.41-1.08.4-.36-.01-1.04-.2-1.55-.37-.63-.2-1.12-.31-1.08-.66.02-.18.27-.36.74-.55 2.92-1.27 4.86-2.11 5.83-2.51 2.78-1.16 3.35-1.36 3.73-1.36.08 0 .27.02.39.12.1.08.13.19.14.27-.01.06.01.24 0 .38z"/></svg>
                Join Free
              </a>
            </div>
          </div>
          
          {/* Mobile Menu */}
          {mobileMenuOpen && (
            <div className="md:hidden border-t border-slate-800/50 py-4 space-y-3">
              <Link href="/player-props" className="block px-4 py-2 text-sm text-slate-300 hover:text-emerald-400 hover:bg-emerald-500/10 rounded transition-colors">
                Player Props
              </Link>
              <Link href="/tennis-tips" className="block px-4 py-2 text-sm text-slate-300 hover:text-emerald-400 hover:bg-emerald-500/10 rounded transition-colors">
                Tennis Tips
              </Link>
              <Link href="/anytime-goalscorer" className="block px-4 py-2 text-sm text-slate-300 hover:text-emerald-400 hover:bg-emerald-500/10 rounded transition-colors">
                Anytime Goalscorer
              </Link>
              <Link href="/bet-builders" className="block px-4 py-2 text-sm text-slate-300 hover:text-emerald-400 hover:bg-emerald-500/10 rounded transition-colors">
                Bet Builders
              </Link>
              <a href="#the-edge" className="block px-4 py-2 text-sm text-slate-300 hover:text-emerald-400 hover:bg-emerald-500/10 rounded transition-colors">
                The Edge
              </a>
              <a href="#track-record" className="block px-4 py-2 text-sm text-slate-300 hover:text-emerald-400 hover:bg-emerald-500/10 rounded transition-colors">
                Track Record
              </a>
              <Link href="/bookmakers" className="block px-4 py-2 text-sm text-slate-300 hover:text-emerald-400 hover:bg-emerald-500/10 rounded transition-colors">
                Bookmakers
              </Link>
              <Link href="/calculator" className="block px-4 py-2 text-sm text-slate-300 hover:text-emerald-400 hover:bg-emerald-500/10 rounded transition-colors">
                Calculator
              </Link>
              <button className="w-full mt-4 bg-emerald-500 hover:bg-emerald-400 text-black text-sm font-medium px-4 py-2.5 rounded transition-colors flex items-center justify-center gap-2">
                <svg className="w-4 h-4" viewBox="0 0 24 24" fill="currentColor"><path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm4.64 6.8c-.15 1.58-.8 5.42-1.13 7.19-.14.75-.42 1-.68 1.03-.58.05-1.02-.38-1.58-.75-.88-.58-1.38-.94-2.23-1.5-.99-.65-.35-1.01.22-1.59.15-.15 2.71-2.48 2.76-2.69a.2.2 0 00-.05-.18c-.06-.05-.14-.03-.21-.02-.09.02-1.49.95-4.22 2.79-.4.27-.76.41-1.08.4-.36-.01-1.04-.2-1.55-.37-.63-.2-1.12-.31-1.08-.66.02-.18.27-.36.74-.55 2.92-1.27 4.86-2.11 5.83-2.51 2.78-1.16 3.35-1.36 3.73-1.36.08 0 .27.02.39.12.1.08.13.19.14.27-.01.06.01.24 0 .38z"/></svg>
                Join Free
              </button>
            </div>
          )}
        </div>
      </nav>

      {/* Hero */}
      <section className="py-16 md:py-24 border-b border-slate-800/50">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="max-w-4xl mx-auto text-center">
            <div className="flex items-center justify-center gap-2 mb-8">
              <span className="text-xs font-mono text-emerald-400 bg-emerald-500/10 px-3 py-1.5 rounded border border-emerald-500/20">FREE BETA</span>
            </div>
            
            <h1 className="text-4xl sm:text-5xl md:text-6xl font-bold mb-6 sm:mb-8 leading-tight tracking-tight">
              Betting with <span className="text-emerald-400">mathematical edge</span>
            </h1>
            
            <p className="text-lg sm:text-xl text-slate-300 mb-8 sm:mb-10 leading-relaxed max-w-2xl mx-auto">
              Professional betting methodology from a former odds compiler. We identify value where bookmakers misprice markets. Data-driven selections, transparent results.
            </p>
            
            <div className="flex flex-wrap justify-center gap-3 sm:gap-4 mb-12 sm:mb-16">
              <a 
                href={TELEGRAM_CHANNEL_URL}
                target="_blank"
                rel="noopener noreferrer"
                className="bg-emerald-500 hover:bg-emerald-400 text-black font-semibold px-6 sm:px-8 py-3 sm:py-3.5 rounded-lg text-base sm:text-lg flex items-center gap-2 transition-all hover:scale-105 shadow-lg shadow-emerald-500/20"
              >
                <svg className="w-5 h-5" viewBox="0 0 24 24" fill="currentColor"><path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm4.64 6.8c-.15 1.58-.8 5.42-1.13 7.19-.14.75-.42 1-.68 1.03-.58.05-1.02-.38-1.58-.75-.88-.58-1.38-.94-2.23-1.5-.99-.65-.35-1.01.22-1.59.15-.15 2.71-2.48 2.76-2.69a.2.2 0 00-.05-.18c-.06-.05-.14-.03-.21-.02-.09.02-1.49.95-4.22 2.79-.4.27-.76.41-1.08.4-.36-.01-1.04-.2-1.55-.37-.63-.2-1.12-.31-1.08-.66.02-.18.27-.36.74-.55 2.92-1.27 4.86-2.11 5.83-2.51 2.78-1.16 3.35-1.36 3.73-1.36.08 0 .27.02.39.12.1.08.13.19.14.27-.01.06.01.24 0 .38z"/></svg>
                Join Telegram Channel
              </a>
              <a href="#the-edge" className="border border-slate-600 hover:border-slate-400 text-slate-200 font-medium px-6 sm:px-8 py-3 sm:py-3.5 rounded-lg text-base sm:text-lg transition-all hover:bg-slate-800/50">
                How It Works
              </a>
            </div>
            
            <div className="flex flex-wrap justify-center gap-4 sm:gap-6 md:gap-8">
              <div className="p-5 sm:p-6 bg-slate-900/60 rounded-lg border border-slate-800/50 hover:border-emerald-500/30 transition-all">
                <div className="text-3xl font-bold text-emerald-400 font-mono mb-2">✓</div>
                <div className="text-sm text-slate-400 font-medium">Verified Edge</div>
              </div>
              <div className="p-5 sm:p-6 bg-slate-900/60 rounded-lg border border-slate-800/50 hover:border-emerald-500/30 transition-all">
                <div className="text-3xl font-bold text-emerald-400 font-mono mb-2">100%</div>
                <div className="text-sm text-slate-400 font-medium">Transparent</div>
              </div>
              <div className="p-5 sm:p-6 bg-slate-900/60 rounded-lg border border-slate-800/50 hover:border-emerald-500/30 transition-all">
                <div className="text-3xl font-bold text-emerald-400 font-mono mb-2">1,200+</div>
                <div className="text-sm text-slate-400 font-medium">Tracked Bets</div>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* Markets */}
      <section id="markets" className="py-20 border-b border-slate-800/50">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex items-center gap-2 mb-6">
            <span className="text-xs font-mono text-emerald-400 tracking-wider">MARKETS</span>
          </div>
          
          <h2 className="text-3xl sm:text-4xl font-bold mb-4 sm:mb-6">Where we find edge</h2>
          <p className="text-base sm:text-lg text-slate-300 mb-12 sm:mb-14 max-w-2xl">
            We focus on markets where bookmaker pricing is inefficient. No mainstream match odds. No markets where the bookies have perfect data.
          </p>

          <div className="grid md:grid-cols-2 lg:grid-cols-4 gap-4">
            {markets.map((market) => {
              const href = market.id === "props" ? "/player-props" : market.id === "atp" ? "/tennis-tips" : "";
              const isActive = market.status === "active";
              
              const cardContent = (
                <>
                  <div className="flex items-center justify-between mb-4">
                    <h3 className="font-semibold">{market.name}</h3>
                    {market.status === "coming" ? (
                      <span className="text-xs font-mono text-slate-600 bg-slate-800/50 px-2 py-0.5 rounded">SOON</span>
                    ) : (
                      <span className="text-xs font-mono text-emerald-400 bg-emerald-500/10 px-2 py-0.5 rounded">LIVE</span>
                    )}
                  </div>
                  <p className="text-sm text-slate-500 mb-4">{market.description}</p>
                  {market.status === "active" && (
                    <div className="flex gap-4 text-sm">
                      <span className="text-slate-400">{market.bets} bets</span>
                      <span className="text-emerald-400 font-mono">{market.profit}</span>
                    </div>
                  )}
                </>
              );
              
              const cardClass = `p-6 sm:p-8 rounded-xl border transition-all cursor-pointer block ${
                market.status === "coming"
                  ? "bg-slate-900/30 border-slate-800/50 opacity-60"
                  : activeMarket === market.id
                  ? "bg-slate-900/80 border-emerald-500/50 shadow-lg shadow-emerald-500/10"
                  : "bg-slate-900/60 border-slate-800/50 hover:border-slate-700 hover:bg-slate-900/70"
              }`;
              
              return isActive ? (
                <Link
                  key={market.id}
                  href={href}
                  className={cardClass}
                  onClick={() => setActiveMarket(market.id)}
                >
                  {cardContent}
                </Link>
              ) : (
                <div
                  key={market.id}
                  className={cardClass}
                >
                  {cardContent}
                </div>
              );
            })}
          </div>
        </div>
      </section>

      {/* Latest Results */}
      <section className="py-20 border-b border-slate-800/50 bg-slate-900/20">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 mb-8 sm:mb-10">
            <div>
              <span className="text-xs font-mono text-emerald-400 mb-3 block tracking-wider">LATEST RESULTS</span>
              <h2 className="text-2xl sm:text-3xl font-bold">Recent Selections</h2>
            </div>
            <div className="flex items-center gap-4">
              <span className="text-xs sm:text-sm text-emerald-400 font-mono">
                Last 7 days: {last7DaysProfit > 0 ? "+" : ""}{last7DaysProfit.toFixed(2)}u
              </span>
            </div>
          </div>
          
          {loading ? (
            <div className="grid md:grid-cols-2 lg:grid-cols-4 gap-4">
              {[1, 2, 3, 4].map((i) => (
                <div key={i} className="bg-slate-900/50 rounded-lg border border-slate-800 p-4 animate-pulse">
                  <div className="h-20 bg-slate-800/50 rounded"></div>
                </div>
              ))}
            </div>
          ) : recentBets.length > 0 ? (
            <div className="bg-slate-900/50 rounded-lg border border-slate-800 overflow-hidden">
              {/* Desktop Table */}
              <div className="hidden md:block overflow-x-auto -mx-4 sm:mx-0">
                <table className="w-full border-collapse min-w-full">
                  <thead>
                    <tr className="border-b border-slate-700 text-xs text-slate-500 uppercase bg-slate-900/50">
                      <th className="px-4 py-3 text-left border-r border-slate-800">Match</th>
                      <th className="px-4 py-3 text-left border-r border-slate-800" style={{ width: '80px' }}>Player</th>
                      <th className="px-4 py-3 text-left border-r border-slate-800">Selection</th>
                      <th className="px-4 py-3 text-center border-r border-slate-800" style={{ width: '70px' }}>Odds</th>
                      <th className="px-4 py-3 text-center border-r border-slate-800" style={{ width: '90px' }}>Bookmaker</th>
                      <th className="px-4 py-3 text-center border-r border-slate-800" style={{ width: '50px' }}>Stake</th>
                      <th className="px-4 py-3 text-center border-r border-slate-800" style={{ width: '70px' }}>Result</th>
                      <th className="px-4 py-3 text-right" style={{ width: '80px' }}>P/L</th>
                    </tr>
                  </thead>
                  <tbody>
                    {recentBets.slice(0, 5).map((bet) => {
                      const href = bet.market === "tennis" ? "/tennis-tips" : bet.market === "props" ? "/player-props" : "#";
                      return (
                        <tr 
                          key={bet.id} 
                          className="border-b border-slate-800/50 hover:bg-slate-800/30 cursor-pointer"
                          onClick={() => window.location.href = href}
                        >
                          <td className="px-4 py-3 font-medium text-slate-200 border-r border-slate-800/50">{bet.event}</td>
                          <td className="px-4 py-3 text-slate-300 border-r border-slate-800/50">{bet.player || '-'}</td>
                          <td className="px-4 py-3 text-slate-300 border-r border-slate-800/50">{bet.selection}</td>
                          <td className="px-4 py-3 text-center border-r border-slate-800/50">
                            <span className="font-mono text-slate-200">{bet.odds}</span>
                          </td>
                          <td className="px-4 py-3 text-center border-r border-slate-800/50">
                            <div className="flex justify-center">
                              <BookmakerLogo bookmaker={bet.bookmaker} size="sm" />
                            </div>
                          </td>
                          <td className="px-4 py-3 text-center font-mono text-slate-200 border-r border-slate-800/50">{bet.stake}u</td>
                          <td className="px-4 py-3 text-center border-r border-slate-800/50">
                            <span className={`text-xs font-mono px-2 py-1 rounded ${bet.status === "won" ? "text-emerald-400 bg-emerald-500/10" : "text-red-400 bg-red-500/10"}`}>
                              {bet.status.toUpperCase()}
                            </span>
                          </td>
                          <td className={`px-4 py-3 text-right font-mono font-medium ${bet.profit_loss && bet.profit_loss > 0 ? "text-emerald-400" : "text-red-400"}`}>
                            {bet.profit_loss && bet.profit_loss > 0 ? "+" : ""}{bet.profit_loss?.toFixed(2) || "0.00"}u
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
              {/* Mobile Cards */}
              <div className="md:hidden divide-y divide-slate-800/50">
                {recentBets.slice(0, 5).map((bet) => {
                  const href = bet.market === "tennis" ? "/atp-tennis" : bet.market === "props" ? "/player-props" : "#";
                  return (
                    <Link key={bet.id} href={href} className="block p-4 hover:bg-slate-800/20">
                      <div className="flex items-start justify-between mb-2">
                        <div className="flex-1">
                          <div className="font-medium text-slate-200 mb-1">{bet.event}</div>
                          <div className="text-sm text-slate-300 mb-1">
                            {bet.player && <span>{bet.player} • </span>}
                            {bet.selection}
                          </div>
                        </div>
                        <span className={`text-xs font-mono px-2 py-1 rounded ml-2 ${bet.status === "won" ? "text-emerald-400 bg-emerald-500/10" : "text-red-400 bg-red-500/10"}`}>
                          {bet.status.toUpperCase()}
                        </span>
                      </div>
                      <div className="flex items-center justify-between text-sm">
                        <div className="flex items-center gap-4">
                          <span className="font-mono text-slate-200">{bet.odds}</span>
                          <BookmakerLogo bookmaker={bet.bookmaker} size="sm" />
                          <span className="font-mono text-slate-200">{bet.stake}u</span>
                        </div>
                        <span className={`font-mono font-medium ${bet.profit_loss && bet.profit_loss > 0 ? "text-emerald-400" : "text-red-400"}`}>
                          {bet.profit_loss && bet.profit_loss > 0 ? "+" : ""}{bet.profit_loss?.toFixed(2)}u
                        </span>
                      </div>
                    </Link>
                  );
                })}
              </div>
            </div>
          ) : (
            <div className="bg-slate-900/30 rounded-lg border border-slate-800 p-8 text-center">
              <p className="text-slate-500">No recent results yet</p>
            </div>
          )}
          
          <div className="mt-6 flex justify-center gap-4">
            <Link href="/tennis-tips" className="text-sm text-slate-400 hover:text-emerald-400 transition-colors">
              View Tennis Tips Results →
            </Link>
            <Link href="/player-props" className="text-sm text-slate-400 hover:text-emerald-400 transition-colors">
              View Player Props Results →
            </Link>
          </div>
        </div>
      </section>

      {/* The Edge Section */}
      <section id="the-edge" className="py-20 border-b border-slate-800/50 relative overflow-hidden">
        {/* Faded Banner Background */}
        <div className="absolute inset-0 flex items-center justify-center opacity-[0.03] pointer-events-none">
          <Image 
            src="/banner.png" 
            alt="Il Margine" 
            width={1200} 
            height={400} 
            className="w-full max-w-6xl h-auto object-contain"
          />
        </div>
        
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 relative z-10">
          <div className="grid lg:grid-cols-2 gap-10 lg:gap-16 items-start">
            <div>
              <span className="text-xs font-mono text-emerald-400 mb-4 block tracking-wider">WHY IT WORKS</span>
              <h2 className="text-3xl sm:text-4xl font-bold mb-6 sm:mb-8">The Edge</h2>
              
              <div className="space-y-6 text-slate-300 leading-relaxed text-base">
                <p>
                  25 years in the betting industry. Former odds compiler. I&apos;ve worked on the other side, building the prices that bookmakers use. I know exactly where they cut corners and where value hides.
                </p>
                <p>
                  Every pick is backed by proprietary models that strip out bookmaker margin to find true odds. We only bet when the numbers say yes. No hunches. No tips from a mate. Pure mathematics.
                </p>
                <p>
                  The results speak for themselves. Over 1,200 tracked bets with consistent, verifiable profits across multiple markets.
                </p>
              </div>
              
              {/* Edge Calculation Example */}
              <div className="mt-8 bg-slate-900/50 rounded-lg border border-slate-800 p-6">
                <div className="flex items-center justify-between mb-6">
                  <span className="font-mono text-sm text-slate-400">HOW WE FIND EDGE</span>
                  <span className="text-[10px] font-mono text-slate-600 bg-slate-800 px-2 py-1 rounded">EXAMPLE</span>
                </div>
                
                <div className="space-y-3 font-mono text-sm">
                  <div className="flex justify-between items-center py-2 border-b border-slate-800/50">
                    <span className="text-slate-400">Bookmaker Odds</span>
                    <span className="text-slate-100">2.10</span>
                  </div>
                  <div className="flex justify-between items-center py-2 border-b border-slate-800/50">
                    <span className="text-slate-400">Implied Probability</span>
                    <span className="text-slate-100">47.62%</span>
                  </div>
                  <div className="flex justify-between items-center py-2 border-b border-slate-800/50">
                    <span className="text-slate-400">Our Fair Odds <span className="text-slate-600">(margin stripped)</span></span>
                    <span className="text-slate-100">1.89</span>
                  </div>
                  <div className="flex justify-between items-center py-2 border-b border-slate-800/50">
                    <span className="text-slate-400">True Probability</span>
                    <span className="text-slate-100">52.91%</span>
                  </div>
                  <div className="flex justify-between items-center py-3 bg-emerald-500/10 rounded px-3 -mx-3 mt-2">
                    <span className="text-emerald-400 font-semibold">Mathematical Edge</span>
                    <span className="text-emerald-400 font-bold text-lg">+11.1%</span>
                  </div>
                </div>
                
                <p className="text-xs text-slate-500 mt-4">
                  We strip bookmaker margin to find true odds. When their price exceeds fair value, we bet.
                </p>
              </div>
            </div>
            
            <div className="bg-slate-900/50 rounded-lg border border-slate-800 p-6">
              <h3 className="font-semibold mb-4 text-emerald-400">The Philosophy</h3>
              <div className="space-y-4 text-sm text-slate-400">
                <div className="flex gap-3">
                  <span className="text-emerald-400 font-mono">01</span>
                  <p><strong className="text-slate-200">Mathematical edge only.</strong> We calculate true odds. We only bet when our odds are better than the bookmaker&apos;s.</p>
                </div>
                <div className="flex gap-3">
                  <span className="text-emerald-400 font-mono">02</span>
                  <p><strong className="text-slate-200">Singles only.</strong> Accumulators compound the bookmaker&apos;s edge. A five-fold with 5% margin per leg = 22.6% against you. That&apos;s the graveyard of the bettor.</p>
                </div>
                <div className="flex gap-3">
                  <span className="text-emerald-400 font-mono">03</span>
                  <p><strong className="text-slate-200">Exploit inefficiencies.</strong> Player props, niche markets, early lines. Where their models are weak, we attack.</p>
                </div>
                <div className="flex gap-3">
                  <span className="text-emerald-400 font-mono">04</span>
                  <p><strong className="text-slate-200">No secrets given away.</strong> We share the picks, not the model. Rest assured we&apos;re not betting for fun.</p>
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* Track Record */}
      <section id="track-record" className="py-20 border-b border-slate-800/50">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <span className="text-xs font-mono text-emerald-400 mb-4 block tracking-wider">TRACK RECORD</span>
          <h2 className="text-3xl sm:text-4xl font-bold mb-6 sm:mb-8">Proven Results</h2>
          <p className="text-base sm:text-lg text-slate-300 mb-12 sm:mb-14 max-w-2xl">
            Transparent results across all active markets. ATP Tennis independently verified on Tipstrr. Player Props self-tracked with timestamped records.
          </p>

          {/* Combined Stats */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 sm:gap-6 mb-12 sm:mb-16">
            <div className="p-6 sm:p-8 bg-slate-900/60 rounded-xl border border-slate-800/50 hover:border-emerald-500/30 transition-all">
              <div className="text-4xl sm:text-5xl font-bold text-emerald-400 font-mono mb-2">
                {loading ? "..." : combinedStats ? `${combinedStats.overall.total_bets.toLocaleString()}+` : "1,200+"}
              </div>
              <div className="text-sm text-slate-400 font-medium">Total Bets</div>
            </div>
            <div className="p-6 sm:p-8 bg-slate-900/60 rounded-xl border border-slate-800/50 hover:border-emerald-500/30 transition-all">
              <div className="text-4xl sm:text-5xl font-bold text-emerald-400 font-mono mb-2">
                {loading ? "..." : combinedStats ? `${combinedStats.overall.win_rate.toFixed(0)}%` : "56%"}
              </div>
              <div className="text-sm text-slate-400 font-medium">Win Rate</div>
            </div>
            <div className="p-6 sm:p-8 bg-slate-900/60 rounded-xl border border-slate-800/50 hover:border-emerald-500/30 transition-all">
              <div className="text-4xl sm:text-5xl font-bold text-emerald-400 font-mono mb-2">
                {loading ? "..." : combinedStats ? `${combinedStats.overall.roi > 0 ? "+" : ""}${combinedStats.overall.roi.toFixed(1)}%` : "+18%"}
              </div>
              <div className="text-sm text-slate-400 font-medium">Combined ROI</div>
            </div>
            <div className="p-6 sm:p-8 bg-slate-900/60 rounded-xl border border-slate-800/50 hover:border-emerald-500/30 transition-all">
              <div className="text-4xl sm:text-5xl font-bold text-emerald-400 font-mono mb-2">2</div>
              <div className="text-sm text-slate-400 font-medium">Markets</div>
            </div>
          </div>

          {/* Individual Markets */}
          <div className="grid md:grid-cols-2 gap-6 sm:gap-8">
            {/* Player Props */}
            <div className="bg-slate-900/60 rounded-xl border border-slate-800/50 p-6 sm:p-8 hover:border-slate-700 transition-all">
              <div className="flex items-center justify-between mb-6">
                <h3 className="font-semibold text-lg">Player Props</h3>
                <span className="text-xs font-mono text-slate-500">FOOTBALL 2025</span>
              </div>
              <div className="grid grid-cols-3 gap-4 mb-4">
                <div>
                  <div className="text-2xl font-bold text-emerald-400 font-mono">
                    {loading ? "..." : combinedStats ? `${combinedStats.props.total_bets}+` : "780+"}
                  </div>
                  <div className="text-xs text-slate-500">Bets</div>
                </div>
                <div>
                  <div className="text-2xl font-bold text-emerald-400 font-mono">
                    {loading ? "..." : combinedStats ? `${combinedStats.props.roi > 0 ? "+" : ""}${combinedStats.props.roi.toFixed(1)}%` : "+25%"}
                  </div>
                  <div className="text-xs text-slate-500">ROI</div>
                </div>
                <div>
                  <div className="text-2xl font-bold text-emerald-400 font-mono">
                    {loading ? "..." : combinedStats ? `${combinedStats.props.win_rate.toFixed(0)}%` : "58%"}
                  </div>
                  <div className="text-xs text-slate-500">Win Rate</div>
                </div>
              </div>
              <p className="text-xs text-slate-500">Self-tracked with timestamped screenshots</p>
            </div>

            {/* ATP Tennis */}
            <div className="bg-slate-900/60 rounded-xl border border-slate-800/50 p-6 sm:p-8 hover:border-slate-700 transition-all">
              <div className="flex items-center justify-between mb-6">
                <h3 className="font-semibold text-lg">ATP Tennis</h3>
                <span className="text-xs font-mono text-emerald-400">TIPSTRR VERIFIED</span>
              </div>
              <div className="grid grid-cols-3 gap-4 mb-4">
                <div>
                  <div className="text-2xl font-bold text-emerald-400 font-mono">
                    {loading ? "..." : combinedStats ? `${combinedStats.tennis.total_bets}` : "447"}
                  </div>
                  <div className="text-xs text-slate-500">Bets</div>
                </div>
                <div>
                  <div className="text-2xl font-bold text-emerald-400 font-mono">
                    {loading ? "..." : combinedStats ? `${combinedStats.tennis.roi > 0 ? "+" : ""}${combinedStats.tennis.roi.toFixed(1)}%` : "+8.6%"}
                  </div>
                  <div className="text-xs text-slate-500">ROI</div>
                </div>
                <div>
                  <div className="text-2xl font-bold text-emerald-400 font-mono">
                    {loading ? "..." : combinedStats ? `${combinedStats.tennis.win_rate.toFixed(0)}%` : "54%"}
                  </div>
                  <div className="text-xs text-slate-500">Win Rate</div>
                </div>
              </div>
              <p className="text-xs text-slate-500">Independently verified on Tipstrr.com</p>
            </div>
          </div>
        </div>
      </section>

      {/* CTA */}
      <section className="py-20">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 text-center">
          <h2 className="text-3xl sm:text-4xl font-bold mb-4 sm:mb-6">Ready to join?</h2>
          <p className="text-base sm:text-lg text-slate-300 mb-8 sm:mb-10 max-w-lg mx-auto">
            Free selections delivered to Telegram. Match, selection, odds, bookmaker. Everything you need to place your bet.
          </p>
          <a 
            href={TELEGRAM_CHANNEL_URL}
            target="_blank"
            rel="noopener noreferrer"
            className="bg-emerald-500 hover:bg-emerald-400 text-black font-semibold px-8 py-4 rounded-lg text-lg inline-flex items-center gap-2 transition-all hover:scale-105 shadow-lg shadow-emerald-500/20"
          >
            <svg className="w-5 h-5" viewBox="0 0 24 24" fill="currentColor"><path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm4.64 6.8c-.15 1.58-.8 5.42-1.13 7.19-.14.75-.42 1-.68 1.03-.58.05-1.02-.38-1.58-.75-.88-.58-1.38-.94-2.23-1.5-.99-.65-.35-1.01.22-1.59.15-.15 2.71-2.48 2.76-2.69a.2.2 0 00-.05-.18c-.06-.05-.14-.03-.21-.02-.09.02-1.49.95-4.22 2.79-.4.27-.76.41-1.08.4-.36-.01-1.04-.2-1.55-.37-.63-.2-1.12-.31-1.08-.66.02-.18.27-.36.74-.55 2.92-1.27 4.86-2.11 5.83-2.51 2.78-1.16 3.35-1.36 3.73-1.36.08 0 .27.02.39.12.1.08.13.19.14.27-.01.06.01.24 0 .38z"/></svg>
            Join Telegram Channel
          </a>
        </div>
      </section>

      {/* Footer */}
      <footer className="border-t border-slate-800 py-8">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex flex-col md:flex-row items-center justify-between gap-4">
            <div className="flex items-center gap-3">
              <Image src="/favicon.png" alt="Il Margine" width={32} height={32} className="rounded" />
              <span className="font-semibold text-sm">Il Margine</span>
              <span className="text-xs font-mono text-emerald-400 bg-emerald-500/10 px-2 py-0.5 rounded">FREE BETA</span>
            </div>
            
            <div className="text-xs text-slate-600">
              Gamble responsibly. 18+ only.
            </div>
          </div>
        </div>
      </footer>
    </div>
  );
}
