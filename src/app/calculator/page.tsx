"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import Footer from "@/components/Footer";
import PageHomeLink from "@/components/PageHomeLink";
import { track } from "@/lib/analytics";
import {
  BASELINE_STATS,
  calculateROI,
  calculateWinRate,
  getBaselineDisplayStats,
} from "@/lib/baseline";
import { supabase, CategoryStats } from "@/lib/supabase";

const FRACTION_PRESETS = [
  { value: 0.1, label: "0.1x", context: "Props" },
  { value: 0.25, label: "0.25x", context: "Tennis" },
  { value: 0.5, label: "0.5x", context: "Aggressive" },
  { value: 1, label: "Full", context: "Max risk" },
] as const;

const STAKE_PRESETS = [25, 50, 100, 250] as const;

interface RecordSummary {
  totalBets: number;
  wins: number;
  losses: number;
  roi: number;
  totalProfit: number;
  totalStake: number;
  source: "live" | "fallback";
}

function formatCurrency(value: number, maximumFractionDigits = 0): string {
  return new Intl.NumberFormat("en-GB", {
    style: "currency",
    currency: "GBP",
    maximumFractionDigits,
  }).format(value);
}

function formatCompactCurrency(value: number): string {
  if (Math.abs(value) >= 1000) {
    return `${formatCurrency(value / 1000, 1)}k`;
  }
  return formatCurrency(value);
}

function parseNum(s: string): number {
  const n = parseFloat(s.replace(/,/g, ""));
  return Number.isFinite(n) ? n : 0;
}

function kellyFraction(decimalOdds: number, winProbability: number): number | null {
  if (decimalOdds <= 1 || winProbability <= 0 || winProbability >= 1) return null;
  const b = decimalOdds - 1;
  const p = winProbability;
  const q = 1 - p;
  const f = (b * p - q) / b;
  return f <= 0 ? null : f;
}

function simulateKellyGrowth(
  bankroll: number,
  odds: number,
  probabilityPct: number,
  fraction: number,
  bets = 200
): number[] {
  const p = probabilityPct / 100;
  const rawKelly = kellyFraction(odds, p) ?? 0;
  const f = rawKelly * fraction;
  if (f <= 0 || f >= 1) return Array.from({ length: bets + 1 }, () => bankroll);

  const b = odds - 1;
  const q = 1 - p;
  const growth = Math.pow(1 + f * b, p) * Math.pow(1 - f, q);
  const pts = [bankroll];
  let balance = bankroll;
  for (let i = 0; i < bets; i += 1) {
    balance *= growth;
    pts.push(balance);
  }
  return pts;
}

function simulateReturnsCurve(
  startBankroll: number,
  totalBets: number,
  roi: number,
  stakePerBet: number
): number[] {
  const pts = [startBankroll];
  const profitPerBet = stakePerBet * (roi / 100);
  let balance = startBankroll;
  for (let i = 0; i < totalBets; i += 1) {
    balance += profitPerBet;
    pts.push(balance);
  }
  return pts;
}

function ChartShell({
  title,
  subtitle,
  children,
}: {
  title: string;
  subtitle?: string;
  children: React.ReactNode;
}) {
  return (
    <div className="rounded-xl border border-slate-700/40 bg-[#0c0f14] p-3">
      <div className="mb-3 flex items-baseline justify-between gap-3">
        <span className="text-[10px] font-mono font-bold uppercase tracking-[0.14em] text-slate-500">
          {title}
        </span>
        {subtitle ? (
          <span className="text-[10px] font-mono text-slate-600">{subtitle}</span>
        ) : null}
      </div>
      {children}
    </div>
  );
}

function EdgeMeter({
  edge,
  impliedProbability,
  yourProbability,
}: {
  edge: number;
  impliedProbability: number;
  yourProbability: number;
}) {
  const maxSpan = 15;
  const pct = Math.max(0, Math.min(100, (Math.abs(edge) / maxSpan) * 100));
  const positive = edge > 0;
  const tone = positive
    ? "text-emerald-400"
    : edge < 0
      ? "text-rose-400"
      : "text-slate-500";

  return (
    <div className="rounded-xl border border-slate-700/40 bg-[#0c0f14] px-4 py-3.5">
      <div className="mb-2.5 flex items-baseline justify-between">
        <span className="text-[10px] font-mono font-bold uppercase tracking-[0.14em] text-slate-500">
          Your edge
        </span>
        <span className={`font-mono text-lg font-extrabold tracking-tight ${tone}`}>
          {edge > 0 ? "+" : ""}
          {edge.toFixed(1)}pp
        </span>
      </div>
      <div className="relative h-1.5 overflow-hidden rounded-full bg-slate-700/40">
        <div
          className="absolute inset-y-0 left-0 rounded-full transition-all duration-500"
          style={{
            width: `${Math.max(2, pct)}%`,
            background: positive
              ? "linear-gradient(90deg, rgba(16,185,129,0.25), #22c55e)"
              : "linear-gradient(90deg, rgba(244,63,94,0.25), #f43f5e)",
          }}
        />
      </div>
      <div className="mt-2 flex justify-between text-[10px] font-mono text-slate-600">
        <span>
          Implied <span className="text-slate-400">{impliedProbability.toFixed(1)}%</span>
        </span>
        <span>
          Yours <span className={positive ? "text-emerald-400" : "text-slate-400"}>{yourProbability.toFixed(1)}%</span>
        </span>
      </div>
    </div>
  );
}

