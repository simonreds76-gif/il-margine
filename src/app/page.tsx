"use client";

import { useCallback, useEffect, useState, type ReactNode } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { questionSlug } from "@/lib/parse-faq";
import { supabase, type Bet, type Bookmaker, type MarketStats } from "@/lib/supabase";
import { BASELINE_STATS, calculateROI, calculateWinRate, getBaselineDisplayStats } from "@/lib/baseline";
import BookmakerLogo from "@/components/BookmakerLogo";
import MarketBadge from "@/components/MarketBadge";
import Footer from "@/components/Footer";
import MonthlyBreakdownSection from "@/components/MonthlyBreakdownSection";
import { formatStake, formatMatchDate, formatOdds } from "@/lib/format";
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
    <div className="relative overflow-hidden rounded-2xl border border-slate-700/35 bg-[#0a0d12] p-5 shadow-2xl shadow-black/35 md:p-6">
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
          <span className="text-[10px] font-mono font-bold uppercase tracking-[0.18em] text-emerald-400/85">
            How we find edge
          </span>
          <span className="flex items-center gap-1.5">
            <span className="h-[5px] w-[5px] rounded-full bg-emerald-400" style={{ animation: "homepage-pulse 2s ease-in-out infinite" }} />
            <span className="text-[8px] font-mono uppercase tracking-[0.16em] text-slate-600">Live example</span>
          </span>
        </div>

        <div className="font-mono text-[13px]">
          {EDGE_ROWS.map(([label, value], index) => (
            <div
              key={label}
              className="flex items-center justify-between border-b border-slate-800/40 py-[9px]"
              style={{
                animation: "homepage-edge-row 0.55s cubic-bezier(0.16,1,0.3,1) both",
                animationDelay: `${700 + index * 180}ms`,
              }}
            >
              <span className="text-slate-500">{label}</span>
              <span className="font-medium tabular-nums text-slate-200">{value}</span>
            </div>
          ))}

          <div
            className="-mx-1.5 mt-3 flex items-center justify-between rounded-xl border px-4 py-3.5"
            style={{
              animation: "homepage-edge-result 0.7s cubic-bezier(0.16,1,0.3,1) both",
              animationDelay: "1450ms",
            }}
          >
            <span className="text-[13px] font-semibold text-emerald-400">Edge</span>
            <span className="font-mono text-[28px] font-black tracking-[-0.04em] text-emerald-400">+11.1%</span>
          </div>
        </div>

        <p className="mt-3 font-mono text-[10px] uppercase tracking-[0.14em] text-slate-600">
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
        <div className="text-[10px] font-mono font-bold uppercase tracking-[0.16em] text-slate-500">{label}</div>
        <div className={`mt-3 font-mono text-[2.1rem] font-extrabold leading-none tracking-tight tabular-nums md:text-[2.4rem] ${accent ? "text-emerald-400" : "text-slate-100"}`}>
          {value}
        </div>
        <div className="mt-2.5 font-mono text-[10px] leading-relaxed text-slate-500/80">{sub}</div>
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
      className="group rounded-xl border border-slate-700/40 bg-[#0c0f14] p-4 transition-all duration-300 hover:-translate-y-[1px] hover:border-emerald-500/20 sm:p-5"
    >
      <h3 className="mb-1 text-[14px] font-semibold text-slate-200 transition-colors group-hover:text-white">{title}</h3>
      <p className="text-[12px] leading-[1.6] text-slate-600 transition-colors group-hover:text-slate-500">{body}</p>
      <span className="mt-3 inline-flex font-mono text-[10px] uppercase tracking-[0.16em] text-emerald-400/45 transition-colors group-hover:text-emerald-400/85">
        View -&gt;
      </span>
    </Link>
  );
}

