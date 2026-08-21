"use client";

import { useCallback, useEffect, useState, type ReactNode } from "react";
import Link from "next/link";
import { BASELINE_STATS, calculateROI, calculateWinRate, getBaselineDisplayStats } from "@/lib/baseline";
import { type MarketStats } from "@/lib/supabase";
import Footer from "@/components/Footer";
import PageHomeLink from "@/components/PageHomeLink";

const FAQ_ITEMS = [
  {
    question: "How is ROI calculated?",
    answer:
      "ROI is total profit divided by total stake. A +10% ROI means 100 units staked would have returned 10 units of profit. We use stake-weighted profit, not raw win rate, because a 2.60 winner and a 1.60 winner do not carry the same value.",
  },
  {
    question: "Are losing runs and voids included?",
    answer:
      "Yes. Losses stay in the record and drawdowns remain visible. Voids are kept in the public history but do not count as wins or losses for win-rate purposes and do not add profit or loss to ROI.",
  },
  {
    question: "Can old picks be edited or removed?",
    answer:
      "No. Once a selection is posted or published, it cannot be retracted, reworded, or repriced. The only post-hoc change we allow is taxonomy: if a Premier League prop was filed under Other by mistake, we can re-tag the category. The bet itself, odds, stake, timestamp, and result stay frozen.",
  },
  {
    question: "Can I follow in real time?",
    answer:
      "Yes. Player props are posted publicly when value is identified, usually close to team-news or market-moving windows. Tennis selections are posted on the site with the same unit-stake logic used in this record.",
  },
  {
    question: "Are results net of bookmaker limits?",
    answer:
      "No public record can know every follower's limit, price delay, or account restriction. We record the posted odds, posted stake, and final settlement. If limits become an issue, that is usually a sign the edge has become visible to the bookmaker too.",
  },
  {
    question: "How should I judge the record?",
    answer:
      "Use ROI, sample size, settlement transparency, and whether prices were posted before the result was known. A hot week is not proof of edge, and a cold week does not kill the thesis. The record matters because both sides stay visible over time.",
  },
  {
    question: "What would this mean for my own stake size?",
    answer:
      "Use the returns calculator to test different unit sizes, bankrolls, and staking assumptions against the same unit-based logic used in the public record.",
    cta: {
      href: "/calculator",
      label: "Open the returns calculator",
    },
  },
] as const;

type DisplayStats = ReturnType<typeof getBaselineDisplayStats>;

interface CombinedMarketStats {
  total_bets: number;
  roi: number;
  win_rate: number;
  avg_odds: number;
  total_profit: number;
}

function getTrackingMonths() {
  const start = new Date("2024-10-01T00:00:00Z");
  const now = new Date();
  const months = Math.max(
    1,
    (now.getUTCFullYear() - start.getUTCFullYear()) * 12 + (now.getUTCMonth() - start.getUTCMonth())
  );
  return `${months}+ months`;
}

function getTrackingRangeLabel() {
  const now = new Date();
  const currentMonth = now.toLocaleDateString("en-GB", {
    month: "short",
    year: "numeric",
    timeZone: "UTC",
  });
  return `Oct 2024 - ${currentMonth}`;
}

