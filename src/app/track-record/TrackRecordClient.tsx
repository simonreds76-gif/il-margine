"use client";

import EditorialIcon from "@/components/EditorialIcon";
import SportCta from "@/components/SportCta";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { BASELINE_STATS, calculateROI, calculateWinRate, getBaselineDisplayStats } from "@/lib/baseline";
import { type MarketStats } from "@/lib/supabase";
import Footer from "@/components/Footer";
import PageHeading from "@/components/PageHeading";
import MonthlyBreakdownSection from "@/components/MonthlyBreakdownSection";

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
    question: "What does the record show?",
    answer: "The published price, stake and settlement for each tracked selection. Historical totals recorded before database tracking are identified separately from the individual database entries. Corrections should be explained rather than treated as new winning selections.",
  },
  {
    question: "Can I follow in real time?",
    answer:
      "Yes. Player props are posted publicly when value is identified, usually close to team-news or market-moving windows. Tennis selections are posted on the site with the same unit-stake logic used in this record.",
  },
  {
    question: "Are results net of bookmaker limits?",
    answer:
      "No public record can know every follower's limit, price delay, or account restriction. We record the posted odds, posted stake, and final settlement. Your own returns can differ when the available odds or accepted stake change.",
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
  const propsLiveStake = Number(propsLive?.total_stake ?? propsLiveBets);

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
  const tennisLiveStake = Number(tennisLive?.total_stake ?? tennisLiveBets);

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
  return `${Math.round(value).toLocaleString("en-GB")}`;
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

export default function TrackRecordClient({ initialStats, initialMonthly }: {
  initialStats: MarketStats[] | null;
  initialMonthly?: React.ComponentProps<typeof MonthlyBreakdownSection>["initialPayload"];
}) {
  const [displayStats, setDisplayStats] = useState<DisplayStats>(() => initialStats ? buildCombinedStats(initialStats) : getBaselineDisplayStats());
  const [statsStatus, setStatsStatus] = useState<"live" | "fallback" | "stale">(initialStats ? "live" : "fallback");

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
      setStatsStatus(previous => previous === "fallback" ? "fallback" : "stale");
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

  const trackingRange = getTrackingRangeLabel();
  const statsNote = statsStatus === "live"
    ? "Updated from settled results in the public record feed."
    : statsStatus === "fallback"
      ? "Earlier recorded results shown while the latest figures are unavailable."
      : "Showing the last available settled record; a refresh is temporarily unavailable.";

  return <div className="min-h-screen bg-[#0f1117] text-slate-100">
    <FaqSchema />
    <main>
      <div className="site-container">
        <PageHeading eyebrow="The public record" title="Track record">
          <p>Published selections, recorded stakes and settled results. Review the sample behind the returns, including the losing bets.</p>
        </PageHeading>
        <p role="status" className="mb-4 text-sm text-slate-400">{statsNote}</p>
        <div className="grid gap-3 sm:grid-cols-3">{[
          ["Overall ROI", formatSignedPercent(displayStats.overall.roi)],
          ["Profit / loss", `${displayStats.overall.total_profit > 0 ? "+" : ""}${displayStats.overall.total_profit.toFixed(2)}u`],
          ["Settled bets", formatBetCount(displayStats.overall.total_bets)],
        ].map(([label,value]) => <div key={label} className="site-card"><div className="flex items-center justify-between gap-3"><p className="site-eyebrow">{label}</p><EditorialIcon name={label === "Overall ROI" ? "analysis" : label === "Settled bets" ? "guide" : "bankroll"} className="h-5 w-5" /></div><p className="mt-2 text-3xl font-semibold tabular-nums tracking-tight">{value}</p></div>)}</div>
        <p className="mt-4 max-w-3xl text-xs text-slate-400">{statsStatus !== "fallback" ? "Includes earlier recorded results and the current betting record." : "Earlier recorded results shown; recent results are currently unavailable."} Tracking began in October 2024. Returns use the recorded odds and stakes; they are not a forecast of future returns.</p>
        <details id="record-method" className="record-method mt-4 max-w-3xl scroll-mt-24"><summary className="cursor-pointer py-2 text-sm font-medium text-emerald-200">How this record is compiled</summary><p className="mt-2 text-sm leading-6 text-slate-400">The combined totals include earlier results preserved as aggregate summaries and the more recent record of individual bets. Earlier summaries do not provide a complete bet-by-bet audit trail; some category splits, win counts and stakes are reconstructed estimates. The individual history and monthly breakdown show the logged results available to inspect. We retain losing results as well as winning ones.</p></details>
        <section className="site-section" aria-labelledby="market-records">
          <div className="mb-5 flex flex-wrap items-end justify-between gap-3"><h2 id="market-records" className="text-2xl font-semibold">Explore the records</h2><span className="text-xs text-slate-400">{trackingRange}</span></div>
          <div className="grid gap-4 md:grid-cols-2">{([
            ["props", "Football player props", "/player-props#picks"],
            ["tennis", "Tennis", "/tennis-tips#picks"],
          ] as const).map(([key,title,href]) => <article key={key} className="site-card">
            <h3 className="text-lg font-semibold">{title}</h3>
            <dl className="my-5 grid grid-cols-3 gap-3">{[
              ["ROI", formatSignedPercent(displayStats[key].roi)],
              ["P/L", `${displayStats[key].total_profit > 0 ? "+" : ""}${displayStats[key].total_profit.toFixed(2)}u`],
              ["Bets", formatBetCount(displayStats[key].total_bets)],
            ].map(([label,value]) => <div key={label}><dt className="text-xs text-slate-400">{label}</dt><dd className="mt-1 text-xl font-semibold tabular-nums">{value}</dd></div>)}</dl>
            <SportCta sport={key === "props" ? "football" : "tennis"} href={href} label="Selections & results" />
          </article>)}</div>
        </section>
      </div>
      <MonthlyBreakdownSection scope="combined" initialPayload={initialMonthly} />
      <section className="site-container site-section">
        <div className="grid gap-8 lg:grid-cols-[.8fr_1.2fr]">
          <div><p className="site-eyebrow">Reading the evidence</p><h2 className="text-2xl font-semibold">More than a win rate.</h2><p className="mt-3 text-sm text-slate-300">ROI measures profit against the amount staked. Always read it alongside sample size, the prices available to you and the full results history.</p><Link className="site-text-link" href="/the-edge">Read our methodology →</Link></div>
          <div className="space-y-2">{FAQ_ITEMS.map(item => <details key={item.question} className="site-disclosure"><summary>{item.question}<span aria-hidden="true">+</span></summary><p>{item.answer}</p>{"cta" in item && <Link className="site-text-link" href={item.cta.href}>{item.cta.label} →</Link>}</details>)}</div>
        </div>
      </section>
    </main><Footer />
  </div>;
}
