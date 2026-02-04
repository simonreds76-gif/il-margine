"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import Image from "next/image";
import { supabase, MarketStats } from "@/lib/supabase";
import { BASELINE_STATS, calculateROI } from "@/lib/baseline";

interface CombinedMarketStats {
  total_bets: number;
  roi: number;
  win_rate: number;
  avg_odds: number;
  total_profit: number;
  total_stake: number;
}

export default function Calculator() {
  const [loading, setLoading] = useState(true);
  const [marketStats, setMarketStats] = useState<MarketStats[]>([]);
  const [combinedStats, setCombinedStats] = useState<{
    props: CombinedMarketStats;
    tennis: CombinedMarketStats;
  } | null>(null);
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);

  useEffect(() => {
    fetchData();
  }, []);

  const fetchData = async () => {
    setLoading(true);
    
    const { data: stats } = await supabase
      .from("market_stats")
      .select("*");
    
    if (stats) setMarketStats(stats);
    calculateCombinedStats(stats || []);
    setLoading(false);
  };

  const calculateCombinedStats = (liveStats: MarketStats[]) => {
    const propsLive = liveStats.find(s => s.market === "props");
    const tennisLive = liveStats.find(s => s.market === "tennis");

    // Player Props
    const propsLiveBets = propsLive?.total_bets || 0;
    const propsLiveProfit = Number(propsLive?.total_profit) || 0;
    const propsLiveStake = propsLiveBets;
    
    const propsCombined: CombinedMarketStats = {
      total_bets: BASELINE_STATS.props.total_bets + propsLiveBets,
      roi: 0,
      win_rate: 0,
      avg_odds: 0,
      total_profit: 0,
      total_stake: 0,
    };
    
    const propsProfit = BASELINE_STATS.props.total_profit + propsLiveProfit;
    const propsStake = BASELINE_STATS.props.total_stake + propsLiveStake;
    
    propsCombined.roi = calculateROI(propsProfit, propsStake || 1);
    propsCombined.total_profit = propsProfit;
    propsCombined.total_stake = propsStake;
    propsCombined.avg_odds = propsLive?.avg_odds ? Number(propsLive.avg_odds) : 1.98;

    // Tennis
    const tennisLiveBets = tennisLive?.total_bets || 0;
    const tennisLiveProfit = Number(tennisLive?.total_profit) || 0;
    const tennisLiveStake = tennisLiveBets;
    
    const tennisCombined: CombinedMarketStats = {
      total_bets: BASELINE_STATS.tennis.total_bets + tennisLiveBets,
      roi: 0,
      win_rate: 0,
      avg_odds: 0,
      total_profit: 0,
      total_stake: 0,
    };
    
    const tennisProfit = BASELINE_STATS.tennis.total_profit + tennisLiveProfit;
    const tennisStake = BASELINE_STATS.tennis.total_stake + tennisLiveStake;
    
    tennisCombined.roi = calculateROI(tennisProfit, tennisStake || 1);
    tennisCombined.total_profit = tennisProfit;
    tennisCombined.total_stake = tennisStake;
    tennisCombined.avg_odds = tennisLive?.avg_odds ? Number(tennisLive.avg_odds) : 2.06;

    setCombinedStats({
      props: propsCombined,
      tennis: tennisCombined,
    });
  };

  const calculateReturns = (stakePerUnit: number, marketStats: CombinedMarketStats) => {
    // Calculate profit directly from units profit × stake per unit
    // This is more accurate than using ROI percentage
    const totalProfit = marketStats.total_profit * stakePerUnit;
    const profitPerBet = marketStats.total_bets > 0 ? totalProfit / marketStats.total_bets : 0;
    
    return {
      stakePerUnit,
      totalProfit,
      profitPerBet,
    };
  };

  const stakeLevels = [25, 50, 100];

  const propsReturns = combinedStats ? stakeLevels.map(stake => calculateReturns(stake, combinedStats.props)) : [];
  const tennisReturns = combinedStats ? stakeLevels.map(stake => calculateReturns(stake, combinedStats.tennis)) : [];

  return (
    <div className="min-h-screen bg-[#0f1117] text-slate-100">
      {/* Nav */}
      <nav className="border-b border-slate-800/80 sticky top-0 z-50 bg-[#0f1117]/95 backdrop-blur-sm">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex items-center justify-between h-16">
            <Link href="/" className="flex items-center">
              <Image src="/logo.png" alt="Il Margine" width={180} height={50} className="h-10 w-auto" style={{ background: 'transparent' }} />
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
              <Link href="/" className="text-sm text-slate-400 hover:text-slate-100 transition-colors">Home</Link>
              <Link href="/player-props" className="text-sm text-slate-400 hover:text-slate-100 transition-colors">Player Props</Link>
              <Link href="/atp-tennis" className="text-sm text-slate-400 hover:text-slate-100 transition-colors">ATP Tennis</Link>
              <Link href="/calculator" className="text-sm text-emerald-400 font-medium">Returns Calculator</Link>
              <button className="bg-emerald-500 hover:bg-emerald-400 text-black text-sm font-medium px-4 py-2 rounded transition-colors flex items-center gap-2">
                <svg className="w-4 h-4" viewBox="0 0 24 24" fill="currentColor"><path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm4.64 6.8c-.15 1.58-.8 5.42-1.13 7.19-.14.75-.42 1-.68 1.03-.58.05-1.02-.38-1.58-.75-.88-.58-1.38-.94-2.23-1.5-.99-.65-.35-1.01.22-1.59.15-.15 2.71-2.48 2.76-2.69a.2.2 0 00-.05-.18c-.06-.05-.14-.03-.21-.02-.09.02-1.49.95-4.22 2.79-.4.27-.76.41-1.08.4-.36-.01-1.04-.2-1.55-.37-.63-.2-1.12-.31-1.08-.66.02-.18.27-.36.74-.55 2.92-1.27 4.86-2.11 5.83-2.51 2.78-1.16 3.35-1.36 3.73-1.36.08 0 .27.02.39.12.1.08.13.19.14.27-.01.06.01.24 0 .38z"/></svg>
                Join Free
              </button>
            </div>
          </div>
          
          {/* Mobile Menu */}
          {mobileMenuOpen && (
            <div className="md:hidden border-t border-slate-800/50 py-4 space-y-3">
              <Link href="/" className="block px-4 py-2 text-sm text-slate-300 hover:text-emerald-400 hover:bg-emerald-500/10 rounded transition-colors">
                Home
              </Link>
              <Link href="/player-props" className="block px-4 py-2 text-sm text-slate-300 hover:text-emerald-400 hover:bg-emerald-500/10 rounded transition-colors">
                Player Props
              </Link>
              <Link href="/atp-tennis" className="block px-4 py-2 text-sm text-slate-300 hover:text-emerald-400 hover:bg-emerald-500/10 rounded transition-colors">
                ATP Tennis
              </Link>
              <Link href="/calculator" className="block px-4 py-2 text-sm text-emerald-400 font-medium hover:bg-emerald-500/10 rounded transition-colors">
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
      <section className="py-12 md:py-16 border-b border-slate-800/50">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex items-center gap-2 mb-4">
            <Link href="/" className="text-sm text-slate-500 hover:text-slate-300">Home</Link>
            <span className="text-slate-600">/</span>
            <span className="text-sm text-emerald-400">Returns Calculator</span>
          </div>
          
          <h1 className="text-3xl sm:text-4xl md:text-5xl font-bold mb-3 sm:mb-4">Potential Returns Calculator</h1>
          <p className="text-base sm:text-lg text-slate-400 max-w-3xl mb-6 sm:mb-8">
            Calculate your potential returns based on our historical performance. All calculations are based on our verified track record and assume you follow our unit recommendations.
          </p>
          
          <div className="bg-amber-500/10 border border-amber-500/30 rounded-lg p-4 mb-8">
            <p className="text-sm text-amber-200">
              <strong className="text-amber-400">Important:</strong> Past performance does not guarantee future results. These calculations are illustrative based on historical data. Always bet responsibly and within your means.
            </p>
          </div>
        </div>
      </section>

      {/* Calculator Tables */}
      <section className="py-12">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          {loading ? (
            <div className="text-center py-12">
              <p className="text-slate-500">Loading performance data...</p>
            </div>
          ) : combinedStats ? (
            <div className="grid lg:grid-cols-2 gap-6 lg:gap-8">
              {/* Player Props */}
              <div className="bg-gradient-to-br from-slate-900/80 to-slate-900/40 rounded-xl border border-slate-800 p-6 sm:p-8">
                <div className="flex items-center justify-between mb-6">
                  <div>
                    <h2 className="text-2xl font-bold mb-2">Player Props</h2>
                    <p className="text-sm text-slate-400">Football individual player markets</p>
                  </div>
                  <div className="text-right">
                    <div className={`text-3xl font-bold font-mono mb-1 ${combinedStats.props.roi >= 0 ? 'text-emerald-400' : 'text-red-400'}`}>
                      {combinedStats.props.roi >= 0 ? "+" : ""}{combinedStats.props.roi.toFixed(1)}%
                    </div>
                    <div className="text-xs text-slate-500">ROI</div>
                  </div>
                </div>
                
                <div className="grid grid-cols-3 gap-4 mb-6 pb-6 border-b border-slate-800">
                  <div>
                    <div className="text-2xl font-bold text-white font-mono">{combinedStats.props.total_bets}</div>
                    <div className="text-xs text-slate-500 mt-1">Total Bets</div>
                  </div>
                  <div>
                    <div className="text-2xl font-bold text-amber-400 font-mono">{combinedStats.props.avg_odds.toFixed(2)}</div>
                    <div className="text-xs text-slate-500 mt-1">Avg Odds</div>
                  </div>
                  <div>
                    <div className={`text-2xl font-bold font-mono ${combinedStats.props.total_profit >= 0 ? 'text-emerald-400' : 'text-red-400'}`}>
                      {combinedStats.props.total_profit >= 0 ? '+' : ''}{combinedStats.props.total_profit.toFixed(1)}u
                    </div>
                    <div className="text-xs text-slate-500 mt-1">Total Profit</div>
                  </div>
                </div>

                <div className="space-y-4">
                  <div className="text-xs font-mono text-slate-500 uppercase mb-4">Returns by Stake Level</div>
                  {propsReturns.map((returns, idx) => (
                    <div 
                      key={returns.stakePerUnit}
                      className="bg-slate-800/50 rounded-lg border border-slate-700/50 p-4 sm:p-6 hover:border-emerald-500/50 transition-all"
                    >
                      <div className="flex items-center justify-between mb-4">
                        <div className="flex items-center gap-3">
                          <div className="w-12 h-12 bg-amber-500/20 rounded-lg flex items-center justify-center">
                            <span className="text-xl font-bold text-amber-400">£{returns.stakePerUnit}</span>
                          </div>
                          <div>
                            <div className="text-sm text-slate-400">Per Unit Stake</div>
                            <div className="text-xs text-slate-600">£{returns.stakePerUnit.toLocaleString()} × {combinedStats.props.total_bets} bets</div>
                          </div>
                        </div>
                        <div className="text-right">
                          <div className={`text-2xl font-bold font-mono ${returns.totalProfit >= 0 ? 'text-emerald-400' : 'text-red-400'}`}>
                            {returns.totalProfit >= 0 ? '+' : ''}£{Math.abs(returns.totalProfit).toLocaleString(undefined, { minimumFractionDigits: 0, maximumFractionDigits: 0 })}
                          </div>
                          <div className="text-xs text-slate-500">Total Profit</div>
                        </div>
                      </div>
                      
                      <div className="mt-4 pt-4 border-t border-slate-700/30">
                        <div className="text-xs text-slate-600">
                          Average profit per bet: <span className={`font-mono ${returns.profitPerBet >= 0 ? 'text-emerald-400' : 'text-red-400'}`}>
                            {returns.profitPerBet >= 0 ? '+' : ''}£{Math.abs(returns.profitPerBet).toFixed(2)}
                          </span>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              </div>

              {/* ATP Tennis */}
              <div className="bg-gradient-to-br from-slate-900/80 to-slate-900/40 rounded-xl border border-slate-800 p-6 sm:p-8">
                <div className="flex items-center justify-between mb-6">
                  <div>
                    <h2 className="text-2xl font-bold mb-2">ATP Tennis</h2>
                    <p className="text-sm text-slate-400">Pre-match singles markets</p>
                  </div>
                  <div className="text-right">
                    <div className={`text-3xl font-bold font-mono mb-1 ${combinedStats.tennis.roi >= 0 ? 'text-emerald-400' : 'text-red-400'}`}>
                      {combinedStats.tennis.roi >= 0 ? "+" : ""}{combinedStats.tennis.roi.toFixed(1)}%
                    </div>
                    <div className="text-xs text-slate-500">ROI</div>
                  </div>
                </div>
                
                <div className="grid grid-cols-3 gap-4 mb-6 pb-6 border-b border-slate-800">
                  <div>
                    <div className="text-2xl font-bold text-white font-mono">{combinedStats.tennis.total_bets}</div>
                    <div className="text-xs text-slate-500 mt-1">Total Bets</div>
                  </div>
                  <div>
                    <div className="text-2xl font-bold text-amber-400 font-mono">{combinedStats.tennis.avg_odds.toFixed(2)}</div>
                    <div className="text-xs text-slate-500 mt-1">Avg Odds</div>
                  </div>
                  <div>
                    <div className={`text-2xl font-bold font-mono ${combinedStats.tennis.total_profit >= 0 ? 'text-emerald-400' : 'text-red-400'}`}>
                      {combinedStats.tennis.total_profit >= 0 ? '+' : ''}{combinedStats.tennis.total_profit.toFixed(1)}u
                    </div>
                    <div className="text-xs text-slate-500 mt-1">Total Profit</div>
                  </div>
                </div>

                <div className="space-y-4">
                  <div className="text-xs font-mono text-slate-500 uppercase mb-4">Returns by Stake Level</div>
                  {tennisReturns.map((returns, idx) => (
                    <div 
                      key={returns.stakePerUnit}
                      className="bg-slate-800/50 rounded-lg border border-slate-700/50 p-4 sm:p-6 hover:border-emerald-500/50 transition-all"
                    >
                      <div className="flex items-center justify-between mb-4">
                        <div className="flex items-center gap-3">
                          <div className="w-12 h-12 bg-amber-500/20 rounded-lg flex items-center justify-center">
                            <span className="text-xl font-bold text-amber-400">£{returns.stakePerUnit}</span>
                          </div>
                          <div>
                            <div className="text-sm text-slate-400">Per Unit Stake</div>
                            <div className="text-xs text-slate-600">£{returns.stakePerUnit.toLocaleString()} × {combinedStats.tennis.total_bets} bets</div>
                          </div>
                        </div>
                        <div className="text-right">
                          <div className={`text-2xl font-bold font-mono ${returns.totalProfit >= 0 ? 'text-emerald-400' : 'text-red-400'}`}>
                            {returns.totalProfit >= 0 ? '+' : ''}£{Math.abs(returns.totalProfit).toLocaleString(undefined, { minimumFractionDigits: 0, maximumFractionDigits: 0 })}
                          </div>
                          <div className="text-xs text-slate-500">Total Profit</div>
                        </div>
                      </div>
                      
                      <div className="mt-4 pt-4 border-t border-slate-700/30">
                        <div className="text-xs text-slate-600">
                          Average profit per bet: <span className={`font-mono ${returns.profitPerBet >= 0 ? 'text-emerald-400' : 'text-red-400'}`}>
                            {returns.profitPerBet >= 0 ? '+' : ''}£{Math.abs(returns.profitPerBet).toFixed(2)}
                          </span>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          ) : (
            <div className="text-center py-12">
              <p className="text-slate-500">Unable to load performance data</p>
            </div>
          )}

          {/* Info Box */}
          <div className="mt-12 bg-slate-900/50 rounded-lg border border-slate-800 p-6">
            <h3 className="font-semibold mb-4 text-emerald-400">How It Works</h3>
            <div className="grid md:grid-cols-2 gap-6 text-sm text-slate-400">
              <div>
                <p className="mb-2">
                  <strong className="text-slate-200">Unit System:</strong> We recommend stakes in "units" (1u, 2u, etc.). 
                  A unit represents a fixed percentage of your betting bankroll (typically 1-2%).
                </p>
                <p>
                  <strong className="text-slate-200">Example:</strong> If your bankroll is £2,500 and you use 1% units, 
                  then 1u = £25. If we recommend 2u on a selection, you would stake £50.
                </p>
              </div>
              <div>
                <p className="mb-2">
                  <strong className="text-slate-200">Calculations:</strong> Returns are calculated by multiplying our historical 
                  ROI by your total stake across all bets. This assumes you follow our unit recommendations exactly.
                </p>
                <p>
                  <strong className="text-slate-200">Remember:</strong> These are historical returns. Future performance may differ. 
                  Always practice responsible bankroll management.
                </p>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* Footer */}
      <footer className="border-t border-slate-800 py-8 mt-12">
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
