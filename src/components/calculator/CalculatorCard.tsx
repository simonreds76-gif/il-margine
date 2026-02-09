"use client";

import { useState, useCallback } from "react";
import { track } from "@/lib/analytics";

const PRESETS = [25, 50, 100] as const;

export interface CalculatorData {
  roi: number;
  nBets: number;
  source: "live" | "fallback";
}

interface CalculatorCardProps {
  loading: boolean;
  data: CalculatorData | null;
}

function parseNum(s: string): number {
  const n = parseFloat(s.replace(/,/g, ""));
  return Number.isFinite(n) ? n : 0;
}

export default function CalculatorCard({ loading, data }: CalculatorCardProps) {
  const [stakePerBet, setStakePerBet] = useState<string>("25");
  const [bankroll, setBankroll] = useState<string>("");

  const roi = data?.roi ?? 0;
  const nBets = data?.nBets ?? 0;
  const source = data?.source ?? "fallback";

  const stakeVal = Math.max(0, parseNum(stakePerBet));
  const bankrollVal = parseNum(bankroll);

  const totalStakedGbp = stakeVal * nBets;
  const profitGbp = totalStakedGbp * (roi / 100);
  const endingBankroll = bankrollVal > 0 ? bankrollVal + profitGbp : null;

  const handlePreset = useCallback(
    (amount: number) => {
      setStakePerBet(String(amount));
      const totalStaked = amount * nBets;
      const profit = totalStaked * (roi / 100);
      track("calculator_calculate", {
        stake_per_bet: amount,
        bankroll_optional: bankrollVal || undefined,
        roi_used: roi,
        bets_count: nBets,
        profit_gbp: profit,
      });
    },
    [bankrollVal, roi, nBets]
  );

  const handleReset = useCallback(() => {
    setStakePerBet("25");
    setBankroll("");
    track("calculator_reset");
  }, []);

  if (loading) {
    return (
      <div
        className="rounded-2xl border border-slate-700/50 bg-slate-800/50 p-6 sm:p-8 shadow-lg min-h-[340px] flex flex-col justify-between"
        aria-busy="true"
      >
        <div className="space-y-4">
          <div className="h-4 w-32 rounded bg-slate-700/60 animate-pulse" />
          <div className="flex gap-2">
            {[1, 2, 3].map((i) => (
              <div key={i} className="h-10 flex-1 rounded-lg bg-slate-700/50 animate-pulse" />
            ))}
          </div>
          <div className="h-12 rounded-lg bg-slate-700/50 animate-pulse" />
          <div className="h-12 rounded-lg bg-slate-700/50 animate-pulse" />
        </div>
        <div className="mt-6 grid grid-cols-2 gap-3">
          {[1, 2, 3, 4].map((i) => (
            <div key={i} className="h-16 rounded-lg bg-slate-700/40 animate-pulse" />
          ))}
        </div>
      </div>
    );
  }

  return (
    <div className="rounded-2xl border border-slate-700/50 bg-slate-800/50 p-6 sm:p-8 shadow-lg">
      <div className="space-y-4">
        {/* Preset buttons */}
        <div>
          <span className="text-xs font-mono text-slate-500 uppercase tracking-wider">Stake per bet</span>
          <div className="mt-2 flex gap-2">
            {PRESETS.map((amount) => (
              <button
                key={amount}
                type="button"
                onClick={() => handlePreset(amount)}
                className={`flex-1 rounded-lg border py-2.5 px-3 font-mono text-sm font-medium tabular-nums transition-colors focus:outline-none focus:ring-2 focus:ring-emerald-500 focus:ring-offset-2 focus:ring-offset-slate-800 ${
                  stakeVal === amount
                    ? "border-emerald-500/50 bg-emerald-500/20 text-emerald-400"
                    : "border-slate-600 bg-slate-900/80 text-slate-300 hover:border-slate-500"
                }`}
              >
                £{amount} per bet
              </button>
            ))}
          </div>
        </div>

        <label className="block">
          <span className="text-xs font-mono text-slate-500 uppercase tracking-wider">Stake per bet (£)</span>
          <input
            type="text"
            inputMode="decimal"
            placeholder="25"
            value={stakePerBet}
            onChange={(e) => {
              setStakePerBet(e.target.value);
              track("calculator_input_change", { field_name: "stake_per_bet" });
            }}
            className="mt-1 block w-full rounded-lg border border-slate-600 bg-slate-900/80 px-4 py-2.5 font-mono text-slate-100 tabular-nums placeholder:text-slate-500 focus:border-emerald-500/50 focus:outline-none focus:ring-1 focus:ring-emerald-500/30"
            aria-label="Stake per bet in pounds"
          />
          <p className="mt-0.5 text-xs text-slate-500">Example: 25, 50, 100</p>
        </label>

        <label className="block">
          <span className="text-xs font-mono text-slate-500 uppercase tracking-wider">Starting bankroll (£) (optional)</span>
          <input
            type="text"
            inputMode="decimal"
            placeholder="1000"
            value={bankroll}
            onChange={(e) => {
              setBankroll(e.target.value);
              track("calculator_input_change", { field_name: "bankroll_optional" });
            }}
            className="mt-1 block w-full rounded-lg border border-slate-600 bg-slate-900/80 px-4 py-2.5 font-mono text-slate-100 tabular-nums placeholder:text-slate-500 focus:border-emerald-500/50 focus:outline-none focus:ring-1 focus:ring-emerald-500/30"
            aria-label="Starting bankroll in pounds, optional"
          />
          <p className="mt-0.5 text-xs text-slate-500">Only used to show bankroll growth</p>
        </label>
      </div>

      {/* Outputs */}
      {data && nBets > 0 && (
        <div className="mt-6 space-y-3">
          <div className="rounded-lg border border-slate-700/50 bg-slate-900/40 px-4 py-3">
            <span className="text-xs font-mono text-slate-500 uppercase tracking-wider">Number of settled bets used</span>
            <p className="mt-0.5 font-mono text-lg tabular-nums text-slate-100">{nBets.toLocaleString()}</p>
          </div>
          <div className="rounded-lg border border-slate-700/50 bg-slate-900/40 px-4 py-3">
            <span className="text-xs font-mono text-slate-500 uppercase tracking-wider">Total staked</span>
            <p className="mt-0.5 font-mono text-lg tabular-nums text-slate-100">
              £{totalStakedGbp.toLocaleString(undefined, { minimumFractionDigits: 0, maximumFractionDigits: 0 })}
            </p>
          </div>
          <div className="rounded-lg border border-slate-700/50 bg-slate-900/40 px-4 py-3">
            <span className="text-xs font-mono text-slate-500 uppercase tracking-wider">Profit / Loss</span>
            <p className={`mt-0.5 font-mono text-xl tabular-nums ${profitGbp >= 0 ? "text-emerald-400" : "text-red-400"}`}>
              {profitGbp >= 0 ? "+" : ""}£{profitGbp.toLocaleString(undefined, { minimumFractionDigits: 0, maximumFractionDigits: 2 })}
            </p>
          </div>
          <div className="rounded-lg border border-slate-700/50 bg-slate-900/40 px-4 py-3">
            <span className="text-xs font-mono text-slate-500 uppercase tracking-wider">ROI</span>
            <p className={`mt-0.5 font-mono text-xl tabular-nums ${roi >= 0 ? "text-emerald-400" : "text-red-400"}`}>
              {roi >= 0 ? "+" : ""}{roi.toFixed(1)}%
            </p>
          </div>
          {bankrollVal > 0 && endingBankroll != null && (
            <div className="rounded-lg border border-emerald-500/20 bg-emerald-500/5 px-4 py-3">
              <span className="text-xs font-mono text-slate-500 uppercase tracking-wider">Ending bankroll</span>
              <p className="mt-0.5 font-mono text-xl tabular-nums text-slate-100">
                £{endingBankroll.toLocaleString(undefined, { minimumFractionDigits: 0, maximumFractionDigits: 0 })}
              </p>
            </div>
          )}
        </div>
      )}

      <div className="mt-6">
        <button
          type="button"
          onClick={handleReset}
          className="rounded-lg border border-slate-600 hover:border-slate-500 text-slate-300 font-medium py-2.5 px-4 transition-colors focus:outline-none focus:ring-2 focus:ring-slate-500 focus:ring-offset-2 focus:ring-offset-slate-900"
        >
          Reset
        </button>
      </div>
    </div>
  );
}
