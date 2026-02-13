"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import { questionSlug } from "@/lib/parse-faq";
import { supabase, MarketStats } from "@/lib/supabase";
import { BASELINE_STATS, calculateROI, calculateWinRate, getBaselineDisplayStats } from "@/lib/baseline";
import BookmakerLogo from "@/components/BookmakerLogo";
import TelegramButton from "@/components/TelegramButton";
import Footer from "@/components/Footer";
import { BETA_NOTICE } from "@/lib/config";
import { formatStake } from "@/lib/format";

interface CombinedMarketStats {
  total_bets: number;
  roi: number;
  win_rate: number;
  avg_odds: number;
  total_profit: number;
}

export default function Home() {
  const [activeMarket, setActiveMarket] = useState("props");
  const [loading, setLoading] = useState(true);
  const [marketStats, setMarketStats] = useState<MarketStats[]>([]);
  const [recentBets, setRecentBets] = useState<any[]>([]);
  const [pendingBets, setPendingBets] = useState<any[]>([]);
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

    // Fetch recent settled bets (max 5 shown on homepage)
    const { data: recent, error: recentError } = await supabase
      .from("bets")
      .select("*, bookmaker:bookmakers(*)")
      .in("status", ["won", "lost"])
      .order("settled_at", { ascending: false })
      .limit(5);
    
    if (recent) setRecentBets(recent);
    if (recentError) console.error("Error fetching recent bets:", recentError);

    // Fetch pending bets for "Active Picks" (same max 5)
    const { data: pending, error: pendingError } = await supabase
      .from("bets")
      .select("*, bookmaker:bookmakers(*)")
      .eq("status", "pending")
      .order("posted_at", { ascending: false })
      .limit(5);
    
    if (pending) setPendingBets(pending);
    if (pendingError) console.error("Error fetching pending bets:", pendingError);

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
    const propsLiveStake = Number(propsLive?.total_stake) || propsLiveBets;
    
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
    const propsStake = BASELINE_STATS.props.total_stake + propsLiveStake;
    
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
    const tennisLiveStake = Number(tennisLive?.total_stake) || tennisLiveBets;
    
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
    const tennisStake = BASELINE_STATS.tennis.total_stake + tennisLiveStake;
    
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
    const overallLiveStake = propsLiveStake + tennisLiveStake;
    
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

  const displayStats = combinedStats ?? getBaselineDisplayStats();
  const markets = [
    { 
      id: "props", 
      name: "Player Props", 
      description: "Football individual player markets", 
      status: "active", 
      bets: `${displayStats.props.total_bets}+`, 
      profit: `${displayStats.props.roi > 0 ? "+" : ""}${displayStats.props.roi.toFixed(1)}% ROI` 
    },
    { 
      id: "atp", 
      name: "ATP Tennis", 
      description: "Pre-match singles markets", 
      status: "active", 
      bets: `${displayStats.tennis.total_bets}`, 
      profit: `${displayStats.tennis.roi > 0 ? "+" : ""}${displayStats.tennis.roi.toFixed(1)}% ROI` 
    },
    { id: "builders", name: "Bet Builders", description: "Same-game combinations", status: "coming" },
    { id: "atg", name: "ATG", description: "Anytime goalscorer markets", status: "coming" },
  ];

  return (
    <div className="min-h-screen bg-[#0f1117] text-slate-100">
      {/* Navigation is now in GlobalNav component in layout.tsx */}

      {/* Hero */}
      <section className="pt-6 pb-12 md:pt-6 md:pb-16 border-b border-slate-800/50">
        <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="max-w-4xl mx-auto text-center">
            <div className="flex flex-col items-center justify-center gap-2 mb-8">
              <div className="flex items-center gap-2">
                <span className="text-xs font-mono text-emerald-400 bg-emerald-500/10 px-3 py-1.5 rounded border border-emerald-500/20">FREE BETA</span>
              </div>
              <p className="text-sm text-slate-500 max-w-md text-center">
                {BETA_NOTICE}
              </p>
            </div>
            
            <h1 className="text-4xl sm:text-5xl md:text-6xl font-bold mb-2 leading-tight tracking-tight">
              Betting with <span className="text-emerald-400">mathematical edge</span>
            </h1>
            <p className="text-lg text-slate-400 font-medium mb-6 sm:mb-8">Il Margine: Mind the margin.</p>
            <p className="text-lg sm:text-xl text-slate-300 mb-8 sm:mb-10 leading-relaxed max-w-2xl mx-auto">
              Professional betting methodology from a former odds compiler. We identify value where bookmakers misprice markets. Data-driven selections, transparent results.
            </p>
            
            <div className="flex flex-wrap justify-center gap-3 sm:gap-4 mb-12 sm:mb-16">
              <TelegramButton variant="cta" className="transition-all hover:scale-105" />
              <Link href="/the-edge" className="border border-slate-600 hover:border-slate-400 text-slate-200 font-medium px-6 sm:px-8 py-3 sm:py-3.5 rounded-lg text-base sm:text-lg transition-all hover:bg-slate-800/50">
                How It Works
              </Link>
            </div>
            
            <div className="flex flex-wrap justify-center gap-4 sm:gap-6 md:gap-8">
              <div className="p-5 sm:p-6 bg-slate-900/60 rounded-lg border border-slate-800/50 hover:border-emerald-500/30 transition-all">
                <div className="text-3xl sm:text-4xl font-semibold text-emerald-400 font-mono mb-2 min-h-[2.25rem]">
                  {loading ? (
                    <span className="inline-block animate-pulse text-slate-500">—</span>
                  ) : (
                    <>{displayStats.overall.roi > 0 ? "+" : ""}{displayStats.overall.roi.toFixed(1)}% ROI</>
                  )}
                </div>
                <div className="text-sm text-slate-300">Since Oct 2024</div>
              </div>
              <div className="p-5 sm:p-6 bg-slate-900/60 rounded-lg border border-slate-800/50 hover:border-emerald-500/30 transition-all">
                <div className="text-3xl sm:text-4xl font-semibold text-emerald-400 font-mono mb-2 min-h-[2.25rem]">
                  {loading ? (
                    <span className="inline-block animate-pulse text-slate-500">—</span>
                  ) : (
                    <>{displayStats.overall.total_bets.toLocaleString()}+ Bets</>
                  )}
                </div>
                <div className="text-sm text-slate-300">
                  {(() => {
                    const start = new Date("2024-10-01");
                    const now = new Date();
                    const months = Math.max(1, (now.getFullYear() - start.getFullYear()) * 12 + (now.getMonth() - start.getMonth()));
                    return `${months}+ Months`;
                  })()}
                </div>
              </div>
              <div className="p-5 sm:p-6 bg-slate-900/60 rounded-lg border border-slate-800/50 hover:border-emerald-500/30 transition-all">
                <div className="text-3xl sm:text-4xl font-semibold text-emerald-400 mb-2">Data-Driven</div>
                <div className="text-sm text-slate-300">Mathematical Edge</div>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* Markets */}
      <section id="markets" className="py-12 md:py-16 border-b border-slate-800/50 scroll-mt-20">
        <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex items-center gap-2 mb-6">
            <span className="text-xs font-mono text-emerald-400 tracking-wider">MARKETS</span>
          </div>
          
          <h2 className="text-3xl sm:text-4xl font-semibold text-slate-100 mb-4 sm:mb-6">Where we find edge</h2>
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

      {/* Active picks (pending) */}
      <section className="py-12 md:py-16 border-b border-slate-800/50 bg-slate-900/20">
        <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="mb-8 sm:mb-10">
            <span className="text-xs font-mono text-emerald-400 mb-3 block tracking-wider">LIVE NOW</span>
            <h2 className="text-3xl sm:text-4xl font-semibold text-slate-100">Active Picks</h2>
          </div>
          <p className="text-slate-500 text-xs mb-6">Stake in units (1u = your standard stake). We typically recommend 0.5u–2u per pick.</p>
          {pendingBets.length > 0 ? (
            <div className="bg-slate-900/50 rounded-lg border border-slate-800 overflow-hidden">
              <div className="hidden md:block overflow-x-auto -mx-4 sm:mx-0">
                <table className="w-full border-collapse min-w-full">
                  <thead>
                    <tr className="border-b border-slate-700 text-xs text-slate-500 uppercase bg-slate-900/50">
                      <th className="px-4 py-3 text-left border-r border-slate-800 min-w-[180px]">Match</th>
                      <th className="px-4 py-3 text-left border-r border-slate-800" style={{ width: '100px' }}>Player</th>
                      <th className="px-4 py-3 text-left border-r border-slate-800">Selection</th>
                      <th className="px-4 py-3 text-center border-r border-slate-800" style={{ width: '70px' }}>Odds</th>
                      <th className="px-4 py-3 text-center border-r border-slate-800" style={{ width: '90px' }}>Bookmaker</th>
                      <th className="px-4 py-3 text-center border-r border-slate-800" style={{ width: '50px' }}>Stake</th>
                    </tr>
                  </thead>
                  <tbody>
                    {pendingBets.map((bet) => {
                      const href = bet.market === "tennis" ? "/tennis-tips#picks" : bet.market === "props" ? "/player-props#picks" : "#";
                      return (
                        <tr
                          key={bet.id}
                          className="border-b border-slate-800/50 hover:bg-slate-800/30 cursor-pointer"
                          onClick={() => window.location.href = href}
                        >
                          <td className="px-4 py-3 font-medium text-slate-200 border-r border-slate-800/50 min-w-[180px] whitespace-nowrap">{bet.event}</td>
                          <td className="px-4 py-3 text-slate-300 border-r border-slate-800/50">{bet.player || "–"}</td>
                          <td className="px-4 py-3 text-slate-300 border-r border-slate-800/50">{bet.selection}</td>
                          <td className="px-4 py-3 text-center border-r border-slate-800/50">
                            <span className="font-mono text-slate-200">{bet.odds}</span>
                          </td>
                          <td className="px-4 py-3 text-center border-r border-slate-800/50">
                            <div className="flex justify-center">
                              <BookmakerLogo bookmaker={bet.bookmaker} size="sm" />
                            </div>
                          </td>
                          <td className="px-4 py-3 text-center font-mono text-slate-200 border-r border-slate-800/50">{formatStake(bet.stake)}u</td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
              <div className="md:hidden divide-y divide-slate-800/50">
                {pendingBets.map((bet) => {
                  const href = bet.market === "tennis" ? "/tennis-tips#picks" : bet.market === "props" ? "/player-props#picks" : "#";
                  return (
                    <Link key={bet.id} href={href} className="block p-4 hover:bg-slate-800/20">
                      <div className="font-medium text-slate-200 mb-1">{bet.event}</div>
                      <div className="text-sm text-slate-300 mb-2">
                        {bet.player && <span>{bet.player} · </span>}
                        {bet.selection}
                      </div>
                      <div className="flex items-center gap-4 text-sm">
                        <span className="font-mono text-slate-200">{bet.odds}</span>
                        <BookmakerLogo bookmaker={bet.bookmaker} size="sm" />
                        <span className="font-mono text-slate-200">{formatStake(bet.stake)}u</span>
                      </div>
                    </Link>
                  );
                })}
              </div>
            </div>
          ) : (
            <div className="bg-slate-900/30 rounded-lg border border-slate-800 p-6 sm:p-8 text-center">
              <p className="text-slate-400 mb-4">No active picks right now. Check back later.</p>
            </div>
          )}
          <div className="mt-6 flex flex-wrap justify-center gap-4 sm:gap-6">
            <Link href="/tennis-tips#picks" className="text-sm text-slate-400 hover:text-emerald-400 transition-colors">
              View latest tennis tips →
            </Link>
            <Link href="/player-props#picks" className="text-sm text-slate-400 hover:text-emerald-400 transition-colors">
              View latest player props →
            </Link>
          </div>
        </div>
      </section>

      {/* Latest Results */}
      <section className="py-12 md:py-16 border-b border-slate-800/50 bg-slate-900/20">
        <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 mb-8 sm:mb-10">
            <div>
              <span className="text-xs font-mono text-emerald-400 mb-3 block tracking-wider">LATEST RESULTS</span>
              <h2 className="text-3xl sm:text-4xl font-semibold text-slate-100">Recent Selections</h2>
            </div>
            <div className="flex items-center gap-4">
              <span className="text-xs sm:text-sm text-emerald-400 font-mono">
                Last 7 days: {last7DaysProfit > 0 ? "+" : ""}{last7DaysProfit.toFixed(2)}u
              </span>
            </div>
          </div>
          <p className="text-slate-500 text-xs mb-6">Stake in units (1u = your standard stake). We typically recommend 0.5u–2u per pick.</p>
          {recentBets.length > 0 ? (
            <div className="bg-slate-900/50 rounded-lg border border-slate-800 overflow-hidden">
              {/* Desktop Table */}
              <div className="hidden md:block overflow-x-auto -mx-4 sm:mx-0">
                <table className="w-full border-collapse min-w-full">
                  <thead>
                    <tr className="border-b border-slate-700 text-xs text-slate-500 uppercase bg-slate-900/50">
                      <th className="px-4 py-3 text-left border-r border-slate-800 min-w-[180px]">Match</th>
                      <th className="px-4 py-3 text-left border-r border-slate-800" style={{ width: '100px' }}>Player</th>
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
                      const href = bet.market === "tennis" ? "/tennis-tips#picks" : bet.market === "props" ? "/player-props#picks" : "#";
                      return (
                        <tr 
                          key={bet.id} 
                          className="border-b border-slate-800/50 hover:bg-slate-800/30 cursor-pointer"
                          onClick={() => window.location.href = href}
                        >
                          <td className="px-4 py-3 font-medium text-slate-200 border-r border-slate-800/50 min-w-[180px] whitespace-nowrap">{bet.event}</td>
                          <td className="px-4 py-3 text-slate-300 border-r border-slate-800/50">{bet.player || "–"}</td>
                          <td className="px-4 py-3 text-slate-300 border-r border-slate-800/50">{bet.selection}</td>
                          <td className="px-4 py-3 text-center border-r border-slate-800/50">
                            <span className="font-mono text-slate-200">{bet.odds}</span>
                          </td>
                          <td className="px-4 py-3 text-center border-r border-slate-800/50">
                            <div className="flex justify-center">
                              <BookmakerLogo bookmaker={bet.bookmaker} size="sm" />
                            </div>
                          </td>
                          <td className="px-4 py-3 text-center font-mono text-slate-200 border-r border-slate-800/50">{formatStake(bet.stake)}u</td>
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
                  const href = bet.market === "tennis" ? "/tennis-tips#picks" : bet.market === "props" ? "/player-props#picks" : "#";
                  return (
                    <Link key={bet.id} href={href} className="block p-4 hover:bg-slate-800/20">
                      <div className="flex items-start justify-between mb-2">
                        <div className="flex-1">
                          <div className="font-medium text-slate-200 mb-1">{bet.event}</div>
                          <div className="text-sm text-slate-300 mb-1">
                            {bet.player && <span>{bet.player} · </span>}
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
                          <span className="font-mono text-slate-200">{formatStake(bet.stake)}u</span>
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
            <div className="bg-slate-900/30 rounded-lg border border-slate-800 p-8 sm:p-10 text-center">
              <p className="text-slate-400 mb-6">No results published yet.</p>
              <div className="flex flex-wrap justify-center gap-3">
                <Link
                  href="/tennis-tips#picks"
                  className="inline-flex items-center gap-2 bg-slate-800 hover:bg-slate-700 text-slate-200 font-medium px-4 py-2.5 rounded-lg transition-colors"
                >
                  Tennis Tips
                </Link>
                <Link
                  href="/player-props#picks"
                  className="inline-flex items-center gap-2 bg-slate-800 hover:bg-slate-700 text-slate-200 font-medium px-4 py-2.5 rounded-lg transition-colors"
                >
                  Player Props
                </Link>
              </div>
            </div>
          )}
          
          {recentBets.length > 0 && (
            <div className="mt-6 flex justify-center gap-4">
              <Link href="/tennis-tips#picks" className="text-sm text-slate-400 hover:text-emerald-400 transition-colors">
                View Tennis Tips Results →
              </Link>
              <Link href="/player-props#picks" className="text-sm text-slate-400 hover:text-emerald-400 transition-colors">
                View Player Props Results →
              </Link>
            </div>
          )}
        </div>
      </section>

      {/* Quick FAQ */}
      <section className="py-12 md:py-16 border-b border-slate-800/50 bg-slate-900/20">
        <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex flex-col sm:flex-row sm:items-end sm:justify-between gap-4 mb-8">
            <div>
              <span className="text-xs font-mono text-emerald-400 mb-2 block tracking-wider">QUICK FAQ</span>
              <h2 className="text-2xl sm:text-3xl font-semibold text-slate-100">Frequently asked questions</h2>
            </div>
            <Link href="/faq" className="text-sm font-medium text-emerald-400 hover:text-emerald-300 transition-colors shrink-0">
              View all FAQ →
            </Link>
          </div>
          <div className="grid sm:grid-cols-2 gap-4 max-w-4xl">
            {(
              [
                {
                  q: "What is Il Margine?",
                  title: "What is Il Margine?",
                  summary: "A professional betting analysis service from a former odds compiler. We find edge in player props and ATP tennis.",
                },
                {
                  q: "How do I start following Il Margine's betting tips?",
                  title: "How do I follow the tips?",
                  summary: "Join our free Telegram for player props; tennis tips are on the website. No payment, no trial.",
                },
                {
                  q: "Do I need a Telegram account to follow your tips?",
                  title: "Do I need Telegram?",
                  summary: "Only for football player props. Tennis tips are published on the site; no Telegram needed.",
                },
                {
                  q: "What is ROI and why does it matter more than win rate?",
                  title: "What is ROI and why does it matter?",
                  summary: "Return on investment. It matters more than win rate. You can win often and still lose money.",
                },
                {
                  q: "How much does Il Margine cost?",
                  title: "How much does it cost?",
                  summary: "Free. We're growing our follower base; all tips are free with no trial or card required.",
                },
                {
                  q: "What are player props in football betting?",
                  title: "What are player props?",
                  summary: "Bets on individual player stats (e.g. shots on target, fouls) rather than the match result.",
                },
              ] as const
            ).map((item) => (
              <Link
                key={item.q}
                href={`/faq#${questionSlug(item.q)}`}
                className="p-4 sm:p-5 rounded-xl bg-slate-800/40 border border-slate-700/50 hover:border-emerald-500/30 transition-colors text-left block"
              >
                <h3 className="font-medium text-slate-200 mb-1">{item.title}</h3>
                <p className="text-sm text-slate-500">{item.summary}</p>
              </Link>
            ))}
          </div>
        </div>
      </section>

      {/* CTA */}
      <section className="py-12 md:py-16">
        <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 text-center">
          <h2 className="text-3xl sm:text-4xl font-semibold text-slate-100 mb-4 sm:mb-6">Ready to join?</h2>
          <p className="text-base sm:text-lg text-slate-300 mb-8 sm:mb-10 max-w-lg mx-auto">
            Free selections delivered to Telegram. Match, selection, odds, bookmaker. Everything you need to place your bet.
          </p>
          <TelegramButton variant="cta" className="transition-all hover:scale-105" />
        </div>
      </section>

      <Footer />
    </div>
  );
}