function GrowthChart({
  paths,
  baseline,
  width = 540,
  height = 210,
}: {
  paths: Array<{ label: string; color: string; active: boolean; pts: number[] }>;
  baseline: number;
  width?: number;
  height?: number;
}) {
  const allPoints = paths.flatMap((path) => path.pts);
  const maxV = Math.max(...allPoints, baseline * 1.1);
  const minV = Math.min(...allPoints, baseline * 0.7);
  const range = maxV - minV || 1;
  const padLeft = 54;
  const padRight = 14;
  const padTop = 20;
  const padBottom = 26;
  const chartW = width - padLeft - padRight;
  const chartH = height - padTop - padBottom;

  const x = (i: number, n: number) => padLeft + (i / Math.max(n - 1, 1)) * chartW;
  const y = (value: number) => padTop + (1 - (value - minV) / range) * chartH;

  const gridLines = Array.from({ length: 5 }, (_, i) => {
    const value = minV + (range * i) / 4;
    return { y: y(value), label: value >= 1000 ? `£${(value / 1000).toFixed(1)}k` : `£${value.toFixed(0)}` };
  });

  return (
    <svg viewBox={`0 0 ${width} ${height}`} className="block h-auto w-full">
      <defs>
        {paths.map((path, index) => (
          <linearGradient key={path.label} id={`kelly-gradient-${index}`} x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor={path.color} stopOpacity={path.active ? 0.22 : 0.06} />
            <stop offset="100%" stopColor={path.color} stopOpacity="0" />
          </linearGradient>
        ))}
      </defs>

      {gridLines.map((grid) => (
        <g key={grid.label}>
          <line x1={padLeft} y1={grid.y} x2={width - padRight} y2={grid.y} stroke="rgba(255,255,255,0.04)" strokeWidth="1" />
          <text x={padLeft - 8} y={grid.y + 3} textAnchor="end" fill="rgba(255,255,255,0.22)" fontSize="9" fontFamily="ui-monospace,SFMono-Regular,monospace">
            {grid.label}
          </text>
        </g>
      ))}

      <line x1={padLeft} y1={y(baseline)} x2={width - padRight} y2={y(baseline)} stroke="rgba(255,255,255,0.1)" strokeDasharray="4 3" strokeWidth="1" />

      {paths.map((path, index) => {
        const n = path.pts.length;
        const line = path.pts
          .map((value, i) => `${i === 0 ? "M" : "L"}${x(i, n).toFixed(1)},${y(value).toFixed(1)}`)
          .join(" ");
        const area = `${line} L${x(n - 1, n).toFixed(1)},${y(minV).toFixed(1)} L${x(0, n).toFixed(1)},${y(minV).toFixed(1)} Z`;
        const endValue = path.pts[n - 1];
        return (
          <g key={path.label}>
            <path d={area} fill={`url(#kelly-gradient-${index})`} />
            <path d={line} fill="none" stroke={path.color} strokeWidth={path.active ? 2.5 : 1} opacity={path.active ? 1 : 0.25} strokeLinejoin="round" />
            <circle cx={x(n - 1, n)} cy={y(endValue)} r={path.active ? 4 : 2} fill={path.color} opacity={path.active ? 1 : 0.35} />
            {path.active ? (
              <text x={x(n - 1, n) - 6} y={y(endValue) - 9} textAnchor="end" fill={path.color} fontSize="10" fontWeight="700" fontFamily="ui-monospace,SFMono-Regular,monospace">
                {endValue >= 1000 ? `£${(endValue / 1000).toFixed(1)}k` : `£${endValue.toFixed(0)}`}
              </text>
            ) : null}
          </g>
        );
      })}

      <text x={padLeft + chartW / 2} y={height - 3} textAnchor="middle" fill="rgba(255,255,255,0.18)" fontSize="8" fontFamily="ui-monospace,SFMono-Regular,monospace">
        bets →
      </text>
    </svg>
  );
}

