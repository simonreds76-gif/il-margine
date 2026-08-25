"use client";

import { useState, useEffect, useCallback } from "react";
import Image from "next/image";
import { Bet, CategoryStats } from "@/lib/supabase";
import { BASELINE_STATS, calculateROI, calculateWinRate } from "@/lib/baseline";
import ProfitProgressionPanel, { type CategoryProgressionRow } from "@/components/ProfitProgressionPanel";
import PlayerPropsMatchGroups from "@/components/PlayerPropsMatchGroups";
import PropsAlertsCta from "@/components/PropsAlertsCta";
import SampleSizeBadge from "@/components/SampleSizeBadge";
import PublicRecordMetricGrid from "@/components/PublicRecordMetricGrid";

import Footer from "@/components/Footer";
import MonthlyBreakdownSection from "@/components/MonthlyBreakdownSection";
import PageHomeLink from "@/components/PageHomeLink";
import { getDisplayBetCategory, normalizeBetCategory } from "@/lib/bet-category";

type PlayerPropsClientProps = {
  initialPendingBets?: Bet[];
  initialRecentBets?: Bet[];
  initialStats?: CategoryStats[];
  initialProgressionRows?: CategoryProgressionRow[];
};

const darkLogoFilter =
  "[filter:brightness(0)_invert(1)_drop-shadow(0_0_5px_rgba(255,255,255,0.58))_drop-shadow(0_0_12px_rgba(87,209,150,0.2))]";
const lowContrastLogoFilter =
  "[filter:brightness(1.9)_saturate(1.45)_contrast(1.15)_drop-shadow(0_0_5px_rgba(255,255,255,0.5))_drop-shadow(0_0_12px_rgba(87,209,150,0.18))]";
const naturalLogoFilter =
  "[filter:drop-shadow(0_0_4px_rgba(255,255,255,0.32))_drop-shadow(0_0_10px_rgba(87,209,150,0.12))]";

function roiToneClass(roi: number): string {
  if (roi > 0) return "text-emerald-400";
  if (roi < 0) return "text-rose-400";
  return "text-slate-400";
}

