"use client";

import { useCallback, useEffect, useState, type ReactNode } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { questionSlug } from "@/lib/parse-faq";
import { type Bet, type Bookmaker, type MarketStats } from "@/lib/supabase";
import { BASELINE_STATS, calculateROI, calculateWinRate, getBaselineDisplayStats } from "@/lib/baseline";
import BetMobileMeta from "@/components/BetMobileMeta";
import PublicBetsTable from "@/components/PublicBetsTable";
import ResultBadge from "@/components/ResultBadge";
import Footer from "@/components/Footer";
import MonthlyBreakdownSection from "@/components/MonthlyBreakdownSection";
import { formatMatchDate } from "@/lib/format";
import { slugifyTip } from "@/lib/slugify";

const HOMEPAGE_KEYFRAMES = `
@keyframes homepage-reveal {
  from { opacity: 0; transform: translateY(18px); }
  to { opacity: 1; transform: translateY(0); }
}
@keyframes homepage-edge-row {
  from { opacity: 0.08; transform: translateX(-4px); }
  to { opacity: 1; transform: translateX(0); }
}
@keyframes homepage-edge-result {
  0% { opacity: 0; transform: scale(0.96); border-color: rgba(16,185,129,0.08); background: transparent; }
  100% { opacity: 1; transform: scale(1); border-color: rgba(16,185,129,0.35); background: rgba(16,185,129,0.08); }
}
@keyframes homepage-edge-scan {
  0% { top: -2px; opacity: 0; }
  10% { opacity: 1; }
  90% { opacity: 1; }
  100% { top: calc(100% + 2px); opacity: 0; }
}
@keyframes homepage-pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.2; }
}
@keyframes homepage-underline {
  from { transform: scaleX(0); }
  to { transform: scaleX(1); }
}
`;

const EDGE_ROWS = [
  ["Bookmaker Odds", "2.10"],
  ["Implied Probability", "47.62%"],
  ["Our Fair Odds", "1.89"],
  ["True Probability", "52.91%"],
] as const;

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

function HomepageEdgeCard() {
  return (
    <div className="relative overflow-hidden rounded-2xl border border-slate-700/40 bg-[#0a0d12] p-6 shadow-2xl shadow-black/35 md:p-7">
      <div
        className="pointer-events-none absolute inset-0 opacity-[0.02]"
        style={{
          backgroundImage:
            "linear-gradient(rgba(255,255,255,0.15) 1px, transparent 1px), linear-gradient(90deg, rgba(255,255,255,0.15) 1px, transparent 1px)",
          backgroundSize: "18px 18px",
        }}
      />
      <div
        className="absolute top-0 left-[8%] right-[8%] h-px"
        style={{ background: "linear-gradient(90deg, transparent, rgba(16,185,129,0.4), transparent)" }}
      />
      <div
        className="pointer-events-none absolute left-0 right-0 h-px"
        style={{
          background: "linear-gradient(90deg, transparent 5%, rgba(16,185,129,0.3) 50%, transparent 95%)",
          animation: "homepage-edge-scan 3s ease-in-out 1.7s both",
        }}
      />

      <div className="relative">
        <div className="mb-4 flex items-center justify-between">
          <span className="text-[10px] font-mono font-bold uppercase tracking-[0.2em] text-emerald-400/90">
            How we find edge
          </span>
          <span className="flex items-center gap-1.5">
            <span className="h-[5px] w-[5px] rounded-full bg-emerald-400" style={{ animation: "homepage-pulse 2s ease-in-out infinite" }} />
            <span className="text-[9px] font-mono uppercase tracking-[0.16em] text-slate-600">Live example</span>
          </span>
        </div>

        <div className="font-mono text-[14px] md:text-[15px]">
          {EDGE_ROWS.map(([label, value], index) => (
            <div
              key={label}
              className="flex items-center justify-between border-b border-slate-800/40 py-[9px]"
              style={{
                animation: "homepage-edge-row 0.55s cubic-bezier(0.16,1,0.3,1) both",
                animationDelay: `${700 + index * 180}ms`,
              }}
            >
              <span className="text-slate-400">{label}</span>
              <span className="text-[15px] font-semibold tabular-nums text-slate-100 md:text-base">{value}</span>
            </div>
          ))}

          <div
            className="-mx-1.5 mt-3 flex items-center justify-between rounded-xl border px-4 py-3.5"
            style={{
              animation: "homepage-edge-result 0.7s cubic-bezier(0.16,1,0.3,1) both",
              animationDelay: "1450ms",
            }}
          >
            <span className="text-[14px] font-semibold text-emerald-400 md:text-[15px]">Mathematical Edge</span>
            <span className="font-mono text-[30px] font-black tracking-[-0.04em] text-emerald-400 md:text-[32px]">+11.1%</span>
          </div>
        </div>

        <p className="mt-3 font-mono text-[10px] leading-relaxed text-slate-600">
          When their price exceeds fair value, we act.
        </p>
      </div>
    </div>
  );
}

