"use client";

import { useState, useCallback } from "react";
import Link from "next/link";

const FRACTION_PRESETS = [
  { label: "0.1x", value: 0.1 },
  { label: "0.25x", value: 0.25 },
  { label: "0.5x", value: 0.5 },
  { label: "Full", value: 1 },
] as const;

function parseNum(s: string): number {
  const n = parseFloat(s.replace(/,/g, ""));
  return Number.isFinite(n) ? n : 0;
}

/**
 * Kelly Criterion: f* = (bp - q) / b
 * b = decimal odds - 1
 * p = win probability (0-1)
 * q = 1 - p
 */
function kellyFraction(
  decimalOdds: number,
  winProbability: number
): number | null {
  if (decimalOdds <= 1 || winProbability <= 0 || winProbability >= 1) return null;
  const b = decimalOdds - 1;
  const p = winProbability;
  const q = 1 - p;
  const f = (b * p - q) / b;
  return f <= 0 ? null : f;
}

export default function KellyCalculatorCard() {
  const [bankroll, setBankroll] = useState<string>("1000");
  const [decimalOdds, setDecimalOdds] = useState<string>("2.10");
  const [winProbability, setWinProbability] = useState<string>("54");
  const [fraction, setFraction] = useState<number>(0.25);

  const bankrollVal = Math.max(0, parseNum(bankroll));
  const oddsVal = parseNum(decimalOdds);
  const probVal = Math.max(0, Math.min(100, parseNum(winProbability))) / 100;

  const fullKelly =
    oddsVal > 1 && probVal > 0 && probVal < 1
      ? kellyFraction(oddsVal, probVal)
      : null;

  const displayKelly = fullKelly != null ? fullKelly * fraction : null;
  const stakePct = displayKelly != null ? displayKelly * 100 : null;
  const stakeAmount =
    bankrollVal > 0 && stakePct != null ? (bankrollVal * stakePct) / 100 : null;

  const hasNoEdge = fullKelly === null && oddsVal > 1 && probVal > 0 && probVal < 1;
  const invalidInputs = oddsVal <= 1 || probVal <= 0 || probVal >= 1;

  const handleReset = useCallback(() => {
    setBankroll("1000");
    setDecimalOdds("2.10");
    setWinProbability("54");
    setFraction(0.25);
  }, []);

  return (
    <div className="rounded-2xl border border-slate-700/50 bg-slate-800/50 p-6 shadow-lg sm:p-8">
      <div className="mb-6 rounded-xl border border-emerald-500/20 bg-emerald-500/8 px-4 py-3">
        <span className="text-[11px] font-mono uppercase tracking-[0.22em] text-emerald-300">
          Example loaded
        </span>
        <p className="mt-1 text-sm text-slate-300">
          Recent ATP tennis selection: £1,000 bankroll, 2.10 odds, 54% win probability, quarter Kelly.
        </p>
      </div>

      <div className="space-y-4">
        <label className="block">
          <span className="text-xs font-mono uppercase tracking-wider text-slate-500">
            Bankroll (£)
          </span>
          <input
            type="text"
            inputMode="decimal"
            placeholder="1000"
            value={bankroll}
            onChange={(e) => setBankroll(e.target.value)}
            className="mt-1 block w-full rounded-lg border border-slate-600 bg-slate-900/80 px-4 py-2.5 font-mono tabular-nums text-slate-100 placeholder:text-slate-500 focus:border-emerald-500/50 focus:outline-none focus:ring-1 focus:ring-emerald-500/30"
            aria-label="Bankroll in pounds"
          />
        </label>

        <label className="block">
          <span className="text-xs font-mono uppercase tracking-wider text-slate-500">
            Decimal odds
          </span>
          <input
            type="text"
            inputMode="decimal"
            placeholder="2.10"
            value={decimalOdds}
            onChange={(e) => setDecimalOdds(e.target.value)}
            className="mt-1 block w-full rounded-lg border border-slate-600 bg-slate-900/80 px-4 py-2.5 font-mono tabular-nums text-slate-100 placeholder:text-slate-500 focus:border-emerald-500/50 focus:outline-none focus:ring-1 focus:ring-emerald-500/30"
            aria-label="Decimal odds"
          />
          <p className="mt-0.5 text-xs text-slate-500">Example: 2.10, 1.91, 2.40</p>
        </label>

        <label className="block">
          <span className="text-xs font-mono uppercase tracking-wider text-slate-500">
            Your win probability (%)
          </span>
          <input
            type="text"
            inputMode="decimal"
            placeholder="54"
            value={winProbability}
            onChange={(e) => setWinProbability(e.target.value)}
            className="mt-1 block w-full rounded-lg border border-slate-600 bg-slate-900/80 px-4 py-2.5 font-mono tabular-nums text-slate-100 placeholder:text-slate-500 focus:border-emerald-500/50 focus:outline-none focus:ring-1 focus:ring-emerald-500/30"
            aria-label="Estimated win probability as percentage"
          />
          <p className="mt-0.5 text-xs text-slate-500">Your edge estimate (0–100)</p>
        </label>

        <div>
          <span className="text-xs font-mono uppercase tracking-wider text-slate-500">
            Kelly fraction
          </span>
          <div className="mt-2 flex flex-wrap gap-2">
            {FRACTION_PRESETS.map(({ label, value }) => (
              <button
                key={value}
                type="button"
                onClick={() => setFraction(value)}
                className={`flex-1 rounded-lg border px-3 py-2.5 font-mono text-sm font-medium transition-all focus:outline-none focus:ring-2 focus:ring-emerald-500 focus:ring-offset-2 focus:ring-offset-slate-800 ${
                  fraction === value
                    ? "border-emerald-400/70 bg-emerald-500/20 text-emerald-200 shadow-[0_0_24px_rgba(16,185,129,0.18)]"
                    : "border-slate-600 bg-slate-900/80 text-slate-300 hover:border-slate-500"
                }`}
              >
                {label}
              </button>
            ))}
          </div>
          <div className="mt-2 space-y-1 text-xs text-slate-400">
            <p>
              <span className="font-medium text-slate-300">Prop bets</span> → use 0.1x
            </p>
            <p>
              <span className="font-medium text-slate-300">Tennis / match markets</span> → use 0.25x
            </p>
          </div>
        </div>
      </div>

      <div className="mt-6 space-y-3">
        {invalidInputs ? (
          <p className="text-sm text-slate-500">
            Enter valid odds greater than 1 and a probability between 0 and 100%.
          </p>
        ) : hasNoEdge ? (
          <div className="rounded-lg border border-amber-500/30 bg-amber-500/10 px-4 py-4">
            <span className="font-semibold text-amber-400">Don&apos;t bet</span>
            <p className="mt-1 text-sm text-slate-300">
              Kelly returns zero or negative. There is no edge at these odds given your probability estimate.
            </p>
          </div>
        ) : displayKelly != null && displayKelly > 0 ? (
          <>
            <div className="rounded-lg border border-slate-700/50 bg-slate-900/40 px-4 py-3">
              <span className="text-xs font-mono uppercase tracking-wider text-slate-500">
                Recommended stake (% of bankroll)
              </span>
              <p className="mt-0.5 font-mono text-xl tabular-nums text-emerald-400">
                {stakePct!.toFixed(2)}%
              </p>
            </div>
            {bankrollVal > 0 && stakeAmount != null && (
              <div className="rounded-lg border border-emerald-500/20 bg-emerald-500/5 px-4 py-3">
                <span className="text-xs font-mono uppercase tracking-wider text-slate-500">
                  Recommended stake
                </span>
                <p className="mt-0.5 font-mono text-xl tabular-nums text-slate-100">
                  £{stakeAmount.toFixed(2)}
                </p>
              </div>
            )}
            {displayKelly > 0.05 && (
              <p className="text-xs text-amber-400/90">
                Full Kelly suggests more than 5% of bankroll. Consider quarter or half Kelly to cut variance.
              </p>
            )}
          </>
        ) : null}
      </div>

      <div className="mt-6 flex flex-wrap items-center gap-3">
        <button
          type="button"
          onClick={handleReset}
          className="rounded-lg border border-slate-600 px-4 py-2.5 font-medium text-slate-300 transition-colors hover:border-slate-500 focus:outline-none focus:ring-2 focus:ring-slate-500 focus:ring-offset-2 focus:ring-offset-slate-900"
        >
          Reset example
        </button>
        <Link
          href="/resources/kelly-criterion-sports-betting"
          className="text-sm text-slate-500 transition-colors hover:text-emerald-400"
        >
          Learn more about Kelly →
        </Link>
      </div>
    </div>
  );
}
