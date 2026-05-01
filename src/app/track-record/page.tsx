"use client";

import { useCallback, useEffect, useState, type ReactNode } from "react";
import Link from "next/link";
import { BASELINE_STATS, calculateROI, calculateWinRate, getBaselineDisplayStats } from "@/lib/baseline";
import { type MarketStats } from "@/lib/supabase";
import Footer from "@/components/Footer";
import PageHomeLink from "@/components/PageHomeLink";

const FAQ_ITEMS = [
  {
    question: "What is included in the headline track record?",
    answer:
      "The headline record combines the original validation baseline with live public selections settled through the site. Player props and ATP tennis are tracked separately, then rolled up into the combined record so the homepage and track record page use the same accounting base.",
  },
  {
    question: "How is ROI calculated?",
    answer:
      "ROI is total profit divided by total stake. A +10% ROI means 100 units staked would have returned 10 units of profit. We use stake-weighted profit, not raw win rate, because a 2.60 winner and a 1.60 winner do not carry the same value.",
  },
  {
    question: "Why can the totals move after a result is settled?",
    answer:
      "The public feed updates when bets move from pending to won, lost, or void. Once a result is settled, the bet count, ROI, win rate, category records, and recent selections can all change automatically from the database feed.",
  },
  {
    question: "Are losing runs and voids included?",
    answer:
      "Yes. Losses stay in the record and drawdowns remain visible. Voids are kept in the public history but do not count as wins or losses for win-rate purposes and do not add profit or loss to ROI.",
  },
  {
    question: "Can old picks be edited or removed?",
    answer:
      "No. The point of public tracking is that selections are logged before the event and settled afterwards. If a category needs correcting, such as moving a football prop from Other to La Liga, the bet itself stays in the record and only the classification changes.",
  },
  {
    question: "Why do market and league records not always move equally?",
    answer:
      "The headline record is market-level. League and category pages are slices of that same record, so their samples are smaller and can move sharply after only a few results. The combined number is the broadest view; category records are useful context, not a replacement for the full sample.",
  },
  {
    question: "How should I judge the record?",
    answer:
      "Use ROI, sample size, settlement transparency, and whether the prices were posted before the event. Short winning streaks are not proof of edge and short losing streaks do not automatically disprove it. The record matters because it keeps both sides visible over time.",
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
      <span
        className="pointer-events-none absolute -right-3 -bottom-4 select-none font-mono text-[80px] font-black leading-none"
        style={{
          color: accent ? "rgba(16,185,129,0.03)" : "rgba(255,255,255,0.015)",
        }}
      >
        {value.replace(/[^0-9.%+]/g, "")}
      </span>
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
      window.clearTimeout(initialFetchId);
      window.removeEventListener("focus", handleFocus);
      document.removeEventListener("visibilitychange", handleVisibility);
    };
  }, [fetchStats]);

  const trackingPeriod = getTrackingMonths();
  const statsNote =
    statsStatus === "live"
      ? "Baseline validation plus live public settlements. Updated from the public record feed."
      : statsStatus === "fallback"
        ? "Baseline validation shown while the live public record feed is unavailable."
        : "Baseline validation shown while live public settlements load.";

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

          <Reveal delay={100}>
            <span className="text-xs font-mono font-bold uppercase tracking-[0.18em] text-emerald-400/95">
              Track Record
            </span>
          </Reveal>

          <Reveal delay={200}>
            <h1 className="mt-4 text-3xl font-semibold leading-tight tracking-tight text-slate-100 sm:text-4xl md:text-5xl">
              Track Record
            </h1>
          </Reveal>

          <Reveal delay={320}>
            <p className="mt-6 max-w-xl text-base leading-relaxed text-slate-300 sm:text-lg">
              Every bet posted before kick-off. Every result logged after settlement. No edits, no
              deletions.
            </p>
          </Reveal>

          <Reveal delay={420}>
            <Link
              href="/the-edge"
              className="mt-4 inline-flex items-center gap-1.5 text-sm text-slate-500 transition-colors hover:text-emerald-400"
            >
              See our methodology
              <svg className="h-3.5 w-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9 5l7 7-7 7" />
              </svg>
            </Link>
          </Reveal>

          <div className="mt-12 grid gap-3 md:grid-cols-3">
            <StatCard
              label="Player Props"
              value={formatBetCount(displayStats.props.total_bets)}
              sub={`${formatSignedPercent(displayStats.props.roi)} ROI | ${displayStats.props.win_rate.toFixed(1)}% win rate`}
              accent
              delay={550}
            />
            <StatCard
              label="ATP Tennis"
              value={formatBetCount(displayStats.tennis.total_bets)}
              sub={`${formatSignedPercent(displayStats.tennis.roi)} ROI | ${displayStats.tennis.win_rate.toFixed(1)}% win rate | Tipstrr verified`}
              delay={650}
            />
            <StatCard
              label="Combined ROI"
              value={formatSignedPercent(displayStats.overall.roi)}
              sub={`${formatBetCount(displayStats.overall.total_bets)} bets | ${trackingPeriod}`}
              accent
              delay={750}
            />
          </div>

          <Reveal delay={850}>
            <p className="mt-4 font-mono text-[10px] leading-relaxed text-slate-600">
              {statsNote}
            </p>
          </Reveal>
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

          <div className="grid gap-3 md:grid-cols-3">
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
                body: "Every selection published on site before kick-off. Timestamps are immutable and verifiable.",
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
                body: "Once settled, the result is logged with outcome and P&L impact. No lag, no filtering.",
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
                body: "The public record cannot be changed after the fact. What is posted stays posted - wins and losses.",
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
            Before you follow
          </span>
          <h2 className="mb-8 text-2xl font-semibold tracking-tight text-slate-100 sm:text-3xl">
            Realistic expectations
          </h2>

          <div className="grid gap-x-12 gap-y-5 md:grid-cols-2">
            {[
              {
                t: "Variance is real",
                d: "Good process still comes with losing runs and ugly short-term swings.",
              },
              {
                t: "Sample size matters",
                d: "Twenty bets tells you almost nothing. Hundreds tell you much more.",
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
                t: "Losses get logged",
                d: "Transparency matters more than a curated feed. Every loss stays visible.",
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
                    Most tipster services are not businesses built on edge. They are marketing funnels built
                    on confidence.
                  </p>
                  <p>
                    The usual playbook: plays of the year with no timestamps, giant unit claims that vanish
                    when they lose, cherry-picked winner screenshots, records that get cleaner after the
                    fact.
                  </p>
                  <p>
                    That is not analysis. It is gambling repackaged as expertise - because confidence sells
                    better than honesty.
                  </p>
                </div>
              </div>

              <div className="flex items-center">
                <div className="w-full rounded-xl border border-slate-700/40 bg-[#0f1117] p-5">
                  <div className="mb-4 text-[10px] font-mono font-bold uppercase tracking-[0.16em] text-emerald-400/80">
                    What real edge looks like
                  </div>
                  <div className="space-y-3">
                    {[
                      "Immutable timestamps",
                      "Visible losses",
                      "Transparent settlement",
                      "Bad runs kept alongside good",
                      "No edited history",
                    ].map((item) => (
                      <div key={item} className="flex items-center gap-3">
                        <div className="flex h-5 w-5 shrink-0 items-center justify-center rounded-md border border-emerald-500/20 bg-emerald-500/[0.06]">
                          <svg
                            className="h-3 w-3 text-emerald-400"
                            fill="none"
                            stroke="currentColor"
                            viewBox="0 0 24 24"
                            strokeWidth="2.5"
                          >
                            <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
                          </svg>
                        </div>
                        <span className="text-sm text-slate-400">{item}</span>
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
              <FAQ key={item.question} q={item.question} a={item.answer} />
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
                Follow the picks
              </h2>
              <p className="mx-auto mt-4 max-w-md text-base leading-relaxed text-slate-400">
                All selections posted on the website with full analysis.
              </p>
              <Link
                href="/player-props"
                className="mt-7 inline-flex items-center gap-2.5 rounded-lg bg-emerald-500 px-8 py-3.5 text-base font-semibold text-white transition-colors hover:bg-emerald-400"
              >
                View Tips -&gt;
              </Link>
            </div>
          </div>
        </section>

        <div className="pb-14">
          <div className="rounded-xl border border-amber-500/10 bg-amber-500/[0.03] px-5 py-4 text-[12px] leading-relaxed text-slate-500">
            <strong className="text-amber-400/80">Responsible gambling:</strong> Past performance does not
            guarantee future results. Only bet what you can afford to lose.{" "}
            <a
              href="https://www.begambleaware.org"
              target="_blank"
              rel="noopener noreferrer"
              className="text-slate-400 underline underline-offset-2"
            >
              BeGambleAware
            </a>{" "}
            <span className="px-1.5 text-slate-500">|</span>
            <a
              href="https://www.gamcare.org.uk"
              target="_blank"
              rel="noopener noreferrer"
              className="text-slate-400 underline underline-offset-2"
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