function buildCombinedStats(liveStats: MarketStats[]): DisplayStats {
  const propsLive = liveStats.find((stat) => stat.market === "props");
  const tennisLive = liveStats.find((stat) => stat.market === "tennis");

  const propsLiveBets = propsLive?.total_bets || 0;
  const propsLiveWins = propsLive?.wins || 0;
  const propsLiveLosses = propsLive?.losses || 0;
  const propsLiveProfit = Number(propsLive?.total_profit) || 0;
  const propsLiveStake = Number(propsLive?.total_stake) || propsLiveBets;

  const propsWins = BASELINE_STATS.props.wins + propsLiveWins;
  const propsLosses = BASELINE_STATS.props.losses + propsLiveLosses;
  const propsProfit = BASELINE_STATS.props.total_profit + propsLiveProfit;
  const propsStake = BASELINE_STATS.props.total_stake + propsLiveStake;

  const propsCombined: CombinedMarketStats = {
    total_bets: BASELINE_STATS.props.total_bets + propsLiveBets,
    roi: calculateROI(propsProfit, propsStake || 1),
    win_rate: calculateWinRate(propsWins, propsLosses),
    avg_odds: propsLive?.avg_odds && propsLiveBets > 0 ? Number(propsLive.avg_odds) : 0,
    total_profit: propsProfit,
  };

  const tennisLiveBets = tennisLive?.total_bets || 0;
  const tennisLiveWins = tennisLive?.wins || 0;
  const tennisLiveLosses = tennisLive?.losses || 0;
  const tennisLiveProfit = Number(tennisLive?.total_profit) || 0;
  const tennisLiveStake = Number(tennisLive?.total_stake) || tennisLiveBets;

  const tennisWins = BASELINE_STATS.tennis.wins + tennisLiveWins;
  const tennisLosses = BASELINE_STATS.tennis.losses + tennisLiveLosses;
  const tennisProfit = BASELINE_STATS.tennis.total_profit + tennisLiveProfit;
  const tennisStake = BASELINE_STATS.tennis.total_stake + tennisLiveStake;

  const tennisCombined: CombinedMarketStats = {
    total_bets: BASELINE_STATS.tennis.total_bets + tennisLiveBets,
    roi: calculateROI(tennisProfit, tennisStake || 1),
    win_rate: calculateWinRate(tennisWins, tennisLosses),
    avg_odds: tennisLive?.avg_odds && tennisLiveBets > 0 ? Number(tennisLive.avg_odds) : 0,
    total_profit: tennisProfit,
  };

  const overallLiveBets = propsLiveBets + tennisLiveBets;
  const overallLiveWins = propsLiveWins + tennisLiveWins;
  const overallLiveLosses = propsLiveLosses + tennisLiveLosses;
  const overallLiveProfit = propsLiveProfit + tennisLiveProfit;
  const overallLiveStake = propsLiveStake + tennisLiveStake;

  const overallWins = BASELINE_STATS.overall.wins + overallLiveWins;
  const overallLosses = BASELINE_STATS.overall.losses + overallLiveLosses;
  const overallProfit = BASELINE_STATS.overall.total_profit + overallLiveProfit;
  const overallStake = BASELINE_STATS.overall.total_stake + overallLiveStake;

  const overallCombined: CombinedMarketStats = {
    total_bets: BASELINE_STATS.overall.total_bets + overallLiveBets,
    roi: calculateROI(overallProfit, overallStake || 1),
    win_rate: calculateWinRate(overallWins, overallLosses),
    avg_odds: 0,
    total_profit: overallProfit,
  };

  if (propsCombined.avg_odds > 0 || tennisCombined.avg_odds > 0) {
    const totalOddsWeight =
      propsCombined.avg_odds * propsCombined.total_bets +
      tennisCombined.avg_odds * tennisCombined.total_bets;
    overallCombined.avg_odds =
      overallCombined.total_bets > 0 ? totalOddsWeight / overallCombined.total_bets : 0;
  }

  return {
    props: propsCombined,
    tennis: tennisCombined,
    overall: overallCombined,
  };
}

function formatBetCount(value: number) {
  return `${Math.round(value).toLocaleString("en-GB")}+`;
}

function formatSignedPercent(value: number) {
  return `${value > 0 ? "+" : ""}${value.toFixed(1)}%`;
}

function formatCashExample(unitsProfit: number, poundsPerUnit = 100) {
  const value = Math.round(unitsProfit * poundsPerUnit);
  return `${value >= 0 ? "+" : "-"}${String.fromCharCode(163)}${Math.abs(value).toLocaleString("en-GB")}`;
}

function FaqSchema() {
  const schema = {
    "@context": "https://schema.org",
    "@type": "FAQPage",
    mainEntity: FAQ_ITEMS.map((item) => ({
      "@type": "Question",
      name: item.question,
      acceptedAnswer: {
        "@type": "Answer",
        text: item.answer,
      },
    })),
  };

  return (
    <script
      type="application/ld+json"
      dangerouslySetInnerHTML={{ __html: JSON.stringify(schema) }}
    />
  );
}

function Reveal({
  children,
  delay = 0,
  className = "",
}: {
  children: ReactNode;
  delay?: number;
  className?: string;
}) {
  return (
    <div
      className={className}
      style={{
        animation: "page-reveal 0.7s cubic-bezier(0.16,1,0.3,1) both",
        animationDelay: `${delay}ms`,
      }}
    >
      {children}
    </div>
  );
}

