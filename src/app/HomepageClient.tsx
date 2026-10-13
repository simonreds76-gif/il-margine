"use client";
import HomeFixtures from "@/components/HomeFixtures";

import { useCallback, useEffect, useRef, useState } from "react";
import Link from "next/link";
import { type Bet, type Bookmaker, type MarketStats } from "@/lib/supabase";
import { BASELINE_STATS, calculateROI, calculateWinRate, getBaselineDisplayStats } from "@/lib/baseline";
import BetMobileMeta from "@/components/BetMobileMeta";
import PublicBetsTable from "@/components/PublicBetsTable";
import ResultBadge from "@/components/ResultBadge";
import TodaysEdge from "@/components/TodaysEdge";
import ToolEmblem, { emblemForHref } from "@/components/ToolEmblem";
import "./home-discovery.css";
import RecordIcon from "@/components/RecordIcon";
import Footer from "@/components/Footer";
import MonthlyBreakdownSection from "@/components/MonthlyBreakdownSection";
import type { MonthRow } from "@/components/MonthlyBreakdown";
import { formatMatchDate } from "@/lib/format";
import { publicTipPath } from "@/lib/tip-seo";

interface CombinedMarketStats {
  total_bets: number;
  roi: number;
  win_rate: number;
  avg_odds: number;
  total_profit: number;
}

type HomepageBet = Bet & {
  bookmaker?: Bookmaker | Bookmaker[] | null;
};

function getTrackingMonths() {
  const start = new Date("2024-10-01T00:00:00Z");
  const now = new Date();
  const months = Math.max(
    1,
    (now.getUTCFullYear() - start.getUTCFullYear()) * 12 + (now.getUTCMonth() - start.getUTCMonth())
  );
  return `${months}+ months`;
}

type HomepageClientProps = {
  initialMonthly?: { show: boolean; rows: MonthRow[] };
  initialMarketStats?: MarketStats[];
  initialRecentBets?: HomepageBet[];
  initialPendingBets?: HomepageBet[];
  initialLast7?: { total: number; count: number } | null;
};

function buildCombinedStats(liveStats: MarketStats[]) {
  const propsLive = liveStats.find((stat) => stat.market === "props");
  const tennisLive = liveStats.find((stat) => stat.market === "tennis");

  const propsLiveBets = propsLive?.total_bets || 0;
  const propsLiveWins = propsLive?.wins || 0;
  const propsLiveLosses = propsLive?.losses || 0;
  const propsLiveProfit = Number(propsLive?.total_profit) || 0;
  const propsLiveStake = Number(propsLive?.total_stake) || propsLiveBets;
  const propsProfit = BASELINE_STATS.props.total_profit + propsLiveProfit;
  const propsStake = BASELINE_STATS.props.total_stake + propsLiveStake;
  const propsCombined: CombinedMarketStats = {
    total_bets: BASELINE_STATS.props.total_bets + propsLiveBets,
    roi: calculateROI(propsProfit, propsStake || 1),
    win_rate: calculateWinRate(BASELINE_STATS.props.wins + propsLiveWins, BASELINE_STATS.props.losses + propsLiveLosses),
    avg_odds: propsLive?.avg_odds && propsLiveBets > 0 ? Number(propsLive.avg_odds) : BASELINE_STATS.props.avg_odds,
    total_profit: propsProfit,
  };

  const tennisLiveBets = tennisLive?.total_bets || 0;
  const tennisLiveWins = tennisLive?.wins || 0;
  const tennisLiveLosses = tennisLive?.losses || 0;
  const tennisLiveProfit = Number(tennisLive?.total_profit) || 0;
  const tennisLiveStake = Number(tennisLive?.total_stake) || tennisLiveBets;
  const tennisProfit = BASELINE_STATS.tennis.total_profit + tennisLiveProfit;
  const tennisStake = BASELINE_STATS.tennis.total_stake + tennisLiveStake;
  const tennisCombined: CombinedMarketStats = {
    total_bets: BASELINE_STATS.tennis.total_bets + tennisLiveBets,
    roi: calculateROI(tennisProfit, tennisStake || 1),
    win_rate: calculateWinRate(BASELINE_STATS.tennis.wins + tennisLiveWins, BASELINE_STATS.tennis.losses + tennisLiveLosses),
    avg_odds: tennisLive?.avg_odds && tennisLiveBets > 0 ? Number(tennisLive.avg_odds) : BASELINE_STATS.tennis.avg_odds,
    total_profit: tennisProfit,
  };

  const overallLiveBets = propsLiveBets + tennisLiveBets;
  const overallLiveWins = propsLiveWins + tennisLiveWins;
  const overallLiveLosses = propsLiveLosses + tennisLiveLosses;
  const overallLiveProfit = propsLiveProfit + tennisLiveProfit;
  const overallLiveStake = propsLiveStake + tennisLiveStake;
  const overallProfit = BASELINE_STATS.overall.total_profit + overallLiveProfit;
  const overallStake = BASELINE_STATS.overall.total_stake + overallLiveStake;
  const totalOddsWeight = propsCombined.avg_odds * propsCombined.total_bets + tennisCombined.avg_odds * tennisCombined.total_bets;
  const overallCombined: CombinedMarketStats = {
    total_bets: BASELINE_STATS.overall.total_bets + overallLiveBets,
    roi: calculateROI(overallProfit, overallStake || 1),
    win_rate: calculateWinRate(BASELINE_STATS.overall.wins + overallLiveWins, BASELINE_STATS.overall.losses + overallLiveLosses),
    avg_odds: totalOddsWeight > 0 ? totalOddsWeight / (BASELINE_STATS.overall.total_bets + overallLiveBets) : BASELINE_STATS.overall.avg_odds,
    total_profit: overallProfit,
  };

  return {
    props: propsCombined,
    tennis: tennisCombined,
    overall: overallCombined,
  };
}

