"use client";

import { useState, useEffect, useCallback } from "react";
import Link from "next/link";
import { supabase, CategoryStats } from "@/lib/supabase";
import { BASELINE_STATS, calculateROI, getBaselineDisplayStats } from "@/lib/baseline";
import { track } from "@/lib/analytics";
import Footer from "@/components/Footer";
import TelegramButton from "@/components/TelegramButton";
import CalculatorCard, { type CalculatorData } from "@/components/calculator/CalculatorCard";
import HowItWorks from "@/components/calculator/HowItWorks";
import AssumptionsCallout from "@/components/calculator/AssumptionsCallout";
import FaqAccordion from "@/components/calculator/FaqAccordion";

interface CombinedMarketStats {
  total_bets: number;
  roi: number;
  total_profit: number;
  total_stake: number;
}

function computeOverallROI(
  props: CombinedMarketStats,
  tennis: CombinedMarketStats
): number {
  const totalProfit = props.total_profit + tennis.total_profit;
  const totalStake = props.total_stake + tennis.total_stake;
  return calculateROI(totalProfit, totalStake || 1);
}

export default function CalculatorPage() {
  const [loading, setLoading] = useState(true);
  const [categoryStats, setCategoryStats] = useState<CategoryStats[]>([]);
  const [combinedStats, setCombinedStats] = useState<{
    props: CombinedMarketStats;
    tennis: CombinedMarketStats;
  } | null>(null);
  const [calculatorData, setCalculatorData] = useState<CalculatorData | null>(null);

  const fetchData = useCallback(async () => {
    setLoading(true);
    try {
      const [statsRes, betsRes] = await Promise.all([
        supabase.from("category_stats").select("*"),
        supabase.from("bets").select("market, stake").in("status", ["won", "lost"]),
      ]);

      const stats = statsRes.data ?? [];
      if (stats.length) setCategoryStats(stats);

      const settledBets = betsRes.data ?? [];
      const liveStakeByMarket = {
        props: settledBets.filter((b) => b.market === "props").reduce((sum, b) => sum + (Number(b.stake) || 0), 0),
        tennis: settledBets.filter((b) => b.market === "tennis").reduce((sum, b) => sum + (Number(b.stake) || 0), 0),
      };

      const propsRows = stats.filter((s: CategoryStats) => s.market === "props");
      const tennisRows = stats.filter((s: CategoryStats) => s.market === "tennis");

      const propsLiveBets = propsRows.reduce((sum, s) => sum + (s.total_bets || 0), 0);
      const propsLiveProfit = propsRows.reduce((sum, s) => sum + (Number(s.total_profit) || 0), 0);
      const propsLiveStake = liveStakeByMarket.props > 0 ? liveStakeByMarket.props : propsLiveBets;
      const tennisLiveBets = tennisRows.reduce((sum, s) => sum + (s.total_bets || 0), 0);
      const tennisLiveProfit = tennisRows.reduce((sum, s) => sum + (Number(s.total_profit) || 0), 0);
      const tennisLiveStake = liveStakeByMarket.tennis > 0 ? liveStakeByMarket.tennis : tennisLiveBets;

      const propsProfit = BASELINE_STATS.props.total_profit + propsLiveProfit;
      const propsStake = BASELINE_STATS.props.total_stake + propsLiveStake;
      const tennisProfit = BASELINE_STATS.tennis.total_profit + tennisLiveProfit;
      const tennisStake = BASELINE_STATS.tennis.total_stake + tennisLiveStake;

      const propsCombined: CombinedMarketStats = {
        total_bets: BASELINE_STATS.props.total_bets + propsLiveBets,
        roi: calculateROI(propsProfit, propsStake || 1),
        total_profit: propsProfit,
        total_stake: propsStake,
      };
      const tennisCombined: CombinedMarketStats = {
        total_bets: BASELINE_STATS.tennis.total_bets + tennisLiveBets,
        roi: calculateROI(tennisProfit, tennisStake || 1),
        total_profit: tennisProfit,
        total_stake: tennisStake,
      };

      setCombinedStats({ props: propsCombined, tennis: tennisCombined });
      const overallROI = computeOverallROI(propsCombined, tennisCombined);
      const nBets = propsCombined.total_bets + tennisCombined.total_bets;
      setCalculatorData({ roi: overallROI, nBets, source: "live" });
      track("calculator_data_loaded", { roi_used: overallROI, bets_count: nBets });
    } catch (e) {
      track("calculator_error", { type: "data_fetch" });
      const baseline = getBaselineDisplayStats();
      const fallbackRoi = baseline.overall.roi;
      const fallbackBets = baseline.overall.total_bets;
      setCalculatorData({ roi: fallbackRoi, nBets: fallbackBets, source: "fallback" });
      track("calculator_data_loaded", { roi_used: fallbackRoi, bets_count: fallbackBets, fallback: true });
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    track("calculator_view");
    fetchData();

    const channel = supabase
      .channel("calculator-bets-changes")
      .on("postgres_changes", { event: "*", schema: "public", table: "bets" }, () => fetchData())
      .subscribe();
    return () => {
      supabase.removeChannel(channel);
    };
  }, [fetchData]);

  // Fallback when no combined stats yet (e.g. empty DB) but no throw
  const displayData = calculatorData ?? (() => {
    const baseline = getBaselineDisplayStats();
    return { roi: baseline.overall.roi, nBets: baseline.overall.total_bets, source: "fallback" as const };
  })();

  return (
    <div className="min-h-screen bg-[#0f1117] text-slate-100">
      {/* Breadcrumbs */}
      <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 pt-4">
        <div className="flex items-center gap-2 text-sm">
          <Link href="/" className="text-slate-500 hover:text-slate-300 transition-colors">Home</Link>
          <span className="text-slate-600">/</span>
          <span className="text-emerald-400 font-medium">Calculator</span>
        </div>
      </div>

      {/* Hero: calculator first on mobile, two columns on desktop */}
      <section className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 pt-6 pb-12 md:pt-8 md:pb-16 border-b border-slate-800/50">
        <div className="grid lg:grid-cols-2 gap-10 lg:gap-12 items-start">
          {/* Left column: H1, What this calculator shows, body. On mobile order-2 so calculator is first. */}
          <div className="lg:order-1 order-2">
            <h1 className="text-[34px] sm:text-[40px] md:text-[44px] font-semibold text-slate-100 mb-6 tracking-tight">
              Returns Calculator
            </h1>
            <h2 className="text-xl sm:text-2xl font-semibold text-slate-100 mb-3">
              What this calculator shows
            </h2>
            <p className="text-base text-slate-300 max-w-prose leading-relaxed mb-4">
              This calculator shows how much you would have won or lost if you had followed our settled bets using a fixed stake per bet (e.g. £25, £50, £100).
              Results are based only on our verified historical track record (player props + ATP tennis). No projections, no simulations.
              If live data is temporarily unavailable, we use the last recorded results and show a notice.
            </p>
            <div className="flex flex-wrap gap-2">
              {["Verified track record", "Settled bets only", "No projections"].map((label) => (
                <span
                  key={label}
                  className="text-xs font-medium text-slate-400 bg-slate-800/60 border border-slate-700/50 px-3 py-1.5 rounded-lg"
                >
                  {label}
                </span>
              ))}
            </div>
          </div>
          {/* Right column: Calculator card. On mobile order-1 (first). */}
          <div className="lg:order-2 order-1">
            <CalculatorCard loading={loading} data={displayData} />
            {displayData.source === "fallback" && (
              <p className="mt-3 text-sm text-amber-400/90">
                Data notice: Live updates are temporarily unavailable. Results are calculated using the last recorded settled-bets performance.
              </p>
            )}
          </div>
        </div>
      </section>

      {/* How it works */}
      <section className="py-12 md:py-16 border-b border-slate-800/50">
        <HowItWorks />
      </section>

      {/* Assumptions (collapsed) */}
      <section className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 py-10">
        <AssumptionsCallout />
      </section>

      {/* Mind the margin: slim full-width divider (subtle brand transition before FAQ) */}
      <section
        className="relative w-full overflow-hidden border-y border-slate-800/50"
        aria-hidden
      >
        <div className="absolute inset-0 flex items-center justify-center">
          <img
            src="/banner-mind-the-margin.png"
            alt=""
            className="w-full max-w-4xl object-contain object-center opacity-[0.18] select-none pointer-events-none"
          />
        </div>
        <div className="relative py-6 md:py-8 min-h-[72px] flex items-center justify-center">
          <span className="text-slate-500/80 text-sm font-medium tracking-wide">
            Mind the margin.
          </span>
        </div>
      </section>

      {/* FAQ accordion */}
      <section className="py-12 md:py-16 border-b border-slate-800/50">
        <div className="px-4 sm:px-6 lg:px-8">
          <FaqAccordion />
        </div>
      </section>

      {/* Responsible gambling notice */}
      <section className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 py-10">
        <div className="rounded-xl border border-amber-500/20 bg-amber-500/5 p-5">
          <p className="text-sm text-slate-300 leading-relaxed">
            <strong className="text-amber-400/95">Responsible gambling:</strong> Past performance does not guarantee future results. These calculations are illustrative. Only bet what you can afford to lose. If you need help, visit BeGambleAware or GamCare.
          </p>
        </div>
      </section>

      {/* Telegram CTA - subtle */}
      <section className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 py-12">
        <div className="rounded-xl border border-slate-700/50 bg-slate-800/40 p-6 text-center">
          <p className="text-slate-300 font-medium mb-2">Want picks in real time?</p>
          <p className="text-sm text-slate-500 mb-4">Join our free Telegram channel for player props and updates.</p>
          <TelegramButton
            variant="cta"
            onClick={() => track("telegram_click", { placement: "calculator" })}
          />
        </div>
      </section>

      <Footer className="mt-12" />
    </div>
  );
}
