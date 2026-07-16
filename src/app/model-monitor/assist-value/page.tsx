import fs from "node:fs";
import path from "node:path";

import Link from "next/link";
import { notFound } from "next/navigation";

import { HeroCard, MODEL_MONITOR_ENABLED, MonitorNav, SectionCard, StatCard, StatusPill } from "../shared";

type GateMetrics = {
  backtest?: {
    status?: string;
    splits?: { test?: { calibrated?: { n?: number; ece?: number; brier?: number } } };
    minutes?: { median5_mae?: number; mean8_mae?: number; selected?: string };
  };
  settlement?: {
    status?: string;
    extraction_status?: string;
    operational_status?: string;
    agreement_rate?: number;
    assist_complete_matches?: number;
    finished_matches?: number;
    instrumented_finished_matches?: number;
  };
  lineup_minutes?: { status?: string; confirmed_lineup_live_wiring?: boolean };
  market?: { status?: string; matched_participants?: number; reason?: string };
  prospective?: { signals?: number; target_minimum?: number; target_preferred?: number; status?: string };
  generated_at?: string;
  reactivation_ready?: boolean;
};

function loadResearchGates(): GateMetrics | null {
  try {
    const target = path.join(process.cwd(), "data", "assist-value", "research", "assist-value-gates.json");
    return JSON.parse(fs.readFileSync(target, "utf8")) as GateMetrics;
  } catch {
    return null;
  }
}

function percent(value?: number) {
  return typeof value === "number" ? `${(value * 100).toFixed(2)}%` : "pending";
}

