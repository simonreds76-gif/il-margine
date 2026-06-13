"use client";

import { useState, useEffect, useCallback } from "react";
import Image from "next/image";
import { useRouter } from "next/navigation";
import { Bet, CategoryStats } from "@/lib/supabase";
import { BASELINE_STATS, calculateROI, calculateWinRate } from "@/lib/baseline";
import BetMobileMeta from "@/components/BetMobileMeta";
import MarketBadge from "@/components/MarketBadge";
import PublicBetsTable from "@/components/PublicBetsTable";
import ResultBadge from "@/components/ResultBadge";

import Footer from "@/components/Footer";
import MonthlyBreakdownSection from "@/components/MonthlyBreakdownSection";
import PageHomeLink from "@/components/PageHomeLink";
import { getDisplayBetCategory, normalizeBetCategory } from "@/lib/bet-category";
import { formatMatchDate, formatOdds } from "@/lib/format";
import { slugifyTip } from "@/lib/slugify";

type PlayerPropsClientProps = {
  initialPendingBets?: Bet[];
  initialRecentBets?: Bet[];
  initialStats?: CategoryStats[];
};

type DisplayStats = {
  total_bets: number;
  total_profit: number;
  avg_stake: number;
  roi: number;
  win_rate: number;
  avg_odds: number;
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

function profitToneClass(units: number): string {
  if (units > 0) return "text-emerald-400";
  if (units < 0) return "text-rose-400";
  return "text-slate-400";
}

function formatSignedUnits(units: number): string {
  const rounded = Math.round(Number(units || 0) * 100) / 100;
  const display = String(parseFloat(rounded.toFixed(2)));
  return `${rounded > 0 ? "+" : ""}${display}u`;
}

function formatUnits(units: number): string {
  const rounded = Math.round(Number(units || 0) * 100) / 100;
  return `${String(parseFloat(rounded.toFixed(2)))}u`;
}

export default function PlayerProps({
  initialPendingBets = [],
  initialRecentBets = [],
  initialStats = [],
}: PlayerPropsClientProps) {
  const router = useRouter();
  const [activeLeague, setActiveLeague] = useState("all");
  const [pendingBets, setPendingBets] = useState<Bet[]>(initialPendingBets);
  const [recentBets, setRecentBets] = useState<Bet[]>(initialRecentBets);
  const [stats, setStats] = useState<CategoryStats[]>(initialStats);
  const hasInitialPayload = initialPendingBets.length > 0 || initialRecentBets.length > 0 || initialStats.length > 0;
  const [loading, setLoading] = useState(!hasInitialPayload);
  const [showAllPending, setShowAllPending] = useState(false);
  const [showAllRecent, setShowAllRecent] = useState(false);

  const leagueConfig = [
    { id: "all", name: "All Leagues", logoPath: "/icons/markets/other-football.svg", logoClassName: naturalLogoFilter },
    { id: "pl", name: "Premier League", logoPath: "/league-logos/epl.png", logoClassName: lowContrastLogoFilter },
    { id: "seriea", name: "Serie A", logoPath: "/league-logos/serie-a.png", logoClassName: naturalLogoFilter },
    { id: "laliga", name: "La Liga", logoPath: "/league-logos/la-liga.png", logoClassName: naturalLogoFilter },
    { id: "bundesliga", name: "Bundesliga", logoPath: "/league-logos/bundesliga.png", logoClassName: naturalLogoFilter },
    { id: "ligue1", name: "Ligue 1", logoPath: "/league-logos/ligue-1.png", logoClassName: darkLogoFilter },
    { id: "ucl", name: "Champions League", logoPath: "/icons/markets/ucl-official.svg", logoClassName: darkLogoFilter },
    { id: "worldcup", name: "World Cup", logoPath: "/world-cup-trophy.svg", logoClassName: naturalLogoFilter },
    { id: "other", name: "Other", logoPath: "/icons/markets/other-football.svg", logoClassName: naturalLogoFilter },
  ];

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

  // Scroll to #picks when landing from homepage link (client-side nav doesn't scroll to hash)
  useEffect(() => {
    if (typeof window === "undefined" || window.location.hash !== "#picks" || loading) return;
    const el = document.getElementById("picks");
    if (!el) return;
    requestAnimationFrame(() => requestAnimationFrame(() => el.scrollIntoView({ behavior: "smooth", block: "start" })));
  }, [loading]);

  const getStatsForLeague = (leagueId: string): DisplayStats => {
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
        total_profit: totalProfit,
        avg_stake: totalBets > 0 ? totalStake / totalBets : 0,
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
        return { total_bets: 0, total_profit: 0, avg_stake: 0, roi: 0, win_rate: 0, avg_odds: 0 };
      }
      const liveBets = leagueStats.total_bets || 0;
      const liveProfit = Number(leagueStats.total_profit) || 0;
      const liveWins = leagueStats.wins || 0;
      const liveLosses = leagueStats.losses || 0;
      const liveStake = Number(leagueStats.total_stake) || liveBets;
      return {
        total_bets: liveBets,
        total_profit: liveProfit,
        avg_stake: liveBets > 0 ? liveStake / liveBets : 0,
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
      total_profit: totalProfit,
      avg_stake: totalBets > 0 ? totalStake / totalBets : 0,
      roi: calculateROI(totalProfit, totalStake || 1),
      win_rate: calculateWinRate(totalWins, totalLosses),
      avg_odds: avgOdds,
    };
  };

  const categoryForBet = (bet: Bet) => getDisplayBetCategory({ market: bet.market, category: bet.category, event: bet.event });
  const filteredPending = activeLeague === "all" ? pendingBets : pendingBets.filter(b => categoryForBet(b) === activeLeague);
  const filteredRecent = activeLeague === "all" ? recentBets : recentBets.filter(b => categoryForBet(b) === activeLeague);

  // Display limits: show 5 initially, or all if expanded
  const displayedPending = showAllPending ? filteredPending : filteredPending.slice(0, 5);
  const displayedRecent = showAllRecent ? filteredRecent : filteredRecent.slice(0, 5);

  const currentStats = getStatsForLeague(activeLeague);
  const statCards = [
    {
      label: "Total Bets",
      value: currentStats.total_bets.toLocaleString(),
      tone: "text-white",
      detail: "settled sample",
    },
    {
      label: "Units P/L",
      value: formatSignedUnits(currentStats.total_profit),
      tone: profitToneClass(currentStats.total_profit),
      detail: "net profit",
    },
    {
      label: "Avg Stake",
      value: formatUnits(currentStats.avg_stake),
      tone: "text-emerald-300",
      detail: "units per bet",
    },
    {
      label: "ROI",
      value: `${currentStats.roi > 0 ? "+" : ""}${currentStats.roi.toFixed(1)}%`,
      tone: roiToneClass(currentStats.roi),
      detail: "return on stake",
    },
    {
      label: "Win Rate",
      value: `${currentStats.win_rate.toFixed(1)}%`,
      tone: "text-emerald-300",
      detail: "settled hit rate",
    },
    {
      label: "Avg Odds",
      value: formatOdds(currentStats.avg_odds),
      tone: "text-emerald-300",
      detail: "average advised odds",
    },
  ];

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
          <div className="mb-5 flex flex-col gap-2 sm:mb-6 sm:flex-row sm:items-end sm:justify-between">
            <div>
              <span className="text-xs font-mono uppercase tracking-[0.18em] text-emerald-400">Record Filters</span>
              <h2 className="mt-2 text-2xl font-semibold text-slate-100">Category breakdown</h2>
            </div>
            <p className="max-w-xl text-xs leading-relaxed text-slate-500">
              Filter the public record without changing the ledger maths. P/L and ROI use the settled stakes in each
              category.
            </p>
          </div>

          <div className="mb-6 grid grid-cols-1 gap-3 sm:mb-8 sm:grid-cols-2 xl:grid-cols-3">
            {leagueConfig.map((league) => {
              const leagueStats = getStatsForLeague(league.id);
              const isActive = activeLeague === league.id;
              return (
                <button
                  key={league.id}
                  onClick={() => setActiveLeague(league.id)}
                  className={`group relative overflow-hidden rounded-2xl border p-3 text-left transition-all sm:p-4 ${
                    isActive
                      ? "border-emerald-400/70 bg-emerald-950/20 shadow-[0_18px_70px_rgba(16,185,129,0.12)]"
                      : "border-slate-800 bg-slate-950/35 hover:border-slate-700 hover:bg-slate-900/45"
                  }`}
                >
                  <div className={`absolute inset-x-0 top-0 h-0.5 bg-gradient-to-r from-emerald-500 to-emerald-300 transition-opacity ${isActive ? "opacity-100" : "opacity-0 group-hover:opacity-45"}`} />
                  <div className="flex items-center gap-3">
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
                      <span className={`block truncate font-semibold ${isActive ? "text-white" : "text-slate-200"}`}>
                        {league.name}
                      </span>
                      <span className="mt-1 block text-[10px] font-mono uppercase tracking-[0.18em] text-slate-500">
                        {isActive ? "selected record" : "view record"}
                      </span>
                    </div>
                  </div>
                  <div className="mt-3 grid grid-cols-2 gap-2 text-xs sm:mt-4">
                    <span className="rounded-xl border border-slate-800/80 bg-black/18 px-2.5 py-1.5 sm:px-3 sm:py-2">
                      <span className="block text-[10px] uppercase tracking-[0.14em] text-slate-500">Bets</span>
                      <span className="mt-1 block font-mono text-sm font-semibold text-white">{leagueStats.total_bets}</span>
                    </span>
                    <span className="rounded-xl border border-slate-800/80 bg-black/18 px-2.5 py-1.5 sm:px-3 sm:py-2">
                      <span className="block text-[10px] uppercase tracking-[0.14em] text-slate-500">P/L</span>
                      <span className={`mt-1 block font-mono text-sm font-semibold ${profitToneClass(leagueStats.total_profit)}`}>
                        {formatSignedUnits(leagueStats.total_profit)}
                      </span>
                    </span>
                    <span className="rounded-xl border border-slate-800/80 bg-black/18 px-2.5 py-1.5 sm:px-3 sm:py-2">
                      <span className="block text-[10px] uppercase tracking-[0.14em] text-slate-500">Avg Stake</span>
                      <span className="mt-1 block font-mono text-sm font-semibold text-emerald-300">
                        {formatUnits(leagueStats.avg_stake)}
                      </span>
                    </span>
                    <span className="rounded-xl border border-slate-800/80 bg-black/18 px-2.5 py-1.5 sm:px-3 sm:py-2">
                      <span className="block text-[10px] uppercase tracking-[0.14em] text-slate-500">ROI</span>
                      <span className={`mt-1 block font-mono text-sm font-semibold ${roiToneClass(leagueStats.roi)}`}>
                        {leagueStats.roi > 0 ? "+" : ""}{leagueStats.roi.toFixed(1)}%
                      </span>
                    </span>
                  </div>
                </button>
              );
            })}
          </div>

          {/* Stats */}
          <div className="grid grid-cols-2 gap-3 sm:gap-4 lg:grid-cols-3 xl:grid-cols-6">
            {statCards.map((card) => (
              <div
                key={card.label}
                className="relative overflow-hidden rounded-2xl border border-slate-800 bg-slate-950/45 p-4 shadow-[0_18px_60px_rgba(0,0,0,0.18)]"
              >
                <div className="absolute inset-x-0 top-0 h-1 bg-gradient-to-r from-emerald-500 to-emerald-300 opacity-70" />
                <div className="text-[10px] font-mono uppercase tracking-[0.2em] text-slate-500">{card.label}</div>
                <div className={`mt-3 font-mono text-2xl font-bold ${card.tone}`}>{card.value}</div>
                <div className="mt-3 inline-flex rounded-full border border-slate-800 bg-slate-900/70 px-2 py-1 text-[10px] uppercase tracking-[0.14em] text-slate-500">
                  {card.detail}
                </div>
              </div>
            ))}
          </div>
          <p className="mt-4 max-w-3xl text-xs leading-relaxed text-slate-500">
            Record cards use the full tracked category record. The recent selections table below is only a browsing
            sample from the latest 50 settled player-prop picks, then filtered by the league tab you choose.
          </p>
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
                <PublicBetsTable bets={displayedPending} mode="pending" />
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
                    <div className="mb-3 flex items-start gap-3">
                      <div className="flex h-11 w-11 shrink-0 items-center justify-center">
                        <MarketBadge market={pick.market} category={pick.category} event={pick.event} />
                      </div>
                      <div className="min-w-0 flex-1">
                        <div className="mb-1 flex items-center justify-between gap-3">
                          <span className="text-xs text-slate-500 whitespace-nowrap">{formatMatchDate(pick.match_date)}</span>
                          <span className="text-xs font-mono px-2 py-1 rounded bg-amber-500/20 text-amber-400">
                            PENDING
                          </span>
                        </div>
                        <div className="font-medium text-slate-200 mb-1 block leading-snug">
                          {pick.event}
                        </div>
                        <div className="text-sm text-slate-400 mb-1 leading-snug">
                          {pick.player && <span>{pick.player} | </span>}
                          {pick.selection}
                        </div>
                      </div>
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
            <p className="mt-3 max-w-3xl text-sm leading-relaxed text-slate-500">
              This is a recent-results window, not the source of truth for the ROI card above. Older bets still count
              in the category record even when they have rolled out of the latest-50 settled feed.
            </p>
          </div>

          {filteredRecent.length > 0 ? (
            <div className="bg-slate-900/50 rounded-lg border border-slate-800 overflow-hidden">
              {/* Desktop Table */}
              <div className="hidden md:block overflow-x-auto -mx-4 sm:mx-0">
                <PublicBetsTable bets={displayedRecent} mode="settled" />
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
                  <p className="text-xs text-slate-500">Showing the 50 most recent settled player-prop bets; older settled bets remain in the record cards.</p>
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
