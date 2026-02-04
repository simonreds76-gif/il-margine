"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import Image from "next/image";
import { supabase, Bet, CategoryStats } from "@/lib/supabase";
import { BASELINE_STATS, calculateROI, calculateWinRate } from "@/lib/baseline";

export default function PlayerProps() {
  const [activeLeague, setActiveLeague] = useState("all");
  const [pendingBets, setPendingBets] = useState<Bet[]>([]);
  const [recentBets, setRecentBets] = useState<Bet[]>([]);
  const [stats, setStats] = useState<CategoryStats[]>([]);
  const [loading, setLoading] = useState(true);
  const [showAllPending, setShowAllPending] = useState(false);
  const [showAllRecent, setShowAllRecent] = useState(false);

  const leagueConfig = [
    { id: "all", name: "All Leagues", color: "emerald" },
    { id: "pl", name: "Premier League", color: "purple" },
    { id: "seriea", name: "Serie A", color: "blue" },
    { id: "ucl", name: "Champions League", color: "amber" },
    { id: "other", name: "Other", color: "cyan" },
  ];

  const colorClasses: Record<string, { border: string; text: string; bg: string; bar: string }> = {
    emerald: { border: "border-emerald-500/50", text: "text-emerald-400", bg: "bg-emerald-500/10", bar: "from-emerald-500 to-emerald-400" },
    purple: { border: "border-purple-500/50", text: "text-purple-400", bg: "bg-purple-500/10", bar: "from-purple-500 to-purple-400" },
    blue: { border: "border-blue-500/50", text: "text-blue-400", bg: "bg-blue-500/10", bar: "from-blue-500 to-blue-400" },
    amber: { border: "border-amber-500/50", text: "text-amber-400", bg: "bg-amber-500/10", bar: "from-amber-500 to-amber-400" },
    cyan: { border: "border-cyan-500/50", text: "text-cyan-400", bg: "bg-cyan-500/10", bar: "from-cyan-500 to-cyan-400" },
  };

  useEffect(() => {
    fetchData();

    // Set up real-time subscription to update when bets change
    const channel = supabase
      .channel('props-bets-changes')
      .on(
        'postgres_changes',
        {
          event: '*', // Listen to all events (INSERT, UPDATE, DELETE)
          schema: 'public',
          table: 'bets',
          filter: 'market=eq.props'
        },
        (payload) => {
          console.log('Props bet changed:', payload.eventType);
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
    
    const { data: pending } = await supabase
      .from("bets")
      .select("*, bookmaker:bookmakers(*)")
      .eq("market", "props")
      .eq("status", "pending")
      .order("posted_at", { ascending: false })
      .limit(50); // Fetch more from DB, but display only 5 initially
    
    if (pending) setPendingBets(pending);

    const { data: recent } = await supabase
      .from("bets")
      .select("*, bookmaker:bookmakers(*)")
      .eq("market", "props")
      .in("status", ["won", "lost"])
      .order("settled_at", { ascending: false })
      .limit(50); // Fetch more from DB, but display only 5 initially
    
    if (recent) setRecentBets(recent);

    const { data: categoryStats } = await supabase
      .from("category_stats")
      .select("*")
      .eq("market", "props");
    
    if (categoryStats) setStats(categoryStats);

    setLoading(false);
  };

  const getStatsForLeague = (leagueId: string) => {
    if (leagueId === "all") {
      // For "All Leagues" - combine baseline + all live data
      const allStats = stats.filter(s => s.market === "props");
      
      const liveBets = allStats.reduce((sum, s) => sum + (s.total_bets || 0), 0);
      const liveProfit = allStats.reduce((sum, s) => sum + (Number(s.total_profit) || 0), 0);
      const liveWins = allStats.reduce((sum, s) => sum + (s.wins || 0), 0);
      const liveLosses = allStats.reduce((sum, s) => sum + (s.losses || 0), 0);
      // Estimate stake from bets (assuming avg 1u per bet if no stake data)
      const liveStake = liveBets;
      
      // Combine with baseline
      const totalBets = BASELINE_STATS.props.total_bets + liveBets;
      const totalProfit = BASELINE_STATS.props.total_profit + liveProfit;
      const totalWins = BASELINE_STATS.props.wins + liveWins;
      const totalLosses = BASELINE_STATS.props.losses + liveLosses;
      const totalStake = BASELINE_STATS.props.total_stake + liveStake;
      
      const avgOdds = allStats.length > 0 ? allStats.reduce((sum, s) => sum + (Number(s.avg_odds) || 0), 0) / allStats.length : 0;
      
      return {
        total_bets: totalBets,
        roi: calculateROI(totalProfit, totalStake || 1),
        win_rate: calculateWinRate(totalWins, totalLosses),
        avg_odds: avgOdds,
      };
    }
    
    // For specific league - combine category baseline + live data for that category
    const categoryBaseline = BASELINE_STATS.categoryBaselines.props[leagueId as keyof typeof BASELINE_STATS.categoryBaselines.props];
    const leagueStats = stats.find(s => s.category === leagueId);
    
    if (!categoryBaseline) {
      // No baseline for this category, show only live data
      if (!leagueStats) {
        return { total_bets: 0, roi: 0, win_rate: 0, avg_odds: 0 };
      }
      const liveBets = leagueStats.total_bets || 0;
      const liveProfit = Number(leagueStats.total_profit) || 0;
      const liveWins = leagueStats.wins || 0;
      const liveLosses = leagueStats.losses || 0;
      // Estimate stake from bets (assuming avg 1u per bet if no stake data)
      const liveStake = liveBets;
      return {
        total_bets: liveBets,
        roi: liveStake > 0 ? calculateROI(liveProfit, liveStake) : 0,
        win_rate: calculateWinRate(liveWins, liveLosses),
        avg_odds: Number(leagueStats.avg_odds) || 0,
      };
    }
    
    const liveBets = leagueStats?.total_bets || 0;
    const liveProfit = Number(leagueStats?.total_profit) || 0;
    const liveWins = leagueStats?.wins || 0;
    const liveLosses = leagueStats?.losses || 0;
    // Estimate stake from bets (assuming avg 1u per bet if no stake data)
    const liveStake = liveBets;
    
    // Combine category baseline + live data
    const totalBets = categoryBaseline.total_bets + liveBets;
    const totalProfit = categoryBaseline.total_profit + liveProfit;
    const totalWins = categoryBaseline.wins + liveWins;
    const totalLosses = categoryBaseline.losses + liveLosses;
    const totalStake = categoryBaseline.total_stake + liveStake;
    
    return {
      total_bets: totalBets,
      roi: calculateROI(totalProfit, totalStake || 1),
      win_rate: calculateWinRate(totalWins, totalLosses),
      avg_odds: Number(leagueStats?.avg_odds) || 0,
    };
  };

  const filteredPending = activeLeague === "all" ? pendingBets : pendingBets.filter(b => b.category === activeLeague);
  const filteredRecent = activeLeague === "all" ? recentBets : recentBets.filter(b => b.category === activeLeague);
  
  // Display limits: show 5 initially, or all if expanded
  const displayedPending = showAllPending ? filteredPending : filteredPending.slice(0, 5);
  const displayedRecent = showAllRecent ? filteredRecent : filteredRecent.slice(0, 5);

  const activeColor = leagueConfig.find(l => l.id === activeLeague)?.color || "emerald";
  const currentStats = getStatsForLeague(activeLeague);

  const timeAgo = (dateString: string) => {
    const date = new Date(dateString);
    const now = new Date();
    const diffMs = now.getTime() - date.getTime();
    const diffMins = Math.floor(diffMs / 60000);
    const diffHours = Math.floor(diffMins / 60);
    const diffDays = Math.floor(diffHours / 24);
    if (diffDays > 0) return `${diffDays}d ago`;
    if (diffHours > 0) return `${diffHours}h ago`;
    if (diffMins > 0) return `${diffMins}m ago`;
    return "Just now";
  };

  return (
    <div className="min-h-screen bg-[#0f1117] text-slate-100">
      {/* Nav */}
      <nav className="border-b border-slate-800/80 sticky top-0 z-50 bg-[#0f1117]/95 backdrop-blur-sm">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex items-center justify-between h-16">
            <Link href="/" className="flex items-center">
              <Image src="/logo.png" alt="Il Margine" width={180} height={50} className="h-10 w-auto" style={{ background: 'transparent' }} />
            </Link>
            
            <div className="hidden md:flex items-center gap-6">
              <Link href="/" className="text-sm text-slate-400 hover:text-slate-100 transition-colors">Home</Link>
              <Link href="/player-props" className="text-sm text-emerald-400 font-medium">Player Props</Link>
              <Link href="/atp-tennis" className="text-sm text-slate-400 hover:text-slate-100 transition-colors">ATP Tennis</Link>
              <Link href="/calculator" className="text-sm text-slate-400 hover:text-slate-100 transition-colors">Calculator</Link>
              <button className="bg-emerald-500 hover:bg-emerald-400 text-black text-sm font-medium px-4 py-2 rounded transition-colors flex items-center gap-2">
                <svg className="w-4 h-4" viewBox="0 0 24 24" fill="currentColor"><path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm4.64 6.8c-.15 1.58-.8 5.42-1.13 7.19-.14.75-.42 1-.68 1.03-.58.05-1.02-.38-1.58-.75-.88-.58-1.38-.94-2.23-1.5-.99-.65-.35-1.01.22-1.59.15-.15 2.71-2.48 2.76-2.69a.2.2 0 00-.05-.18c-.06-.05-.14-.03-.21-.02-.09.02-1.49.95-4.22 2.79-.4.27-.76.41-1.08.4-.36-.01-1.04-.2-1.55-.37-.63-.2-1.12-.31-1.08-.66.02-.18.27-.36.74-.55 2.92-1.27 4.86-2.11 5.83-2.51 2.78-1.16 3.35-1.36 3.73-1.36.08 0 .27.02.39.12.1.08.13.19.14.27-.01.06.01.24 0 .38z"/></svg>
                Join Free
              </button>
            </div>
          </div>
        </div>
      </nav>

      {/* Hero */}
      <section className="py-12 border-b border-slate-800/50">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex items-center gap-2 mb-4">
            <Link href="/" className="text-sm text-slate-500 hover:text-slate-300">Home</Link>
            <span className="text-slate-600">/</span>
            <span className="text-sm text-emerald-400">Player Props</span>
          </div>
          
          <h1 className="text-3xl md:text-4xl font-bold mb-4">Football Player Props</h1>
          <p className="text-slate-400 max-w-3xl mb-8">
            Individual player markets represent one of the most inefficient pricing areas in football betting. 
            While bookmakers dedicate significant resources to match odds, player props receive far less attention.
          </p>

          <div className="flex flex-wrap gap-2 mb-8">
            <span className="px-3 py-1.5 bg-slate-800/50 rounded text-xs font-mono text-slate-400 border border-slate-700/50">Shots</span>
            <span className="px-3 py-1.5 bg-slate-800/50 rounded text-xs font-mono text-slate-400 border border-slate-700/50">Shots on Target</span>
            <span className="px-3 py-1.5 bg-slate-800/50 rounded text-xs font-mono text-slate-400 border border-slate-700/50">Fouls</span>
            <span className="px-3 py-1.5 bg-slate-800/50 rounded text-xs font-mono text-slate-400 border border-slate-700/50">Tackles</span>
            <span className="px-3 py-1.5 bg-slate-800/50 rounded text-xs font-mono text-slate-400 border border-slate-700/50">Cards</span>
          </div>

          <div className="bg-slate-900/50 rounded-lg border border-slate-800 p-6">
            <h3 className="font-semibold mb-4 text-emerald-400">Why Player Props?</h3>
            <div className="grid md:grid-cols-3 gap-6 text-sm text-slate-400">
              <div>
                <span className="text-slate-200 font-medium block mb-2">Market Inefficiency</span>
                Bookmakers apply wider margins but their pricing models are far less sophisticated than match odds. 
                Significant discrepancies exist between bookies.
              </div>
              <div>
                <span className="text-slate-200 font-medium block mb-2">Lower Limits, Higher Edge</span>
                Stakes are capped lower than match betting. But edges are substantially larger. 
                +25% ROI on capped stakes beats +2% ROI on unlimited stakes.
              </div>
              <div>
                <span className="text-slate-200 font-medium block mb-2">Data-Driven Selection</span>
                Every pick is backed by statistical analysis: player performance, 
                opponent metrics, tactical matchups. Pure numbers.
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* League Tabs */}
      <section className="py-8 border-b border-slate-800/50">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex flex-wrap gap-3 mb-8">
            {leagueConfig.map((league) => {
              const leagueStats = getStatsForLeague(league.id);
              return (
                <button
                  key={league.id}
                  onClick={() => setActiveLeague(league.id)}
                  className={`px-4 py-3 rounded-lg border transition-all ${
                    activeLeague === league.id
                      ? `bg-slate-900/80 ${colorClasses[league.color].border} ${colorClasses[league.color].text}`
                      : "bg-slate-900/30 border-slate-800 text-slate-400 hover:border-slate-700"
                  }`}
                >
                  <span className="font-medium">{league.name}</span>
                  <div className="flex gap-3 mt-1 text-xs">
                    <span>{leagueStats.total_bets} bets</span>
                    <span className={`${colorClasses[league.color].text} font-mono`}>
                      {leagueStats.roi > 0 ? "+" : ""}{leagueStats.roi.toFixed(1)}%
                    </span>
                  </div>
                </button>
              );
            })}
          </div>

          {/* Stats */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <div className="p-5 bg-slate-900/50 rounded-lg border border-slate-800">
              <div className="text-2xl font-bold text-white font-mono mb-2">{currentStats.total_bets}</div>
              <div className="text-xs text-slate-500 mb-3">Total Bets</div>
              <div className="h-2 bg-slate-800 rounded-full overflow-hidden">
                <div className={`h-full bg-gradient-to-r ${colorClasses[activeColor].bar} rounded-full`} style={{ width: `${Math.min((currentStats.total_bets / 1000) * 100, 100)}%` }} />
              </div>
            </div>
            <div className="p-5 bg-slate-900/50 rounded-lg border border-slate-800">
              <div className={`text-2xl font-bold ${colorClasses[activeColor].text} font-mono mb-2`}>{currentStats.roi > 0 ? "+" : ""}{currentStats.roi.toFixed(1)}%</div>
              <div className="text-xs text-slate-500 mb-3">ROI</div>
              <div className="h-2 bg-slate-800 rounded-full overflow-hidden">
                <div className={`h-full bg-gradient-to-r ${colorClasses[activeColor].bar} rounded-full`} style={{ width: `${Math.min(Math.abs(currentStats.roi) * 3, 100)}%` }} />
              </div>
            </div>
            <div className="p-5 bg-slate-900/50 rounded-lg border border-slate-800">
              <div className={`text-2xl font-bold ${colorClasses[activeColor].text} font-mono mb-2`}>{currentStats.win_rate.toFixed(0)}%</div>
              <div className="text-xs text-slate-500 mb-3">Win Rate</div>
              <div className="h-2 bg-slate-800 rounded-full overflow-hidden">
                <div className={`h-full bg-gradient-to-r ${colorClasses[activeColor].bar} rounded-full`} style={{ width: `${currentStats.win_rate}%` }} />
              </div>
            </div>
            <div className="p-5 bg-slate-900/50 rounded-lg border border-slate-800">
              <div className={`text-2xl font-bold ${colorClasses[activeColor].text} font-mono mb-2`}>{currentStats.avg_odds.toFixed(2)}</div>
              <div className="text-xs text-slate-500 mb-3">Avg Odds</div>
              <div className="h-2 bg-slate-800 rounded-full overflow-hidden">
                <div className={`h-full bg-gradient-to-r ${colorClasses[activeColor].bar} rounded-full`} style={{ width: `${(currentStats.avg_odds / 3) * 100}%` }} />
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* Active Picks */}
      <section className="py-12 border-b border-slate-800/50">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex items-center justify-between mb-6">
            <div>
              <span className="text-xs font-mono text-emerald-400 mb-2 block">ACTIVE SELECTIONS</span>
              <h2 className="text-2xl font-bold">Current Picks</h2>
            </div>
            <span className="text-xs text-slate-500">Updated in real-time via Telegram</span>
          </div>

          {loading ? (
            <div className="bg-slate-900/30 rounded-lg border border-slate-800 p-8 text-center">
              <p className="text-slate-500">Loading...</p>
            </div>
          ) : filteredPending.length > 0 ? (
            <div className="bg-slate-900/50 rounded-lg border border-slate-800 overflow-hidden">
              {/* Desktop Table */}
              <div className="hidden md:block overflow-x-auto">
                <table className="w-full border-collapse">
                  <thead>
                    <tr className="border-b border-slate-700 text-xs text-slate-500 uppercase bg-slate-900/50">
                      <th className="px-4 py-3 text-left border-r border-slate-800">Match</th>
                      <th className="px-4 py-3 text-left border-r border-slate-800" style={{ width: '80px' }}>Player</th>
                      <th className="px-4 py-3 text-left border-r border-slate-800">Selection</th>
                      <th className="px-4 py-3 text-center border-r border-slate-800" style={{ width: '70px' }}>Odds</th>
                      <th className="px-4 py-3 text-center border-r border-slate-800" style={{ width: '90px' }}>Bookmaker</th>
                      <th className="px-4 py-3 text-center border-r border-slate-800" style={{ width: '50px' }}>Stake</th>
                      <th className="px-4 py-3 text-center" style={{ width: '70px' }}>Status</th>
                    </tr>
                  </thead>
                  <tbody>
                    {displayedPending.map((pick) => (
                      <tr key={pick.id} className="border-b border-slate-800/50 hover:bg-slate-800/20">
                        <td className="px-4 py-3 font-medium text-slate-200 border-r border-slate-800/30">{pick.event}</td>
                        <td className="px-4 py-3 text-slate-400 border-r border-slate-800/30">{pick.player || '-'}</td>
                        <td className="px-4 py-3 text-slate-300 border-r border-slate-800/30">{pick.selection}</td>
                        <td className="px-4 py-3 text-center border-r border-slate-800/30">
                          <span className="font-mono text-slate-200">{pick.odds}</span>
                        </td>
                        <td className="px-4 py-3 text-center border-r border-slate-800/30">
                          {pick.bookmaker?.short_name ? (
                            <span className="text-xs text-slate-400">{pick.bookmaker.short_name}</span>
                          ) : (
                            <span className="text-xs text-slate-600">-</span>
                          )}
                        </td>
                        <td className="px-4 py-3 text-center font-mono text-slate-200 border-r border-slate-800/30">{pick.stake}u</td>
                        <td className="px-4 py-3 text-center">
                          <span className="text-xs font-mono px-2 py-1 rounded bg-amber-500/20 text-amber-400">
                            PENDING
                          </span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              {/* Mobile Cards */}
              <div className="md:hidden divide-y divide-slate-800/50">
                {displayedPending.map((pick) => (
                  <div key={pick.id} className="p-4">
                    <div className="flex items-start justify-between mb-2">
                      <div className="flex-1">
                        <div className="font-medium text-slate-200 mb-1">{pick.event}</div>
                        <div className="text-sm text-slate-400 mb-1">
                          {pick.player && <span>{pick.player} • </span>}
                          {pick.selection}
                        </div>
                      </div>
                      <span className="text-xs font-mono px-2 py-1 rounded bg-amber-500/20 text-amber-400 ml-2">
                        PENDING
                      </span>
                    </div>
                    <div className="flex items-center gap-4 text-sm">
                      <span className="font-mono text-slate-200">{pick.odds}</span>
                      <span className="text-xs text-slate-400">{pick.bookmaker?.short_name || '-'}</span>
                      <span className="font-mono text-slate-300">{pick.stake}u</span>
                    </div>
                  </div>
                ))}
              </div>
              
              {/* Show More/Less Button */}
              {filteredPending.length > 5 && (
                <div className="border-t border-slate-800 p-4 text-center">
                  <button
                    onClick={() => setShowAllPending(!showAllPending)}
                    className="text-sm text-emerald-400 hover:text-emerald-300 font-medium transition-colors"
                  >
                    {showAllPending ? (
                      <>Show Less ({filteredPending.length - 5} hidden)</>
                    ) : (
                      <>Show All ({filteredPending.length - 5} more)</>
                    )}
                  </button>
                </div>
              )}
            </div>
          ) : (
            <div className="bg-slate-900/30 rounded-lg border border-slate-800 p-8 text-center">
              <p className="text-slate-500">No active selections at the moment</p>
              <p className="text-xs text-slate-600 mt-2">Join Telegram to get notified when new selections are posted</p>
            </div>
          )}
          
          <div className="mt-6 p-4 bg-slate-900/30 rounded-lg border border-slate-800 text-center">
            <p className="text-sm text-slate-400 mb-3">Get real-time alerts when new selections are posted</p>
            <button className="bg-emerald-500 hover:bg-emerald-400 text-black font-medium px-5 py-2 rounded inline-flex items-center gap-2 transition-colors text-sm">
              <svg className="w-4 h-4" viewBox="0 0 24 24" fill="currentColor"><path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm4.64 6.8c-.15 1.58-.8 5.42-1.13 7.19-.14.75-.42 1-.68 1.03-.58.05-1.02-.38-1.58-.75-.88-.58-1.38-.94-2.23-1.5-.99-.65-.35-1.01.22-1.59.15-.15 2.71-2.48 2.76-2.69a.2.2 0 00-.05-.18c-.06-.05-.14-.03-.21-.02-.09.02-1.49.95-4.22 2.79-.4.27-.76.41-1.08.4-.36-.01-1.04-.2-1.55-.37-.63-.2-1.12-.31-1.08-.66.02-.18.27-.36.74-.55 2.92-1.27 4.86-2.11 5.83-2.51 2.78-1.16 3.35-1.36 3.73-1.36.08 0 .27.02.39.12.1.08.13.19.14.27-.01.06.01.24 0 .38z"/></svg>
              Join Telegram Channel
            </button>
          </div>
        </div>
      </section>

      {/* Recent Results */}
      <section className="py-12 border-b border-slate-800/50">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="mb-6">
            <span className="text-xs font-mono text-emerald-400 mb-2 block">RESULTS</span>
            <h2 className="text-2xl font-bold">Recent Selections</h2>
          </div>

          {filteredRecent.length > 0 ? (
            <div className="bg-slate-900/50 rounded-lg border border-slate-800 overflow-hidden">
              {/* Desktop Table */}
              <div className="hidden md:block overflow-x-auto">
                <table className="w-full border-collapse">
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
                    {displayedRecent.map((result) => (
                      <tr key={result.id} className="border-b border-slate-800/50 hover:bg-slate-800/20">
                        <td className="px-4 py-3 font-medium text-slate-200 border-r border-slate-800/30">{result.event}</td>
                        <td className="px-4 py-3 text-slate-400 border-r border-slate-800/30">{result.player || '-'}</td>
                        <td className="px-4 py-3 text-slate-300 border-r border-slate-800/30">{result.selection}</td>
                        <td className="px-4 py-3 text-center border-r border-slate-800/30">
                          <span className="font-mono text-slate-200">{result.odds}</span>
                        </td>
                        <td className="px-4 py-3 text-center border-r border-slate-800/30">
                          {result.bookmaker?.short_name ? (
                            <span className="text-xs text-slate-400">{result.bookmaker.short_name}</span>
                          ) : (
                            <span className="text-xs text-slate-600">-</span>
                          )}
                        </td>
                        <td className="px-4 py-3 text-center font-mono text-slate-200 border-r border-slate-800/30">{result.stake}u</td>
                        <td className="px-4 py-3 text-center border-r border-slate-800/30">
                          <span className={`text-xs font-mono px-2 py-1 rounded ${result.status === "won" ? "text-emerald-400 bg-emerald-500/10" : "text-red-400 bg-red-500/10"}`}>
                            {result.status.toUpperCase()}
                          </span>
                        </td>
                        <td className={`px-4 py-3 text-right font-mono font-medium ${result.profit_loss && result.profit_loss > 0 ? "text-emerald-400" : "text-red-400"}`}>
                          {result.profit_loss && result.profit_loss > 0 ? "+" : ""}{result.profit_loss?.toFixed(2)}u
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              {/* Mobile Cards */}
              <div className="md:hidden divide-y divide-slate-800/50">
                {displayedRecent.map((result) => (
                  <div key={result.id} className="p-4">
                    <div className="flex items-start justify-between mb-2">
                      <div className="flex-1">
                        <div className="font-medium text-slate-200 mb-1">{result.event}</div>
                        <div className="text-sm text-slate-400 mb-1">
                          {result.player && <span>{result.player} • </span>}
                          {result.selection}
                        </div>
                      </div>
                      <span className={`text-xs font-mono px-2 py-1 rounded ml-2 ${result.status === "won" ? "text-emerald-400 bg-emerald-500/10" : "text-red-400 bg-red-500/10"}`}>
                        {result.status.toUpperCase()}
                      </span>
                    </div>
                    <div className="flex items-center justify-between text-sm">
                      <div className="flex items-center gap-4">
                        <span className="font-mono text-slate-200">{result.odds}</span>
                        <span className="text-xs text-slate-400">{result.bookmaker?.short_name || '-'}</span>
                        <span className="font-mono text-slate-300">{result.stake}u</span>
                      </div>
                      <span className={`font-mono font-medium ${result.profit_loss && result.profit_loss > 0 ? "text-emerald-400" : "text-red-400"}`}>
                        {result.profit_loss && result.profit_loss > 0 ? "+" : ""}{result.profit_loss?.toFixed(2)}u
                      </span>
                    </div>
                  </div>
                ))}
              </div>
              
              {/* Show More/Less Button */}
              {filteredRecent.length > 5 && (
                <div className="border-t border-slate-800 p-4 text-center">
                  <button
                    onClick={() => setShowAllRecent(!showAllRecent)}
                    className="text-sm text-emerald-400 hover:text-emerald-300 font-medium transition-colors"
                  >
                    {showAllRecent ? (
                      <>Show Less ({filteredRecent.length - 5} hidden)</>
                    ) : (
                      <>Show All ({filteredRecent.length - 5} more)</>
                    )}
                  </button>
                </div>
              )}
            </div>
          ) : (
            <div className="bg-slate-900/30 rounded-lg border border-slate-800 p-8 text-center">
              <p className="text-slate-500">No settled bets yet</p>
            </div>
          )}
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
            <div className="text-xs text-slate-600">Gamble responsibly. 18+ only.</div>
          </div>
        </div>
      </footer>
    </div>
  );
}
