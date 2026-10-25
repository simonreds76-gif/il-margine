"use client";
import { buildCombinedStats, type CombinedMarketStats } from "@/lib/homepage-record";
import HomeFixtures from "@/components/HomeFixtures";

import { useCallback, useEffect, useRef, useState } from "react";
import Link from "next/link";
import { type Bet, type Bookmaker, type MarketStats } from "@/lib/supabase";
import { getBaselineDisplayStats } from "@/lib/baseline";
import BetMobileMeta from "@/components/BetMobileMeta";
import PublicBetsTable from "@/components/PublicBetsTable";
import ResultBadge from "@/components/ResultBadge";
import TodaysEdge from "@/components/TodaysEdge";
import ToolEmblem, { emblemForHref } from "@/components/ToolEmblem";
import "./home-discovery.css";
import HomePerformanceRecord from "@/components/HomePerformanceRecord";
import Footer from "@/components/Footer";
import MonthlyBreakdownSection from "@/components/MonthlyBreakdownSection";
import type { MonthRow } from "@/components/MonthlyBreakdown";
import { formatMatchDate } from "@/lib/format";
import { publicTipPath } from "@/lib/tip-seo";

type HomepageBet = Bet & {
  bookmaker?: Bookmaker | Bookmaker[] | null;
};

type HomepageClientProps = {
  initialMonthly?: { show: boolean; rows: MonthRow[] };
  initialMonthlyBySport?: Partial<Record<'props' | 'tennis', { show: boolean; rows: MonthRow[] }>>;
  initialMarketStats?: MarketStats[];
  initialRecentBets?: HomepageBet[];
  initialPendingBets?: HomepageBet[];
  initialLast7?: { total: number; count: number } | null;
};

export default function HomepageClient({
  initialMonthly,
  initialMonthlyBySport,
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
  return (
    <div className="min-h-screen bg-[#0f1117] text-slate-100">
      <main id="main-content">

      <section className="home-hero border-b border-slate-800/70 py-7 sm:py-10">
        <div className="home-lead hf-container">
          <div className="home-lead-intro">
            <p className="hf-eyebrow">Il Margine · Football &amp; tennis</p>
            <h1>Data driven betting.<br /><span>Tools for sharper decisions.</span></h1>
            <p className="home-lead-copy">Football and tennis models, published selections and free research tools. Compare player statistics, explore club and manager head to head records, and see how past bets performed at the recorded odds.</p>
          </div>
          <div className="home-lead-picks"><TodaysEdge picks={pendingBets} lastSettled={recentBets[0] ?? null} last7Profit={last7DaysProfit} /></div>
          <div className="home-lead-record">
            <HomePerformanceRecord stats={displayStats} status={recordStatus} />
          </div>
        </div>
      </section>
      <HomeFixtures />
      <MonthlyBreakdownSection scope="combined" initialPayload={initialMonthly} bySport={initialMonthlyBySport} cards />
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
              <Link href="/tennis-tips#recent-results" className="text-slate-400 transition-colors hover:text-[var(--brand-green)]">
                Review tennis results -&gt;
              </Link>
              <Link href="/player-props#recent-results" className="text-slate-400 transition-colors hover:text-[var(--brand-green)]">
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
            ["/penalty-takers", "Club penalty takers", "First choices, backups and recent penalty history."],
          ].map(([href,title,copy]) => <Link prefetch={false} href={href} key={href}><ToolEmblem name={emblemForHref(href)} /><div><h3>{title}</h3><p>{copy}</p></div><span aria-hidden="true">↗</span></Link>)}</div>
          <div className="mt-6 flex flex-wrap gap-x-6 gap-y-2 text-sm text-slate-400"><Link href="/resources" className="inline-flex min-h-11 items-center">Betting guides ↗</Link><Link href="/the-edge" className="inline-flex min-h-11 items-center">Our methodology ↗</Link></div>
        </div>
      </section>
      </main>
      <Footer />
    </div>
  );
}