function ReturnsChart({
  points,
  startBankroll,
  width = 540,
  height = 160,
}: {
  points: number[];
  startBankroll: number;
  width?: number;
  height?: number;
}) {
  const endValue = points[points.length - 1] ?? startBankroll;
  const returnPct = startBankroll > 0 ? ((endValue - startBankroll) / startBankroll) * 100 : 0;
  const maxV = Math.max(...points);
  const minV = Math.min(...points, startBankroll * 0.95);
  const range = maxV - minV || 1;
  const padLeft = 54;
  const padRight = 14;
  const padTop = 16;
  const padBottom = 22;
  const chartW = width - padLeft - padRight;
  const chartH = height - padTop - padBottom;
  const n = Math.max(points.length - 1, 1);

  const x = (i: number) => padLeft + (i / n) * chartW;
  const y = (value: number) => padTop + (1 - (value - minV) / range) * chartH;
  const line = points.map((value, i) => `${i === 0 ? "M" : "L"}${x(i).toFixed(1)},${y(value).toFixed(1)}`).join(" ");
  const area = `${line} L${x(n).toFixed(1)},${y(minV).toFixed(1)} L${x(0).toFixed(1)},${y(minV).toFixed(1)} Z`;

  return (
    <svg viewBox={`0 0 ${width} ${height}`} className="block h-auto w-full">
      <defs>
        <linearGradient id="returns-gradient" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor="#22c55e" stopOpacity="0.18" />
          <stop offset="100%" stopColor="#22c55e" stopOpacity="0" />
        </linearGradient>
      </defs>
      <line x1={padLeft} y1={y(startBankroll)} x2={width - padRight} y2={y(startBankroll)} stroke="rgba(255,255,255,0.08)" strokeDasharray="4 3" strokeWidth="1" />
      <text x={padLeft - 6} y={y(startBankroll) + 3} textAnchor="end" fill="rgba(255,255,255,0.25)" fontSize="9" fontFamily="ui-monospace,SFMono-Regular,monospace">
        {formatCompactCurrency(startBankroll)}
      </text>
      <path d={area} fill="url(#returns-gradient)" />
      <path d={line} fill="none" stroke="#22c55e" strokeWidth="2.5" strokeLinejoin="round" />
      <circle cx={x(n)} cy={y(points[n])} r="4" fill="#22c55e" />
      <text x={x(n) - 6} y={y(points[n]) - 9} textAnchor="end" fill="#22c55e" fontSize="11" fontWeight="700" fontFamily="ui-monospace,SFMono-Regular,monospace">
        {formatCompactCurrency(endValue)} ({returnPct >= 0 ? "+" : ""}{returnPct.toFixed(0)}%)
      </text>
      <text x={padLeft + chartW / 2} y={height - 3} textAnchor="middle" fill="rgba(255,255,255,0.15)" fontSize="8" fontFamily="ui-monospace,SFMono-Regular,monospace">
        settled bets →
      </text>
    </svg>
  );
}

