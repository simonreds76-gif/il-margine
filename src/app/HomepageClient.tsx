"use client";

import { useCallback, useEffect, useState, type ReactNode } from "react";
import Link from "next/link";
import { questionSlug } from "@/lib/parse-faq";
import { type Bet, type Bookmaker, type MarketStats } from "@/lib/supabase";
import { BASELINE_STATS, calculateROI, calculateWinRate, getBaselineDisplayStats } from "@/lib/baseline";
import BetMobileMeta from "@/components/BetMobileMeta";
import PublicBetsTable from "@/components/PublicBetsTable";
import ResultBadge from "@/components/ResultBadge";
import TodaysEdge from "@/components/TodaysEdge";
import Footer from "@/components/Footer";
import MonthlyBreakdownSection from "@/components/MonthlyBreakdownSection";
import type { MonthRow } from "@/components/MonthlyBreakdown";
import LabNotesSection from "@/components/LabNotesSection";
import PropsAlertsCta from "@/components/PropsAlertsCta";
import { formatMatchDate } from "@/lib/format";
import { publicTipPath } from "@/lib/tip-seo";
import type { Resource } from "@/lib/resources";

const HOMEPAGE_KEYFRAMES = `
@keyframes homepage-reveal {
  from { opacity: 0; transform: translateY(18px); }
  to { opacity: 1; transform: translateY(0); }
}
@keyframes homepage-underline {
  from { transform: scaleX(0); }
  to { transform: scaleX(1); }
}
`;

const COMPILER_CARDS = [
  {
    number: "01",
    title: "Template pricing",
    body: "Props are rarely handcrafted per match. Opponent context and role changes often go missing.",
  },
  {
    number: "02",
    title: "Margin allocation",
    body: "Player props usually carry more margin and less oversight than headline markets.",
  },
  {
    number: "03",
    title: "Copy-paste lines",
    body: "If the original number is wrong, smaller books inherit the same error.",
  },
  {
    number: "04",
    title: "Risk gaps",
    body: "High-profile markets get monitored hardest. We look where value survives longer.",
  },
] as const;

const EXPLORE_LINKS = [
  {
    href: "/the-edge",
    title: "The Edge",
    body: "Our methodology. Former compiler knowledge applied to find value.",
  },
  {
    href: "/track-record",
    title: "Track Record",
    body: "Verified performance, immutable timestamps, and transparent settlement.",
  },
  {
    href: "/calculator",
    title: "Calculator",
    body: "Returns tracking and Kelly sizing built around the same approach.",
  },
  {
    href: "/bookmakers",
    title: "Bookmakers",
    body: "Which books to use, how limits work, and how to stay operational.",
  },
] as const;

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

function HomepageReveal({ children, delay = 0, className = "" }: { children: ReactNode; delay?: number; className?: string }) {
  return (
    <div
      className={className}
      style={{
        animation: "homepage-reveal 0.75s cubic-bezier(0.16,1,0.3,1) both",
        animationDelay: `${delay}ms`,
      }}
    >
      {children}
    </div>
  );
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
        <div className="mb-3 flex items-center gap-2.5">
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
          <div className="mt-4 flex items-baseline gap-4 font-mono text-[12px]">
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
    <Link href={href} className="block h-full">
      {card}
    </Link>
  );
}

function ExploreCard({ href, title, body }: { href: string; title: string; body: string }) {
  return (
    <Link
      href={href}
      className="group flex h-full flex-col rounded-xl border border-slate-700/40 bg-[#0c0f14] p-4 transition-all duration-300 hover:-translate-y-[1px] hover:border-[rgba(87,209,150,0.20)] sm:p-5"
    >
      <h3 className="mb-1 text-[14px] font-semibold text-slate-200 transition-colors group-hover:text-white">{title}</h3>
      <p className="text-[13px] leading-[1.6] text-slate-400 transition-colors group-hover:text-slate-300">{body}</p>
      <span className="mt-auto inline-flex w-full items-center justify-between pt-4 font-mono text-[11px] uppercase tracking-[0.15em] text-[rgba(87,209,150,0.78)] transition-colors group-hover:text-[var(--brand-green)]">
        View page {"\u2192"}
      </span>
    </Link>
  );
}

