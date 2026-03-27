"use client";

import { useState, useEffect, useCallback } from "react";
import Link from "next/link";
import { supabase, CategoryStats } from "@/lib/supabase";
import { BASELINE_STATS, calculateROI, getBaselineDisplayStats } from "@/lib/baseline";
import { track } from "@/lib/analytics";
import Footer from "@/components/Footer";
import CalculatorCard, { type CalculatorData } from "@/components/calculator/CalculatorCard";
import KellyCalculatorCard from "@/components/calculator/KellyCalculatorCard";
import HowItWorks from "@/components/calculator/HowItWorks";
import AssumptionsCallout from "@/components/calculator/AssumptionsCallout";
import FaqAccordion from "@/components/calculator/FaqAccordion";
import PageHomeLink from "@/components/PageHomeLink";

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
  const [calculatorData, setCalculatorData] = useState<CalculatorData | null>(null);

  const fetchData = useCallback(async () => {
    setLoading(true);
    try {
      const { data } = await supabase.from("category_stats").select("*");
      const stats = data ?? [];

      const propsRows = stats.filter((s: CategoryStats) => s.market === "props");
      const tennisRows = stats.filter((s: CategoryStats) => s.market === "tennis");

      const propsLiveBets = propsRows.reduce((sum, s) => sum + (s.total_bets || 0), 0);
      const propsLiveProfit = propsRows.reduce((sum, s) => sum + (Number(s.total_profit) || 0), 0);
      const propsLiveStake =
        propsRows.reduce((sum, s) => sum + (Number(s.total_stake) || 0), 0) || propsLiveBets;
      const tennisLiveBets = tennisRows.reduce((sum, s) => sum + (s.total_bets || 0), 0);
      const tennisLiveProfit =
        tennisRows.reduce((sum, s) => sum + (Number(s.total_profit) || 0), 0);
      const tennisLiveStake =
        tennisRows.reduce((sum, s) => sum + (Number(s.total_stake) || 0), 0) || tennisLiveBets;

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

      const overallROI = computeOverallROI(propsCombined, tennisCombined);
      const nBets = propsCombined.total_bets + tennisCombined.total_bets;
      setCalculatorData({ roi: overallROI, nBets, source: "live" });
      track("calculator_data_loaded", { roi_used: overallROI, bets_count: nBets });
    } catch (_e) {
      track("calculator_error", { type: "data_fetch" });
      const baseline = getBaselineDisplayStats();
      const fallbackRoi = baseline.overall.roi;
      const fallbackBets = baseline.overall.total_bets;
      setCalculatorData({ roi: fallbackRoi, nBets: fallbackBets, source: "fallback" });
      track("calculator_data_loaded", {
        roi_used: fallbackRoi,
        bets_count: fallbackBets,
        fallback: true,
      });
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

  const displayData =
    calculatorData ??
    (() => {
      const baseline = getBaselineDisplayStats();
      return {
        roi: baseline.overall.roi,
        nBets: baseline.overall.total_bets,
        source: "fallback" as const,
      };
    })();

  return (
    <div className="min-h-screen bg-[#0f1117] text-slate-100">
      <section className="border-b border-slate-800/50 pb-12 pt-6 md:pb-16">
        <div className="mx-auto max-w-6xl px-4 sm:px-6 lg:px-8">
          <PageHomeLink className="mb-8" />
          <span className="mb-3 block text-xs font-mono tracking-wider text-emerald-400">
            CALCULATORS
          </span>
          <h1 className="text-3xl font-semibold text-slate-100 sm:text-4xl">
            Betting calculators
          </h1>
          <p className="mt-4 max-w-3xl text-base leading-relaxed text-slate-400 sm:text-lg">
            Track your returns from our settled bets, or size your stakes with the Kelly Criterion.
          </p>

          <div className="mt-10 grid items-start gap-10 lg:grid-cols-2 lg:gap-12">
            <div className="space-y-4">
              <div>
                <h2 className="mb-2 text-xl font-semibold text-slate-100">
                  Returns calculator
                </h2>
                <p className="mb-4 text-sm leading-relaxed text-slate-400">
                  See what a flat-stake approach would have returned across our settled bets.
                  Based on our{" "}
                  <Link
                    href="/track-record"
                    className="text-emerald-400 underline underline-offset-2 transition-colors hover:text-emerald-300"
                  >
                    verified track record
                  </Link>
                  . No projections.
                </p>
              </div>
              <CalculatorCard loading={loading} data={displayData} />
              {displayData.source === "fallback" && (
                <p className="text-sm text-amber-400/90">
                  Data notice: Live updates temporarily unavailable. Using last recorded results.
                </p>
              )}
            </div>

            <div className="flex items-center gap-4 text-slate-600 lg:hidden">
              <div className="h-px flex-1 bg-slate-800/70" />
              <span className="text-[11px] font-mono uppercase tracking-[0.24em]">Or</span>
              <div className="h-px flex-1 bg-slate-800/70" />
            </div>

            <div className="space-y-4">
              <div>
                <h2 className="mb-2 text-xl font-semibold text-slate-100">
                  Kelly criterion calculator
                </h2>
                <p className="mb-4 text-sm leading-relaxed text-slate-400">
                  Size a stake from your edge: bankroll, price, probability, then choose
                  the Kelly fraction that fits the market.
                </p>
              </div>
              <KellyCalculatorCard />
            </div>
          </div>
        </div>
      </section>

      <section className="border-b border-slate-800/50 py-12 md:py-16">
        <HowItWorks />
      </section>

      <section className="border-b border-slate-800/50 py-10">
        <div className="mx-auto max-w-6xl px-4 sm:px-6 lg:px-8">
          <div className="rounded-2xl border border-emerald-500/20 bg-emerald-500/6 p-6 sm:p-7">
            <span className="text-xs font-mono uppercase tracking-[0.22em] text-emerald-300">
              Why we use fractional Kelly
            </span>
            <p className="mt-3 max-w-3xl text-sm leading-relaxed text-slate-300 sm:text-base">
              We use one-tenth Kelly for player props and quarter Kelly for tennis. Full
              Kelly maximizes long-run bankroll growth on paper, but it also creates
              violent swings in the real world. Fractional Kelly gives up a little growth
              to cut variance dramatically.
            </p>
            <Link
              href="/resources/kelly-criterion-sports-betting"
              className="mt-4 inline-flex items-center gap-2 text-sm text-emerald-400 transition-colors hover:text-emerald-300"
            >
              Read the full Kelly guide →
            </Link>
          </div>
        </div>
      </section>

      <section className="mx-auto max-w-6xl px-4 py-10 sm:px-6 lg:px-8">
        <AssumptionsCallout />
      </section>

      <section className="border-b border-slate-800/50 py-12 md:py-16">
        <div className="px-4 sm:px-6 lg:px-8">
          <FaqAccordion />
        </div>
      </section>

      <section className="mx-auto max-w-6xl px-4 py-10 sm:px-6 lg:px-8">
        <div className="rounded-xl border border-amber-500/20 bg-amber-500/5 p-5">
          <p className="text-sm leading-relaxed text-slate-300">
            <strong className="text-amber-400/95">Responsible gambling:</strong> Past
            performance does not guarantee future results. These calculations are
            illustrative. Only bet what you can afford to lose. If you need help, visit
            BeGambleAware or GamCare.
          </p>
        </div>
      </section>

      <section className="mx-auto max-w-6xl px-4 py-12 sm:px-6 lg:px-8">
        <div className="rounded-xl border border-slate-700/50 bg-slate-800/40 p-6 text-center">
          <p className="mb-2 font-medium text-slate-300">Looking for today&apos;s picks?</p>
          <p className="mb-4 text-sm text-slate-500">
            All selections are posted free on the website with full analysis.
          </p>
          <a
            href="/tennis-tips"
            className="inline-flex items-center gap-2 rounded-lg bg-emerald-500 px-6 py-3 font-semibold text-white transition-colors hover:bg-emerald-400"
          >
            View Tips
          </a>
        </div>
      </section>

      <Footer className="mt-12" />
    </div>
  );
}
