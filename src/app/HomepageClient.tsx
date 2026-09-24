"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { type Bet, type Bookmaker, type MarketStats } from "@/lib/supabase";
import { BASELINE_STATS, calculateROI, calculateWinRate, getBaselineDisplayStats } from "@/lib/baseline";
import BetMobileMeta from "@/components/BetMobileMeta";
import PublicBetsTable from "@/components/PublicBetsTable";
import ResultBadge from "@/components/ResultBadge";
import TodaysEdge from "@/components/TodaysEdge";
import ToolEmblem, { emblemForHref } from "@/components/ToolEmblem";
import "./home-discovery.css";
import SportCta from "@/components/SportCta";
import ReturnAtlasFeature from "@/components/ReturnAtlasFeature";
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

type HomepageMarket = {
  id: string;
  name: string;
  description: string;
  status: "active" | "coming";
  bets?: string;
  profit?: string;
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

function MarketCard({
  market,
  href,
}: {
  market: HomepageMarket;
  href?: string;
}) {
  const active = market.status === "active";
  const card = (
    <div
      className={`group relative flex h-full min-h-[160px] flex-col overflow-hidden rounded-2xl border p-5 transition-all duration-300 md:p-6 ${
        active
          ? "border-[rgba(87,209,150,0.20)] bg-[#0c0f14] hover:-translate-y-[2px] hover:border-[rgba(87,209,150,0.30)] hover:shadow-[0_12px_48px_rgba(87,209,150,0.04)]"
          : "border-slate-700/40 bg-[#0c0f14] opacity-90"
      }`}
    >
      {active ? (
        <div
          className="absolute top-0 left-[8%] right-[8%] h-px"
          style={{ background: "linear-gradient(90deg, transparent, rgba(87,209,150,0.22), transparent)" }}
        />
      ) : null}
      <div className="relative flex h-full flex-col">
        <div className="home-market-art"><ToolEmblem name={market.id === "atp" ? "tennis" : market.id === "atg" ? "lab" : "football"} /><span className="home-discovery-arrow" aria-hidden="true">↗</span></div>
        <div className="mb-3 flex flex-wrap items-center gap-2.5">
          <h3 className="text-[15px] font-semibold text-slate-200">{market.name}</h3>
          <span
            className={`rounded-full border px-2.5 py-[2px] text-[10px] font-mono font-bold uppercase tracking-[0.14em] ${
              active
                ? "border-[rgba(87,209,150,0.20)] bg-[rgba(87,209,150,0.08)] text-[rgba(87,209,150,0.85)]"
                : "border-slate-700/40 bg-slate-800/50 text-slate-400"
            }`}
          >
            {active ? (market.id === "atg" ? "Model" : "Active") : "Soon"}
          </span>
        </div>
        <p className="text-[13px] leading-[1.65] text-slate-400 transition-colors duration-300 group-hover:text-slate-300">{market.description}</p>
        {active && market.profit ? (
          <div className="mt-4 flex items-baseline gap-4 tabular-nums text-[12px]">
            {market.bets ? <span className="tabular-nums text-slate-400">{market.bets} bets</span> : null}
            <span className="font-semibold tabular-nums text-[rgba(87,209,150,0.90)]">{market.profit}</span>
          </div>
        ) : null}
      </div>
    </div>
  );

  if (!href || !active) {
    return card;
  }

  return (
    <Link prefetch={false} href={href} className="home-market-link block h-full">
      {card}
    </Link>
  );
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

  const fetchData = useCallback(async () => {
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
      value: `${displayStats.overall.roi > 0 ? "+" : ""}${displayStats.overall.roi.toFixed(1)}%`,
    },
    {
      label: "Settled bets",
      value: `${displayStats.overall.total_bets.toLocaleString()}`,
    },
    {
      label: "Tracking period",
      value: trackingPeriod,
    },
  ];
  const markets: HomepageMarket[] = [
    {
      id: "props",
      name: "Player Props",
      description: "Published football player selections, recorded odds and settled results.",
      status: "active" as const,
      bets: `${displayStats.props.total_bets}+`,
      profit: `${displayStats.props.roi > 0 ? "+" : ""}${displayStats.props.roi.toFixed(1)}% ROI`,
    },
    {
      id: "atp",
      name: "ATP Tennis",
      description: "Tennis selections with recorded stakes, prices and results.",
      status: "active" as const,
      bets: `${displayStats.tennis.total_bets}+`,
      profit: `${displayStats.tennis.roi > 0 ? "+" : ""}${displayStats.tennis.roi.toFixed(1)}% ROI`,
    },
    {
      id: "atg",
      name: "Fair Odds Lab",
      description: "Expected and confirmed lineups, model fair odds and Bet365 price comparisons.",
      status: "active" as const,
      profit: "Explore lineups & odds",
    },
  ];

  return (
    <div className="min-h-screen bg-[#0f1117] text-slate-100">
      <main id="main-content">

      <section className="home-hero border-b border-slate-800/70 py-8 sm:py-12 lg:py-14">
        <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
          <div className="grid items-start gap-8 lg:grid-cols-[minmax(0,1.08fr)_minmax(22rem,.92fr)] lg:gap-12">
            <div>
              <p className="text-xs font-semibold uppercase tracking-wider text-emerald-300">Football player props &amp; tennis</p>
              <h1 className="mt-3 max-w-2xl text-4xl font-semibold leading-[1.1] tracking-tight text-slate-100 sm:text-5xl xl:text-6xl">Independent <span className="text-emerald-300">betting analysis.</span></h1>
              <p className="mt-4 text-xl font-semibold tracking-tight text-emerald-200 sm:text-2xl">Sharp tools. Mathematical edge.</p>
              <p className="mt-4 max-w-xl text-base leading-7 text-slate-300 sm:text-lg sm:leading-8">We combine statistical models, market expertise and specialist betting tools to identify value in football and tennis. Explore our published picks, investigate the numbers yourself and follow our results month by month.</p>
              <nav aria-label="Explore our betting tools" className="mt-4 flex flex-wrap gap-x-4 gap-y-1 text-sm text-emerald-200">{[["/fair-odds-lab", "Fair Odds Lab"], ["/#return-atlas", "Return Atlas"], ["/penalty-takers", "Penalty takers"], ["/calculator", "Calculators"], ["/resources", "Insights"], ["/tools", "All tools →"]].map(([href, label]) => <Link prefetch={false} key={href} href={href} className="inline-flex min-h-11 items-center underline decoration-emerald-300/25 underline-offset-4 hover:decoration-emerald-200">{label}</Link>)}</nav>
              <div className="mt-6 flex flex-wrap items-center gap-3">
                <SportCta sport="football" />
                <SportCta sport="tennis" />
                <a href="#monthly" className="home-record-link">Monthly results <span aria-hidden="true">↓</span></a>
              </div>
              <div className="mt-5 flex flex-wrap items-center gap-x-4 gap-y-2 text-xs text-slate-400">
                {["Selected free picks", "Every result logged", "Transparent record"].map((item) => <span key={item} className="inline-flex items-center gap-2"><span aria-hidden="true" className="h-1 w-1 rounded-full bg-slate-500" />{item}</span>)}
              </div>
              <div className="mt-6 rounded-2xl border border-slate-800 bg-slate-900/40 p-4 sm:p-5">
                <div className="mb-4 flex flex-wrap items-center justify-between gap-2"><p className="text-xs font-semibold uppercase tracking-wider text-slate-400">{recordStatus === "historical" || !combinedStats ? "Historical performance baseline" : "Public performance record"}</p><Link href="/track-record" className="text-xs text-emerald-300 underline decoration-emerald-400/30 underline-offset-4 hover:text-emerald-200">View results</Link></div>
                <dl className="grid grid-cols-3 gap-3">{heroProofStats.map((stat) => <div key={stat.label}>
                  <dt className="text-xs leading-5 text-slate-400">{stat.label}</dt><dd className="mt-1.5 text-lg font-semibold tabular-nums tracking-tight text-slate-100 sm:text-2xl">{stat.value}</dd>
                </div>)}</dl>
                <p className="mt-3 text-xs text-slate-400">{recordStatus === "unavailable" ? "Record refresh unavailable. Previously loaded figures are retained; historical baseline shown if no current record has loaded." : recordStatus === "historical" ? "Historical figures recorded before database tracking. Current database results have not been included." : "Includes the historical baseline plus settled database results. Past performance is not a forecast."}</p>
              </div>
            </div>
            <div className="lg:pt-1"><TodaysEdge picks={pendingBets} lastSettled={recentBets[0] ?? null} last7Profit={last7DaysProfit} /></div>
          </div>
        </div>
      </section>
      <MonthlyBreakdownSection scope="combined" initialPayload={initialMonthly} />
      <ReturnAtlasFeature />
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
                          {bet.player ? <span>{bet.player} - </span> : null}
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


      <section id="markets" className="border-b border-slate-800/30 py-9 md:py-12 scroll-mt-20">
        <div className="mx-auto max-w-6xl px-4 sm:px-6 lg:px-8">
          <span className="mb-2 block text-xs font-mono font-bold uppercase tracking-[0.18em] text-[rgba(87,209,150,0.95)]">
            Where we operate
          </span>
          <h2 className="text-2xl font-semibold text-slate-100 sm:text-3xl">Markets</h2>
          <p className="mt-4 max-w-2xl text-base leading-relaxed text-slate-400">
            Follow published selections or use the goalscorer board to make your own comparisons.
          </p>

          <div className={`mt-6 grid gap-3 md:grid-cols-2 ${markets.length > 3 ? "lg:grid-cols-4" : "lg:grid-cols-3"}`}>
            {markets.map((market) => {
              const href =
                market.id === "props"
                  ? "/player-props"
                  : market.id === "atp"
                    ? "/tennis-tips"
                    : market.id === "atg"
                      ? "/fair-odds-lab"
                      : undefined;
              return <MarketCard key={market.id} market={market} href={href} />;
            })}
          </div>

        </div>
      </section>

      <section className="site-section">
        <div className="site-container grid gap-6 lg:grid-cols-[1fr_1.3fr]">
          <div><p className="site-eyebrow">The approach</p><h2 className="text-2xl font-semibold tracking-tight">A price is only useful with context.</h2><p className="mt-3 text-sm text-slate-300">We assess the evidence, compare an estimated fair price with the market and record what happens. Our methodology explains the assumptions and limitations.</p><Link href="/the-edge" className="site-text-link">Read our methodology →</Link></div>
          <div className="grid gap-3 sm:grid-cols-2">{[
            ["/track-record", "Review the results", "ROI, sample sizes and links to the full public histories."],
            ["/penalty-takers", "Penalty taker directory", "First choices, deputies and the evidence behind each order."],
            ["/tools", "Find your betting tool", "Fair prices, historical research and staking — choose the tool for your question."],
            ["/resources", "Understand the method", "Practical guides to probability, pricing and value."],
          ].map(([href,title,copy]) => <Link prefetch={false} href={href} key={href} className="site-card site-card-link home-approach-card"><div className="home-approach-art"><ToolEmblem name={emblemForHref(href)} /></div><div className="home-approach-copy"><h3 className="font-semibold">{title}</h3><p className="mt-2 text-sm text-slate-400">{copy}</p></div><span className="home-discovery-arrow" aria-hidden="true">↗</span></Link>)}</div>
        </div>
      </section>
      </main>
      <Footer />
    </div>
  );
}