function StatCard({
  label,
  value,
  sub,
  accent = false,
  delay = 0,
}: {
  label: string;
  value: string;
  sub: string;
  accent?: boolean;
  delay?: number;
}) {
  const stripped = value.replace(/[^0-9.%]/g, "");
  const watermark = stripped.length >= 2 ? stripped : "";

  return (
    <div
      className={`relative overflow-hidden rounded-2xl border p-5 md:p-6 ${
        accent ? "border-emerald-500/20 bg-[#0c0f14]" : "border-slate-700/40 bg-[#0c0f14]"
      }`}
      style={{
        animation: "track-record-stat-reveal 0.6s cubic-bezier(0.16,1,0.3,1) both",
        animationDelay: `${delay}ms`,
      }}
    >
      {accent ? (
        <div
          className="absolute top-0 left-[10%] right-[10%] h-px"
          style={{
            background: "linear-gradient(90deg, transparent, rgba(16,185,129,0.35), transparent)",
          }}
        />
      ) : null}
      {watermark ? (
        <span
          className="pointer-events-none absolute -right-3 -bottom-4 select-none font-mono text-[80px] font-black leading-none"
          style={{
            color: accent ? "rgba(16,185,129,0.03)" : "rgba(255,255,255,0.015)",
          }}
        >
          {watermark}
        </span>
      ) : null}
      <div className="relative">
        <div className="text-[10px] font-mono font-bold uppercase tracking-[0.14em] text-slate-500">
          {label}
        </div>
        <div
          className={`mt-3 font-mono text-[2.2rem] font-extrabold leading-none tracking-tight tabular-nums md:text-[2.5rem] ${
            accent ? "text-emerald-400" : "text-slate-100"
          }`}
        >
          {value}
        </div>
        <div className="mt-3 font-mono text-[11px] leading-relaxed text-slate-500">{sub}</div>
      </div>
    </div>
  );
}

function FAQ({ q, a }: { q: string; a: ReactNode }) {
  return (
    <details className="group overflow-hidden rounded-xl border border-slate-700/30 bg-[#0c0f14]">
      <summary className="flex cursor-pointer list-none items-center justify-between gap-3 px-5 py-4 text-[14px] font-medium text-slate-300 transition-colors hover:text-white">
        {q}
        <svg
          aria-hidden="true"
          className="h-4 w-4 shrink-0 text-emerald-500/40 transition-transform group-open:rotate-180"
          fill="none"
          stroke="currentColor"
          viewBox="0 0 24 24"
        >
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M19 9l-7 7-7-7" />
        </svg>
      </summary>
      <div className="border-t border-slate-800/40 px-5 py-4 text-[13px] leading-[1.7] text-slate-500">
        {a}
      </div>
    </details>
  );
}

