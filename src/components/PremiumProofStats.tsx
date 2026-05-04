"use client";

import { useCallback, useEffect, useState } from "react";
import { getBaselineDisplayStats } from "@/lib/baseline";
import { type MarketStats } from "@/lib/supabase";
import {
  buildCombinedDisplayStats,
  formatBetCount,
  formatCashExample,
  formatSignedPercent,
  type DisplayStats,
} from "@/lib/public-record-display";

type PublicRecordPayload = {
  stats?: MarketStats[];
};

function ProofTile({ label, value, sub, accent = false }: { label: string; value: string; sub: string; accent?: boolean }) {
  return (
    <div className={`rounded-2xl border p-5 ${accent ? "border-emerald-500/25 bg-emerald-500/[0.055]" : "border-slate-700/45 bg-[#0c0f14]"}`}>
      <div className="text-[10px] font-mono font-bold uppercase tracking-[0.16em] text-slate-500">{label}</div>
      <div className={`mt-3 font-mono text-3xl font-black tracking-tight tabular-nums ${accent ? "text-emerald-300" : "text-slate-100"}`}>
        {value}
      </div>
      <p className="mt-2 text-sm leading-relaxed text-slate-500">{sub}</p>
    </div>
  );
}

export default function PremiumProofStats() {
  const [displayStats, setDisplayStats] = useState<DisplayStats>(() => getBaselineDisplayStats());
  const [status, setStatus] = useState<"baseline" | "live" | "fallback">("baseline");

  const fetchStats = useCallback(async () => {
    try {
      const res = await fetch("/api/public-record?scope=home", { cache: "no-store" });
      if (!res.ok) throw new Error("Failed to load public record");
      const payload = (await res.json()) as PublicRecordPayload;
      setDisplayStats(buildCombinedDisplayStats(payload.stats ?? []));
      setStatus("live");
    } catch {
      setStatus("fallback");
    }
  }, []);

  useEffect(() => {
    void fetchStats();
  }, [fetchStats]);

  return (
    <div>
      <div className="grid gap-3 md:grid-cols-4">
        <ProofTile
          label="Tracked cash example"
          value={formatCashExample(displayStats.overall.total_profit)}
          sub={`Current props + tennis P/L if 1u equals ${String.fromCharCode(163)}100.`}
          accent
        />
        <ProofTile
          label="Combined ROI"
          value={formatSignedPercent(displayStats.overall.roi)}
          sub="Stake-weighted ROI across the public record."
        />
        <ProofTile
          label="Settled sample"
          value={formatBetCount(displayStats.overall.total_bets)}
          sub="Football player props plus ATP tennis."
        />
        <ProofTile
          label="Win rate"
          value={`${displayStats.overall.win_rate.toFixed(1)}%`}
          sub="Useful context, but ROI is the headline measure."
        />
      </div>
      <p className="mt-3 font-mono text-[10px] uppercase tracking-[0.14em] text-slate-600">
        {status === "live" ? "Live record loaded from the public ledger." : "Baseline record shown while the live ledger loads."}
      </p>
    </div>
  );
}
