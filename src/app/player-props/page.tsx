"use client";

import { useState, useEffect, useCallback } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { supabase, Bet, CategoryStats } from "@/lib/supabase";
import { BASELINE_STATS, calculateROI, calculateWinRate } from "@/lib/baseline";
import BookmakerLogo from "@/components/BookmakerLogo";
import BetMobileMeta from "@/components/BetMobileMeta";
import MarketBadge from "@/components/MarketBadge";
import PnL from "@/components/PnL";
import ResultBadge from "@/components/ResultBadge";

import Footer from "@/components/Footer";
import MonthlyBreakdownSection from "@/components/MonthlyBreakdownSection";
import PageHomeLink from "@/components/PageHomeLink";
import { formatStake, formatMatchDate, formatOdds } from "@/lib/format";
import { slugifyTip } from "@/lib/slugify";

export default function PlayerProps() {
  const router = useRouter();
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

  const fetchData = useCallback(async () => {
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
      .in("status", ["won", "lost", "void"])
      .order("settled_at", { ascending: false })
      .limit(50); // Fetch more from DB, but display only 5 initially
    
    if (recent) setRecentBets(recent);

    const { data: categoryStats } = await supabase
      .from("category_stats")
      .select("*")
      .eq("market", "props");
    
    if (categoryStats) setStats(categoryStats);
    setLoading(false);
  }, []);

  useEffect(() => {
    const initialFetch = window.setTimeout(() => {
      void fetchData();
    }, 0);
    const handleFocus = () => {
      void fetchData();
    };
    const handleVisibility = () => {
      if (document.visibilityState === "visible") {
        void fetchData();
      }
    };
    window.addEventListener("focus", handleFocus);
    document.addEventListener("visibilitychange", handleVisibility);

    return () => {
      window.clearTimeout(initialFetch);
      window.removeEventListener("focus", handleFocus);
      document.removeEventListener("visibilitychange", handleVisibility);
    };
  }, [fetchData]);

  // Scroll to #picks when landing from homepage link (client-side nav doesn't scroll to hash)
  useEffect(() => {
    if (typeof window === "undefined" || window.location.hash !== "#picks" || loading) return;
    const el = document.getElementById("picks");
    if (!el) return;
    requestAnimationFrame(() => requestAnimationFrame(() => el.scrollIntoView({ behavior: "smooth", block: "start" })));
  }, [loading]);

  const getStatsForLeague = (leagueId: string) => {
    if (leagueId === "all") {
      // For "All Leagues" - combine baseline + all live data
      const allStats = stats.filter(s => s.market === "props");
      
      const liveBets = allStats.reduce((sum, s) => sum + (s.total_bets || 0), 0);
      const liveProfit = allStats.reduce((sum, s) => sum + (Number(s.total_profit) || 0), 0);
      const liveWins = allStats.reduce((sum, s) => sum + (s.wins || 0), 0);
      const liveLosses = allStats.reduce((sum, s) => sum + (s.losses || 0), 0);
      // Use actual stake from DB (won+lost); fallback to bet count for legacy/no settled
      const liveStake = allStats.reduce((sum, s) => sum + (Number(s.total_stake) || 0), 0) || liveBets;
      
      // Combine with baseline
      const totalBets = BASELINE_STATS.props.total_bets + liveBets;
      const totalProfit = BASELINE_STATS.props.total_profit + liveProfit;
      const totalWins = BASELINE_STATS.props.wins + liveWins;
      const totalLosses = BASELINE_STATS.props.losses + liveLosses;
      const totalStake = BASELINE_STATS.props.total_stake + liveStake;
      
      // Weighted avg by bet count (baseline + live)
      const baselineOddsWeight = Object.values(BASELINE_STATS.categoryBaselines.props).reduce(
        (sum, c) => sum + (c.avg_odds || 0) * (c.total_bets || 0), 0
      );
      const liveOddsWeight = allStats.reduce((sum, s) => sum + (Number(s.avg_odds) || 0) * (s.total_bets || 0), 0);
      const avgOdds = totalBets > 0 ? (baselineOddsWeight + liveOddsWeight) / totalBets : 0;
      
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
      const liveStake = Number(leagueStats.total_stake) || liveBets;
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
    const liveStake = Number(leagueStats?.total_stake) || liveBets;
    const liveAvgOdds = Number(leagueStats?.avg_odds) || 0;
    
    // Combine category baseline + live data
    const totalBets = categoryBaseline.total_bets + liveBets;
    const totalProfit = categoryBaseline.total_profit + liveProfit;
    const totalWins = categoryBaseline.wins + liveWins;
    const totalLosses = categoryBaseline.losses + liveLosses;
    const totalStake = categoryBaseline.total_stake + liveStake;
    
    // Weighted avg odds (baseline + live); fallback to baseline when no live data
    const baselineOddsWeight = (categoryBaseline.avg_odds || 0) * (categoryBaseline.total_bets || 0);
    const liveOddsWeight = liveAvgOdds * liveBets;
    const avgOdds = totalBets > 0 ? (baselineOddsWeight + liveOddsWeight) / totalBets : (categoryBaseline.avg_odds || 0);
    
    return {
      total_bets: totalBets,
      roi: calculateROI(totalProfit, totalStake || 1),
      win_rate: calculateWinRate(totalWins, totalLosses),
      avg_odds: avgOdds,
    };
  };

  const filteredPending = activeLeague === "all" ? pendingBets : pendingBets.filter(b => b.category === activeLeague);
  const filteredRecent = activeLeague === "all" ? recentBets : recentBets.filter(b => b.category === activeLeague);
  
  // Display limits: show 5 initially, or all if expanded
  const displayedPending = showAllPending ? filteredPending : filteredPending.slice(0, 5);
  const displayedRecent = showAllRecent ? filteredRecent : filteredRecent.slice(0, 5);

  const activeColor = leagueConfig.find(l => l.id === activeLeague)?.color || "emerald";
  const currentStats = getStatsForLeague(activeLeague);

  return (
    <div className="min-h-screen bg-[#0f1117] text-slate-100">
      {/* Nav */}
            {/* Navigation is now in GlobalNav component in layout.tsx */}


      {/* Hero */}
      <section className="pt-6 pb-12 md:pt-6 md:pb-16 border-b border-slate-800/50">
        <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="mb-6 flex flex-wrap items-center gap-3">
            <PageHomeLink />
            <span className="text-xs font-mono uppercase tracking-[0.18em] text-emerald-400">Player Props</span>
          </div>
          
          <h1 className="text-3xl sm:text-4xl font-semibold text-slate-100 mb-4 sm:mb-6">
            Football Player <span className="text-emerald-400">Props</span>
          </h1>
          <p className="text-base sm:text-lg text-slate-300 max-w-3xl leading-relaxed">
            Player props are one of the few football markets where detailed matchup work still pays. We focus on
            shots, tackles, fouls and cards where role, volume and game state move faster than the bookmaker template,
            and where the wrong line appears more often than it does in the main match odds.
          </p>

          <div className="mt-6 flex flex-wrap gap-2">
            <span className="rounded-full border border-slate-700/60 bg-slate-900/50 px-3 py-1.5 text-xs font-mono text-slate-400">Shots</span>
            <span className="rounded-full border border-slate-700/60 bg-slate-900/50 px-3 py-1.5 text-xs font-mono text-slate-400">Shots on Target</span>
            <span className="rounded-full border border-slate-700/60 bg-slate-900/50 px-3 py-1.5 text-xs font-mono text-slate-400">Fouls</span>
            <span className="rounded-full border border-slate-700/60 bg-slate-900/50 px-3 py-1.5 text-xs font-mono text-slate-400">Tackles</span>
            <span className="rounded-full border border-slate-700/60 bg-slate-900/50 px-3 py-1.5 text-xs font-mono text-slate-400">Cards</span>
          </div>
        </div>
      </section>

      {/* League Tabs */}
      <section className="py-12 md:py-16 border-b border-slate-800/50">
        <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex flex-wrap gap-2 sm:gap-3 mb-6 sm:mb-8">
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
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3 sm:gap-4">
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
              <div className={`text-2xl font-bold ${colorClasses[activeColor].text} font-mono mb-2`}>{currentStats.win_rate.toFixed(1)}%</div>
              <div className="text-xs text-slate-500 mb-3">Win Rate</div>
              <div className="h-2 bg-slate-800 rounded-full overflow-hidden">
                <div className={`h-full bg-gradient-to-r ${colorClasses[activeColor].bar} rounded-full`} style={{ width: `${currentStats.win_rate}%` }} />
              </div>
            </div>
            <div className="p-5 bg-slate-900/50 rounded-lg border border-slate-800">
              <div className={`text-2xl font-bold ${colorClasses[activeColor].text} font-mono mb-2`}>{formatOdds(currentStats.avg_odds)}</div>
              <div className="text-xs text-slate-500 mb-3">Avg Odds</div>
              <div className="h-2 bg-slate-800 rounded-full overflow-hidden">
                <div className={`h-full bg-gradient-to-r ${colorClasses[activeColor].bar} rounded-full`} style={{ width: `${(currentStats.avg_odds / 3) * 100}%` }} />
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* Active Picks - id for deep link from homepage */}
      <section id="picks" className="py-12 md:py-16 border-b border-slate-800/50 scroll-mt-6">
        <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex items-center justify-between mb-6">
            <div>
              <span className="text-xs font-mono text-emerald-400 mb-2 block">ACTIVE SELECTIONS</span>
              <h2 className="text-3xl sm:text-4xl font-semibold text-slate-100">Current Picks</h2>
            </div>
            <span className="text-xs text-slate-500 hidden sm:block">Updated in real-time on site</span>
          </div>
          <p className="text-slate-500 text-xs mb-6">Stake in units (1u = your standard stake). We typically recommend 0.5u-2u per pick.</p>

          {loading ? (
            <div className="bg-slate-900/30 rounded-lg border border-slate-800 p-8 text-center">
              <p className="text-slate-500">Loading...</p>
            </div>
          ) : filteredPending.length > 0 ? (
            <div className="bg-slate-900/50 rounded-lg border border-slate-800 overflow-hidden">
              {/* Desktop Table */}
              <div className="hidden md:block overflow-x-auto -mx-4 sm:mx-0">
                <table className="w-full border-collapse min-w-full">
                  <thead>
                    <tr className="border-b border-slate-700 text-xs text-slate-500 uppercase bg-slate-900/50">
                      <th className="px-4 py-3 text-left border-r border-slate-800" style={{ width: '50px' }}></th>
                      <th className="px-4 py-3 text-left border-r border-slate-800" style={{ width: '70px' }}>Date</th>
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
                      <tr key={pick.id} className="border-b border-slate-700 hover:bg-slate-800/30">
                        <td className="px-4 py-4 text-center border-r border-slate-800/50">
                          <MarketBadge market={pick.market} category={pick.category} hideOnMobile />
                        </td>
                        <td className="px-4 py-4 text-slate-400 border-r border-slate-800/50 text-sm whitespace-nowrap">{formatMatchDate(pick.match_date)}</td>
                        <td className="px-4 py-4 font-medium text-slate-200 border-r border-slate-800/50">
                          <Link href={`/tips/${slugifyTip(pick.event, pick.id)}`} className="hover:text-emerald-400 transition-colors">
                            {pick.event}
                          </Link>
                        </td>
                        <td className="px-4 py-4 text-slate-300 border-r border-slate-800/50">{pick.player || '-'}</td>
                        <td className="px-4 py-4 text-slate-300 border-r border-slate-800/50">{pick.selection}</td>
                        <td className="px-4 py-4 text-center border-r border-slate-800/50">
                          <span className="font-mono text-slate-200">{formatOdds(pick.odds)}</span>
                        </td>
                        <td className="px-4 py-4 text-center border-r border-slate-800/50">
                          <div className="flex justify-center">
                            <BookmakerLogo bookmaker={pick.bookmaker} size="sm" />
                          </div>
                        </td>
                        <td className="px-4 py-4 text-center font-mono text-slate-200 border-r border-slate-800/50">{formatStake(pick.stake)}u</td>
                        <td className="px-4 py-4 text-center">
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
              <div className="md:hidden divide-y divide-slate-600">
                {displayedPending.map((pick) => (
                  <div
                    key={pick.id}
                    role="link"
                    tabIndex={0}
                    className="block cursor-pointer p-5 hover:bg-slate-800/20 active:bg-slate-800/30"
                    onClick={() => router.push(`/tips/${slugifyTip(pick.event, pick.id)}`)}
                    onKeyDown={(event) => {
                      if (event.key === "Enter" || event.key === " ") {
                        event.preventDefault();
                        router.push(`/tips/${slugifyTip(pick.event, pick.id)}`);
                      }
                    }}
                  >
                    <div className="flex items-start justify-between mb-2">
                      <div className="flex-1">
                        <div className="flex items-center gap-2 mb-1">
                          <span className="text-xs text-slate-500 whitespace-nowrap">{formatMatchDate(pick.match_date)}</span>
                        </div>
                        <div className="font-medium text-slate-200 mb-1 block">
                          {pick.event}
                        </div>
                        <div className="text-sm text-slate-400 mb-1">
                          {pick.player && <span>{pick.player} | </span>}
                          {pick.selection}
                        </div>
                      </div>
                      <span className="text-xs font-mono px-2 py-1 rounded bg-amber-500/20 text-amber-400 ml-2">
                        PENDING
                      </span>
                    </div>
                    <BetMobileMeta odds={pick.odds} bookmaker={pick.bookmaker} stake={pick.stake} />
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
              <p className="text-xs text-slate-600 mt-2">Check back soon for new selections</p>
            </div>
          )}
          
          <div className="mt-6 p-4 bg-slate-900/30 rounded-lg border border-slate-800 text-center">
            <p className="text-sm text-slate-400">All selections posted here in real time. Bookmark this page.</p>
          </div>
        </div>
      </section>

      <section className="py-12 md:py-16 border-b border-slate-800/50">
        <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="rounded-2xl border border-slate-800 bg-slate-900/55 p-6 sm:p-7">
            <div className="mb-5">
              <div className="text-xs font-mono uppercase tracking-[0.18em] text-emerald-400">Our methodology</div>
              <h2 className="mt-2 text-2xl sm:text-3xl font-semibold text-slate-100">How the edge is built</h2>
            </div>
            <div className="grid gap-4 md:grid-cols-3">
              <div className="rounded-xl border border-slate-800/80 bg-slate-950/40 p-5">
                <div className="text-[11px] font-mono uppercase tracking-[0.18em] text-emerald-400">01</div>
                <h3 className="mt-3 text-base font-semibold text-slate-100">Less efficient than main markets</h3>
                <p className="mt-2 text-sm leading-6 text-slate-400">
                  Match odds attract the sharpest pricing and the most attention. Props usually do not. The margins are
                  wider, but the modelling is also thinner, which leaves more room for one bookmaker to hang a number
                  that another would never copy.
                </p>
              </div>
              <div className="rounded-xl border border-slate-800/80 bg-slate-950/40 p-5">
                <div className="text-[11px] font-mono uppercase tracking-[0.18em] text-emerald-400">02</div>
                <h3 className="mt-3 text-base font-semibold text-slate-100">Role and matchup before averages</h3>
                <p className="mt-2 text-sm leading-6 text-slate-400">
                  A prop line only makes sense in context. We care about role, likely minutes, set-piece share, team
                  shape, opponent tendencies and referee profile. A shots line for a high-volume winger means something
                  very different from the same number on a full-back.
                </p>
              </div>
              <div className="rounded-xl border border-slate-800/80 bg-slate-950/40 p-5">
                <div className="text-[11px] font-mono uppercase tracking-[0.18em] text-emerald-400">03</div>
                <h3 className="mt-3 text-base font-semibold text-slate-100">Price before player name</h3>
                <p className="mt-2 text-sm leading-6 text-slate-400">
                  We are not trying to bet the most famous player on the slate. We are trying to take the best number.
                  Sometimes that means a star in a strong spot; sometimes it means a less glamorous role player whose
                  line has been copied without enough thought.
                </p>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* Recent Results */}
      <section className="py-12 md:py-16 border-b border-slate-800/50">
        <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="mb-6">
            <span className="text-xs font-mono text-emerald-400 mb-2 block">RESULTS</span>
            <h2 className="text-3xl sm:text-4xl font-semibold text-slate-100">Recent Selections</h2>
          </div>

          {filteredRecent.length > 0 ? (
            <div className="bg-slate-900/50 rounded-lg border border-slate-800 overflow-hidden">
              {/* Desktop Table */}
              <div className="hidden md:block overflow-x-auto -mx-4 sm:mx-0">
                <table className="w-full border-collapse min-w-full">
                  <thead>
                    <tr className="border-b border-slate-700 text-xs text-slate-500 uppercase bg-slate-900/50">
                      <th className="px-4 py-3 text-left border-r border-slate-800" style={{ width: '50px' }}></th>
                      <th className="px-4 py-3 text-left border-r border-slate-800" style={{ width: '70px' }}>Date</th>
                      <th className="px-4 py-3 text-left border-r border-slate-800">Match</th>
                      <th className="px-4 py-3 text-left border-r border-slate-800" style={{ width: '80px' }}>Player</th>
                      <th className="px-4 py-3 text-left border-r border-slate-800">Selection</th>
                      <th className="px-4 py-3 text-center border-r border-slate-800" style={{ width: '70px' }}>Odds</th>
                      <th className="px-4 py-3 text-center border-r border-slate-800" style={{ width: '90px' }}>Bookmaker</th>
                      <th className="px-4 py-3 text-center border-r border-slate-800" style={{ width: '50px' }}>Stake</th>
                      <th className="px-4 py-3 text-center border-r border-slate-800" style={{ width: '84px' }}>Result</th>
                      <th className="px-4 py-3 text-right" style={{ width: '84px' }}>P/L</th>
                    </tr>
                  </thead>
                  <tbody>
                    {displayedRecent.map((result) => (
                      <tr key={result.id} className="border-b border-slate-700 hover:bg-slate-800/30">
                        <td className="px-4 py-4 text-center border-r border-slate-800/50">
                          <MarketBadge market={result.market} category={result.category} hideOnMobile />
                        </td>
                        <td className="px-4 py-3 text-slate-400 border-r border-slate-800/50 text-sm whitespace-nowrap">{formatMatchDate(result.match_date)}</td>
                        <td className="px-4 py-4 font-medium text-slate-200 border-r border-slate-800/50">
                          <Link href={`/tips/${slugifyTip(result.event, result.id)}`} className="hover:text-emerald-400 transition-colors">
                            {result.event}
                          </Link>
                        </td>
                        <td className="px-4 py-4 text-slate-300 border-r border-slate-800/50">{result.player || '-'}</td>
                        <td className="px-4 py-4 text-slate-300 border-r border-slate-800/50">{result.selection}</td>
                        <td className="px-4 py-4 text-center border-r border-slate-800/50">
                          <span className="font-mono text-slate-200">{formatOdds(result.odds)}</span>
                        </td>
                          <td className="px-4 py-4 text-center border-r border-slate-800/50">
                            <div className="flex justify-center">
                              <BookmakerLogo bookmaker={result.bookmaker} size="sm" />
                            </div>
                          </td>
                        <td className="px-4 py-4 text-center font-mono text-slate-200 border-r border-slate-800/50">{formatStake(result.stake)}u</td>
                        <td className="px-4 py-4 text-center border-r border-slate-800/30">
                          <ResultBadge status={result.status} />
                        </td>
                        <td className="px-4 py-4 text-right">
                          <PnL value={result.profit_loss} status={result.status} />
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              {/* Mobile Cards */}
              <div className="md:hidden divide-y divide-slate-600">
                {displayedRecent.map((result) => (
                  <div
                    key={result.id}
                    role="link"
                    tabIndex={0}
                    className="block cursor-pointer p-5 hover:bg-slate-800/20 active:bg-slate-800/30"
                    onClick={() => router.push(`/tips/${slugifyTip(result.event, result.id)}`)}
                    onKeyDown={(event) => {
                      if (event.key === "Enter" || event.key === " ") {
                        event.preventDefault();
                        router.push(`/tips/${slugifyTip(result.event, result.id)}`);
                      }
                    }}
                  >
                    <div className="flex items-start justify-between mb-2">
                      <div className="flex-1">
                        <div className="flex items-center gap-2 mb-1">
                          <span className="text-xs text-slate-500 whitespace-nowrap">{formatMatchDate(result.match_date)}</span>
                        </div>
                        <div className="font-medium text-slate-200 mb-1 block">
                          {result.event}
                        </div>
                        <div className="text-sm text-slate-400 mb-1">
                          {result.player && <span>{result.player} | </span>}
                          {result.selection}
                        </div>
                      </div>
                      <ResultBadge status={result.status} size="sm" className="ml-3" />
                    </div>
                    <BetMobileMeta
                      odds={result.odds}
                      bookmaker={result.bookmaker}
                      stake={result.stake}
                      status={result.status}
                      profitLoss={result.profit_loss}
                      showProfit
                    />
                  </div>
                ))}
              </div>
              
              {/* Note when showing max 50 results */}
              {showAllRecent && filteredRecent.length === 50 && (
                <div className="border-t border-slate-800 px-4 py-2 text-center">
                  <p className="text-xs text-slate-500">Showing the 50 most recent settled bets.</p>
                </div>
              )}
              
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

      <MonthlyBreakdownSection scope="props" />

      <Footer />
    </div>
  );
}