type HomepageClientProps = {
  initialMarketStats?: MarketStats[];
  initialRecentBets?: HomepageBet[];
  initialPendingBets?: HomepageBet[];
  initialLast7?: { total: number; count: number } | null;
  initialMonthlyPayload?: { show: boolean; rows: MonthRow[] };
  initialLabNotes?: Resource[];
  currentlyWatching?: string | null;
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
  initialMarketStats = [],
  initialRecentBets = [],
  initialPendingBets = [],
  initialLast7 = null,
  initialMonthlyPayload,
  initialLabNotes = [],
  currentlyWatching = null,
}: HomepageClientProps) {
  const [recentBets, setRecentBets] = useState<HomepageBet[]>(initialRecentBets);
  const [pendingBets, setPendingBets] = useState<HomepageBet[]>(initialPendingBets);
  const [last7DaysProfit, setLast7DaysProfit] = useState<number | null>(initialLast7?.total ?? null);
  const [last7DaysCount, setLast7DaysCount] = useState<number>(initialLast7?.count ?? 0);
  const [last7Error, setLast7Error] = useState<boolean>(!initialLast7);
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
      calculateCombinedStats([]);
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
      value: `${displayStats.overall.total_bets.toLocaleString()}+`,
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
      description: "Football individual player markets where tactical context changes probability fast.",
      status: "active" as const,
      bets: `${displayStats.props.total_bets}+`,
      profit: `${displayStats.props.roi > 0 ? "+" : ""}${displayStats.props.roi.toFixed(1)}% ROI`,
    },
    {
      id: "atp",
      name: "ATP Tennis",
      description: "Pre-match singles markets backed by deeper model work and pricing discipline.",
      status: "active" as const,
      bets: `${displayStats.tennis.total_bets}+`,
      profit: `${displayStats.tennis.roi > 0 ? "+" : ""}${displayStats.tennis.roi.toFixed(1)}% ROI`,
    },
    {
      id: "atg",
      name: "Fair Odds Lab",
      description: "Anytime goalscorer value spots where our model's fair price is shorter than the bookies'.",
      status: "active" as const,
      profit: "Live intelligence board",
    },
  ];

  return (
    <div className="min-h-screen bg-[#0f1117] text-slate-100">
      <style jsx global>{HOMEPAGE_KEYFRAMES}</style>

      <section className="relative overflow-hidden border-b border-slate-800/40 pt-6 pb-12 md:pb-14 lg:pb-16">
        <div
          className="pointer-events-none absolute inset-x-0 -top-24 h-[640px]"
          style={{ background: "radial-gradient(ellipse 1200px 550px at 50% -120px, rgba(87,209,150,0.10), transparent)" }}
        />
        <div className="pointer-events-none absolute -right-36 top-0 h-[420px] w-[420px] rounded-full bg-[rgba(87,209,150,0.035)] blur-[120px]" />

        <div className="relative z-10 mx-auto max-w-6xl px-4 sm:px-6 lg:px-8">
          <div className="grid items-start gap-8 lg:grid-cols-[minmax(0,1.08fr)_minmax(23rem,0.92fr)] lg:gap-10 xl:gap-14">
            <div className="lg:py-4">
              <HomepageReveal delay={80}>
                <h1 className="text-[3rem] font-semibold leading-[0.98] tracking-[-0.045em] text-white sm:text-6xl md:text-7xl">
                  Betting with
                  <br className="hidden md:block" />{" "}
                  <span className="relative inline-block text-[var(--brand-green)]">
                    mathematical
                    <span
                      className="absolute bottom-0 left-0 right-0 h-[2px] origin-left rounded-full bg-[rgba(87,209,150,0.32)]"
                      style={{ animation: "homepage-underline 0.8s cubic-bezier(0.16,1,0.3,1) both", animationDelay: "850ms" }}
                    />
                  </span>
                  <br className="hidden md:block" />{" "}
                  <span className="relative inline-block text-[var(--brand-green)]">
                    edge
                    <span
                      className="absolute bottom-0 left-0 right-0 h-[2px] origin-left rounded-full bg-[rgba(87,209,150,0.32)]"
                      style={{ animation: "homepage-underline 0.8s cubic-bezier(0.16,1,0.3,1) both", animationDelay: "1025ms" }}
                    />
                  </span>
                </h1>
              </HomepageReveal>

              <HomepageReveal delay={240}>
                <p className="mt-6 max-w-xl text-lg leading-relaxed text-slate-300">
                  Professional betting methodology from a former odds compiler. We identify value where bookmakers misprice markets.
                </p>
              </HomepageReveal>

              <HomepageReveal delay={380}>
                <div className="mt-8 flex flex-wrap items-center gap-4">
                  <PropsAlertsCta source="homepage_hero" variant="pill" />
                  <Link
                    href="/player-props#picks"
                    className="inline-flex items-center gap-2 rounded-lg border border-slate-600 px-6 py-3 text-base font-medium text-slate-200 transition-all hover:border-slate-400 hover:bg-slate-800/40"
                  >
                    Today&apos;s picks {"\u2192"}
                  </Link>
                </div>
              </HomepageReveal>

              <HomepageReveal delay={520}>
                <div className="mt-7 flex flex-wrap items-center gap-3 font-mono text-xs text-slate-400">
                  {[
                    "Selected free picks",
                    "Every result logged",
                    "Transparent record",
                  ].map((item) => (
                    <span key={item} className="inline-flex items-center gap-2">
                      <span className="h-[3px] w-[3px] rounded-full bg-slate-600" />
                      {item}
                    </span>
                  ))}
                </div>
              </HomepageReveal>

              <HomepageReveal delay={650}>
                <div className="mt-8 max-w-3xl rounded-[1.4rem] border border-[rgba(87,209,150,0.22)] bg-[linear-gradient(135deg,rgba(87,209,150,0.13),rgba(9,13,19,0.78)_34%,rgba(9,13,19,0.96))] p-2 shadow-[0_24px_80px_rgba(0,0,0,0.32)]">
                  <div className="mb-2 flex items-center justify-between px-2 pt-1 font-mono text-[10px] font-bold uppercase tracking-[0.18em] text-[rgba(87,209,150,0.82)]">
                    <span>Public record</span>
                    <span className="text-slate-400">Updated within a minute</span>
                  </div>
                  <div className="grid grid-cols-3 gap-1.5 sm:gap-2">
                    {heroProofStats.map((stat) => (
                      <div key={stat.label} className="rounded-xl border border-white/[0.06] bg-slate-950/55 px-2 py-3 text-center sm:rounded-2xl sm:px-4 sm:py-4 sm:text-left">
                        <div className="font-mono text-[10px] font-bold uppercase leading-tight tracking-[0.09em] text-slate-400 sm:text-[11px] sm:tracking-[0.14em]">
                          {stat.label}
                        </div>
                        <div className="mt-2 font-mono text-lg font-black leading-none tracking-tight text-[var(--brand-green)] sm:text-2xl">
                          {stat.value}
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              </HomepageReveal>
            </div>

            <HomepageReveal delay={380} className="lg:mt-8">
              <TodaysEdge
                picks={pendingBets}
                lastSettled={recentBets[0] ?? null}
                last7Profit={last7DaysProfit}
              />
            </HomepageReveal>
          </div>
        </div>
      </section>

      {recentBets.length > 0 ? (
        <section className="border-b border-slate-800/30 bg-[#0b0e13] py-16 md:py-20">
          <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
            <div className="mb-8 flex flex-col gap-4 sm:mb-10 sm:flex-row sm:items-center sm:justify-between">
              <div>
                <span className="mb-2 block text-xs font-mono font-bold uppercase tracking-[0.18em] text-[rgba(87,209,150,0.95)]">Latest results</span>
                <h2 className="text-2xl font-semibold text-slate-100 sm:text-3xl">Latest settled picks</h2>
              </div>
              {last7DaysProfit != null && !last7Error && last7DaysCount > 0 ? (
                <span
                  className={`font-mono text-xs sm:text-sm ${
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
            <PropsAlertsCta source="homepage_after_results" className="mt-8" />
          </div>
        </section>
      ) : null}

      <MonthlyBreakdownSection scope="combined" initialPayload={initialMonthlyPayload} />

      <section id="markets" className="border-b border-slate-800/30 py-16 md:py-20 scroll-mt-20">
        <div className="mx-auto max-w-6xl px-4 sm:px-6 lg:px-8">
          <span className="mb-2 block text-xs font-mono font-bold uppercase tracking-[0.18em] text-[rgba(87,209,150,0.95)]">
            Where we operate
          </span>
          <h2 className="text-2xl font-semibold text-slate-100 sm:text-3xl">Markets</h2>
          <p className="mt-4 max-w-2xl text-base leading-relaxed text-slate-400">
            We focus on markets where our pricing can be stronger than the number on offer - usually football player props and selective ATP tennis rather than headline match odds.
          </p>

          <div className={`mt-10 grid gap-3 md:grid-cols-2 ${markets.length > 3 ? "lg:grid-cols-4" : "lg:grid-cols-3"}`}>
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

      <section className="border-b border-slate-800/30 py-16 md:py-20">
        <div className="mx-auto max-w-6xl px-4 sm:px-6 lg:px-8">
          <div className="grid gap-10 lg:grid-cols-[minmax(0,1fr)_minmax(0,0.9fr)] lg:gap-16">
            <div className="lg:sticky lg:top-28 lg:self-start">
              <div className="mb-5 flex items-center gap-3">
                <div className="h-10 w-[3px] rounded-full bg-[var(--brand-green)]" />
                <span className="text-xs font-mono font-bold uppercase tracking-[0.18em] text-[rgba(87,209,150,0.95)]">
                  Why Il Margine
                </span>
              </div>
              <h2 className="text-2xl font-semibold leading-tight text-slate-100 sm:text-3xl">
                Built from the
                <br />
                other side
              </h2>
              <div className="mt-5 space-y-4 text-base leading-relaxed text-slate-400">
                <p>
                  Most betting services learn by betting. We learned by <span className="font-medium text-slate-200">building the prices</span> bookmakers use.
                </p>
                <p>
                  Template pricing, margin allocation, copied lines, and risk-management blind spots are where the machinery leaves room for edge.
                </p>
              </div>
              <Link
                href="/the-edge"
                className="group mt-6 inline-flex items-center gap-1.5 text-sm font-medium text-[rgba(87,209,150,0.80)] transition-colors hover:text-[var(--brand-green)]"
              >
                Read full methodology
                <svg className="h-3.5 w-3.5 transition-transform group-hover:translate-x-0.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9 5l7 7-7 7" />
                </svg>
              </Link>
            </div>

            <div className="grid gap-2.5 sm:grid-cols-2">
              {COMPILER_CARDS.map((item) => (
                <div key={item.number} className="group relative overflow-hidden rounded-xl border border-slate-700/40 bg-[#0c0f14] p-4 transition-all duration-300 hover:border-slate-600/50">
                  <span className="pointer-events-none absolute -right-1 -top-3 select-none font-mono text-[52px] font-black leading-none text-white/[0.015]">
                    {item.number}
                  </span>
                  <div className="relative">
                    <span className="font-mono text-[10px] font-bold text-[rgba(87,209,150,0.70)]">{item.number}</span>
                    <h3 className="mt-1 text-[14px] font-semibold text-slate-200">{item.title}</h3>
                    <p className="mt-1.5 text-[13px] leading-[1.6] text-slate-400 transition-colors duration-300 group-hover:text-slate-300">
                      {item.body}
                    </p>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      </section>



      <section className="border-b border-slate-800/30 bg-[#0b0e13] py-16 md:py-20">
        <div className="mx-auto max-w-6xl px-4 sm:px-6 lg:px-8">
          <span className="mb-2 block text-xs font-mono font-bold uppercase tracking-[0.18em] text-[rgba(87,209,150,0.95)]">
            Go deeper
          </span>
          <h2 className="text-2xl font-semibold text-slate-100 sm:text-3xl">Explore</h2>
          <div className="mt-8 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            {EXPLORE_LINKS.map((item) => (
              <ExploreCard key={item.href} href={item.href} title={item.title} body={item.body} />
            ))}
          </div>
        </div>
      </section>

      <LabNotesSection notes={initialLabNotes} currentlyWatching={currentlyWatching} />

      <section className="border-b border-slate-800/30 py-16 md:py-20">
        <div className="mx-auto max-w-6xl px-4 sm:px-6 lg:px-8">
          <div className="mb-8 flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
            <div>
              <span className="mb-2 block text-xs font-mono font-bold uppercase tracking-[0.18em] text-[rgba(87,209,150,0.95)]">
                Common questions
              </span>
              <h2 className="text-2xl font-semibold text-slate-100 sm:text-3xl">Frequently asked questions</h2>
            </div>
            <Link href="/faq" className="shrink-0 text-sm font-medium text-[var(--brand-green)] transition-colors hover:text-[var(--brand-green)]">
              View all FAQ -&gt;
            </Link>
          </div>

          <div className="grid max-w-4xl gap-4 sm:grid-cols-2">
            {(
              [
                {
                  q: "What does \"betting with mathematical edge\" mean?",
                  title: "What makes a bet value instead of just a guess?",
                  summary: "We price the event first, then only act when the odds on screen are bigger than the true probability.",
                },
                {
                  q: "Why do you focus on player props and tennis instead of mainstream match odds?",
                  title: "Why these markets instead of headline match odds?",
                  summary: "Because player props and selective ATP tennis give us more room to beat the screen than generic top-line markets do.",
                },
                {
                  q: "How do I follow Il Margine's betting tips?",
                  title: "Where do the tips actually get posted?",
                  summary: "Every pick is posted on the site. Football player-prop picks can also reach you through our free Telegram alerts.",
                },
                {
                  q: "Why does ROI matter more than win rate?",
                  title: "How should I judge whether the picks actually work?",
                  summary: "Not by raw win rate. ROI tells you whether the prices taken are genuinely profitable over a real sample.",
                },
              ] as const
            ).map((item) => (
              <Link
                key={item.q}
                href={`/faq#${questionSlug(item.q)}`}
                className="group flex h-full flex-col rounded-xl border border-slate-700/40 bg-[#0c0f14] p-4 text-left transition-all duration-300 hover:-translate-y-[1px] hover:border-[rgba(87,209,150,0.25)] sm:p-5"
              >
                <h3 className="mb-2 text-[15px] font-medium text-slate-200 transition-colors group-hover:text-white">{item.title}</h3>
                <p className="text-sm leading-relaxed text-slate-400 transition-colors group-hover:text-slate-300">{item.summary}</p>
                <span className="mt-auto pt-4 font-mono text-[11px] uppercase tracking-[0.15em] text-[rgba(87,209,150,0.78)] transition-colors group-hover:text-[var(--brand-green)]">
                  Read answer {"\u2192"}
                </span>
              </Link>
            ))}
          </div>
        </div>
      </section>

      <section className="py-16 md:py-20">
        <div className="mx-auto max-w-6xl px-4 sm:px-6 lg:px-8">
          <div className="relative overflow-hidden rounded-2xl border border-[rgba(87,209,150,0.15)] px-6 py-10 text-center md:px-10 md:py-14">
            <div className="absolute inset-0 bg-[#0c0f14]" />
            <div
              className="pointer-events-none absolute inset-0"
              style={{ background: "radial-gradient(circle at 50% 140%, rgba(87,209,150,0.12), transparent 55%)" }}
            />
            <div
              className="absolute top-0 left-[12%] right-[12%] h-px"
              style={{ background: "linear-gradient(90deg, transparent, rgba(87,209,150,0.35), transparent)" }}
            />
            <div className="relative">
              <h2 className="text-3xl font-semibold text-slate-100">See the edge in practice</h2>
              <p className="mx-auto mt-4 max-w-lg text-base leading-relaxed text-slate-300">
                Free selections posted on site. Match, market, selection, odds, bookmaker, and stake. Everything needed to place the bet with clarity.
              </p>
              <div className="mt-8 flex flex-wrap items-center justify-center gap-4">
                <Link
                  href="/player-props#picks"
                  className="inline-flex items-center gap-2 rounded-lg bg-[var(--brand-green)] px-8 py-3.5 text-[15px] font-semibold text-slate-950 transition-all hover:brightness-110 hover:shadow-[0_0_50px_rgba(87,209,150,0.22)]"
                >
                  Open latest picks {"\u2192"}
                </Link>
                <Link
                  href="/track-record"
                  className="inline-flex items-center gap-2 rounded-lg border border-slate-600 px-8 py-3.5 text-[15px] font-medium text-slate-200 transition-all hover:border-slate-400 hover:bg-slate-800/40"
                >
                  See track record {"\u2192"}
                </Link>
              </div>
            </div>
          </div>
        </div>
      </section>

      <div className="mx-auto max-w-6xl px-4 pb-14 sm:px-6 lg:px-8">
        <div className="rounded-xl border border-amber-500/20 bg-amber-500/[0.05] px-5 py-4 text-[13px] leading-relaxed text-slate-300">
          <strong className="text-amber-400">Responsible gambling:</strong> Past performance does not guarantee future results. Only bet what you can afford to lose.{" "}
          <a href="https://www.begambleaware.org" target="_blank" rel="noopener noreferrer" className="text-slate-200 underline underline-offset-2">BeGambleAware</a>
          <span className="px-1.5 text-slate-500">|</span>
          <a href="https://www.gamcare.org.uk" target="_blank" rel="noopener noreferrer" className="text-slate-200 underline underline-offset-2">GamCare</a>
        </div>
      </div>

      <Footer />
    </div>
  );
}
