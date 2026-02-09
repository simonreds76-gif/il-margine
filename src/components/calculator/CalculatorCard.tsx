"use client";

import { useState, useCallback } from "react";
import { track } from "@/lib/analytics";

const UNIT_PCT_MIN = 0.25;
const UNIT_PCT_MAX = 5;

export interface CalculatorData {
  roi: number;
  source: "live" | "fallback";
}

interface CalculatorCardProps {
  loading: boolean;
  data: CalculatorData | null;
}

export default function CalculatorCard({ loading, data }: CalculatorCardProps) {
  const [bankroll, setBankroll] = useState<string>("");
  const [unitPct, setUnitPct] = useState<string>("1");
  const [totalStakeUnits, setTotalStakeUnits] = useState<string>("100");
  const [touched, setTouched] = useState({ bankroll: false, unitPct: false, totalStake: false });
  const [hasCalculated, setHasCalculated] = useState(false);

  const roi = data?.roi ?? 0;
  const roiSource = data?.source ?? "fallback";

  const parseNum = (s: string): number => {
    const n = parseFloat(s.replace(/,/g, ""));
    return Number.isFinite(n) ? n : 0;
  };

  const bankrollVal = parseNum(bankroll);
  const unitPctVal = parseNum(unitPct);
  const totalStakeVal = parseNum(totalStakeUnits);

  const unitPctError =
    touched.unitPct &&
    (unitPctVal < UNIT_PCT_MIN || unitPctVal > UNIT_PCT_MAX
      ? `Enter ${UNIT_PCT_MIN} to ${UNIT_PCT_MAX}%`
      : unitPctVal < 0
        ? "Must be positive"
        : null);
  const totalStakeError =
    touched.totalStake && (totalStakeVal < 0 ? "Must be 0 or more" : null);
  const bankrollError = touched.bankroll && bankrollVal < 0 ? "Must be 0 or more" : null;

  const expectedProfitUnits = totalStakeVal * (roi / 100);
  const unitSizePounds = bankrollVal > 0 && unitPctVal > 0 ? (bankrollVal * unitPctVal) / 100 : 0;
  const expectedProfitPounds = expectedProfitUnits * unitSizePounds;
  const endingBankroll = bankrollVal > 0 ? bankrollVal + expectedProfitPounds : null;

  const handleCalculate = useCallback(() => {
    setTouched({ bankroll: true, unitPct: true, totalStake: true });
    if (
      totalStakeVal < 0 ||
      unitPctVal < UNIT_PCT_MIN ||
      unitPctVal > UNIT_PCT_MAX ||
      bankrollVal < 0
    ) {
      track("calculator_error", { type: "validation" });
      return;
    }
    setHasCalculated(true);
    track("calculator_calculate", {
      roi_used: roi,
      bankroll: bankrollVal || undefined,
      unit_size: unitPctVal,
      total_stake: totalStakeVal,
      profit_estimate: expectedProfitUnits,
    });
  }, [
    totalStakeVal,
    unitPctVal,
    bankrollVal,
    roi,
    expectedProfitUnits,
  ]);

  const handleReset = useCallback(() => {
    setBankroll("");
    setUnitPct("1");
    setTotalStakeUnits("100");
    setTouched({ bankroll: false, unitPct: false, totalStake: false });
    setHasCalculated(false);
    track("calculator_reset");
  }, []);

  const fireInputChange = useCallback((field: string) => {
    track("calculator_input_change", { field_name: field });
  }, []);

  if (loading) {
    return (
      <div
        className="rounded-2xl border border-slate-700/50 bg-slate-800/50 p-6 sm:p-8 shadow-lg min-h-[320px] flex flex-col justify-between"
        aria-busy="true"
      >
        <div className="space-y-4">
          <div className="h-4 w-24 rounded bg-slate-700/60 animate-pulse" />
          <div className="grid gap-3 sm:grid-cols-2">
            {[1, 2, 3, 4].map((i) => (
              <div key={i} className="h-12 rounded-lg bg-slate-700/50 animate-pulse" />
            ))}
          </div>
          <div className="h-10 w-full rounded-lg bg-slate-700/40 animate-pulse" />
          <div className="h-10 w-24 rounded-lg bg-slate-700/40 animate-pulse" />
        </div>
        <div className="mt-6 flex gap-3">
          <div className="h-11 flex-1 rounded-lg bg-slate-700/50 animate-pulse" />
          <div className="h-11 w-24 rounded-lg bg-slate-700/50 animate-pulse" />
        </div>
      </div>
    );
  }

  return (
    <div className="rounded-2xl border border-slate-700/50 bg-slate-800/50 p-6 sm:p-8 shadow-lg">
      <div className="space-y-4">
        <label className="block">
          <span className="text-xs font-mono text-slate-500 uppercase tracking-wider">Bankroll (£, optional)</span>
          <input
            type="text"
            inputMode="decimal"
            placeholder="e.g. 1000"
            value={bankroll}
            onChange={(e) => {
              setBankroll(e.target.value);
              fireInputChange("bankroll");
            }}
            onBlur={() => setTouched((t) => ({ ...t, bankroll: true }))}
            className="mt-1 block w-full rounded-lg border border-slate-600 bg-slate-900/80 px-4 py-2.5 font-mono text-slate-100 tabular-nums placeholder:text-slate-500 focus:border-emerald-500/50 focus:outline-none focus:ring-1 focus:ring-emerald-500/30"
            aria-invalid={bankrollError ? true : undefined}
            aria-describedby={bankrollError ? "bankroll-err" : undefined}
          />
          {bankrollError && (
            <p id="bankroll-err" className="mt-1 text-xs text-red-400">{bankrollError}</p>
          )}
        </label>

        <label className="block">
          <span className="text-xs font-mono text-slate-500 uppercase tracking-wider">Unit size (%)</span>
          <input
            type="text"
            inputMode="decimal"
            placeholder="1"
            value={unitPct}
            onChange={(e) => {
              setUnitPct(e.target.value);
              fireInputChange("unit_size");
            }}
            onBlur={() => setTouched((t) => ({ ...t, unitPct: true }))}
            className="mt-1 block w-full rounded-lg border border-slate-600 bg-slate-900/80 px-4 py-2.5 font-mono text-slate-100 tabular-nums placeholder:text-slate-500 focus:border-emerald-500/50 focus:outline-none focus:ring-1 focus:ring-emerald-500/30"
            aria-invalid={unitPctError ? true : undefined}
            aria-describedby={unitPctError ? "unitpct-err" : undefined}
          />
          {unitPctError && (
            <p id="unitpct-err" className="mt-1 text-xs text-red-400">{unitPctError}</p>
          )}
          <p className="mt-0.5 text-xs text-slate-500">Recommended 0.25 to 5%</p>
        </label>

        <label className="block">
          <span className="text-xs font-mono text-slate-500 uppercase tracking-wider">Total stake (units over period)</span>
          <input
            type="text"
            inputMode="decimal"
            placeholder="e.g. 100"
            value={totalStakeUnits}
            onChange={(e) => {
              setTotalStakeUnits(e.target.value);
              fireInputChange("total_stake");
            }}
            onBlur={() => setTouched((t) => ({ ...t, totalStake: true }))}
            className="mt-1 block w-full rounded-lg border border-slate-600 bg-slate-900/80 px-4 py-2.5 font-mono text-slate-100 tabular-nums placeholder:text-slate-500 focus:border-emerald-500/50 focus:outline-none focus:ring-1 focus:ring-emerald-500/30"
            aria-invalid={totalStakeError ? true : undefined}
            aria-describedby={totalStakeError ? "stake-err" : undefined}
          />
          {totalStakeError && (
            <p id="stake-err" className="mt-1 text-xs text-red-400">{totalStakeError}</p>
          )}
        </label>

        {/* Read-only: ROI used */}
        <div className="rounded-lg border border-slate-700/50 bg-slate-900/40 px-4 py-3">
          <span className="text-xs font-mono text-slate-500 uppercase tracking-wider">Historical ROI used</span>
          <p className="mt-0.5 font-mono text-lg tabular-nums text-slate-100">
            {roi >= 0 ? "+" : ""}{roi.toFixed(1)}%
          </p>
          {roiSource === "fallback" && (
            <p className="mt-1 text-xs text-amber-400/90">Using last known ROI</p>
          )}
        </div>

        {hasCalculated && (
          <>
            <div className="rounded-lg border border-emerald-500/20 bg-emerald-500/5 px-4 py-3">
              <span className="text-xs font-mono text-slate-500 uppercase tracking-wider">Expected profit (units)</span>
              <p className={`mt-0.5 font-mono text-xl tabular-nums ${expectedProfitUnits >= 0 ? "text-emerald-400" : "text-red-400"}`}>
                {expectedProfitUnits >= 0 ? "+" : ""}{expectedProfitUnits.toFixed(1)}u
              </p>
            </div>
            {bankrollVal > 0 && unitPctVal > 0 && (
              <div className="rounded-lg border border-slate-700/50 bg-slate-900/40 px-4 py-3">
                <span className="text-xs font-mono text-slate-500 uppercase tracking-wider">Expected profit (£)</span>
                <p className={`mt-0.5 font-mono text-xl tabular-nums ${expectedProfitPounds >= 0 ? "text-emerald-400" : "text-red-400"}`}>
                  {expectedProfitPounds >= 0 ? "+" : ""}£{Math.abs(expectedProfitPounds).toLocaleString(undefined, { minimumFractionDigits: 0, maximumFractionDigits: 0 })}
                </p>
                <span className="text-xs font-mono text-slate-500 uppercase tracking-wider mt-2 block">Illustrative ending bankroll</span>
                <p className="mt-0.5 font-mono text-lg tabular-nums text-slate-100">
                  £{endingBankroll != null ? endingBankroll.toLocaleString(undefined, { minimumFractionDigits: 0, maximumFractionDigits: 0 }) : "—"}
                </p>
              </div>
            )}
          </>
        )}
      </div>

      <div className="mt-6 flex flex-wrap gap-3">
        <button
          type="button"
          onClick={handleCalculate}
          className="flex-1 min-w-[120px] rounded-lg bg-emerald-500 hover:bg-emerald-400 text-slate-900 font-semibold py-2.5 px-4 transition-colors focus:outline-none focus:ring-2 focus:ring-emerald-400 focus:ring-offset-2 focus:ring-offset-slate-900"
        >
          Calculate
        </button>
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