export default function Home() {
  const router = useRouter();
  const showGoalscorerMarket =
    process.env.NODE_ENV !== "production" ||
    process.env.NEXT_PUBLIC_ENABLE_GOALSCORER_PAGE === "1";
  const [recentBets, setRecentBets] = useState<HomepageBet[]>([]);
  const [pendingBets, setPendingBets] = useState<HomepageBet[]>([]);
  const [showAllPending, setShowAllPending] = useState(false);
  const [last7DaysProfit, setLast7DaysProfit] = useState<number | null>(null);
  const [last7DaysCount, setLast7DaysCount] = useState<number>(0);
  const [last7Error, setLast7Error] = useState<boolean>(false);
  const [combinedStats, setCombinedStats] = useState<{
    props: CombinedMarketStats;
    tennis: CombinedMarketStats;
    overall: CombinedMarketStats;
  } | null>(null);

  const calculateCombinedStats = (liveStats: MarketStats[]) => {
    const propsLive = liveStats.find((stat) => stat.market === "props");
    const tennisLive = liveStats.find((stat) => stat.market === "tennis");

    const propsLiveBets = propsLive?.total_bets || 0;
    const propsLiveWins = propsLive?.wins || 0;
    const propsLiveLosses = propsLive?.losses || 0;
    const propsLiveProfit = Number(propsLive?.total_profit) || 0;
    const propsLiveStake = Number(propsLive?.total_stake) || propsLiveBets;

    const propsCombined: CombinedMarketStats = {
      total_bets: BASELINE_STATS.props.total_bets + propsLiveBets,
      roi: 0,
      win_rate: 0,
      avg_odds: 0,
      total_profit: 0,
    };

    const propsWins = BASELINE_STATS.props.wins + propsLiveWins;
    const propsLosses = BASELINE_STATS.props.losses + propsLiveLosses;
    const propsProfit = BASELINE_STATS.props.total_profit + propsLiveProfit;
    const propsStake = BASELINE_STATS.props.total_stake + propsLiveStake;

    propsCombined.win_rate = calculateWinRate(propsWins, propsLosses);
    propsCombined.roi = calculateROI(propsProfit, propsStake || 1);
    propsCombined.total_profit = propsProfit;

    if (propsLive?.avg_odds && propsLiveBets > 0) {
      propsCombined.avg_odds = Number(propsLive.avg_odds);
    }

    const tennisLiveBets = tennisLive?.total_bets || 0;
    const tennisLiveWins = tennisLive?.wins || 0;
    const tennisLiveLosses = tennisLive?.losses || 0;
    const tennisLiveProfit = Number(tennisLive?.total_profit) || 0;
    const tennisLiveStake = Number(tennisLive?.total_stake) || tennisLiveBets;

    const tennisCombined: CombinedMarketStats = {
      total_bets: BASELINE_STATS.tennis.total_bets + tennisLiveBets,
      roi: 0,
      win_rate: 0,
      avg_odds: 0,
      total_profit: 0,
    };

    const tennisWins = BASELINE_STATS.tennis.wins + tennisLiveWins;
    const tennisLosses = BASELINE_STATS.tennis.losses + tennisLiveLosses;
    const tennisProfit = BASELINE_STATS.tennis.total_profit + tennisLiveProfit;
    const tennisStake = BASELINE_STATS.tennis.total_stake + tennisLiveStake;

    tennisCombined.win_rate = calculateWinRate(tennisWins, tennisLosses);
    tennisCombined.roi = calculateROI(tennisProfit, tennisStake || 1);
    tennisCombined.total_profit = tennisProfit;

    if (tennisLive?.avg_odds && tennisLiveBets > 0) {
      tennisCombined.avg_odds = Number(tennisLive.avg_odds);
    }

    const overallLiveBets = propsLiveBets + tennisLiveBets;
    const overallLiveWins = propsLiveWins + tennisLiveWins;
    const overallLiveLosses = propsLiveLosses + tennisLiveLosses;
    const overallLiveProfit = propsLiveProfit + tennisLiveProfit;
    const overallLiveStake = propsLiveStake + tennisLiveStake;

    const overallCombined: CombinedMarketStats = {
      total_bets: BASELINE_STATS.overall.total_bets + overallLiveBets,
      roi: 0,
      win_rate: 0,
      avg_odds: 0,
      total_profit: 0,
    };

    const overallWins = BASELINE_STATS.overall.wins + overallLiveWins;
    const overallLosses = BASELINE_STATS.overall.losses + overallLiveLosses;
    const overallProfit = BASELINE_STATS.overall.total_profit + overallLiveProfit;
    const overallStake = BASELINE_STATS.overall.total_stake + overallLiveStake;

    overallCombined.win_rate = calculateWinRate(overallWins, overallLosses);
    overallCombined.roi = calculateROI(overallProfit, overallStake || 1);
    overallCombined.total_profit = overallProfit;

    if (propsCombined.avg_odds > 0 || tennisCombined.avg_odds > 0) {
      const totalOddsWeight =
        propsCombined.avg_odds * propsCombined.total_bets +
        tennisCombined.avg_odds * tennisCombined.total_bets;
      overallCombined.avg_odds = overallCombined.total_bets > 0 ? totalOddsWeight / overallCombined.total_bets : 0;
    }

    setCombinedStats({
      props: propsCombined,
      tennis: tennisCombined,
      overall: overallCombined,
    });
  };

  const fetchData = useCallback(async () => {
    const [statsResponse, recentResponse, pendingResponse] = await Promise.all([
      supabase.from("market_stats").select("*"),
      supabase
        .from("bets")
        .select("*, bookmaker:bookmakers(*)")
        .in("status", ["won", "lost", "void"])
        .order("settled_at", { ascending: false })
        .limit(5),
      supabase
        .from("bets")
        .select("*, bookmaker:bookmakers(*)")
        .eq("status", "pending")
        .order("posted_at", { ascending: false })
        .limit(20),
    ]);

    const { data: stats, error: statsError } = statsResponse;
    const { data: recent, error: recentError } = recentResponse;
    const { data: pending, error: pendingError } = pendingResponse;

    if (statsError) console.error("Error fetching market stats:", statsError);
    if (recentError) console.error("Error fetching recent bets:", recentError);
    if (pendingError) console.error("Error fetching pending bets:", pendingError);

    if (recent) setRecentBets(recent as HomepageBet[]);
    if (pending) setPendingBets(pending as HomepageBet[]);

    try {
      setLast7Error(false);
      const res = await fetch("/api/last7-profit", { cache: "no-store" });
      const json = await res.json();
      if (res.ok && typeof json.total === "number") {
        setLast7DaysProfit(json.total);
        setLast7DaysCount(typeof json.count === "number" ? json.count : 0);
      } else {
        setLast7Error(true);
      }
    } catch (error) {
      console.error("Error fetching last 7 days:", error);
      setLast7Error(true);
    }

    calculateCombinedStats((stats as MarketStats[] | null) ?? []);
  }, []);

  useEffect(() => {
    const initialFetchId = window.setTimeout(() => {
      void fetchData();
    }, 0);

    const channel = supabase
      .channel("bets-changes")
      .on(
        "postgres_changes",
        {
          event: "*",
          schema: "public",
          table: "bets",
        },
        (payload) => {
          console.log("Bet changed:", payload.eventType);
          void fetchData();
        }
      )
      .subscribe();

    return () => {
      window.clearTimeout(initialFetchId);
      void supabase.removeChannel(channel);
    };
  }, [fetchData]);

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
      name: "Goalscorer Model",
      description: "Anytime goalscorer fair odds and automated value surfacing.",
      status: "active" as const,
      profit: "In development",
    },
  ].filter((market) => showGoalscorerMarket || market.id !== "atg");

  return (
    <div className="min-h-screen bg-[#0f1117] text-slate-100">
      <style jsx global>{HOMEPAGE_KEYFRAMES}</style>

      <section className="relative overflow-hidden border-b border-slate-800/30 pt-6 pb-16 md:pb-20 lg:pb-24">
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
                <h1 className="mt-5 text-4xl font-bold leading-[1.02] tracking-tight text-white sm:text-5xl md:text-6xl">
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
                    View Tips -&gt;
                  </Link>
                  <Link
                    href="/the-edge"
                    className="inline-flex items-center gap-2 rounded-lg border border-slate-600 px-6 py-3 text-base font-medium text-slate-200 transition-all hover:border-slate-400 hover:bg-slate-800/40"
                  >
                    How It Works
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

      <section className="border-b border-slate-800/30 py-14 md:py-16">
        <div className="mx-auto max-w-6xl px-4 sm:px-6 lg:px-8">
          <div className="mb-8 flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
            <div>
              <span className="mb-2 block text-xs font-mono font-bold uppercase tracking-[0.18em] text-emerald-400/95">
                Verified performance
              </span>
              <h2 className="text-2xl font-semibold text-slate-100 sm:text-3xl">Track record</h2>
            </div>
            <Link href="/track-record" className="shrink-0 text-sm font-medium text-slate-500 transition-colors hover:text-emerald-400">
              Full details -&gt;
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
                      ? "/anytime-goalscorer"
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
          <div className="mx-auto max-w-6xl px-4 sm:px-6 lg:px-8">
            <div className="mb-8 sm:mb-10">
              <span className="mb-2 block text-xs font-mono font-bold uppercase tracking-[0.18em] text-emerald-400/95">Live now</span>
              <h2 className="text-2xl font-semibold text-slate-100 sm:text-3xl">Active picks</h2>
            </div>
            <p className="mb-6 text-xs text-slate-500">Stake in units (1u = your standard stake). We typically recommend 0.5u to 2u per pick.</p>
            <div className="overflow-hidden rounded-2xl border border-slate-700/40 bg-[#0c0f14]">
              <div className="hidden md:block">
                <table className="w-full table-fixed border-collapse">
                  <thead>
                    <tr className="border-b border-slate-800/40 bg-slate-950/40 text-[11px] uppercase text-slate-500">
                      <th className="w-11 border-r border-slate-800/40 px-2.5 py-3 text-left"></th>
                      <th className="w-16 border-r border-slate-800/40 px-2.5 py-3 text-left">Date</th>
                      <th className="w-[24%] border-r border-slate-800/40 px-3 py-3 text-left">Match</th>
                      <th className="w-[14%] border-r border-slate-800/40 px-3 py-3 text-left">Player</th>
                      <th className="w-[17%] border-r border-slate-800/40 px-3 py-3 text-left">Selection</th>
                      <th className="w-16 border-r border-slate-800/40 px-2.5 py-3 text-center">Odds</th>
                      <th className="w-20 border-r border-slate-800/40 px-2.5 py-3 text-center">Bookmaker</th>
                      <th className="w-16 px-2.5 py-3 text-center">Stake</th>
                    </tr>
                  </thead>
                  <tbody>
                    {displayedPendingBets.map((bet) => (
                      <tr key={bet.id} className="border-b border-slate-800/40 last:border-b-0 hover:bg-slate-800/20">
                        <td className="border-r border-slate-800/40 px-2.5 py-3.5 text-center align-middle">
                          <MarketBadge market={bet.market} category={bet.category} hideOnMobile />
                        </td>
                        <td className="border-r border-slate-800/40 px-2.5 py-3.5 align-middle text-sm whitespace-nowrap text-slate-400">{formatMatchDate(bet.match_date)}</td>
                        <td className="border-r border-slate-800/40 px-3 py-3.5 align-middle font-medium text-slate-200">
                          <Link href={`/tips/${slugifyTip(bet.event, bet.id)}`} className="block truncate transition-colors hover:text-emerald-400" title={bet.event}>
                            {bet.event}
                          </Link>
                        </td>
                        <td className="border-r border-slate-800/40 px-3 py-3.5 align-middle text-slate-300">
                          <span className="block truncate">{bet.player || "-"}</span>
                        </td>
                        <td className="border-r border-slate-800/40 px-3 py-3.5 align-middle text-slate-300">
                          <span className="block whitespace-normal break-words leading-snug" title={bet.selection}>{bet.selection}</span>
                        </td>
                        <td className="border-r border-slate-800/40 px-2.5 py-3.5 align-middle text-center">
                          <span className="font-mono text-slate-200">{formatOdds(bet.odds)}</span>
                        </td>
                        <td className="border-r border-slate-800/40 px-2.5 py-3.5 align-middle text-center">
                          <div className="flex justify-center">
                            <BookmakerLogo bookmaker={bet.bookmaker} size="sm" />
                          </div>
                        </td>
                        <td className="px-2.5 py-3.5 text-center align-middle font-mono text-slate-200">{formatStake(bet.stake)}u</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
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
                    <div className="flex items-center justify-between text-sm">
                      <div className="flex items-center gap-4">
                        <span className="font-mono font-semibold text-slate-200">{formatOdds(bet.odds)}</span>
                        <BookmakerLogo bookmaker={bet.bookmaker} size="sm" stopPropagationOnClick />
                        <span className="min-w-[2.5rem] text-right font-mono font-bold text-slate-100">{formatStake(bet.stake)}u</span>
                      </div>
                    </div>
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
          <div className="mx-auto max-w-6xl px-4 sm:px-6 lg:px-8">
            <div className="mb-8 flex flex-col gap-4 sm:mb-10 sm:flex-row sm:items-center sm:justify-between">
              <div>
                <span className="mb-2 block text-xs font-mono font-bold uppercase tracking-[0.18em] text-emerald-400/95">Latest results</span>
                <h2 className="text-2xl font-semibold text-slate-100 sm:text-3xl">Recent selections</h2>
              </div>
              {last7DaysProfit != null && !last7Error && last7DaysProfit > 0 ? (
                <span className="font-mono text-xs text-emerald-400 sm:text-sm">
                  Last 7 days: +{last7DaysProfit.toFixed(2)}u
                  <span className="ml-1 font-normal text-slate-500">
                    ({last7DaysCount} bet{last7DaysCount !== 1 ? "s" : ""})
                  </span>
                </span>
              ) : null}
            </div>
            <p className="mb-6 text-xs text-slate-500">Stake in units (1u = your standard stake). We typically recommend 0.5u to 2u per pick.</p>
            <div className="overflow-hidden rounded-2xl border border-slate-700/40 bg-[#0c0f14]">
              <div className="hidden md:block">
                <table className="w-full table-fixed border-collapse text-sm">
                  <thead>
                    <tr className="border-b border-slate-800/40 bg-slate-950/40 text-[11px] uppercase text-slate-500">
                      <th className="w-11 border-r border-slate-800/40 px-2.5 py-3 text-left"></th>
                      <th className="w-16 border-r border-slate-800/40 px-2.5 py-3 text-left">Date</th>
                      <th className="w-[24%] border-r border-slate-800/40 px-3 py-3 text-left">Match</th>
                      <th className="w-[14%] border-r border-slate-800/40 px-3 py-3 text-left">Player</th>
                      <th className="w-[17%] border-r border-slate-800/40 px-3 py-3 text-left">Selection</th>
                      <th className="w-16 border-r border-slate-800/40 px-2.5 py-3 text-center">Odds</th>
                      <th className="w-20 border-r border-slate-800/40 px-2.5 py-3 text-center">Bookmaker</th>
                      <th className="w-16 border-r border-slate-800/40 px-2.5 py-3 text-center">Stake</th>
                      <th className="w-16 border-r border-slate-800/40 px-2.5 py-3 text-center">Result</th>
                      <th className="w-16 px-2.5 py-3 text-right">P/L</th>
                    </tr>
                  </thead>
                  <tbody>
                    {recentBets.slice(0, 5).map((bet) => (
                      <tr key={bet.id} className="border-b border-slate-800/40 last:border-b-0 hover:bg-slate-800/20">
                        <td className="border-r border-slate-800/40 px-2.5 py-3.5 text-center align-middle">
                          <MarketBadge market={bet.market} category={bet.category} hideOnMobile />
                        </td>
                        <td className="border-r border-slate-800/40 px-2.5 py-3.5 align-middle text-sm whitespace-nowrap text-slate-400">{formatMatchDate(bet.match_date)}</td>
                        <td className="border-r border-slate-800/40 px-3 py-3.5 align-middle font-medium text-slate-200">
                          <Link href={`/tips/${slugifyTip(bet.event, bet.id)}`} className="block truncate transition-colors hover:text-emerald-400" title={bet.event}>
                            {bet.event}
                          </Link>
                        </td>
                        <td className="border-r border-slate-800/40 px-3 py-3.5 align-middle text-slate-300">
                          <span className="block truncate">{bet.player || "-"}</span>
                        </td>
                        <td className="border-r border-slate-800/40 px-3 py-3.5 align-middle text-slate-300">
                          <span className="block whitespace-normal break-words leading-snug" title={bet.selection}>{bet.selection}</span>
                        </td>
                        <td className="border-r border-slate-800/40 px-2.5 py-3.5 align-middle text-center">
                          <span className="font-mono text-slate-200">{formatOdds(bet.odds)}</span>
                        </td>
                        <td className="border-r border-slate-800/40 px-2.5 py-3.5 align-middle text-center">
                          <div className="flex justify-center">
                            <BookmakerLogo bookmaker={bet.bookmaker} size="sm" />
                          </div>
                        </td>
                        <td className="border-r border-slate-800/40 px-2.5 py-3.5 text-center align-middle font-mono text-slate-200">{formatStake(bet.stake)}u</td>
                        <td className="border-r border-slate-800/40 px-2.5 py-3.5 align-middle text-center">
                          <span
                            className={`inline-flex min-w-[3.5rem] justify-center rounded px-1.5 py-1 font-mono text-[10px] ${
                              bet.status === "won"
                                ? "bg-emerald-500/10 text-emerald-400"
                                : bet.status === "void"
                                  ? "bg-slate-500/10 text-slate-400"
                                  : "bg-red-500/10 text-red-400"
                            }`}
                          >
                            {bet.status.toUpperCase()}
                          </span>
                        </td>
                        <td
                          className={`px-2.5 py-3.5 text-right align-middle font-mono text-sm font-medium ${
                            bet.status === "void"
                              ? "text-slate-400"
                              : bet.profit_loss && bet.profit_loss > 0
                                ? "text-emerald-400"
                                : "text-red-400"
                          }`}
                        >
                          {bet.status === "void"
                            ? "0.00"
                            : `${bet.profit_loss && bet.profit_loss > 0 ? "+" : ""}${bet.profit_loss?.toFixed(2) || "0.00"}`}u
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
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
                      <span
                        className={`ml-2 rounded px-2 py-1 font-mono text-xs ${
                          bet.status === "won"
                            ? "bg-emerald-500/10 text-emerald-400"
                            : bet.status === "void"
                              ? "bg-slate-500/10 text-slate-400"
                              : "bg-red-500/10 text-red-400"
                        }`}
                      >
                        {bet.status.toUpperCase()}
                      </span>
                    </div>
                    <div className="flex items-center justify-between text-sm">
                      <div className="flex items-center gap-4">
                        <span className="font-mono text-slate-200">{formatOdds(bet.odds)}</span>
                        <BookmakerLogo bookmaker={bet.bookmaker} size="sm" stopPropagationOnClick />
                        <span className="min-w-[2.5rem] text-right font-mono font-bold text-slate-100">{formatStake(bet.stake)}u</span>
                      </div>
                      <span
                        className={`shrink-0 font-mono font-medium ${
                          bet.status === "void"
                            ? "text-slate-400"
                            : bet.profit_loss && bet.profit_loss > 0
                              ? "text-emerald-400"
                              : "text-red-400"
                        }`}
                      >
                        {bet.status === "void"
                          ? "0.00"
                          : `${bet.profit_loss && bet.profit_loss > 0 ? "+" : ""}${bet.profit_loss?.toFixed(2)}`}u
                      </span>
                    </div>
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
                  q: "What is Il Margine?",
                  title: "What is Il Margine?",
                  summary: "A professional betting analysis service from a former odds compiler. We find edge in player props and ATP tennis.",
                },
                {
                  q: "How do I start following Il Margine's betting tips?",
                  title: "How do I follow the tips?",
                  summary: "All tips are posted directly on the website. Tennis tips, player props, and all selections are free - no payment, no sign-up required.",
                },
                {
                  q: "What is ROI and why does it matter more than win rate?",
                  title: "What is ROI and why does it matter?",
                  summary: "Return on investment. It matters more than win rate. You can win often and still lose money.",
                },
                {
                  q: "How much does Il Margine cost?",
                  title: "How much does it cost?",
                  summary: "Free. We're growing our follower base; all tips are free with no trial or card required.",
                },
                {
                  q: "What are player props in football betting?",
                  title: "What are player props?",
                  summary: "Bets on individual player stats (e.g. shots on target, fouls) rather than the match result.",
                },
              ] as const
            ).map((item) => (
              <Link
                key={item.q}
                href={`/faq#${questionSlug(item.q)}`}
                className="block rounded-xl border border-slate-700/40 bg-[#0c0f14] p-4 text-left transition-colors hover:border-emerald-500/25 sm:p-5"
              >
                <h3 className="mb-1 font-medium text-slate-200">{item.title}</h3>
                <p className="text-sm text-slate-500">{item.summary}</p>
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
              <Link
                href="/player-props"
                className="mt-8 inline-flex items-center gap-2 rounded-lg bg-emerald-500 px-8 py-3.5 text-[15px] font-semibold text-white transition-all hover:bg-emerald-400 hover:shadow-[0_0_50px_rgba(16,185,129,0.22)]"
              >
                View Tips -&gt;
              </Link>
            </div>
          </div>
        </div>
      </section>

      <div className="mx-auto max-w-6xl px-4 pb-14 sm:px-6 lg:px-8">
        <div className="rounded-xl border border-amber-500/10 bg-amber-500/[0.03] px-5 py-4 text-[12px] leading-relaxed text-slate-500">
          <strong className="text-amber-400/80">Responsible gambling:</strong> Past performance does not guarantee future results. Only bet what you can afford to lose.{" "}
          <a href="https://www.begambleaware.org" className="text-slate-400 underline underline-offset-2">BeGambleAware</a> ·{" "}
          <a href="https://www.gamcare.org.uk" className="text-slate-400 underline underline-offset-2">GamCare</a>
        </div>
      </div>

      <Footer />
    </div>
  );
}

