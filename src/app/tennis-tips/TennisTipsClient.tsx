"use client";

import { useState, useEffect, useCallback } from "react";
import Image from "next/image";
import Link from "next/link";
import { Bet, CategoryStats } from "@/lib/supabase";
import { BASELINE_STATS, calculateROI, calculateWinRate } from "@/lib/baseline";
import BetMobileMeta from "@/components/BetMobileMeta";
import MarketBadge from "@/components/MarketBadge";
import PublicBetsTable from "@/components/PublicBetsTable";
import ProfitProgressionPanel, { type CategoryProgressionRow } from "@/components/ProfitProgressionPanel";
import ResultBadge from "@/components/ResultBadge";
import Footer from "@/components/Footer";
import MonthlyBreakdownSection from "@/components/MonthlyBreakdownSection";
import PageHomeLink from "@/components/PageHomeLink";
import SampleSizeBadge from "@/components/SampleSizeBadge";
import PublicRecordMetricGrid from "@/components/PublicRecordMetricGrid";
import { normalizeBetCategory } from "@/lib/bet-category";
import { formatMatchDate } from "@/lib/format";
import { publicTipPath } from "@/lib/tip-seo";

type TennisTipsClientProps = {
  initialPendingBets?: Bet[];
  initialRecentBets?: Bet[];
  initialStats?: CategoryStats[];
  initialProgressionRows?: CategoryProgressionRow[];
};

const naturalLogoFilter =
  "[filter:drop-shadow(0_0_4px_rgba(255,255,255,0.32))_drop-shadow(0_0_10px_rgba(87,209,150,0.12))]";

function roiToneClass(roi: number): string {
  if (roi > 0) return "text-emerald-400";
  if (roi < 0) return "text-rose-400";
  return "text-slate-400";
}

