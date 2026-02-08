"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import Image from "next/image";
import { supabase, MarketStats } from "@/lib/supabase";
import { BASELINE_STATS, calculateROI, calculateWinRate, getBaselineDisplayStats } from "@/lib/baseline";
import Footer from "@/components/Footer";

interface CombinedMarketStats {
  total_bets: number;
  roi: number;
  win_rate: number;
  avg_odds: number;
  total_profit: number;
}

export default function TrackRecordPage() {
  const [marketStats, setMarketStats] = useState<MarketStats[]>([]);
  const [loading, setLoading] = useState(true);
  const [combinedStats, setCombinedStats] = useState<{
    props: CombinedMarketStats;
    tennis: CombinedMarketStats;
    overall: CombinedMarketStats;
  } | null>(null);

  useEffect(() => {
    const fetchData = async () => {
      const { data } = await supabase.from("market_stats").select("*");
      if (data) setMarketStats(data);
      calculateCombinedStats(data || []);
      setLoading(false);
    };
    fetchData();
  }, []);

  function calculateCombinedStats(liveStats: MarketStats[]) {
    const propsLive = liveStats.find(s => s.market === "props");
    const tennisLive = liveStats.find(s => s.market === "tennis");

    const propsLiveBets = propsLive?.total_bets || 0;
    const propsLiveWins = propsLive?.wins || 0;
    const propsLiveLosses = propsLive?.losses || 0;
    const propsLiveProfit = Number(propsLive?.total_profit) || 0;
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
    const propsStake = BASELINE_STATS.props.total_stake + (propsLiveStake || propsLiveBets);
    propsCombined.win_rate = calculateWinRate(propsWins, propsLosses);
    propsCombined.roi = calculateROI(propsProfit, propsStake || 1);
    propsCombined.total_profit = propsProfit;
    propsCombined.avg_odds = propsLive?.avg_odds ? Number(propsLive.avg_odds) : 0;

    const tennisLiveBets = tennisLive?.total_bets || 0;
    const tennisLiveWins = tennisLive?.wins || 0;
    const tennisLiveLosses = tennisLive?.losses || 0;
    const tennisLiveProfit = Number(tennisLive?.total_profit) || 0;
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
    tennisCombined.avg_odds = tennisLive?.avg_odds ? Number(tennisLive.avg_odds) : 0;

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
    const overallWins = BASELINE_STATS.overall.wins + overallLiveWins;
    const overallLosses = BASELINE_STATS.overall.losses + overallLiveLosses;
    const overallProfit = BASELINE_STATS.overall.total_profit + overallLiveProfit;
    const overallStake = BASELINE_STATS.overall.total_stake + overallLiveStake;
    overallCombined.win_rate = calculateWinRate(overallWins, overallLosses);
    overallCombined.roi = calculateROI(overallProfit, overallStake || 1);
    overallCombined.total_profit = overallProfit;
    if (propsCombined.avg_odds > 0 || tennisCombined.avg_odds > 0) {
      const totalOddsWeight = (propsCombined.avg_odds * propsCombined.total_bets) + (tennisCombined.avg_odds * tennisCombined.total_bets);
      overallCombined.avg_odds = overallCombined.total_bets > 0 ? totalOddsWeight / overallCombined.total_bets : 0;
    }

    setCombinedStats({ props: propsCombined, tennis: tennisCombined, overall: overallCombined });
  }

  const displayStats = combinedStats ?? getBaselineDisplayStats();

  return (
    <div className="min-h-screen bg-[#0f1117] text-slate-100">
      <section className="pt-4 pb-12 md:pt-6 md:pb-16 border-b border-slate-800/50">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <Link href="/" className="inline-flex items-center gap-2 text-sm text-slate-500 hover:text-slate-300 mb-8">
            <Image src="/favicon.png" alt="" width={40} height={40} className="h-10 w-10 object-contain shrink-0" />
            <span>← Home</span>
          </Link>
          <span className="text-xs font-mono text-emerald-400 mb-3 block tracking-wider">TRACK RECORD</span>
          <h1 className="text-3xl sm:text-4xl font-semibold text-slate-100 mb-6 sm:mb-8">Proven Results</h1>
          <p className="text-base sm:text-lg text-slate-300 mb-12 sm:mb-14 max-w-2xl">
            Transparent results across all active markets. ATP Tennis independently verified on Tipstrr. Player Props self-tracked with timestamped records.
          </p>

          {loading ? (
            <p className="text-slate-500">Loading...</p>
          ) : (
            <>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4 sm:gap-6 mb-12 sm:mb-16">
                <div className="p-6 sm:p-8 bg-slate-900/60 rounded-xl border border-slate-800/50 hover:border-emerald-500/30 transition-all">
                  <div className="text-4xl sm:text-5xl font-bold text-emerald-400 font-mono mb-2">
                    {displayStats.overall.total_bets.toLocaleString()}+
                  </div>
                  <div className="text-sm text-slate-400 font-medium">Total Bets</div>
                </div>
                <div className="p-6 sm:p-8 bg-slate-900/60 rounded-xl border border-slate-800/50 hover:border-emerald-500/30 transition-all">
                  <div className="text-4xl sm:text-5xl font-bold text-emerald-400 font-mono mb-2">
                    {displayStats.overall.win_rate.toFixed(0)}%
                  </div>
                  <div className="text-sm text-slate-400 font-medium">Win Rate</div>
                </div>
                <div className="p-6 sm:p-8 bg-slate-900/60 rounded-xl border border-slate-800/50 hover:border-emerald-500/30 transition-all">
                  <div className="text-4xl sm:text-5xl font-bold text-emerald-400 font-mono mb-2">
                    {displayStats.overall.roi > 0 ? "+" : ""}{displayStats.overall.roi.toFixed(1)}%
                  </div>
                  <div className="text-sm text-slate-400 font-medium">Combined ROI</div>
                </div>
                <div className="p-6 sm:p-8 bg-slate-900/60 rounded-xl border border-slate-800/50 hover:border-emerald-500/30 transition-all">
                  <div className="text-4xl sm:text-5xl font-bold text-emerald-400 font-mono mb-2">2</div>
                  <div className="text-sm text-slate-400 font-medium">Markets</div>
                </div>
              </div>

              <div className="grid md:grid-cols-2 gap-6 sm:gap-8">
                <div className="bg-slate-900/60 rounded-xl border border-slate-800/50 p-6 sm:p-8 hover:border-slate-700 transition-all">
                  <div className="flex items-center justify-between mb-6">
                    <h2 className="font-semibold text-lg">Player Props</h2>
                    <span className="text-xs font-mono text-slate-500">FOOTBALL 2025</span>
                  </div>
                  <div className="grid grid-cols-3 gap-4 mb-4">
                    <div>
                      <div className="text-2xl font-bold text-emerald-400 font-mono">{displayStats.props.total_bets}+</div>
                      <div className="text-xs text-slate-500">Bets</div>
                    </div>
                    <div>
                      <div className="text-2xl font-bold text-emerald-400 font-mono">{displayStats.props.roi > 0 ? "+" : ""}{displayStats.props.roi.toFixed(1)}%</div>
                      <div className="text-xs text-slate-500">ROI</div>
                    </div>
                    <div>
                      <div className="text-2xl font-bold text-emerald-400 font-mono">{displayStats.props.win_rate.toFixed(0)}%</div>
                      <div className="text-xs text-slate-500">Win Rate</div>
                    </div>
                  </div>
                  <p className="text-xs text-slate-500">Self-tracked with timestamped screenshots</p>
                </div>

                <div className="bg-slate-900/60 rounded-xl border border-slate-800/50 p-6 sm:p-8 hover:border-slate-700 transition-all">
                  <div className="flex items-center justify-between mb-6">
                    <h2 className="font-semibold text-lg">ATP Tennis</h2>
                    <span className="text-xs font-mono text-emerald-400">TIPSTRR VERIFIED</span>
                  </div>
                  <div className="grid grid-cols-3 gap-4 mb-4">
                    <div>
                      <div className="text-2xl font-bold text-emerald-400 font-mono">{displayStats.tennis.total_bets}</div>
                      <div className="text-xs text-slate-500">Bets</div>
                    </div>
                    <div>
                      <div className="text-2xl font-bold text-emerald-400 font-mono">{displayStats.tennis.roi > 0 ? "+" : ""}{displayStats.tennis.roi.toFixed(1)}%</div>
                      <div className="text-xs text-slate-500">ROI</div>
                    </div>
                    <div>
                      <div className="text-2xl font-bold text-emerald-400 font-mono">{displayStats.tennis.win_rate.toFixed(0)}%</div>
                      <div className="text-xs text-slate-500">Win Rate</div>
                    </div>
                  </div>
                  <p className="text-xs text-slate-500">Independently verified on Tipstrr.com</p>
                </div>
              </div>
              <p className="mt-8 text-xs text-slate-500 max-w-2xl">
                Past performance does not guarantee future results. These calculations are illustrative based on historical data. Always bet responsibly and within your means.
              </p>
            </>
          )}
        </div>
      </section>
      <Footer />
    </div>
  );
}