export default function TrackRecordPage() {
  const [displayStats, setDisplayStats] = useState<DisplayStats>(() => getBaselineDisplayStats());
  const [statsStatus, setStatsStatus] = useState<"loading" | "live" | "fallback">("loading");
  const [showStatsNote, setShowStatsNote] = useState(false);

  const fetchStats = useCallback(async () => {
    try {
      const res = await fetch("/api/public-record?scope=home", { cache: "no-store" });
      const json = await res.json();
      if (!res.ok) {
        throw new Error(json?.error || "Failed to load public record");
      }
      setDisplayStats(buildCombinedStats((json.stats as MarketStats[] | null) ?? []));
      setStatsStatus("live");
    } catch (error) {
      console.error("Error fetching track record stats:", error);
      setDisplayStats(getBaselineDisplayStats());
      setStatsStatus("fallback");
    }
  }, []);

  useEffect(() => {
    const statsNoteTimer = window.setTimeout(() => setShowStatsNote(true), 300);
    const initialFetchId = window.setTimeout(() => {
      void fetchStats();
    }, 0);
    const handleFocus = () => {
      void fetchStats();
    };
    const handleVisibility = () => {
      if (document.visibilityState === "visible") {
        void fetchStats();
      }
    };
    window.addEventListener("focus", handleFocus);
    document.addEventListener("visibilitychange", handleVisibility);

    return () => {
      window.clearTimeout(statsNoteTimer);
      window.clearTimeout(initialFetchId);
      window.removeEventListener("focus", handleFocus);
      document.removeEventListener("visibilitychange", handleVisibility);
    };
  }, [fetchStats]);

  const trackingPeriod = getTrackingMonths();
  const trackingRange = getTrackingRangeLabel();
  const statsNote =
    statsStatus === "live"
      ? "Updated automatically from settled results in the public record feed."
      : statsStatus === "fallback"
        ? "Stored public record shown while the live feed is unavailable."
        : showStatsNote
          ? "Loading the latest settled public record."
          : "";

  return (
    <div className="min-h-screen bg-[#0f1117] text-slate-100">
      <FaqSchema />

      <section className="relative overflow-hidden border-b border-slate-800/40 pt-6 pb-16 md:pb-20">
        <div
          className="pointer-events-none absolute inset-x-0 -top-20 h-[600px]"
          style={{
            background:
              "radial-gradient(ellipse 1100px 500px at 50% -100px, rgba(16,185,129,0.09), transparent)",
          }}
        />
        <div className="pointer-events-none absolute -left-40 top-20 h-[350px] w-[350px] rounded-full bg-emerald-600/[0.025] blur-[100px]" />

        <div className="relative z-10 mx-auto max-w-6xl px-4 sm:px-6 lg:px-8">
          <Reveal delay={0}>
            <PageHomeLink className="mb-12" />
          </Reveal>

          <Reveal delay={60}>
            <span className="text-xs font-mono font-bold uppercase tracking-[0.18em] text-emerald-400/95">
              Verified public record | updated live
            </span>
          </Reveal>

          <Reveal delay={120}>
            <h1 className="mt-4 max-w-4xl text-4xl font-semibold leading-[0.95] tracking-tight text-slate-100 sm:text-5xl md:text-6xl">
              {formatCashExample(displayStats.overall.total_profit)} of evidence.
            </h1>
          </Reveal>

          <Reveal delay={190}>
            <p className="mt-6 max-w-2xl text-base leading-relaxed text-slate-300 sm:text-lg">
              {formatBetCount(displayStats.overall.total_bets)} settled bets across player props and ATP tennis. {" "}
              {formatSignedPercent(displayStats.overall.roi)} ROI over {trackingPeriod}. Posted before the result was known,
              logged after settlement, never edited.
            </p>
          </Reveal>

          <Reveal delay={250}>
            <ul className="mt-5 flex flex-wrap gap-2 text-[11px] font-mono font-semibold uppercase tracking-[0.12em] text-slate-400">
              {[
                "Public site ledger",
                "Pre-result timestamps",
                "Settlement audit trail",
                "No edited history",
              ].map((label) => (
                <li
                  key={label}
                  className="rounded-full border border-slate-700/50 bg-[#0c0f14] px-3 py-2"
                >
                  {label}
                </li>
              ))}
            </ul>
          </Reveal>

          <Reveal delay={310}>
            <div className="mt-6 flex flex-wrap gap-3">
              <Link
                href="/player-props"
                className="inline-flex items-center gap-2 rounded-lg bg-emerald-500 px-5 py-3 text-sm font-semibold text-white transition-colors hover:bg-emerald-400"
              >
                View today&apos;s selections &rarr;
              </Link>
              <Link
                href="/calculator"
                className="inline-flex items-center gap-2 rounded-lg border border-slate-700/60 bg-[#0c0f14] px-5 py-3 text-sm font-semibold text-slate-200 transition-colors hover:border-emerald-500/30 hover:text-emerald-300"
              >
                Open returns calculator &rarr;
              </Link>
              <Link
                href="/the-edge"
                className="inline-flex items-center gap-1.5 px-1 py-3 text-sm text-slate-500 transition-colors hover:text-emerald-400"
              >
                See methodology &rarr;
              </Link>
              <Link
                href="/resources/how-to-read-a-tipster-track-record"
                className="inline-flex items-center gap-1.5 px-1 py-3 text-sm text-slate-500 transition-colors hover:text-emerald-400"
              >
                How to audit a betting record &rarr;
              </Link>
            </div>
          </Reveal>

          <div className="mt-10 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            <StatCard
              label="Player Props"
              value={formatBetCount(displayStats.props.total_bets)}
              sub={`${formatSignedPercent(displayStats.props.roi)} ROI | ${displayStats.props.win_rate.toFixed(1)}% win rate`}
              accent
              delay={380}
            />
            <StatCard
              label="Combined ROI"
              value={formatSignedPercent(displayStats.overall.roi)}
              sub={`${formatBetCount(displayStats.overall.total_bets)} bets | ${trackingRange}`}
              accent
              delay={440}
            />
            <StatCard
              label="ATP Tennis"
              value={formatBetCount(displayStats.tennis.total_bets)}
              sub={`${formatSignedPercent(displayStats.tennis.roi)} ROI | ${displayStats.tennis.win_rate.toFixed(1)}% win rate`}
              delay={500}
            />
          </div>

          <Reveal delay={560}>
            <div className="mt-4 rounded-2xl border border-emerald-500/15 bg-emerald-500/[0.035] p-5 md:flex md:items-center md:justify-between md:gap-8">
              <div>
                <div className="text-[10px] font-mono font-bold uppercase tracking-[0.16em] text-emerald-400/90">
                  Calculated result at &pound;100 per unit
                </div>
                <p className="mt-2 max-w-2xl text-sm leading-relaxed text-slate-400">
                  Every posted stake is scaled directly: 0.5u = &pound;50, 1u = &pound;100, 2u = &pound;200.
                  The figure uses the current props + tennis P/L at that staking level.
                </p>
                <Link
                  href="/calculator"
                  className="mt-3 inline-flex text-sm font-medium text-emerald-400 underline underline-offset-4 transition-colors hover:text-emerald-300"
                >
                  Test the same record against your stake size &rarr;
                </Link>
              </div>
              <div className="mt-5 shrink-0 md:mt-0 md:text-right">
                <div className="font-mono text-3xl font-black tracking-tight text-emerald-400 tabular-nums md:text-4xl">
                  {formatCashExample(displayStats.overall.total_profit)}
                </div>
                <div className="mt-3 flex flex-wrap gap-2 md:justify-end">
                  <span className="rounded-full border border-emerald-500/15 bg-[#0c0f14]/80 px-3 py-1.5 font-mono text-[11px] text-slate-400">
                    Props{" "}
                    <span className="font-semibold text-emerald-400">
                      {formatCashExample(displayStats.props.total_profit)}
                    </span>
                  </span>
                  <span className="rounded-full border border-emerald-500/15 bg-[#0c0f14]/80 px-3 py-1.5 font-mono text-[11px] text-slate-400">
                    Tennis{" "}
                    <span className="font-semibold text-emerald-400">
                      {formatCashExample(displayStats.tennis.total_profit)}
                    </span>
                  </span>
                </div>
              </div>
            </div>
          </Reveal>

          {statsNote ? (
            <Reveal delay={600}>
              <p className="mt-4 font-mono text-[10px] leading-relaxed text-slate-600">
                {statsNote}
              </p>
            </Reveal>
          ) : null}
        </div>
      </section>

      <div className="mx-auto max-w-6xl px-4 sm:px-6 lg:px-8">
        <section className="border-b border-slate-800/30 py-16 md:py-20">
          <span className="mb-3 block text-xs font-mono font-bold uppercase tracking-[0.18em] text-emerald-400/90">
            How we prove it
          </span>
          <h2 className="mb-8 text-2xl font-semibold tracking-tight text-slate-100 sm:text-3xl">
            Verification system
          </h2>

          <div className="grid gap-3 md:grid-cols-2 lg:grid-cols-4">
            {[
              {
                icon: (
                  <svg
                    className="h-5 w-5 text-emerald-400"
                    fill="none"
                    stroke="currentColor"
                    viewBox="0 0 24 24"
                    strokeWidth="1.5"
                  >
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      d="M12 6v6h4.5m4.5 0a9 9 0 11-18 0 9 9 0 0118 0z"
                    />
                  </svg>
                ),
                title: "Pre-match posting",
                body: "Posted before the event. Public posting timestamps for props and site publish times for tennis make timing visible before the result is known.",
              },
              {
                icon: (
                  <svg
                    className="h-5 w-5 text-emerald-400"
                    fill="none"
                    stroke="currentColor"
                    viewBox="0 0 24 24"
                    strokeWidth="1.5"
                  >
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      d="M9 12.75L11.25 15 15 9.75M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
                    />
                  </svg>
                ),
                title: "Post-match settlement",
                body: "Result, profit/loss, odds and stake are logged after settlement. We do not wait to see how the week looks first.",
              },
              {
                icon: (
                  <svg
                    className="h-5 w-5 text-emerald-400"
                    fill="none"
                    stroke="currentColor"
                    viewBox="0 0 24 24"
                    strokeWidth="1.5"
                  >
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      d="M16.5 10.5V6.75a4.5 4.5 0 10-9 0v3.75m-.75 11.25h10.5a2.25 2.25 0 002.25-2.25v-6.75a2.25 2.25 0 00-2.25-2.25H6.75a2.25 2.25 0 00-2.25 2.25v6.75a2.25 2.25 0 002.25 2.25z"
                    />
                  </svg>
                ),
                title: "No editing",
                body: "Selections cannot be retracted, repriced, or quietly removed. Category fixes can happen, but the bet itself stays frozen.",
              },
              {
                icon: (
                  <svg
                    className="h-5 w-5 text-emerald-400"
                    fill="none"
                    stroke="currentColor"
                    viewBox="0 0 24 24"
                    strokeWidth="1.5"
                  >
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      d="M9 12h6m-6 4h6M9 8h6M5.25 19.5h13.5a1.5 1.5 0 001.5-1.5V6a1.5 1.5 0 00-1.5-1.5H5.25A1.5 1.5 0 003.75 6v12a1.5 1.5 0 001.5 1.5z"
                    />
                  </svg>
                ),
                title: "Settlement audit trail",
                body: "Every settlement is appended, never overwritten. Reclassifications are written as new rows so the original odds, stake, and result stay intact.",
              },
            ].map((item) => (
              <div
                key={item.title}
                className="group rounded-2xl border border-slate-700/40 bg-[#0c0f14] p-5 transition-all duration-300 hover:border-slate-600/60 md:p-6"
              >
                <div className="mb-4 flex h-10 w-10 items-center justify-center rounded-lg border border-emerald-500/15 bg-emerald-500/[0.06]">
                  {item.icon}
                </div>
                <h3 className="mb-2 text-base font-semibold text-slate-200">{item.title}</h3>
                <p className="text-sm leading-relaxed text-slate-500 transition-colors duration-300 group-hover:text-slate-400">
                  {item.body}
                </p>
              </div>
            ))}
          </div>
        </section>

        <section className="border-b border-slate-800/30 py-16 md:py-20">
          <span className="mb-3 block text-xs font-mono font-bold uppercase tracking-[0.18em] text-emerald-400/90">
            Benchmark
          </span>
          <div className="grid gap-8 lg:grid-cols-[0.85fr,1.15fr] lg:items-start">
            <div>
              <h2 className="text-2xl font-semibold tracking-tight text-slate-100 sm:text-3xl">
                Where {formatSignedPercent(displayStats.overall.roi)} ROI sits
              </h2>
              <p className="mt-4 text-sm leading-relaxed text-slate-500">
                Sustained positive ROI over {formatBetCount(displayStats.overall.total_bets)} settled bets is the point.
                The comparison below is a plain-English yardstick, not a promise about future returns.
              </p>
            </div>
            <div className="overflow-hidden rounded-2xl border border-slate-700/40 bg-[#0c0f14]">
              {[
                ["Average punter", "-5% to -10%", formatSignedPercent(displayStats.overall.roi)],
                ["Tipster services", "+2% to +5%", formatSignedPercent(displayStats.overall.roi)],
                ["Sharp bettors", "+5% to +10%", formatSignedPercent(displayStats.overall.roi)],
                ["Pro syndicates", "+10% to +15%", formatSignedPercent(displayStats.overall.roi)],
              ].map(([group, typical, ilmargine]) => (
                <div
                  key={group}
                  className="grid grid-cols-[1.2fr,0.85fr,0.85fr] border-b border-slate-800/50 px-4 py-3 last:border-b-0 sm:px-5"
                >
                  <span className="text-sm font-medium text-slate-300">{group}</span>
                  <span className="font-mono text-sm text-slate-500">{typical}</span>
                  <span className="text-right font-mono text-sm font-bold text-emerald-400">{ilmargine}</span>
                </div>
              ))}
            </div>
          </div>
        </section>

        <section className="border-b border-slate-800/30 py-16 md:py-20">
          <span className="mb-3 block text-xs font-mono font-bold uppercase tracking-[0.18em] text-emerald-400/90">
            Before you follow
          </span>
          <h2 className="mb-8 text-2xl font-semibold tracking-tight text-slate-100 sm:text-3xl">
            Realistic expectations
          </h2>

          <div className="grid gap-x-12 gap-y-5 md:grid-cols-2">
            {[
              {
                t: "Sample size matters",
                d: "Twenty bets tells you almost nothing. Hundreds tell you much more.",
              },
              {
                t: "Variance is real",
                d: "Good process still comes with losing runs and ugly short-term swings.",
              },
              {
                t: "ROI varies by market",
                d: "Props and tennis are different types of edge with different return profiles.",
              },
              {
                t: "Posting is irregular",
                d: "We post when value exists, not because a schedule needs content.",
              },
              {
                t: "Stakes can get limited",
                d: "Win consistently and bookmakers may cut your size. That's a signal it works.",
              },
              {
                t: "No staking gimmicks",
                d: "Flat units only. No martingales, recovery plans, or compounding tricks dressed up as edge.",
              },
            ].map((item) => (
              <div key={item.t} className="flex items-start gap-3.5">
                <div className="mt-[7px] h-[6px] w-[6px] shrink-0 rounded-full border border-emerald-500/40 bg-emerald-500/20" />
                <div>
                  <span className="text-base font-semibold text-slate-200">{item.t}.</span>{" "}
                  <span className="text-base leading-relaxed text-slate-500">{item.d}</span>
                </div>
              </div>
            ))}
          </div>
        </section>

        <section className="border-b border-slate-800/30 py-16 md:py-20">
          <div className="relative overflow-hidden rounded-2xl border border-emerald-500/15 bg-[#0c0f14] p-6 md:p-8 lg:p-10">
            <div
              className="absolute top-0 left-0 right-0 h-px"
              style={{
                background:
                  "linear-gradient(90deg, transparent 5%, rgba(16,185,129,0.4) 50%, transparent 95%)",
              }}
            />
            <div className="pointer-events-none absolute -right-20 -top-20 h-48 w-48 rounded-full bg-emerald-500/[0.04] blur-[60px]" />

            <div className="relative grid gap-10 lg:grid-cols-[1fr,0.6fr] lg:gap-14">
              <div>
                <span className="mb-3 block text-xs font-mono font-bold uppercase tracking-[0.18em] text-emerald-400/90">
                  Why we are different
                </span>
                <h2 className="mb-5 text-2xl font-semibold tracking-tight text-slate-100 sm:text-3xl">
                  The tipster problem
                </h2>
                <div className="space-y-4 text-base leading-relaxed text-slate-400">
                  <p>
                    Most tipsters are not businesses built on edge. They are funnels built on confidence.
                  </p>
                  <p>
                    Plays of the year with no timestamps. Unit claims that quietly shrink after a loss.
                    Cherry-picked screenshots. Records that get cleaner the longer you stare.
                  </p>
                  <p>
                    Edge is boring by comparison: a posted price, a logged stake, a settled result, and a
                    number that keeps climbing while the losses stay visible too.
                  </p>
                </div>
              </div>

              <div className="flex items-center">
                <div className="w-full rounded-xl border border-slate-700/40 bg-[#0f1117] p-5">
                  <div className="mb-4 text-[10px] font-mono font-bold uppercase tracking-[0.16em] text-emerald-400/80">
                    Receipts, not slogans
                  </div>
                  <div className="grid gap-3">
                    {[
                      ["Settled sample", formatBetCount(displayStats.overall.total_bets)],
                      ["\u00A3100 / unit example", formatCashExample(displayStats.overall.total_profit)],
                      ["Tracking window", trackingRange],
                      ["Verification", "Pre-result timestamps"],
                    ].map(([label, value]) => (
                      <div key={label} className="rounded-lg border border-slate-800/70 bg-[#0c0f14] px-4 py-3">
                        <div className="font-mono text-[10px] font-bold uppercase tracking-[0.14em] text-slate-500">
                          {label}
                        </div>
                        <div className="mt-1 font-mono text-lg font-black text-slate-100 tabular-nums">
                          {value}
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            </div>
          </div>
        </section>

        <section className="border-b border-slate-800/30 py-16 md:py-20">
          <span className="mb-3 block text-xs font-mono font-bold uppercase tracking-[0.18em] text-emerald-400/90">
            Common questions
          </span>
          <h2 className="mb-6 text-xl font-semibold text-slate-100">FAQ</h2>
          <div className="max-w-3xl space-y-2">
            {FAQ_ITEMS.map((item) => (
              <FAQ
                key={item.question}
                q={item.question}
                a={
                  <>
                    {item.answer}
                    {"cta" in item ? (
                      <>
                        {" "}
                        <Link
                          href={item.cta.href}
                          className="font-medium text-emerald-400 underline underline-offset-4 transition-colors hover:text-emerald-300"
                        >
                          {item.cta.label}
                        </Link>
                        .
                      </>
                    ) : null}
                  </>
                }
              />
            ))}
          </div>
        </section>

        <section className="py-16 md:py-20">
          <div className="relative overflow-hidden rounded-2xl border border-emerald-500/15 p-10 text-center md:p-14">
            <div className="absolute inset-0 bg-[#0c0f14]" />
            <div
              className="pointer-events-none absolute inset-0"
              style={{
                background:
                  "radial-gradient(circle at 50% 130%, rgba(16,185,129,0.10), transparent 55%)",
              }}
            />
            <div
              className="absolute top-0 left-[15%] right-[15%] h-px"
              style={{
                background:
                  "linear-gradient(90deg, transparent, rgba(16,185,129,0.3), transparent)",
              }}
            />

            <div className="relative">
              <h2 className="text-2xl font-semibold tracking-tight text-slate-100 sm:text-3xl">
                See what is posted now
              </h2>
              <p className="mx-auto mt-4 max-w-md text-base leading-relaxed text-slate-400">
                Today&apos;s selections and the calculator use the same unit logic as the public record.
              </p>
              <div className="mt-7 flex flex-col justify-center gap-3 sm:flex-row">
                <Link
                  href="/player-props"
                  className="inline-flex items-center justify-center gap-2.5 rounded-lg bg-emerald-500 px-7 py-3.5 text-base font-semibold text-white transition-colors hover:bg-emerald-400"
                >
                  Today&apos;s selections &rarr;
                </Link>
                <Link
                  href="/calculator"
                  className="inline-flex items-center justify-center gap-2.5 rounded-lg border border-slate-700/60 bg-[#111522] px-7 py-3.5 text-base font-semibold text-slate-200 transition-colors hover:border-emerald-500/30 hover:text-emerald-300"
                >
                  Open returns calculator &rarr;
                </Link>
              </div>
              <Link
                href="/player-props"
                className="mt-5 inline-flex text-sm text-slate-500 underline underline-offset-4 transition-colors hover:text-emerald-300"
              >
                Open the latest props feed &rarr;
              </Link>
            </div>
          </div>
        </section>

        <div className="pb-14">
          <div className="rounded-xl border border-amber-500/10 bg-amber-500/[0.03] px-5 py-4 text-[12px] leading-relaxed text-slate-500">
            <strong className="text-amber-300">Responsible gambling:</strong>{" "}
            <span className="text-slate-300">Past performance does not guarantee future results. Only bet what you can afford to lose.</span>{" "}
            <a
              href="https://www.begambleaware.org"
              target="_blank"
              rel="noopener noreferrer"
              className="text-slate-500 underline underline-offset-2 transition-colors hover:text-slate-300"
            >
              BeGambleAware
            </a>{" "}
            <span className="px-1.5 text-slate-500">|</span>
            <a
              href="https://www.gamcare.org.uk"
              target="_blank"
              rel="noopener noreferrer"
              className="text-slate-500 underline underline-offset-2 transition-colors hover:text-slate-300"
            >
              GamCare
            </a>
          </div>
        </div>
      </div>

      <Footer />

      <style jsx global>{`
        @keyframes page-reveal {
          from {
            opacity: 0;
            transform: translateY(18px);
          }
          to {
            opacity: 1;
            transform: translateY(0);
          }
        }

        @keyframes track-record-stat-reveal {
          from {
            opacity: 0;
            transform: translateY(12px);
          }
          to {
            opacity: 1;
            transform: translateY(0);
          }
        }
      `}</style>
    </div>
  );
}