export default function AssistValueMonitorPage() {
  if (!MODEL_MONITOR_ENABLED) {
    notFound();
  }

  const gates = loadResearchGates();
  const testMetrics = gates?.backtest?.splits?.test?.calibrated;
  const settlement = gates?.settlement;
  const prospective = gates?.prospective;

  return (
    <main className="min-h-screen bg-[#050b12] px-4 py-6 text-slate-100 sm:px-6 lg:px-8">
      <div className="mx-auto max-w-6xl space-y-5">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <Link href="/model-monitor" className="text-sm font-semibold text-emerald-300 hover:text-emerald-200">
            Back to model monitor
          </Link>
          <MonitorNav current="assist-value" />
        </div>

        <HeroCard title="Assist Value Research Archive" eyebrow="Frozen lane, measured rebuild in progress">
          <p className="max-w-3xl text-slate-400">
            Assist Value remains private and paused. Historical calibration and settlement now pass measured gates, but
            one-sided market pricing and prospective evidence still block any betting product.
          </p>
          <div className="mt-4 flex flex-wrap gap-2">
            <StatusPill label="frozen" tone="border-rose-500/25 bg-rose-500/10 text-rose-300" />
            <StatusPill label="not public" tone="border-amber-500/25 bg-amber-500/10 text-amber-300" />
            <StatusPill label="backtest measured" tone="border-emerald-500/25 bg-emerald-500/10 text-emerald-300" />
            <StatusPill label="manual research only" tone="border-slate-700 bg-slate-900/70 text-slate-300" />
          </div>
        </HeroCard>

        <section className="grid gap-3 sm:grid-cols-2 xl:grid-cols-5">
          <StatCard label="Product status" value="Paused" detail="No assist tips or fair-odds publication" tone="text-rose-300" />
          <StatCard
            label="Historical backtest"
            value={gates?.backtest?.status ?? "Pending"}
            detail={testMetrics ? `${testMetrics.n?.toLocaleString()} holdout rows | ECE ${percent(testMetrics.ece)}` : "Run the research gate builder"}
            tone={gates?.backtest?.status === "PASS" ? "text-emerald-300" : "text-amber-300"}
          />
          <StatCard
            label="Settlement"
            value={settlement?.status ?? "Pending"}
            detail={settlement ? `${percent(settlement.agreement_rate)} agreement | ${settlement.assist_complete_matches}/${settlement.instrumented_finished_matches} instrumented fixtures complete` : "Independent validation not run"}
            tone={settlement?.status === "PASS" ? "text-emerald-300" : "text-amber-300"}
          />
          <StatCard
            label="Lineups / minutes"
            value={gates?.lineup_minutes?.confirmed_lineup_live_wiring ? "Wired" : "Pending"}
            detail={gates?.backtest?.minutes ? `Median-5 MAE ${gates.backtest.minutes.median5_mae?.toFixed(2)} minutes` : "Confirmed-lineup gate not measured"}
            tone={gates?.lineup_minutes?.confirmed_lineup_live_wiring ? "text-emerald-300" : "text-amber-300"}
          />
          <StatCard
            label="Prospective proof"
            value={`${prospective?.signals ?? 0} / ${prospective?.target_minimum ?? 100}`}
            detail="Requires 100-150 locked v1 signals"
            tone="text-rose-300"
          />
        </section>

        <section className="grid gap-5 lg:grid-cols-2">
          <SectionCard title="What We Know" subtitle="Measured evidence, not a track record.">
            <div className="space-y-3 text-sm leading-6 text-slate-300">
              <p>The three-season walk-forward probability backtest passes its locked 2025-26 holdout.</p>
              <p>FotMob extraction accuracy and post-instrumentation settlement coverage pass independent validation.</p>
              <p>Bet365 exposes one-sided assist prices, so implied probability still contains an unknown player-market margin.</p>
              <p>No candidates, P/L chart or ROI panel is shown because no prospective v1 evidence exists.</p>
            </div>
          </SectionCard>

          <SectionCard title="Reactivation Gates" subtitle="Every gate must pass before this lane can return.">
            <ol className="space-y-3 text-sm leading-6 text-slate-300">
              <li><span className="font-semibold text-emerald-300">PASS 1.</span> Walk-forward backtest with a locked 2025-26 holdout.</li>
              <li><span className="font-semibold text-emerald-300">PASS 2.</span> Extraction accuracy and instrumented FotMob settlement coverage pass.</li>
              <li><span className="font-semibold text-amber-300">PARTIAL 3.</span> Median-five minutes and confirmed-lineup gating are wired but need prospective validation.</li>
              <li><span className="font-semibold text-rose-300">BLOCKED 4.</span> One-sided Bet365 margin cannot yet support fair market calibration or CLV.</li>
              <li><span className="font-semibold text-rose-300">NOT STARTED 5.</span> Collect at least 100-150 prospective v1 signals with credible ROI evidence.</li>
            </ol>
          </SectionCard>
        </section>

        <SectionCard title="Measured Evidence" subtitle={gates?.generated_at ? `Last rebuilt ${gates.generated_at}` : "Research artifacts not found"}>
          <div className="grid gap-3 text-sm sm:grid-cols-2 lg:grid-cols-4">
            <div className="rounded-xl border border-slate-800 bg-slate-950/60 p-4">
              <p className="text-xs uppercase tracking-[0.18em] text-slate-500">Holdout Brier</p>
              <p className="mt-2 text-xl font-semibold text-white">{testMetrics?.brier?.toFixed(5) ?? "pending"}</p>
            </div>
            <div className="rounded-xl border border-slate-800 bg-slate-950/60 p-4">
              <p className="text-xs uppercase tracking-[0.18em] text-slate-500">Assist agreement</p>
              <p className="mt-2 text-xl font-semibold text-emerald-300">{percent(settlement?.agreement_rate)}</p>
            </div>
            <div className="rounded-xl border border-slate-800 bg-slate-950/60 p-4">
              <p className="text-xs uppercase tracking-[0.18em] text-slate-500">Market matches</p>
              <p className="mt-2 text-xl font-semibold text-white">{gates?.market?.matched_participants?.toLocaleString() ?? "pending"}</p>
            </div>
            <div className="rounded-xl border border-slate-800 bg-slate-950/60 p-4">
              <p className="text-xs uppercase tracking-[0.18em] text-slate-500">Promotion</p>
              <p className="mt-2 text-xl font-semibold text-rose-300">{gates?.reactivation_ready ? "Ready" : "Hard blocked"}</p>
            </div>
          </div>
        </SectionCard>

        <div className="rounded-2xl border border-slate-800 bg-slate-950/55 px-5 py-4 text-sm leading-6 text-slate-400">
          Research code and evidence remain manual-only. Normal localhost startup and daily automation do not refresh or publish this lane.
        </div>
      </div>
    </main>
  );
}