export default function HomepageClient({
  initialMonthly,
  initialMarketStats = [],
  initialRecentBets = [],
  initialPendingBets = [],
  initialLast7 = null,
}: HomepageClientProps) {
  const [recentBets, setRecentBets] = useState<HomepageBet[]>(initialRecentBets);
  const [pendingBets, setPendingBets] = useState<HomepageBet[]>(initialPendingBets);
  const [last7DaysProfit, setLast7DaysProfit] = useState<number | null>(initialLast7?.total ?? null);
  const [last7DaysCount, setLast7DaysCount] = useState<number>(initialLast7?.count ?? 0);
  const [last7Error, setLast7Error] = useState<boolean>(!initialLast7);
  const [recordStatus, setRecordStatus] = useState<"loaded" | "historical" | "unavailable">(initialMarketStats.length ? "loaded" : "historical");
  const [combinedStats, setCombinedStats] = useState<{
    props: CombinedMarketStats;
    tennis: CombinedMarketStats;
    overall: CombinedMarketStats;
  } | null>(() => (initialMarketStats.length ? buildCombinedStats(initialMarketStats) : null));
  const hasInitialPayload = initialMarketStats.length > 0 || initialRecentBets.length > 0 || initialPendingBets.length > 0;

  const calculateCombinedStats = (liveStats: MarketStats[]) => {
    setCombinedStats(buildCombinedStats(liveStats));
  };

  const refreshInFlight = useRef(false);
  const lastRefreshStarted = useRef(0);

  const fetchData = useCallback(async () => {
    // A tab switch fires both focus and visibilitychange. Keep the displayed
    // record in place and avoid starting two requests.
    if (refreshInFlight.current || Date.now() - lastRefreshStarted.current < 1000) return;
    refreshInFlight.current = true;
    lastRefreshStarted.current = Date.now();
    try {
      const res = await fetch("/api/public-record?scope=home");
      const json = await res.json();
      if (!res.ok) throw new Error(json?.error || "Failed to load public homepage record");

      setRecentBets((json.recent ?? []) as HomepageBet[]);
      setPendingBets((json.pending ?? []) as HomepageBet[]);
      calculateCombinedStats((json.stats as MarketStats[] | null) ?? []);
      setRecordStatus(Array.isArray(json.stats) && json.stats.length ? "loaded" : "historical");
      setLast7Error(false);
      if (json.last7 && typeof json.last7.total === "number") {
        setLast7DaysProfit(json.last7.total);
        setLast7DaysCount(typeof json.last7.count === "number" ? json.last7.count : 0);
      } else {
        setLast7Error(true);
      }
    } catch (error) {
      console.error("Error fetching public homepage record:", error);
      setLast7Error(true);
      setRecordStatus("unavailable");
    } finally {
      refreshInFlight.current = false;
    }
  }, []);

  useEffect(() => {
    const initialFetchId = hasInitialPayload ? undefined : window.setTimeout(() => {
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
      if (initialFetchId !== undefined) window.clearTimeout(initialFetchId);
      window.removeEventListener("focus", handleFocus);
      document.removeEventListener("visibilitychange", handleVisibility);
    };
  }, [fetchData, hasInitialPayload]);

  const displayStats = combinedStats ?? getBaselineDisplayStats();
  const trackingPeriod = getTrackingMonths();
  const heroProofStats = [
    {
      label: "Overall ROI",
      icon: "roi" as const,
      value: `${displayStats.overall.roi > 0 ? "+" : ""}${displayStats.overall.roi.toFixed(1)}%`,
    },
    {
      label: "Settled bets",
      icon: "bets" as const,
      value: `${displayStats.overall.total_bets.toLocaleString()}`,
    },
    {
      label: "Tracking period",
      icon: "calendar" as const,
      value: trackingPeriod,
    },
  ];
  return (
    <div className="min-h-screen bg-[#0f1117] text-slate-100">
      <main id="main-content">

      <section className="home-hero border-b border-slate-800/70 py-7 sm:py-10">
        <div className="home-lead hf-container">
          <div className="home-lead-intro">
            <p className="hf-eyebrow">Il Margine · Football &amp; tennis</p>
            <h1>Betting insight.<br /><span>Tools. Models. Picks.</span></h1>
            <p className="home-lead-copy">Our latest selections, plus free tools to explore the players, clubs and managers behind your next bet.</p>
          </div>
          <div className="home-lead-picks"><TodaysEdge picks={pendingBets} lastSettled={recentBets[0] ?? null} last7Profit={last7DaysProfit} /></div>
          <div className="home-lead-record">
            <div className="home-performance-proof mt-5 rounded-2xl border border-slate-700/60 p-4 sm:p-5">
              <div className="mb-4 flex flex-wrap items-center justify-between gap-2"><p className="text-xs font-semibold uppercase tracking-wider text-slate-400">{recordStatus === "historical" || !combinedStats ? "Earlier recorded results" : "Public performance record"}</p><Link href="/track-record" className="text-xs text-emerald-300 underline underline-offset-4">View results ↗</Link></div>
              <dl className="grid grid-cols-3 gap-3">{heroProofStats.map(stat => <div key={stat.label}><RecordIcon name={stat.icon} className="mb-3 h-6 w-6 text-emerald-200" /><dt className="text-xs leading-5 text-slate-400">{stat.label}</dt><dd className="mt-1.5 text-lg font-semibold tabular-nums tracking-tight sm:text-2xl">{stat.value}</dd></div>)}</dl>
              <p className="mt-4 text-xs leading-5 text-slate-400">{recordStatus === "unavailable" ? "The latest refresh is unavailable. These are the last available figures, which may exclude recent results." : recordStatus === "historical" ? "Earlier recorded results are shown. The latest results are unavailable and are not included." : "Past performance is not a forecast."}</p><Link prefetch={false} href="/track-record#record-method" className="mt-2 inline-flex min-h-9 items-center text-xs text-emerald-200 underline underline-offset-4">How the record is calculated →</Link>
            </div>
          </div>
        </div>
      </section>
      <HomeFixtures />
      <MonthlyBreakdownSection scope="combined" initialPayload={initialMonthly} cards />
      {recentBets.length > 0 ? (
        <section className="border-b border-slate-800/30 bg-[#0b0e13] py-9 md:py-12">
          <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
            <div className="mb-5 flex flex-col gap-4 sm:mb-6 sm:flex-row sm:items-center sm:justify-between">
              <div>
                <span className="mb-2 block text-xs font-mono font-bold uppercase tracking-[0.18em] text-[rgba(87,209,150,0.95)]">Latest results</span>
                <h2 className="text-2xl font-semibold text-slate-100 sm:text-3xl">Latest settled picks</h2>
              </div>
              {last7DaysProfit != null && !last7Error && last7DaysCount > 0 ? (
                <span
                  className={`tabular-nums text-xs sm:text-sm ${
                    last7DaysProfit > 0 ? "text-[var(--brand-green)]" : last7DaysProfit < 0 ? "text-red-400" : "text-slate-300"
                  }`}
                >
                  Last 7 days: {last7DaysProfit > 0 ? "+" : ""}{last7DaysProfit.toFixed(2)}u
                  <span className="ml-1 font-normal text-slate-400">
                    ({last7DaysCount} bet{last7DaysCount !== 1 ? "s" : ""})
                  </span>
                </span>
              ) : null}
            </div>
            <p className="mb-6 text-xs text-slate-400">Stake in units (1u = your standard stake). We typically recommend 0.5u to 2u per pick.</p>
            <div className="overflow-hidden rounded-2xl border border-slate-700/40 bg-[#0c0f14]">
              <div className="hidden overflow-x-auto md:block">
                <PublicBetsTable bets={recentBets.slice(0, 5)} mode="settled" />
              </div>
              <div className="divide-y divide-slate-800/40 md:hidden">
                {recentBets.slice(0, 5).map((bet) => (
                  <Link
                    key={bet.id}
                    href={publicTipPath(bet)}
                    className="block cursor-pointer p-5 hover:bg-slate-800/20 active:bg-slate-800/30"
                  >
                    <div className="mb-2 flex items-start justify-between">
                      <div className="flex-1">
                        <div className="mb-1 flex items-center gap-2">
                          <span className="text-xs whitespace-nowrap text-slate-400">{formatMatchDate(bet.match_date)}</span>
                        </div>
                        <div className="mb-1 font-medium text-slate-200">{bet.event}</div>
                        <div className="mb-1 text-sm text-slate-300">
                          {bet.player ? <span>{bet.player}: </span> : null}
                          {bet.selection}
                        </div>
                      </div>
                      <ResultBadge status={bet.status} size="sm" className="ml-3" />
                    </div>
                    <BetMobileMeta
                      odds={bet.odds}
                      bookmaker={bet.bookmaker}
                      stake={bet.stake}
                      status={bet.status}
                      profitLoss={bet.profit_loss}
                      showProfit
                    />
                  </Link>
                ))}
              </div>
            </div>

            <div className="mt-6 flex flex-wrap justify-center gap-x-5 gap-y-2 text-sm">
              <Link href="/tennis-tips#picks" className="text-slate-400 transition-colors hover:text-[var(--brand-green)]">
                Review tennis results -&gt;
              </Link>
              <Link href="/player-props#picks" className="text-slate-400 transition-colors hover:text-[var(--brand-green)]">
                Review player props results -&gt;
              </Link>
            </div>
          </div>
        </section>
      ) : null}


      <section className="site-section" id="tools">
        <div className="hf-container"><div className="hf-heading"><div><p className="hf-eyebrow">Go deeper</p><h2>Your research desk.</h2><p>Choose the question. Open the tool.</p></div><Link prefetch={false} href="/tools">All tools ↗</Link></div>
          <div className="home-compact-directory">{[
            ["/football-atlas", "Football Return Atlas", "Club returns by season, venue and price."],
            ["/manager-atlas", "Manager Return Atlas", "Follow managers across clubs and meetings."],
            ["/return-atlas", "Tennis Return Atlas", "Player returns at the recorded match odds."],
            ["/tennis-matchup", "Tennis Matchup Lab", "Serve, return and head to head profiles."],
            ["/fair-odds-lab", "Fair Odds Lab", "Compare goalscorer prices and lineups."],
            ["/fair-odds-lab/aerial", "Air Control", "Height, aerial profiles and delivery."],
          ].map(([href,title,copy]) => <Link prefetch={false} href={href} key={href}><ToolEmblem name={emblemForHref(href)} /><div><h3>{title}</h3><p>{copy}</p></div><span aria-hidden="true">↗</span></Link>)}</div>
          <div className="mt-6 flex flex-wrap gap-x-6 gap-y-2 text-sm text-slate-400"><Link href="/penalty-takers" className="inline-flex min-h-11 items-center">Penalty takers ↗</Link><Link href="/resources" className="inline-flex min-h-11 items-center">Betting guides ↗</Link><Link href="/the-edge" className="inline-flex min-h-11 items-center">Our methodology ↗</Link></div>
        </div>
      </section>
      </main>
      <Footer />
    </div>
  );
}