export default function PlayerProps({
  initialPendingBets = [],
  initialRecentBets = [],
  initialStats = [],
  initialProgressionRows = [],
}: PlayerPropsClientProps) {
  const [activeLeague, setActiveLeague] = useState("all");
  const [pendingBets, setPendingBets] = useState<Bet[]>(initialPendingBets);
  const [recentBets, setRecentBets] = useState<Bet[]>(initialRecentBets);
  const [stats, setStats] = useState<CategoryStats[]>(initialStats);
  const [progressionRows, setProgressionRows] = useState<CategoryProgressionRow[]>(initialProgressionRows);
  const hasInitialPayload =
    initialPendingBets.length > 0 ||
    initialRecentBets.length > 0 ||
    initialStats.length > 0 ||
    initialProgressionRows.length > 0;
  const [loading, setLoading] = useState(!hasInitialPayload);

  const leagueConfig = [
    { id: "all", name: "All Leagues", color: "emerald", logoPath: "/icons/markets/other-football.svg", logoClassName: naturalLogoFilter },
    { id: "pl", name: "Premier League", color: "purple", logoPath: "/league-logos/epl.png", logoClassName: lowContrastLogoFilter },
    { id: "seriea", name: "Serie A", color: "blue", logoPath: "/league-logos/serie-a.png", logoClassName: naturalLogoFilter },
    { id: "laliga", name: "La Liga", color: "red", logoPath: "/league-logos/la-liga.png", logoClassName: naturalLogoFilter },
    { id: "bundesliga", name: "Bundesliga", color: "rose", logoPath: "/league-logos/bundesliga.png", logoClassName: naturalLogoFilter },
    { id: "ligue1", name: "Ligue 1", color: "cyan", logoPath: "/league-logos/ligue-1.png", logoClassName: darkLogoFilter },
    { id: "ucl", name: "Champions League", color: "amber", logoPath: "/icons/markets/ucl-official.svg", logoClassName: darkLogoFilter },
    { id: "worldcup", name: "World Cup", color: "emerald", logoPath: "/world-cup-trophy.svg", logoClassName: naturalLogoFilter },
    { id: "other", name: "Other", color: "slate", logoPath: "/icons/markets/other-football.svg", logoClassName: naturalLogoFilter },
  ];

  const colorClasses: Record<string, { border: string; text: string; bg: string; bar: string }> = {
    emerald: { border: "border-emerald-500/50", text: "text-emerald-400", bg: "bg-emerald-500/10", bar: "from-emerald-500 to-emerald-400" },
    purple: { border: "border-purple-500/50", text: "text-purple-400", bg: "bg-purple-500/10", bar: "from-purple-500 to-purple-400" },
    blue: { border: "border-blue-500/50", text: "text-blue-400", bg: "bg-blue-500/10", bar: "from-blue-500 to-blue-400" },
    amber: { border: "border-amber-500/50", text: "text-amber-400", bg: "bg-amber-500/10", bar: "from-amber-500 to-amber-400" },
    red: { border: "border-red-500/50", text: "text-red-400", bg: "bg-red-500/10", bar: "from-red-500 to-red-400" },
    rose: { border: "border-rose-500/50", text: "text-rose-400", bg: "bg-rose-500/10", bar: "from-rose-500 to-rose-400" },
    cyan: { border: "border-cyan-500/50", text: "text-cyan-400", bg: "bg-cyan-500/10", bar: "from-cyan-500 to-cyan-400" },
    slate: { border: "border-slate-600/70", text: "text-slate-300", bg: "bg-slate-700/20", bar: "from-slate-600 to-slate-500" },
  };
  const logoMarkClassName = "flex h-10 w-10 shrink-0 items-center justify-center overflow-visible";
  const logoImageClassName = "h-full w-full object-contain";

  const fetchData = useCallback(async () => {
    setLoading(true);

    try {
      const res = await fetch("/api/public-record?scope=props");
      const json = await res.json();
      if (!res.ok) throw new Error(json?.error || "Failed to load player props record");

      setPendingBets((json.pending ?? []) as Bet[]);
      setRecentBets((json.recent ?? []) as Bet[]);
      setStats((json.stats ?? []) as CategoryStats[]);
      setProgressionRows((json.progression ?? []) as CategoryProgressionRow[]);
    } catch (error) {
      console.error("Error fetching player props record:", error);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    const initialFetch = hasInitialPayload ? undefined : window.setTimeout(() => {
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
      if (initialFetch !== undefined) window.clearTimeout(initialFetch);
      window.removeEventListener("focus", handleFocus);
      document.removeEventListener("visibilitychange", handleVisibility);
    };
  }, [fetchData, hasInitialPayload]);

  useEffect(() => {
    if (typeof window === "undefined") return;
    const competition = new URLSearchParams(window.location.search).get("comp");
    if (competition === "worldcup") setActiveLeague("worldcup");
  }, []);

  // Client-side navigation does not reliably scroll after the record payload hydrates.
  useEffect(() => {
    if (typeof window === "undefined" || loading) return;
    const targetId = window.location.hash === "#picks"
      ? "picks"
      : window.location.hash === "#competition-record"
        ? "competition-record"
        : null;
    if (!targetId) return;
    const el = document.getElementById(targetId);
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
        total_stake: totalStake,
        total_profit: totalProfit,
        roi: calculateROI(totalProfit, totalStake || 1),
        win_rate: calculateWinRate(totalWins, totalLosses),
        avg_odds: avgOdds,
      };
    }

    // For specific league - combine category baseline + live data for that category
    const categoryBaseline = BASELINE_STATS.categoryBaselines.props[leagueId as keyof typeof BASELINE_STATS.categoryBaselines.props];
    const categoryRows = stats.filter((s) => normalizeBetCategory(s.category) === leagueId);
    const leagueStats = categoryRows.length > 0
      ? {
          total_bets: categoryRows.reduce((sum, s) => sum + (s.total_bets || 0), 0),
          wins: categoryRows.reduce((sum, s) => sum + (s.wins || 0), 0),
          losses: categoryRows.reduce((sum, s) => sum + (s.losses || 0), 0),
          total_profit: categoryRows.reduce((sum, s) => sum + (Number(s.total_profit) || 0), 0),
          total_stake: categoryRows.reduce((sum, s) => sum + (Number(s.total_stake) || 0), 0),
          avg_odds: (() => {
            const bets = categoryRows.reduce((sum, s) => sum + (s.total_bets || 0), 0);
            const weighted = categoryRows.reduce((sum, s) => sum + (Number(s.avg_odds) || 0) * (s.total_bets || 0), 0);
            return bets > 0 ? weighted / bets : 0;
          })(),
        }
      : undefined;

    if (!categoryBaseline) {
      // No baseline for this category, show only live data
      if (!leagueStats) {
        return { total_bets: 0, total_stake: 0, total_profit: 0, roi: 0, win_rate: 0, avg_odds: 0 };
      }
      const liveBets = leagueStats.total_bets || 0;
      const liveProfit = Number(leagueStats.total_profit) || 0;
      const liveWins = leagueStats.wins || 0;
      const liveLosses = leagueStats.losses || 0;
      const liveStake = Number(leagueStats.total_stake) || liveBets;
      return {
        total_bets: liveBets,
        total_stake: liveStake,
        total_profit: liveProfit,
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
      total_stake: totalStake,
      total_profit: totalProfit,
      roi: calculateROI(totalProfit, totalStake || 1),
      win_rate: calculateWinRate(totalWins, totalLosses),
      avg_odds: avgOdds,
    };
  };

  const getArchiveStatsForLeague = (leagueId: string) => {
    if (leagueId === "all") return BASELINE_STATS.props;
    return BASELINE_STATS.categoryBaselines.props[leagueId] ?? null;
  };

  const categoryForBet = (bet: Bet) => getDisplayBetCategory({ market: bet.market, category: bet.category, event: bet.event });
  const filteredPending = activeLeague === "all" ? pendingBets : pendingBets.filter(b => categoryForBet(b) === activeLeague);
  const filteredRecent = activeLeague === "all" ? recentBets : recentBets.filter(b => categoryForBet(b) === activeLeague);
  const filteredProgressionRows =
    activeLeague === "all" ? progressionRows : progressionRows.filter((row) => normalizeBetCategory(row.category) === activeLeague);

  const activeName = leagueConfig.find(l => l.id === activeLeague)?.name || "Selected";
  const currentStats = getStatsForLeague(activeLeague);
  const archiveStats = getArchiveStatsForLeague(activeLeague);

  return (
    <div className="min-h-screen bg-[#0f1117] text-slate-100">
      <PropsAlertsCta
        source="player_props_persistent"
        variant="pill"
        className="fixed bottom-5 right-5 z-40 hidden lg:inline-flex"
      />
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

      {/* Active Picks - id for deep link from homepage */}
      <section id="picks" className="py-12 md:py-16 border-b border-slate-800/50 scroll-mt-6">
        <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex items-center justify-between mb-6">
            <div>
              <span className="text-xs font-mono text-emerald-400 mb-2 block">ACTIVE SELECTIONS</span>
              <h2 className="text-3xl sm:text-4xl font-semibold text-slate-100">Current Picks</h2>
            </div>
            <span className="text-xs text-slate-500 hidden sm:block">Updates on site within a minute</span>
          </div>
          <p className="text-slate-500 text-xs mb-6">Stake in units (1u = your standard stake). We typically recommend 0.5u-2u per pick.</p>

          {loading ? (
            <div className="bg-slate-900/30 rounded-lg border border-slate-800 p-8 text-center">
              <p className="text-slate-500">Loading...</p>
            </div>
          ) : filteredPending.length > 0 ? (
            <PlayerPropsMatchGroups bets={filteredPending} mode="pending" />
          ) : (
            <div className="bg-slate-900/30 rounded-lg border border-slate-800 p-8 text-center">
              <p className="text-slate-500">No active selections at the moment</p>
              <p className="text-xs text-slate-600 mt-2">Check back soon for new selections</p>
            </div>
          )}

          <PropsAlertsCta source="player_props_alerts" className="mt-6" />
        </div>
      </section>

      {/* League Tabs */}
      <section id="competition-record" className="scroll-mt-24 py-12 md:py-16 border-b border-slate-800/50">
        <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex flex-wrap gap-2 sm:gap-3 mb-6 sm:mb-8">
            {leagueConfig.map((league) => {
              const leagueStats = getStatsForLeague(league.id);
              const isActive = activeLeague === league.id;
              return (
                <button
                  key={league.id}
                  onClick={() => setActiveLeague(league.id)}
                  className={`flex min-w-[152px] items-center gap-3 rounded-xl border px-3 py-3 text-left transition-all sm:min-w-[174px] ${
                    isActive
                      ? `bg-slate-900/80 ${colorClasses[league.color].border} text-slate-100`
                      : "bg-slate-900/30 border-slate-800 text-slate-400 hover:border-slate-700"
                  }`}
                >
                  <span className={`${logoMarkClassName} ${isActive ? "scale-105" : ""}`}>
                    <Image
                      src={league.logoPath}
                      alt=""
                      width={36}
                      height={36}
                      className={`${logoImageClassName} ${league.logoClassName}`}
                    />
                  </span>
                  <div className="min-w-0">
                    <span className="block truncate font-medium">{league.name}</span>
                    <div className="mt-1 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs">
                      {leagueStats.total_bets > 0 ? (
                        <>
                          <span>{leagueStats.total_bets} bets</span>
                          <span className={`${leagueStats.total_bets < 50 ? "text-slate-400/70" : roiToneClass(leagueStats.roi)} font-mono`}>
                            {leagueStats.roi > 0 ? "+" : ""}{leagueStats.roi.toFixed(1)}% ROI
                          </span>
                        </>
                      ) : (
                        <span className="text-slate-500">0 bets</span>
                      )}
                    </div>
                    <SampleSizeBadge settled={leagueStats.total_bets} compact className="mt-1.5" />
                  </div>
                </button>
              );
            })}
          </div>

          <div className="mb-4 flex justify-end">
            <SampleSizeBadge settled={currentStats.total_bets} />
          </div>

          <PublicRecordMetricGrid
            activeName={activeName}
            totalBets={currentStats.total_bets}
            totalStake={currentStats.total_stake}
            totalProfit={currentStats.total_profit}
            roi={currentStats.roi}
            winRate={currentStats.win_rate}
            avgOdds={currentStats.avg_odds}
            hasArchiveBaseline={Boolean(archiveStats?.total_bets)}
          />

          <ProfitProgressionPanel rows={filteredProgressionRows} activeName={activeName} archiveStats={archiveStats} />

          <p className="mt-4 max-w-3xl text-xs leading-relaxed text-slate-500">
            Record cards use the full tracked category record. The recent selections table below is only a browsing
            sample from the wider settled player-prop feed, then filtered by the league tab you choose. The P/L
            progression shows any pre-tracking baseline as a dashed aggregate summary, then uses settled public ledger
            rows for the selected tab.
          </p>
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
            <p className="mt-3 max-w-3xl text-sm leading-relaxed text-slate-500">
              This is a recent-results window, not the source of truth for the ROI card above. Older bets still count
              in the category record even when they have rolled out of the wider settled feed.
            </p>
          </div>

          {filteredRecent.length > 0 ? (
            <>
              <PlayerPropsMatchGroups bets={filteredRecent} mode="settled" />
              {activeLeague === "all" && recentBets.length >= 500 ? (
                <div className="mt-3 rounded-lg border border-slate-800 bg-slate-900/40 px-4 py-2 text-center">
                  <p className="text-xs text-slate-500">Showing the most recent settled player-prop feed; older settled bets remain in the record cards and progression.</p>
                </div>
              ) : null}
            </>
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