function ProofStatCard({
  label,
  value,
  sub,
  accent = false,
}: {
  label: string;
  value: string;
  sub: string;
  accent?: boolean;
}) {
  return (
    <div
      className={`relative overflow-hidden rounded-2xl border p-5 md:p-6 ${
        accent ? "border-emerald-500/20 bg-[#0c0f14]" : "border-slate-700/40 bg-[#0c0f14]"
      }`}
    >
      {accent ? (
        <div
          className="absolute top-0 left-[10%] right-[10%] h-px"
          style={{ background: "linear-gradient(90deg, transparent, rgba(16,185,129,0.35), transparent)" }}
        />
      ) : null}
      <span
        className="pointer-events-none absolute -right-3 -bottom-4 select-none font-mono text-[80px] font-black leading-none"
        style={{ color: accent ? "rgba(16,185,129,0.025)" : "rgba(255,255,255,0.015)" }}
      >
        {value.replace(/[^0-9.%+]/g, "")}
      </span>
      <div className="relative">
        <div className="text-[10px] font-mono font-bold uppercase tracking-[0.14em] text-slate-500">{label}</div>
        <div className={`mt-3 font-mono text-[2.2rem] font-extrabold leading-none tracking-tight tabular-nums md:text-[2.5rem] ${accent ? "text-emerald-400" : "text-slate-100"}`}>
          {value}
        </div>
        <div className="mt-3 font-mono text-[11px] leading-relaxed text-slate-500">{sub}</div>
      </div>
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
          ? "border-emerald-500/20 bg-[#0c0f14] hover:-translate-y-[2px] hover:border-emerald-500/30 hover:shadow-[0_12px_48px_rgba(16,185,129,0.04)]"
          : "border-slate-700/40 bg-[#0c0f14] opacity-70"
      }`}
    >
      {active ? (
        <div
          className="absolute top-0 left-[8%] right-[8%] h-px"
          style={{ background: "linear-gradient(90deg, transparent, rgba(16,185,129,0.22), transparent)" }}
        />
      ) : null}
      <div className="relative flex h-full flex-col">
        <div className="mb-3 flex items-center gap-2.5">
          <h3 className="text-[15px] font-semibold text-slate-200">{market.name}</h3>
          <span
            className={`rounded-full border px-2.5 py-[2px] text-[8px] font-mono font-bold uppercase tracking-[0.16em] ${
              active
                ? "border-emerald-500/20 bg-emerald-500/8 text-emerald-400/85"
                : "border-slate-700/40 bg-slate-800/50 text-slate-600"
            }`}
          >
            {active ? (market.id === "atg" ? "Model" : "Active") : "Soon"}
          </span>
        </div>
        <p className="text-[13px] leading-[1.65] text-slate-500 transition-colors duration-300 group-hover:text-slate-400">{market.description}</p>
        {active && market.profit ? (
          <div className="mt-4 flex items-baseline gap-4 font-mono text-[12px]">
            {market.bets ? <span className="tabular-nums text-slate-400/80">{market.bets} bets</span> : null}
            <span className="font-semibold tabular-nums text-emerald-400/90">{market.profit}</span>
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
      className="group flex h-full flex-col rounded-xl border border-slate-700/40 bg-[#0c0f14] p-4 transition-all duration-300 hover:-translate-y-[1px] hover:border-emerald-500/20 sm:p-5"
    >
      <h3 className="mb-1 text-[14px] font-semibold text-slate-200 transition-colors group-hover:text-white">{title}</h3>
      <p className="text-[12px] leading-[1.6] text-slate-600 transition-colors group-hover:text-slate-500">{body}</p>
      <span className="mt-auto inline-flex w-full items-center justify-between pt-4 font-mono text-[10px] uppercase tracking-[0.16em] text-emerald-400/45 transition-colors group-hover:text-emerald-400/85">
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
}: HomepageClientProps) {
  const router = useRouter();
  const [recentBets, setRecentBets] = useState<HomepageBet[]>(initialRecentBets);
  const [pendingBets, setPendingBets] = useState<HomepageBet[]>(initialPendingBets);
  const [showAllPending, setShowAllPending] = useState(false);
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
  const displayedPendingBets = showAllPending ? pendingBets : pendingBets.slice(0, 5);
  const trackingPeriod = getTrackingMonths();
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
      id: "builders",
      name: "Bet Builders",
      description: "Same-game combinations where correlation is still being mapped.",
      status: "coming" as const,
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

      <section className="relative overflow-hidden border-b border-slate-800/40 pt-6 pb-16 md:pb-20 lg:pb-24">
        <div
          className="pointer-events-none absolute inset-x-0 -top-24 h-[640px]"
          style={{ background: "radial-gradient(ellipse 1200px 550px at 50% -120px, rgba(16,185,129,0.08), transparent)" }}
        />
        <div className="pointer-events-none absolute -right-36 top-0 h-[420px] w-[420px] rounded-full bg-emerald-500/[0.02] blur-[120px]" />

        <div className="relative z-10 mx-auto max-w-6xl px-4 sm:px-6 lg:px-8">
          <div className="grid items-start gap-12 lg:grid-cols-[1.2fr,0.8fr] lg:gap-16">
            <div className="lg:py-4">
              <HomepageReveal delay={0}>
                <span className="text-xs font-mono font-bold uppercase tracking-[0.18em] text-emerald-400/95">
                  Il Margine
                </span>
              </HomepageReveal>

              <HomepageReveal delay={120}>
                <h1 className="mt-5 text-4xl font-semibold leading-[1.02] tracking-tight text-white sm:text-5xl md:text-6xl">
                  Betting with
                  <br className="hidden md:block" />{" "}
                  <span className="relative inline-block text-emerald-400">
                    mathematical
                    <span
                      className="absolute bottom-0 left-0 right-0 h-[2px] origin-left rounded-full bg-emerald-500/25"
                      style={{ animation: "homepage-underline 0.8s cubic-bezier(0.16,1,0.3,1) both", animationDelay: "850ms" }}
                    />
                  </span>
                  <br className="hidden md:block" />{" "}
                  <span className="relative inline-block text-emerald-400">
                    edge
                    <span
                      className="absolute bottom-0 left-0 right-0 h-[2px] origin-left rounded-full bg-emerald-500/25"
                      style={{ animation: "homepage-underline 0.8s cubic-bezier(0.16,1,0.3,1) both", animationDelay: "1025ms" }}
                    />
                  </span>
                </h1>
              </HomepageReveal>

              <HomepageReveal delay={280}>
                <p className="mt-6 max-w-xl text-lg leading-relaxed text-slate-300">
                  Professional betting methodology from a former odds compiler. We identify value where bookmakers misprice markets.
                </p>
              </HomepageReveal>

              <HomepageReveal delay={420}>
                <div className="mt-8 flex flex-wrap items-center gap-4">
                  <Link
                    href="/player-props"
                    className="inline-flex items-center gap-2 rounded-lg bg-emerald-500 px-6 py-3 text-base font-semibold text-white transition-all hover:bg-emerald-400 hover:shadow-[0_0_40px_rgba(16,185,129,0.2)]"
                  >
                    Player Props Tips {"\u2192"}
                  </Link>
                  <Link
                    href="/tennis-tips"
                    className="inline-flex items-center gap-2 rounded-lg border border-slate-600 px-6 py-3 text-base font-medium text-slate-200 transition-all hover:border-slate-400 hover:bg-slate-800/40"
                  >
                    ATP Tennis Tips {"\u2192"}
                  </Link>
                  <Link
                    href="/the-edge"
                    className="inline-flex items-center gap-2 text-sm font-medium text-slate-400 transition-colors hover:text-emerald-400"
                  >
                    How It Works {"\u2192"}
                  </Link>
                </div>
              </HomepageReveal>

              <HomepageReveal delay={560}>
                <div className="mt-7 flex flex-wrap items-center gap-3 font-mono text-xs text-slate-600">
                  {[
                    "Free picks",
                    "No sign-up",
                    "Transparent results",
                  ].map((item) => (
                    <span key={item} className="inline-flex items-center gap-2">
                      <span className="h-[3px] w-[3px] rounded-full bg-slate-600" />
                      {item}
                    </span>
                  ))}
                </div>
              </HomepageReveal>
            </div>

            <HomepageReveal delay={380} className="lg:mt-8">
              <HomepageEdgeCard />
            </HomepageReveal>
          </div>
        </div>
      </section>

      <section className="border-b border-slate-800/30 py-16 md:py-20">
        <div className="mx-auto max-w-6xl px-4 sm:px-6 lg:px-8">
          <div className="mb-8 flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
            <div>
              <span className="mb-2 block text-xs font-mono font-bold uppercase tracking-[0.18em] text-emerald-400/95">
                Verified performance
              </span>
              <h2 className="text-2xl font-semibold text-slate-100 sm:text-3xl">Track record</h2>
            </div>
            <Link href="/track-record" className="shrink-0 text-sm font-medium text-slate-500 transition-colors hover:text-emerald-400">
              Full details {"\u2192"}
            </Link>
          </div>

          <div className="grid gap-3 md:grid-cols-3">
            <ProofStatCard
              label="Overall ROI"
              value={`${displayStats.overall.roi > 0 ? "+" : ""}${displayStats.overall.roi.toFixed(1)}%`}
              sub="Combined baseline plus live public tracking"
              accent
            />
            <ProofStatCard
              label="Settled bets"
              value={`${displayStats.overall.total_bets.toLocaleString()}+`}
              sub="Player props and ATP tennis combined"
            />
            <ProofStatCard label="Tracking period" value={trackingPeriod} sub="Validation-phase history plus public tracking" accent />
          </div>

          <p className="mt-4 font-mono text-[10px] uppercase tracking-[0.14em] text-slate-600">
            Baseline validation data shown immediately. Live public figures refresh automatically.
          </p>
        </div>
      </section>

      <MonthlyBreakdownSection scope="combined" />

      <section id="markets" className="border-b border-slate-800/30 py-16 md:py-20 scroll-mt-20">
        <div className="mx-auto max-w-6xl px-4 sm:px-6 lg:px-8">
          <span className="mb-2 block text-xs font-mono font-bold uppercase tracking-[0.18em] text-emerald-400/95">
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
          <div className="grid gap-10 lg:grid-cols-[1fr,0.9fr] lg:gap-16">
            <div className="lg:sticky lg:top-28 lg:self-start">
              <div className="mb-5 flex items-center gap-3">
                <div className="h-10 w-[3px] rounded-full bg-emerald-500" />
                <span className="text-xs font-mono font-bold uppercase tracking-[0.18em] text-emerald-400/95">
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
                className="group mt-6 inline-flex items-center gap-1.5 text-sm font-medium text-emerald-400/80 transition-colors hover:text-emerald-400"
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
                    <span className="font-mono text-[10px] font-bold text-emerald-500/35">{item.number}</span>
                    <h3 className="mt-1 text-[14px] font-semibold text-slate-200">{item.title}</h3>
                    <p className="mt-1.5 text-[12px] leading-[1.6] text-slate-600 transition-colors duration-300 group-hover:text-slate-500">
                      {item.body}
                    </p>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      </section>

      {pendingBets.length > 0 ? (
        <section className="border-b border-slate-800/30 py-16 md:py-20">
          <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
            <div className="mb-8 sm:mb-10">
              <span className="mb-2 block text-xs font-mono font-bold uppercase tracking-[0.18em] text-emerald-400/95">Live now</span>
              <h2 className="text-2xl font-semibold text-slate-100 sm:text-3xl">Active picks</h2>
            </div>
            <p className="mb-6 text-xs text-slate-500">Stake in units (1u = your standard stake). We typically recommend 0.5u to 2u per pick.</p>
            <div className="overflow-hidden rounded-2xl border border-slate-700/40 bg-[#0c0f14]">
              <div className="hidden overflow-x-auto md:block">
                <PublicBetsTable bets={displayedPendingBets} mode="pending" />
              </div>
              <div className="divide-y divide-slate-800/40 md:hidden">
                {displayedPendingBets.map((bet) => (
                  <div
                    key={bet.id}
                    role="link"
                    tabIndex={0}
                    className="block cursor-pointer p-5 hover:bg-slate-800/20 active:bg-slate-800/30"
                    onClick={() => router.push(`/tips/${slugifyTip(bet.event, bet.id)}`)}
                    onKeyDown={(event) => {
                      if (event.key === "Enter" || event.key === " ") {
                        event.preventDefault();
                        router.push(`/tips/${slugifyTip(bet.event, bet.id)}`);
                      }
                    }}
                  >
                    <div className="mb-1 flex items-center justify-between">
                      <span className="text-xs whitespace-nowrap text-slate-500">{formatMatchDate(bet.match_date)}</span>
                      <span className="rounded bg-amber-500/20 px-2 py-0.5 font-mono text-xs text-amber-400">PENDING</span>
                    </div>
                    <div className="mb-1 font-medium text-slate-200">{bet.event}</div>
                    <div className="mb-2 text-sm text-slate-300">
                      {bet.player ? <span>{bet.player} - </span> : null}
                      {bet.selection}
                    </div>
                    <BetMobileMeta odds={bet.odds} bookmaker={bet.bookmaker} stake={bet.stake} />
                  </div>
                ))}
              </div>
              {pendingBets.length > 5 ? (
                <div className="border-t border-slate-800/40 p-4 text-center">
                  <button
                    onClick={() => setShowAllPending(!showAllPending)}
                    className="text-sm font-medium text-emerald-400 transition-colors hover:text-emerald-300"
                  >
                    {showAllPending ? `Show Less (${pendingBets.length - 5} hidden)` : `Show All Active Picks (${pendingBets.length - 5} more)`}
                  </button>
                </div>
              ) : null}
            </div>
            <div className="mt-6 flex flex-wrap justify-center gap-3">
              <Link
                href="/tennis-tips#picks"
                className="inline-flex items-center gap-3 rounded-full border border-slate-700/70 bg-slate-900/45 px-4 py-2.5 text-sm text-slate-200 transition-all hover:border-emerald-500/35 hover:bg-slate-900/70 hover:text-white"
              >
                <span className="text-[11px] font-mono uppercase tracking-[0.18em] text-emerald-400">Tennis</span>
                <span className="font-medium">Open latest tips</span>
              </Link>
              <Link
                href="/player-props#picks"
                className="inline-flex items-center gap-3 rounded-full border border-slate-700/70 bg-slate-900/45 px-4 py-2.5 text-sm text-slate-200 transition-all hover:border-emerald-500/35 hover:bg-slate-900/70 hover:text-white"
              >
                <span className="text-[11px] font-mono uppercase tracking-[0.18em] text-emerald-400">Props</span>
                <span className="font-medium">Open latest props</span>
              </Link>
            </div>
          </div>
        </section>
      ) : null}

      {recentBets.length > 0 ? (
        <section className="border-b border-slate-800/30 py-16 md:py-20">
          <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
            <div className="mb-8 flex flex-col gap-4 sm:mb-10 sm:flex-row sm:items-center sm:justify-between">
              <div>
                <span className="mb-2 block text-xs font-mono font-bold uppercase tracking-[0.18em] text-emerald-400/95">Latest results</span>
                <h2 className="text-2xl font-semibold text-slate-100 sm:text-3xl">Recent selections</h2>
              </div>
              {last7DaysProfit != null && !last7Error && last7DaysCount > 0 ? (
                <span
                  className={`font-mono text-xs sm:text-sm ${
                    last7DaysProfit > 0 ? "text-emerald-400" : last7DaysProfit < 0 ? "text-red-400" : "text-slate-300"
                  }`}
                >
                  Last 7 days: {last7DaysProfit > 0 ? "+" : ""}{last7DaysProfit.toFixed(2)}u
                  <span className="ml-1 font-normal text-slate-500">
                    ({last7DaysCount} bet{last7DaysCount !== 1 ? "s" : ""})
                  </span>
                </span>
              ) : null}
            </div>
            <p className="mb-6 text-xs text-slate-500">Stake in units (1u = your standard stake). We typically recommend 0.5u to 2u per pick.</p>
            <div className="overflow-hidden rounded-2xl border border-slate-700/40 bg-[#0c0f14]">
              <div className="hidden overflow-x-auto md:block">
                <PublicBetsTable bets={recentBets.slice(0, 5)} mode="settled" />
              </div>
              <div className="divide-y divide-slate-800/40 md:hidden">
                {recentBets.slice(0, 5).map((bet) => (
                  <div
                    key={bet.id}
                    role="link"
                    tabIndex={0}
                    className="block cursor-pointer p-5 hover:bg-slate-800/20 active:bg-slate-800/30"
                    onClick={() => router.push(`/tips/${slugifyTip(bet.event, bet.id)}`)}
                    onKeyDown={(event) => {
                      if (event.key === "Enter" || event.key === " ") {
                        event.preventDefault();
                        router.push(`/tips/${slugifyTip(bet.event, bet.id)}`);
                      }
                    }}
                  >
                    <div className="mb-2 flex items-start justify-between">
                      <div className="flex-1">
                        <div className="mb-1 flex items-center gap-2">
                          <span className="text-xs whitespace-nowrap text-slate-500">{formatMatchDate(bet.match_date)}</span>
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
                  </div>
                ))}
              </div>
            </div>

            <div className="mt-6 flex flex-wrap justify-center gap-x-5 gap-y-2 text-sm">
              <Link href="/tennis-tips#picks" className="text-slate-400 transition-colors hover:text-emerald-400">
                Review tennis results -&gt;
              </Link>
              <Link href="/player-props#picks" className="text-slate-400 transition-colors hover:text-emerald-400">
                Review player props results -&gt;
              </Link>
            </div>
          </div>
        </section>
      ) : null}

      <section className="border-b border-slate-800/30 py-16 md:py-20">
        <div className="mx-auto max-w-6xl px-4 sm:px-6 lg:px-8">
          <span className="mb-2 block text-xs font-mono font-bold uppercase tracking-[0.18em] text-emerald-400/95">
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

      <section className="border-b border-slate-800/30 py-16 md:py-20">
        <div className="mx-auto max-w-6xl px-4 sm:px-6 lg:px-8">
          <div className="mb-8 flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
            <div>
              <span className="mb-2 block text-xs font-mono font-bold uppercase tracking-[0.18em] text-emerald-400/95">
                Common questions
              </span>
              <h2 className="text-2xl font-semibold text-slate-100 sm:text-3xl">Frequently asked questions</h2>
            </div>
            <Link href="/faq" className="shrink-0 text-sm font-medium text-emerald-400 transition-colors hover:text-emerald-300">
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
                  summary: "Directly on the site. You get the market, price, bookmaker, and stake there without Telegram or a paywall.",
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
                className="group flex h-full flex-col rounded-xl border border-slate-700/40 bg-[#0c0f14] p-4 text-left transition-all duration-300 hover:-translate-y-[1px] hover:border-emerald-500/25 sm:p-5"
              >
                <h3 className="mb-2 text-[15px] font-medium text-slate-200 transition-colors group-hover:text-white">{item.title}</h3>
                <p className="text-sm leading-relaxed text-slate-500 transition-colors group-hover:text-slate-400">{item.summary}</p>
                <span className="mt-auto pt-4 font-mono text-[10px] uppercase tracking-[0.16em] text-emerald-400/45 transition-colors group-hover:text-emerald-400/85">
                  Read answer {"\u2192"}
                </span>
              </Link>
            ))}
          </div>
        </div>
      </section>

      <section className="py-16 md:py-20">
        <div className="mx-auto max-w-6xl px-4 sm:px-6 lg:px-8">
          <div className="relative overflow-hidden rounded-2xl border border-emerald-500/15 px-6 py-10 text-center md:px-10 md:py-14">
            <div className="absolute inset-0 bg-[#0c0f14]" />
            <div
              className="pointer-events-none absolute inset-0"
              style={{ background: "radial-gradient(circle at 50% 140%, rgba(16,185,129,0.12), transparent 55%)" }}
            />
            <div
              className="absolute top-0 left-[12%] right-[12%] h-px"
              style={{ background: "linear-gradient(90deg, transparent, rgba(16,185,129,0.35), transparent)" }}
            />
            <div className="relative">
              <h2 className="text-3xl font-semibold text-slate-100">See the edge in practice</h2>
              <p className="mx-auto mt-4 max-w-lg text-base leading-relaxed text-slate-300">
                Free selections posted on site. Match, market, selection, odds, bookmaker, and stake. Everything needed to place the bet with clarity.
              </p>
              <div className="mt-8 flex flex-wrap items-center justify-center gap-4">
                <Link
                  href="/player-props"
                  className="inline-flex items-center gap-2 rounded-lg bg-emerald-500 px-8 py-3.5 text-[15px] font-semibold text-white transition-all hover:bg-emerald-400 hover:shadow-[0_0_50px_rgba(16,185,129,0.22)]"
                >
                  Player Props Tips {"\u2192"}
                </Link>
                <Link
                  href="/tennis-tips"
                  className="inline-flex items-center gap-2 rounded-lg border border-slate-600 px-8 py-3.5 text-[15px] font-medium text-slate-200 transition-all hover:border-slate-400 hover:bg-slate-800/40"
                >
                  ATP Tennis Tips {"\u2192"}
                </Link>
              </div>
            </div>
          </div>
        </div>
      </section>

      <div className="mx-auto max-w-6xl px-4 pb-14 sm:px-6 lg:px-8">
        <div className="rounded-xl border border-amber-500/10 bg-amber-500/[0.03] px-5 py-4 text-[12px] leading-relaxed text-slate-500">
          <strong className="text-amber-400/80">Responsible gambling:</strong> Past performance does not guarantee future results. Only bet what you can afford to lose.{" "}
          <a href="https://www.begambleaware.org" target="_blank" rel="noopener noreferrer" className="text-slate-400 underline underline-offset-2">BeGambleAware</a>
          <span className="px-1.5 text-slate-500">|</span>
          <a href="https://www.gamcare.org.uk" target="_blank" rel="noopener noreferrer" className="text-slate-400 underline underline-offset-2">GamCare</a>
        </div>
      </div>

      <Footer />
    </div>
  );
}