export default function TennisTips({
  initialPendingBets = [],
  initialRecentBets = [],
  initialStats = [],
  initialProgressionRows = [],
}: TennisTipsClientProps) {
  const [activeCategory, setActiveCategory] = useState("all");
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
  const [showAllPending, setShowAllPending] = useState(false);
  const [showAllRecent, setShowAllRecent] = useState(false);

  const categoryConfig = [
    { id: "all", name: "All Tennis", color: "emerald", logoPath: "/icons/markets/tennis.svg", logoClassName: naturalLogoFilter },
    { id: "atp", name: "ATP Tour", color: "blue", logoPath: "/icons/markets/atp-logo.png", logoClassName: naturalLogoFilter },
    { id: "challenger", name: "Challenger", color: "amber", logoPath: "/icons/markets/tennis.svg", logoClassName: naturalLogoFilter },
    { id: "ausopen", name: "Australian Open", color: "cyan", logoPath: "/icons/markets/slams/australian-open.png", logoClassName: naturalLogoFilter },
    { id: "rolandgarros", name: "Roland Garros", color: "rose", logoPath: "/icons/markets/slams/roland-garros.png", logoClassName: naturalLogoFilter },
    { id: "wimbledon", name: "Wimbledon", color: "green", logoPath: "/icons/markets/slams/wimbledon.png", logoClassName: naturalLogoFilter },
    { id: "usopen", name: "US Open", color: "indigo", logoPath: "/icons/markets/slams/us-open.png", logoClassName: naturalLogoFilter },
    { id: "other", name: "Other", color: "purple", logoPath: "/icons/markets/tennis.svg", logoClassName: naturalLogoFilter },
  ];

  const colorClasses: Record<string, { border: string; text: string; bg: string; bar: string }> = {
    emerald: { border: "border-emerald-500/50", text: "text-emerald-400", bg: "bg-emerald-500/10", bar: "from-emerald-500 to-emerald-400" },
    blue: { border: "border-blue-500/50", text: "text-blue-400", bg: "bg-blue-500/10", bar: "from-blue-500 to-blue-400" },
    amber: { border: "border-amber-500/50", text: "text-amber-400", bg: "bg-amber-500/10", bar: "from-amber-500 to-amber-400" },
    cyan: { border: "border-cyan-500/50", text: "text-cyan-400", bg: "bg-cyan-500/10", bar: "from-cyan-500 to-cyan-400" },
    purple: { border: "border-purple-500/50", text: "text-purple-400", bg: "bg-purple-500/10", bar: "from-purple-500 to-purple-400" },
    rose: { border: "border-rose-500/50", text: "text-rose-400", bg: "bg-rose-500/10", bar: "from-rose-500 to-rose-400" },
    green: { border: "border-green-500/50", text: "text-green-400", bg: "bg-green-500/10", bar: "from-green-500 to-green-400" },
    indigo: { border: "border-indigo-500/50", text: "text-indigo-400", bg: "bg-indigo-500/10", bar: "from-indigo-500 to-indigo-400" },
  };
  const logoMarkClassName = "flex h-10 w-10 shrink-0 items-center justify-center overflow-visible";
  const logoImageClassName = "h-full w-full object-contain";

  const fetchData = useCallback(async () => {
    setLoading(true);

    try {
      const res = await fetch("/api/public-record?scope=tennis");
      const json = await res.json();
      if (!res.ok) throw new Error(json?.error || "Failed to load tennis record");

      setPendingBets((json.pending ?? []) as Bet[]);
      setRecentBets((json.recent ?? []) as Bet[]);
      setStats((json.stats ?? []) as CategoryStats[]);
      setProgressionRows((json.progression ?? []) as CategoryProgressionRow[]);
    } catch (error) {
      console.error("Error fetching tennis record:", error);
    } finally {
      setLoading(false);
    }
  }, []);

  // Fetch data on load
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

  // Calculate stats for display
  const getStatsForCategory = (categoryId: string) => {
    if (categoryId === "all") {
      // For "All Tennis" - combine baseline + all live data
      const allStats = stats.filter(s => s.market === "tennis");

      const liveBets = allStats.reduce((sum, s) => sum + (s.total_bets || 0), 0);
      const liveProfit = allStats.reduce((sum, s) => sum + (Number(s.total_profit) || 0), 0);
      const liveWins = allStats.reduce((sum, s) => sum + (s.wins || 0), 0);
      const liveLosses = allStats.reduce((sum, s) => sum + (s.losses || 0), 0);
      const liveStake = allStats.reduce((sum, s) => sum + (Number(s.total_stake) || 0), 0) || liveBets;

      // Combine with baseline
      const totalBets = BASELINE_STATS.tennis.total_bets + liveBets;
      const totalProfit = BASELINE_STATS.tennis.total_profit + liveProfit;
      const totalWins = BASELINE_STATS.tennis.wins + liveWins;
      const totalLosses = BASELINE_STATS.tennis.losses + liveLosses;
      const totalStake = BASELINE_STATS.tennis.total_stake + liveStake;

      // Weighted avg by bet count (baseline + live)
      const baselineOddsWeight = Object.values(BASELINE_STATS.categoryBaselines.tennis).reduce(
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

    // For specific category - combine category baseline + live data for that category
    const categoryBaseline = BASELINE_STATS.categoryBaselines.tennis[categoryId as keyof typeof BASELINE_STATS.categoryBaselines.tennis];
    const catStats = stats.find(s => s.category === categoryId);

    if (!categoryBaseline) {
      // No baseline for this category, show only live data
      if (!catStats) {
        return { total_bets: 0, total_stake: 0, total_profit: 0, roi: 0, win_rate: 0, avg_odds: 0 };
      }
      const liveBets = catStats.total_bets || 0;
      const liveProfit = Number(catStats.total_profit) || 0;
      const liveWins = catStats.wins || 0;
      const liveLosses = catStats.losses || 0;
      const liveStake = Number(catStats.total_stake) || liveBets;
      return {
        total_bets: liveBets,
        total_stake: liveStake,
        total_profit: liveProfit,
        roi: liveStake > 0 ? calculateROI(liveProfit, liveStake) : 0,
        win_rate: calculateWinRate(liveWins, liveLosses),
        avg_odds: Number(catStats.avg_odds) || 0,
      };
    }

    const liveBets = catStats?.total_bets || 0;
    const liveProfit = Number(catStats?.total_profit) || 0;
    const liveWins = catStats?.wins || 0;
    const liveLosses = catStats?.losses || 0;
    const liveStake = Number(catStats?.total_stake) || liveBets;
    const liveAvgOdds = Number(catStats?.avg_odds) || 0;

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

  const getArchiveStatsForCategory = (categoryId: string) => {
    if (categoryId === "all") return BASELINE_STATS.tennis;
    return BASELINE_STATS.categoryBaselines.tennis[categoryId] ?? null;
  };

  // Filter bets by category
  const filteredPending = activeCategory === "all"
    ? pendingBets
    : pendingBets.filter(b => b.category === activeCategory);

  const filteredRecent = activeCategory === "all"
    ? recentBets
    : recentBets.filter(b => b.category === activeCategory);

  const filteredProgressionRows = activeCategory === "all"
    ? progressionRows
    : progressionRows.filter((row) => normalizeBetCategory(row.category) === activeCategory);

  // Display limits: show 5 initially, or all if expanded
  const displayedPending = showAllPending ? filteredPending : filteredPending.slice(0, 5);
  const displayedRecent = showAllRecent ? filteredRecent : filteredRecent.slice(0, 5);

  const activeName = categoryConfig.find(c => c.id === activeCategory)?.name || "Selected";
  const currentStats = getStatsForCategory(activeCategory);
  const archiveStats = getArchiveStatsForCategory(activeCategory);

  return (
    <div className="min-h-screen bg-[#0f1117] text-slate-100">
      {/* Navigation is now in GlobalNav component in layout.tsx */}

      {/* Hero */}
      <section className="pt-6 pb-12 md:pt-6 md:pb-16 border-b border-slate-800/50">
        <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="mb-6 flex flex-wrap items-center gap-3">
            <PageHomeLink />
            <span className="text-xs font-mono uppercase tracking-[0.18em] text-emerald-400">Tennis Tips</span>
          </div>

          <h1 className="text-3xl sm:text-4xl font-semibold text-slate-100 mb-4 sm:mb-6">
            Tennis Betting <span className="text-emerald-400">Tips</span>
          </h1>
          <p className="text-base sm:text-lg text-slate-300 max-w-3xl leading-relaxed">
            Daily ATP, Challenger and Grand Slam picks built around price rather than noise. The aim is not to
            pretend we can call every winner in isolation; it is to find numbers that are too big, handicaps that
            are a touch loose, and totals that have been shaped by generic assumptions instead of the actual match.
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
          </div>
          <p className="text-slate-500 text-xs mb-3">Stake in units (1u = your standard stake). We typically recommend 0.5u-2u per pick.</p>
          <p className="text-slate-500 text-xs mb-6 italic">
            <strong className="text-slate-400 not-italic">ML (Moneyline):</strong> A straight win bet with no handicap attached.
          </p>

          {loading ? (
            <div className="bg-slate-900/30 rounded-lg border border-slate-800 p-8 text-center">
              <p className="text-slate-500">Loading...</p>
            </div>
          ) : filteredPending.length > 0 ? (
            <div className="bg-slate-900/50 rounded-lg border border-slate-800 overflow-hidden">
              {/* Desktop Table */}
              <div className="hidden md:block overflow-x-auto -mx-4 sm:mx-0">
                <PublicBetsTable bets={displayedPending} mode="pending" playerHeader="Pick" />
              </div>
              {/* Mobile Cards */}
              <div className="md:hidden divide-y divide-slate-600">
                {displayedPending.map((pick) => (
                  <Link
                    key={pick.id}
                    href={publicTipPath(pick)}
                    className="block cursor-pointer p-5 hover:bg-slate-800/20 active:bg-slate-800/30"
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
                        <div className="font-medium text-slate-200 mb-1 leading-snug">
                          {pick.event}
                        </div>
                        <div className="text-sm text-slate-400 leading-snug">
                          {pick.player && <span>{pick.player} | </span>}
                          {pick.selection}
                        </div>
                      </div>
                    </div>
                    <BetMobileMeta odds={pick.odds} bookmaker={pick.bookmaker} stake={pick.stake} />
                  </Link>
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
            </div>
          )}
          <p className="mt-5 text-sm text-slate-500">
            Tennis picks are posted on this page only. Bookmark it to check the latest card.
          </p>
        </div>
      </section>

      {/* Category Tabs */}
      <section className="py-12 md:py-16 border-b border-slate-800/50">
        <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex flex-wrap gap-2 sm:gap-3 mb-6 sm:mb-8">
            {categoryConfig.map((cat) => {
              const catStats = getStatsForCategory(cat.id);
              const isActive = activeCategory === cat.id;
              return (
                <button
                  key={cat.id}
                  onClick={() => setActiveCategory(cat.id)}
                  className={`flex min-w-[152px] items-center gap-3 rounded-xl border px-3 py-3 text-left transition-all sm:min-w-[174px] ${
                    isActive
                      ? `bg-slate-900/80 ${colorClasses[cat.color].border} text-slate-100`
                      : "bg-slate-900/30 border-slate-800 text-slate-400 hover:border-slate-700"
                  }`}
                >
                  <span className={`${logoMarkClassName} ${isActive ? "scale-105" : ""}`}>
                    <Image
                      src={cat.logoPath}
                      alt=""
                      width={36}
                      height={36}
                      className={`${logoImageClassName} ${cat.logoClassName}`}
                    />
                  </span>
                  <div className="min-w-0">
                    <span className="block truncate font-medium">{cat.name}</span>
                    <div className="mt-1 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs">
                      {catStats.total_bets > 0 ? (
                        <>
                          <span>{catStats.total_bets} bets</span>
                          <span className={`${catStats.total_bets < 50 ? "text-slate-400/70" : roiToneClass(catStats.roi)} font-mono`}>
                            {catStats.roi > 0 ? "+" : ""}{catStats.roi.toFixed(1)}% ROI
                          </span>
                        </>
                      ) : (
                        <span className="text-slate-500">0 bets</span>
                      )}
                    </div>
                    <SampleSizeBadge settled={catStats.total_bets} compact className="mt-1.5" />
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
            Record cards use the full tracked tennis category record. The recent selections table below is only a
            browsing sample from the latest 50 settled tennis picks, then filtered by the category tab you choose. The
            P/L progression shows any pre-tracking baseline as a dashed aggregate summary, then uses settled public
            ledger rows for the selected tab.
          </p>
        </div>
      </section>

      <section className="py-12 md:py-16 border-b border-slate-800/50">
        <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="rounded-2xl border border-slate-800 bg-slate-900/55 p-6 sm:p-7">
            <div className="mb-5">
              <div className="text-xs font-mono uppercase tracking-[0.18em] text-emerald-400">Our methodology</div>
              <h2 className="mt-2 text-2xl sm:text-3xl font-semibold text-slate-100">How the model builds the card</h2>
            </div>
            <div className="grid gap-4 md:grid-cols-3">
              <div className="rounded-xl border border-slate-800/80 bg-slate-950/40 p-5">
                <div className="text-[11px] font-mono uppercase tracking-[0.18em] text-emerald-400">01</div>
                <h3 className="mt-3 text-base font-semibold text-slate-100">Every match starts as fair odds</h3>
                <p className="mt-2 text-sm leading-6 text-slate-400">
                  We do not begin with a tip or a hunch. We begin by pricing the match. Surface-specific serve and
                  return data are blended with Elo so the model captures both underlying level and actual conditions,
                  then a point-by-point tennis engine turns that into fair moneyline, handicap and total prices.
                </p>
              </div>
              <div className="rounded-xl border border-slate-800/80 bg-slate-950/40 p-5">
                <div className="text-[11px] font-mono uppercase tracking-[0.18em] text-emerald-400">02</div>
                <h3 className="mt-3 text-base font-semibold text-slate-100">Raw output gets calibrated hard</h3>
                <p className="mt-2 text-sm leading-6 text-slate-400">
                  Raw probabilities are not enough, especially below the very top tier. We shrink thin samples, weight
                  tournament class properly, and account for things like venue speed, recent workload, rust, form and
                  matchup shape. The point is not to force fake monster edges; it is to stop the fair odds drifting
                  away from tennis reality.
                </p>
              </div>
              <div className="rounded-xl border border-slate-800/80 bg-slate-950/40 p-5">
                <div className="text-[11px] font-mono uppercase tracking-[0.18em] text-emerald-400">03</div>
                <h3 className="mt-3 text-base font-semibold text-slate-100">We only bet when the price is wrong</h3>
                <p className="mt-2 text-sm leading-6 text-slate-400">
                  Once our fair odds are set, we compare them to the live market and only move when the gap is worth
                  taking. Sometimes that means moneyline, sometimes games, sometimes totals, and very often it means
                  passing. The proof is not a lucky day; it is whether the number was strong enough to beat the market
                  by the close.
                </p>
              </div>
            </div>
            <div className="mt-5 rounded-xl border border-slate-800/80 bg-slate-950/40 p-4 text-sm leading-6 text-slate-400">
              Want the caveats behind the current surface model? Read the{" "}
              <Link
                href="/resources/clay-season-tennis-model-caveats"
                className="border-b border-emerald-500/30 text-emerald-400 hover:text-emerald-300"
              >
                ATP clay model note
              </Link>
              {" "}and the{" "}
              <Link
                href="/resources/how-to-read-a-tipster-track-record"
                className="border-b border-emerald-500/30 text-emerald-400 hover:text-emerald-300"
              >
                track-record guide
              </Link>
              {" "}before treating any short sample as proof.
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
                <PublicBetsTable bets={displayedRecent} mode="settled" playerHeader="Pick" />
              </div>
              {/* Mobile Cards */}
              <div className="md:hidden divide-y divide-slate-600">
                {displayedRecent.map((result) => (
                  <Link
                    key={result.id}
                    href={publicTipPath(result)}
                    className="block cursor-pointer p-5 hover:bg-slate-800/20 active:bg-slate-800/30"
                  >
                    <div className="flex items-start justify-between mb-2">
                      <div className="flex-1">
                        <div className="flex items-center gap-2 mb-1">
                          <span className="text-xs text-slate-500 whitespace-nowrap">{formatMatchDate(result.match_date)}</span>
                        </div>
                        <div className="font-medium text-slate-200 mb-1">
                          {result.event}
                        </div>
                        <div className="text-sm text-slate-400">
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
                  </Link>
                ))}
              </div>

              {/* Note when showing max 50 results */}
              {showAllRecent && filteredRecent.length === 50 && (
                <div className="border-t border-slate-800 px-4 py-2 text-center">
                  <p className="text-xs text-slate-500">Showing the 50 most recent settled tennis bets; older settled bets remain in the record cards.</p>
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

      <MonthlyBreakdownSection scope="tennis" />

      <Footer />
    </div>
  );
}
