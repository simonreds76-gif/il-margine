"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import Image from "next/image";
import { supabase, MarketStats } from "@/lib/supabase";
import { BASELINE_STATS, calculateROI } from "@/lib/baseline";
import Footer from "@/components/Footer";

/** Stake amount chip (neutral; green reserved for profit/ROI). */
function StakeNote({ amount }: { amount: number }) {
  return (
    <div
      className="relative inline-flex h-10 min-w-[4rem] items-center justify-center rounded-lg overflow-hidden border border-amber-700/40 bg-gradient-to-br from-stone-700/90 to-stone-800/90 shadow-inner"
      aria-label={`£${amount} per unit`}
    >
      <div
        className="absolute inset-0 opacity-[0.07]"
        style={{
          backgroundImage: `repeating-linear-gradient(45deg, transparent, transparent 4px, currentColor 4px, currentColor 5px)`,
        }}
      />
      <span className="relative font-bold font-mono text-sm text-amber-100/95 drop-shadow-sm">
        £{amount}
      </span>
    </div>
  );
}

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
    // Profit in £ = profit in units × your stake per unit
    const totalProfit = marketStats.total_profit * stakePerUnit;
    // Avg per bet = total profit (£) / total bets — accurate over the full track record
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
            {/* Navigation is now in GlobalNav component in layout.tsx */}


      {/* Hero */}
      <section className="pt-4 pb-10 md:pt-6 md:pb-14 border-b border-slate-800/50">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex items-center gap-2 mb-6">
            <Link href="/" className="text-sm text-slate-500 hover:text-slate-300 transition-colors">Home</Link>
            <span className="text-slate-600">/</span>
            <span className="text-sm text-emerald-400 font-medium">Calculator</span>
          </div>
          <div className="flex items-center gap-2 mb-3">
            <span className="text-xs font-mono text-emerald-400/90 bg-emerald-500/10 border border-emerald-500/20 px-2.5 py-1 rounded">Calculator</span>
          </div>
          <h1 className="text-3xl sm:text-4xl font-semibold text-slate-100 mb-3 sm:mb-4">Returns Calculator</h1>
          <p className="text-base sm:text-lg text-slate-300 max-w-3xl leading-relaxed mb-6">
            Calculate your potential returns based on our historical performance. All calculations are based on our verified track record and assume you follow our unit recommendations.
          </p>
          <div className="border-l-4 border-amber-500/60 bg-amber-500/5 rounded-r-lg py-3 px-4 max-w-2xl">
            <p className="text-sm text-slate-300 leading-relaxed">
              <strong className="text-amber-400/95">Important:</strong> Past performance does not guarantee future results. These calculations are illustrative. Always bet responsibly and within your means.
            </p>
          </div>
        </div>
      </section>

      {/* Calculator Tables */}
      <section className="py-12 md:py-16">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          {loading ? (
            <div className="flex flex-col items-center justify-center py-16 gap-4">
              <div className="h-2 w-32 rounded-full bg-slate-800 overflow-hidden">
                <div className="h-full w-1/2 rounded-full bg-emerald-500/40 animate-pulse" />
              </div>
              <p className="text-sm text-slate-500">Loading performance data…</p>
            </div>
          ) : combinedStats ? (
            <div className="grid lg:grid-cols-2 gap-8 lg:gap-10">
              {/* Player Props */}
              <div className="rounded-2xl border border-slate-800/80 bg-slate-900/50 overflow-hidden shadow-lg shadow-black/20">
                <div className="h-1 bg-gradient-to-r from-emerald-500 to-emerald-400/80" aria-hidden />
                <div className="p-6 sm:p-8">
                  <div className="flex flex-wrap items-end justify-between gap-4 mb-6">
                    <div>
                      <h2 className="text-2xl sm:text-3xl font-semibold text-slate-100">Player Props</h2>
                      <p className="text-sm text-slate-400 mt-1">Football individual player markets</p>
                    </div>
                    <span className={`inline-flex items-center px-3 py-1.5 rounded-full text-sm font-bold font-mono ${combinedStats.props.roi >= 0 ? 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/30' : 'bg-red-500/20 text-red-400 border border-red-500/30'}`}>
                      {combinedStats.props.roi >= 0 ? "+" : ""}{combinedStats.props.roi.toFixed(1)}% ROI
                    </span>
                  </div>
                  <div className="grid grid-cols-3 gap-3 mb-6">
                    <div className="rounded-xl bg-slate-800/60 border border-slate-700/50 p-4 text-center">
                      <div className="text-xl sm:text-2xl font-bold font-mono text-slate-100">{combinedStats.props.total_bets}</div>
                      <div className="text-xs text-slate-500 mt-1 uppercase tracking-wider">Bets</div>
                    </div>
                    <div className="rounded-xl bg-slate-800/60 border border-slate-700/50 p-4 text-center">
                      <div className="text-xl sm:text-2xl font-bold font-mono text-amber-400/90">{combinedStats.props.avg_odds.toFixed(2)}</div>
                      <div className="text-xs text-slate-500 mt-1 uppercase tracking-wider">Avg Odds</div>
                    </div>
                    <div className="rounded-xl bg-slate-800/60 border border-slate-700/50 p-4 text-center">
                      <div className={`text-xl sm:text-2xl font-bold font-mono ${combinedStats.props.total_profit >= 0 ? 'text-emerald-400' : 'text-red-400'}`}>
                        {combinedStats.props.total_profit >= 0 ? '+' : ''}{combinedStats.props.total_profit.toFixed(1)}u
                      </div>
                      <div className="text-xs text-slate-500 mt-1 uppercase tracking-wider">Profit</div>
                    </div>
                  </div>
                  <p className="text-xs font-mono text-slate-500 uppercase tracking-wider mb-3">Returns by stake</p>
                  <div className="space-y-3">
                    {propsReturns.map((returns) => (
                      <div
                        key={returns.stakePerUnit}
                        className="rounded-xl bg-slate-800/40 border border-slate-700/50 p-4 flex flex-wrap items-center justify-between gap-3 hover:border-emerald-500/40 transition-colors"
                      >
                        <div className="flex items-center gap-3">
                          <StakeNote amount={returns.stakePerUnit} />
                          <span className="text-xs text-slate-500">per unit × {combinedStats.props.total_bets} bets</span>
                        </div>
                        <div className="text-right">
                          <div className={`text-lg font-bold font-mono ${returns.totalProfit >= 0 ? 'text-emerald-400' : 'text-red-400'}`}>
                            {returns.totalProfit >= 0 ? '+' : ''}£{Math.abs(returns.totalProfit).toLocaleString(undefined, { minimumFractionDigits: 0, maximumFractionDigits: 0 })}
                          </div>
                          <div className="text-[11px] text-slate-500">avg {returns.profitPerBet >= 0 ? '+' : ''}£{Math.abs(returns.profitPerBet).toFixed(2)}/bet</div>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              </div>

              {/* Tennis Tips */}
              <div className="rounded-2xl border border-slate-800/80 bg-slate-900/50 overflow-hidden shadow-lg shadow-black/20">
                <div className="h-1 bg-gradient-to-r from-amber-500/90 to-amber-400/70" aria-hidden />
                <div className="p-6 sm:p-8">
                  <div className="flex flex-wrap items-end justify-between gap-4 mb-6">
                    <div>
                      <h2 className="text-2xl sm:text-3xl font-semibold text-slate-100">Tennis Tips</h2>
                      <p className="text-sm text-slate-400 mt-1">Pre-match singles markets</p>
                    </div>
                    <span className={`inline-flex items-center px-3 py-1.5 rounded-full text-sm font-bold font-mono ${combinedStats.tennis.roi >= 0 ? 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/30' : 'bg-red-500/20 text-red-400 border border-red-500/30'}`}>
                      {combinedStats.tennis.roi >= 0 ? "+" : ""}{combinedStats.tennis.roi.toFixed(1)}% ROI
                    </span>
                  </div>
                  <div className="grid grid-cols-3 gap-3 mb-6">
                    <div className="rounded-xl bg-slate-800/60 border border-slate-700/50 p-4 text-center">
                      <div className="text-xl sm:text-2xl font-bold font-mono text-slate-100">{combinedStats.tennis.total_bets}</div>
                      <div className="text-xs text-slate-500 mt-1 uppercase tracking-wider">Bets</div>
                    </div>
                    <div className="rounded-xl bg-slate-800/60 border border-slate-700/50 p-4 text-center">
                      <div className="text-xl sm:text-2xl font-bold font-mono text-amber-400/90">{combinedStats.tennis.avg_odds.toFixed(2)}</div>
                      <div className="text-xs text-slate-500 mt-1 uppercase tracking-wider">Avg Odds</div>
                    </div>
                    <div className="rounded-xl bg-slate-800/60 border border-slate-700/50 p-4 text-center">
                      <div className={`text-xl sm:text-2xl font-bold font-mono ${combinedStats.tennis.total_profit >= 0 ? 'text-emerald-400' : 'text-red-400'}`}>
                        {combinedStats.tennis.total_profit >= 0 ? '+' : ''}{combinedStats.tennis.total_profit.toFixed(1)}u
                      </div>
                      <div className="text-xs text-slate-500 mt-1 uppercase tracking-wider">Profit</div>
                    </div>
                  </div>
                  <p className="text-xs font-mono text-slate-500 uppercase tracking-wider mb-3">Returns by stake</p>
                  <div className="space-y-3">
                    {tennisReturns.map((returns) => (
                      <div
                        key={returns.stakePerUnit}
                        className="rounded-xl bg-slate-800/40 border border-slate-700/50 p-4 flex flex-wrap items-center justify-between gap-3 hover:border-amber-500/40 transition-colors"
                      >
                        <div className="flex items-center gap-3">
                          <StakeNote amount={returns.stakePerUnit} />
                          <span className="text-xs text-slate-500">per unit × {combinedStats.tennis.total_bets} bets</span>
                        </div>
                        <div className="text-right">
                          <div className={`text-lg font-bold font-mono ${returns.totalProfit >= 0 ? 'text-emerald-400' : 'text-red-400'}`}>
                            {returns.totalProfit >= 0 ? '+' : ''}£{Math.abs(returns.totalProfit).toLocaleString(undefined, { minimumFractionDigits: 0, maximumFractionDigits: 0 })}
                          </div>
                          <div className="text-[11px] text-slate-500">avg {returns.profitPerBet >= 0 ? '+' : ''}£{Math.abs(returns.profitPerBet).toFixed(2)}/bet</div>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            </div>
          ) : (
            <div className="text-center py-12">
              <p className="text-slate-500">Unable to load performance data</p>
            </div>
          )}

          {/* How It Works */}
          <div className="mt-14 rounded-2xl border border-slate-800/80 bg-slate-900/50 overflow-hidden">
            <div className="border-l-4 border-emerald-500/60 bg-emerald-500/5 px-5 py-3">
              <h3 className="font-semibold text-emerald-400">How It Works</h3>
            </div>
            <div className="grid md:grid-cols-2 gap-8 p-6 sm:p-8 text-sm text-slate-400">
              <div className="space-y-4">
                <p className="leading-relaxed">
                  <strong className="text-slate-200">Unit system:</strong> We recommend stakes in units (1u, 2u, etc.). 
                  A unit is a fixed % of your bankroll (typically 1–2%).
                </p>
                <p className="leading-relaxed">
                  <strong className="text-slate-200">Example:</strong> £2,500 bankroll at 1% → 1u = £25. A 2u pick = £50 stake.
                </p>
              </div>
              <div className="space-y-4">
                <p className="leading-relaxed">
                  <strong className="text-slate-200">Calculations:</strong> Returns use our historical ROI × your total stake. 
                  Assumes you follow our unit recommendations.
                </p>
                <p className="leading-relaxed">
                  <strong className="text-slate-200">Remember:</strong> Historical only. Future results may differ. Practice responsible bankroll management.
                </p>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* Banner */}
      <section className="py-12 border-b border-slate-800/50">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 flex justify-center">
          <Image src="/banner-mind-the-margin.png" alt="Il Margine: Mind the margin" width={1200} height={400} className="w-full max-w-2xl h-auto object-contain rounded-lg" />
        </div>
      </section>

      <Footer className="mt-12" />
    </div>
  );
}