export default function CalculatorPage() {
  const [activeTab, setActiveTab] = useState<"returns" | "kelly">("returns");
  const [recordSummary, setRecordSummary] = useState<RecordSummary>(() => {
    const baseline = getBaselineDisplayStats();
    return {
      totalBets: baseline.overall.total_bets,
      wins: BASELINE_STATS.overall.wins,
      losses: BASELINE_STATS.overall.losses,
      roi: baseline.overall.roi,
      totalProfit: baseline.overall.total_profit,
      totalStake: BASELINE_STATS.overall.total_stake,
      source: "fallback",
    };
  });

  const [bankroll, setBankroll] = useState("1000");
  const [odds, setOdds] = useState("2.10");
  const [probability, setProbability] = useState("54");
  const [fraction, setFraction] = useState<number>(0.25);

  const [stake, setStake] = useState("50");
  const [returnsBankroll, setReturnsBankroll] = useState("");

  const fetchData = useCallback(async () => {
    try {
      const { data } = await supabase.from("category_stats").select("*");
      const stats = data ?? [];
      const propsRows = stats.filter((s: CategoryStats) => s.market === "props");
      const tennisRows = stats.filter((s: CategoryStats) => s.market === "tennis");

      const propsLiveBets = propsRows.reduce((sum, s) => sum + (s.total_bets || 0), 0);
      const propsLiveWins = propsRows.reduce((sum, s) => sum + (s.wins || 0), 0);
      const propsLiveLosses = propsRows.reduce((sum, s) => sum + (s.losses || 0), 0);
      const propsLiveProfit = propsRows.reduce((sum, s) => sum + (Number(s.total_profit) || 0), 0);
      const propsLiveStake = propsRows.reduce((sum, s) => sum + (Number(s.total_stake) || 0), 0) || propsLiveBets;

      const tennisLiveBets = tennisRows.reduce((sum, s) => sum + (s.total_bets || 0), 0);
      const tennisLiveWins = tennisRows.reduce((sum, s) => sum + (s.wins || 0), 0);
      const tennisLiveLosses = tennisRows.reduce((sum, s) => sum + (s.losses || 0), 0);
      const tennisLiveProfit = tennisRows.reduce((sum, s) => sum + (Number(s.total_profit) || 0), 0);
      const tennisLiveStake = tennisRows.reduce((sum, s) => sum + (Number(s.total_stake) || 0), 0) || tennisLiveBets;

      const totalBets = BASELINE_STATS.props.total_bets + BASELINE_STATS.tennis.total_bets + propsLiveBets + tennisLiveBets;
      const wins = BASELINE_STATS.overall.wins + propsLiveWins + tennisLiveWins;
      const losses = BASELINE_STATS.overall.losses + propsLiveLosses + tennisLiveLosses;
      const totalProfit = BASELINE_STATS.overall.total_profit + propsLiveProfit + tennisLiveProfit;
      const totalStake = BASELINE_STATS.overall.total_stake + propsLiveStake + tennisLiveStake;

      setRecordSummary({
        totalBets,
        wins,
        losses,
        roi: calculateROI(totalProfit, totalStake || 1),
        totalProfit,
        totalStake,
        source: "live",
      });
      track("calculator_data_loaded", { roi_used: calculateROI(totalProfit, totalStake || 1), bets_count: totalBets });
    } catch {
      track("calculator_error", { type: "data_fetch" });
      const baseline = getBaselineDisplayStats();
      setRecordSummary({
        totalBets: baseline.overall.total_bets,
        wins: BASELINE_STATS.overall.wins,
        losses: BASELINE_STATS.overall.losses,
        roi: baseline.overall.roi,
        totalProfit: baseline.overall.total_profit,
        totalStake: BASELINE_STATS.overall.total_stake,
        source: "fallback",
      });
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

  const bankrollValue = Math.max(0, parseNum(bankroll));
  const oddsValue = parseNum(odds);
  const probabilityValue = Math.max(0, Math.min(100, parseNum(probability)));
  const probabilityDecimal = probabilityValue / 100;
  const rawKelly = kellyFraction(oddsValue, probabilityDecimal) ?? 0;
  const adjustedKelly = rawKelly * fraction;
  const adjustedKellyPct = adjustedKelly * 100;
  const adjustedStake = bankrollValue * adjustedKelly;
  const impliedProbability = oddsValue > 0 ? 100 / oddsValue : 0;
  const edge = probabilityValue - impliedProbability;
  const hasEdge = rawKelly > 0;

  const kellyPaths = useMemo(() => {
    const colors: Record<number, string> = {
      0.1: "#94a3b8",
      0.25: "#22c55e",
      0.5: "#f59e0b",
      1: "#ef4444",
    };

    return FRACTION_PRESETS.map((preset) => ({
      label: preset.label,
      color: colors[preset.value],
      active: preset.value === fraction,
      pts: simulateKellyGrowth(
        Math.max(bankrollValue, 1000),
        oddsValue > 1 ? oddsValue : 2.1,
        probabilityValue > 0 ? probabilityValue : 54,
        preset.value
      ),
    }));
  }, [bankrollValue, oddsValue, probabilityValue, fraction]);

  const stakeValue = Math.max(0, parseNum(stake));
  const totalStaked = stakeValue * recordSummary.totalBets;
  const flatProfit = totalStaked * (recordSummary.roi / 100);
  const returnsBankrollValue = Math.max(0, parseNum(returnsBankroll));
  const endingBalance = returnsBankrollValue > 0 ? returnsBankrollValue + flatProfit : null;
  const endingReturnPct =
    returnsBankrollValue > 0 ? (flatProfit / returnsBankrollValue) * 100 : null;
  const returnsPoints = useMemo(
    () =>
      returnsBankrollValue > 0 && stakeValue > 0
        ? simulateReturnsCurve(returnsBankrollValue, recordSummary.totalBets, recordSummary.roi, stakeValue)
        : [],
    [returnsBankrollValue, recordSummary.totalBets, recordSummary.roi, stakeValue]
  );

  const winRate = calculateWinRate(recordSummary.wins, recordSummary.losses);
  const inputClassName =
    "mt-1.5 block w-full rounded-lg border border-slate-600 bg-[#0c0f14] px-4 py-2.5 font-mono text-[15px] tabular-nums text-slate-100 placeholder:text-slate-500 focus:border-emerald-500/50 focus:outline-none focus:ring-1 focus:ring-emerald-500/30";
  const labelClassName =
    "text-[10px] font-mono font-bold uppercase tracking-[0.14em] text-slate-500";

  return (
    <div className="min-h-screen bg-[#0f1117] text-slate-200">
      <div
        className="pointer-events-none absolute inset-x-0 top-0 h-80"
        style={{
          background:
            "radial-gradient(ellipse 800px 320px at 50% -40px, rgba(16,185,129,0.10), transparent)",
        }}
      />

      <div className="relative mx-auto max-w-[940px] px-5 pb-20 pt-6">
        <PageHomeLink className="mb-8" />

        <div className="mb-8">
          <span className="text-[10px] font-mono font-bold uppercase tracking-[0.22em] text-emerald-400">
            Calculators
          </span>
          <h1 className="mt-2 text-[34px] font-semibold leading-tight tracking-tight text-slate-100">
            Betting calculators
          </h1>
          <p className="mt-3 max-w-xl text-[15px] leading-relaxed text-slate-400">
            Track returns from our settled bets, or size your stakes with the Kelly Criterion.
          </p>
        </div>

        <div className="overflow-hidden rounded-2xl border border-slate-700/50 bg-slate-800/50 shadow-lg">
          <div className="flex border-b border-slate-700/50">
            {[
              { key: "returns", label: "Returns" },
              { key: "kelly", label: "Kelly criterion" },
            ].map((tab) => (
              <button
                key={tab.key}
                type="button"
                onClick={() => setActiveTab(tab.key as "returns" | "kelly")}
                className={`border-b-2 px-6 py-3 text-[11px] font-mono font-bold uppercase tracking-[0.12em] transition-all ${
                  activeTab === tab.key
                    ? "border-emerald-400 text-white"
                    : "border-transparent text-slate-500 hover:text-slate-300"
                }`}
              >
                {tab.label}
              </button>
            ))}
          </div>

          {activeTab === "returns" ? (
            <div className="p-7">
              <div className="mb-2 flex flex-wrap items-center justify-between gap-3">
                <h2 className="text-xl font-semibold text-slate-100">Returns calculator</h2>
                <Link
                  href="/track-record"
                  className="text-[11px] font-mono font-bold uppercase tracking-[0.1em] text-emerald-400 transition-colors hover:text-emerald-300"
                >
                  View track record →
                </Link>
              </div>
              <p className="mb-6 max-w-lg text-sm leading-relaxed text-slate-400">
                What a flat-stake approach would have returned across our verified settled bets. No projections, just the record.
              </p>

              <div className="mb-5">
                <span className={labelClassName}>Stake per bet</span>
                <div className="mt-2 flex flex-wrap gap-2">
                  {STAKE_PRESETS.map((preset) => {
                    const active = stakeValue === preset;
                    return (
                      <button
                        key={preset}
                        type="button"
                        onClick={() => setStake(String(preset))}
                        className={`rounded-lg border px-5 py-2.5 font-mono text-[15px] font-bold transition-all ${
                          active
                            ? "border-emerald-400/50 bg-emerald-500/12 text-white shadow-[0_0_16px_rgba(16,185,129,0.08)]"
                            : "border-slate-600 bg-[#0c0f14] text-slate-500 hover:border-slate-500"
                        }`}
                      >
                        £{preset}
                      </button>
                    );
                  })}
                  <input
                    type="number"
                    placeholder="Custom"
                    value={STAKE_PRESETS.includes(stakeValue as (typeof STAKE_PRESETS)[number]) ? "" : stake}
                    onChange={(e) => setStake(e.target.value)}
                    onFocus={(e) => e.target.select()}
                    className="w-28 rounded-lg border border-slate-600 bg-[#0c0f14] px-4 py-2.5 font-mono text-[15px] text-slate-100 placeholder:text-slate-600 focus:border-emerald-500/50 focus:outline-none focus:ring-1 focus:ring-emerald-500/30"
                  />
                </div>
              </div>

              <div className="mb-5 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
                {[
                  {
                    label: "Total staked",
                    value: `£${totalStaked.toLocaleString(undefined, { maximumFractionDigits: 0 })}`,
                    sub: `${recordSummary.totalBets.toLocaleString()} settled bets`,
                    accent: false,
                  },
                  {
                    label: "Profit / loss",
                    value: `${flatProfit >= 0 ? "+" : ""}£${flatProfit.toLocaleString(undefined, { maximumFractionDigits: 0 })}`,
                    sub: `at £${stakeValue || 0}/bet`,
                    accent: true,
                  },
                  {
                    label: "ROI",
                    value: `${recordSummary.roi >= 0 ? "+" : ""}${recordSummary.roi.toFixed(1)}%`,
                    sub: recordSummary.source === "live" ? "live + baseline record" : "baseline record",
                    accent: true,
                  },
                  {
                    label: "Win rate",
                    value: `${winRate.toFixed(1)}%`,
                    sub: `${recordSummary.wins}W / ${recordSummary.losses}L`,
                    accent: false,
                  },
                ].map((stat) => (
                  <div
                    key={stat.label}
                    className={`rounded-xl border p-4 ${
                      stat.accent
                        ? "border-emerald-500/20 bg-emerald-500/[0.03]"
                        : "border-slate-700/40 bg-[#0c0f14]"
                    }`}
                  >
                    <div className={labelClassName}>{stat.label}</div>
                    <div className={`mt-1.5 font-mono text-xl font-bold tracking-tight ${stat.accent ? "text-emerald-400" : "text-slate-100"}`}>
                      {stat.value}
                    </div>
                    <div className="mt-1 font-mono text-[10px] text-slate-600">{stat.sub}</div>
                  </div>
                ))}
              </div>

              <div className="mb-5">
                <div className="mb-3 flex flex-wrap items-end gap-4">
                  <label className="block min-w-[220px] flex-1">
                    <span className={labelClassName}>Optional: starting bankroll (£)</span>
                  <input
                    type="number"
                    value={returnsBankroll}
                    onChange={(e) => setReturnsBankroll(e.target.value)}
                    onFocus={(e) => e.target.select()}
                    placeholder="e.g. 1000"
                    className={inputClassName}
                  />
                </label>
                {endingBalance != null ? (
                  <div className="pb-1">
                    <span className={labelClassName}>Ending balance</span>
                    <div className="mt-1 font-mono text-lg font-bold text-emerald-400">
                      {formatCurrency(endingBalance)}
                    </div>
                    {endingReturnPct != null ? (
                      <div className="font-mono text-[10px] text-slate-600">
                        {endingReturnPct >= 0 ? "+" : ""}
                        {endingReturnPct.toFixed(1)}% return
                      </div>
                    ) : null}
                  </div>
                ) : null}
              </div>

                {returnsPoints.length > 0 ? (
                  <ChartShell title="Illustrative bankroll curve" subtitle="flat stake · aggregate record">
                    <ReturnsChart points={returnsPoints} startBankroll={returnsBankrollValue} />
                  </ChartShell>
                ) : null}
                <p className="mt-2 text-[11px] font-mono leading-relaxed text-slate-600">
                  This curve is illustrative. It uses the aggregate settled record and
                  flat-stake ROI, not the exact historical order of wins and losses.
                </p>
              </div>

              {recordSummary.source === "fallback" ? (
                <div className="rounded-lg border border-amber-500/20 bg-amber-500/[0.05] px-4 py-3 text-sm text-amber-300">
                  Live track-record data is temporarily unavailable. Using the last recorded baseline numbers.
                </div>
              ) : null}
            </div>
          ) : (
            <div className="p-7">
              <div className="mb-2 flex flex-wrap items-center justify-between gap-3">
                <h2 className="text-xl font-semibold text-slate-100">Kelly Criterion</h2>
                <span className="inline-flex items-center gap-1.5 rounded-md border border-emerald-500/25 bg-emerald-500/8 px-2.5 py-1 text-[10px] font-mono font-bold uppercase tracking-[0.12em] text-emerald-300">
                  <span className="h-1.5 w-1.5 rounded-full bg-emerald-400 shadow-[0_0_6px_rgba(16,185,129,0.6)]" />
                  Pre-filled example
                </span>
              </div>
              <p className="mb-6 max-w-lg text-sm leading-relaxed text-slate-400">
                Adjust the fields and watch the stake update live.
                <button
                  type="button"
                  onClick={() => {
                    setBankroll("1000");
                    setOdds("2.10");
                    setProbability("54");
                    setFraction(0.25);
                  }}
                  className="ml-1 bg-transparent p-0 text-sm text-emerald-400 underline underline-offset-2 transition-colors hover:text-emerald-300"
                >
                  Reset to example
                </button>
                {" · "}
                <Link
                  href="/resources/kelly-criterion-sports-betting"
                  className="text-slate-500 transition-colors hover:text-emerald-400"
                >
                  Full guide {"->"}
                </Link>
              </p>

              <div className="mb-4 grid gap-4 md:grid-cols-3">
                <label className="block">
                  <span className={labelClassName}>Bankroll (GBP)</span>
                  <input
                    type="number"
                    value={bankroll}
                    onChange={(e) => setBankroll(e.target.value)}
                    onFocus={(e) => e.target.select()}
                    className={inputClassName}
                  />
                </label>
                <label className="block">
                  <span className={labelClassName}>Decimal odds</span>
                  <input
                    type="text"
                    value={odds}
                    onChange={(e) => setOdds(e.target.value)}
                    onFocus={(e) => e.target.select()}
                    className={inputClassName}
                  />
                </label>
                <label className="block">
                  <span className={labelClassName}>Win probability (%)</span>
                  <input
                    type="number"
                    value={probability}
                    onChange={(e) => setProbability(e.target.value)}
                    onFocus={(e) => e.target.select()}
                    className={inputClassName}
                  />
                </label>
              </div>

              <div className="mb-5">
                <EdgeMeter
                  edge={edge}
                  impliedProbability={impliedProbability}
                  yourProbability={probabilityValue}
                />
              </div>

              <div className="mb-5">
                <ChartShell title="Expected bankroll growth" subtitle="200 bets · fractional Kelly curves">
                  <GrowthChart paths={kellyPaths} baseline={Math.max(bankrollValue, 1000)} />
                </ChartShell>
                <div className="mt-3 flex flex-wrap gap-3">
                  {kellyPaths.map((path) => (
                    <button
                      key={path.label}
                      type="button"
                      onClick={() => {
                        const preset = FRACTION_PRESETS.find((item) => item.label === path.label);
                        if (preset) setFraction(preset.value);
                      }}
                      className="flex items-center gap-2 bg-transparent p-0 text-[10px] font-mono transition-opacity"
                      style={{ color: path.color, opacity: path.active ? 1 : 0.35 }}
                    >
                      <span
                        className="h-[3px] w-3 rounded-full"
                        style={{ backgroundColor: path.color }}
                      />
                      {path.label}
                    </button>
                  ))}
                </div>
              </div>

              <div className="mb-5">
                <span className={labelClassName}>Kelly fraction</span>
                <div className="mt-2 grid grid-cols-2 gap-2 md:grid-cols-4">
                  {FRACTION_PRESETS.map((preset) => {
                    const active = fraction === preset.value;
                    return (
                      <button
                        key={preset.label}
                        type="button"
                        onClick={() => setFraction(preset.value)}
                        className={`rounded-xl border px-3 py-3 text-center transition-all ${
                          active
                            ? "border-emerald-400/50 bg-emerald-500/12 shadow-[0_0_20px_rgba(16,185,129,0.10)]"
                            : "border-slate-600 bg-[#0c0f14] hover:border-slate-500"
                        }`}
                      >
                        <div className={`font-mono text-lg font-extrabold ${active ? "text-white" : "text-slate-500"}`}>
                          {preset.label}
                        </div>
                        <div className={`mt-0.5 font-mono text-[10px] ${active ? "text-emerald-400" : "text-slate-600"}`}>
                          {preset.context}
                        </div>
                      </button>
                    );
                  })}
                </div>
                <div className="mt-2 space-y-1 text-xs text-slate-500">
                  <p>
                    Prop bets {"->"} <span className="text-slate-300">use 0.1x</span>
                  </p>
                  <p>
                    Tennis / match markets {"->"} <span className="text-slate-300">use 0.25x</span>
                  </p>
                </div>
              </div>

              <div className="mb-4 grid gap-3 md:grid-cols-2">
                <div
                  className={`relative overflow-hidden rounded-xl border p-5 ${
                    hasEdge
                      ? "border-emerald-500/25 bg-emerald-500/[0.03]"
                      : "border-slate-700/50 bg-[#0c0f14]"
                  }`}
                >
                  {hasEdge ? (
                    <div
                      className="absolute left-[10%] right-[10%] top-0 h-px"
                      style={{
                        background:
                          "linear-gradient(90deg, transparent, rgba(16,185,129,0.45), transparent)",
                      }}
                    />
                  ) : null}
                  <div className={labelClassName}>Recommended stake</div>
                  <div className={`mt-2 font-mono text-3xl font-extrabold tracking-tight ${hasEdge ? "text-emerald-400" : "text-slate-600"}`}>
                    {formatCurrency(adjustedStake, 2)}
                  </div>
                  <div className="mt-1.5 font-mono text-[11px] text-slate-500">
                    {adjustedKellyPct.toFixed(2)}% of bankroll · {fraction}x Kelly
                  </div>
                </div>

                <div className="rounded-xl border border-slate-700/50 bg-[#0c0f14] p-5">
                  <div className={labelClassName}>Full Kelly (unreduced)</div>
                  <div className="mt-2 font-mono text-2xl font-bold tracking-tight text-slate-500">
                    {(rawKelly * 100).toFixed(1)}%
                  </div>
                  <div className="mt-1.5 font-mono text-[11px] text-slate-600">
                    {formatCurrency(bankrollValue * rawKelly)} at full size · too volatile for most bettors
                  </div>
                </div>
              </div>

              {!hasEdge ? (
                <div className="rounded-lg border border-rose-500/20 bg-rose-500/[0.05] px-4 py-3 font-mono text-[13px] text-rose-300">
                  No edge at these inputs. Kelly says do not bet.
                </div>
              ) : null}
            </div>
          )}
        </div>

        <div className="mt-12">
          <h2 className="mb-5 text-[11px] font-mono font-bold uppercase tracking-[0.2em] text-slate-500">
            How it works
          </h2>
          <div className="grid gap-3 md:grid-cols-2">
            {[
              {
                title: "Returns",
                steps: [
                  "Choose a flat stake: 25, 50, 100, 250, or your own number.",
                  "See total staked, profit/loss, ROI, and win rate from the verified record.",
                  "Add a starting bankroll to see an illustrative ending balance.",
                ],
              },
              {
                title: "Kelly Criterion",
                steps: [
                  "Enter bankroll, decimal odds, and your win probability estimate.",
                  "Pick a fraction: 0.1x for props, 0.25x for tennis, or larger if you accept more variance.",
                  "Read the recommended stake. If there is no edge, Kelly tells you not to bet.",
                ],
              },
            ].map((section) => (
              <div key={section.title} className="rounded-xl border border-slate-700/40 bg-slate-800/40 p-5">
                <span className="text-[10px] font-mono font-bold uppercase tracking-[0.14em] text-emerald-400">
                  {section.title}
                </span>
                <div className="mt-4 space-y-3">
                  {section.steps.map((step, index) => (
                    <div key={step} className="flex items-start gap-3">
                      <span className="mt-0.5 w-5 shrink-0 font-mono text-[11px] font-bold text-slate-700">
                        0{index + 1}
                      </span>
                      <span className="text-[13px] leading-relaxed text-slate-400">{step}</span>
                    </div>
                  ))}
                </div>
              </div>
            ))}
          </div>
        </div>

        <div className="mt-6 rounded-xl border border-emerald-500/15 bg-emerald-500/[0.03] px-5 py-4">
          <span className="text-[10px] font-mono font-bold uppercase tracking-[0.14em] text-emerald-400">
            Why fractional Kelly?
          </span>
          <p className="mt-2 text-[13px] leading-relaxed text-slate-400">
            Full Kelly maximises long-term growth but creates violent drawdowns. Quarter Kelly gives up some theoretical growth in exchange for much lower variance. We use 0.1x for props and 0.25x for tennis.
            {" "}
            <Link
              href="/resources/kelly-criterion-sports-betting"
              className="text-emerald-400 transition-colors hover:text-emerald-300"
            >
              Read the full guide {"->"}
            </Link>
          </p>
        </div>

        <div className="mt-10">
          <h2 className="mb-4 text-[11px] font-mono font-bold uppercase tracking-[0.2em] text-slate-500">
            FAQ
          </h2>
          {[
            {
              question: "What do these calculators show?",
              answer:
                "The Returns Calculator shows what you would have won or lost following our settled bets at a chosen stake. The Kelly Calculator computes the stake for any bet from your bankroll, the odds, and your estimated win probability. Both use real arithmetic. Neither is a prediction of future results.",
            },
            {
              question: "What if live data is unavailable?",
              answer:
                "If the live results feed is temporarily down, the Returns Calculator falls back to the last recorded baseline numbers. The Kelly Calculator always works because it uses only your inputs.",
            },
          ].map((item) => (
            <details
              key={item.question}
              className="mb-2 overflow-hidden rounded-xl border border-slate-700/40 bg-slate-800/40 group"
            >
              <summary className="flex cursor-pointer list-none items-center justify-between px-5 py-3.5 text-[14px] font-medium text-slate-200 transition-colors hover:bg-slate-700/20">
                {item.question}
                <span className="ml-3 shrink-0 text-emerald-400/60 transition-transform group-open:rotate-180">
                  <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M19 9l-7 7-7-7" />
                  </svg>
                </span>
              </summary>
              <div className="border-t border-slate-700/30 px-5 py-3.5 text-[13px] leading-relaxed text-slate-400">
                {item.answer}
              </div>
            </details>
          ))}
        </div>

        <div className="mt-8 rounded-xl border border-amber-500/15 bg-amber-500/[0.03] px-5 py-3.5 text-[13px] leading-relaxed text-slate-400">
          <strong className="text-amber-400/90">Responsible gambling:</strong> Past performance does not guarantee future results. Only bet what you can afford to lose.
          {" "}
          <a href="https://www.begambleaware.org" className="text-slate-300 underline underline-offset-2">
            BeGambleAware
          </a>
          {" · "}
          <a href="https://www.gamcare.org.uk" className="text-slate-300 underline underline-offset-2">
            GamCare
          </a>
        </div>
      </div>

      <Footer />
    </div>
  );
}
