import Link from "next/link";
import { notFound } from "next/navigation";

import { HeroCard, MODEL_MONITOR_ENABLED, MonitorNav, SectionCard, StatCard, StatusPill } from "../shared";

export default function AssistValueMonitorPage() {
  if (!MODEL_MONITOR_ENABLED) {
    notFound();
  }

  return (
    <main className="min-h-screen bg-[#050b12] px-4 py-6 text-slate-100 sm:px-6 lg:px-8">
      <div className="mx-auto max-w-6xl space-y-5">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <Link href="/model-monitor" className="text-sm font-semibold text-emerald-300 hover:text-emerald-200">
            Back to model monitor
          </Link>
          <MonitorNav current="assist-value" />
        </div>

        <HeroCard title="Assist Value Research Archive" eyebrow="Frozen lane, not a betting product">
          <p className="max-w-3xl text-slate-400">
            Assist Value is preserved for future research, but automatic refreshes and candidate displays are disabled.
            The existing model was never backtested, and its settlement record is not valid promotion evidence.
          </p>
          <div className="mt-4 flex flex-wrap gap-2">
            <StatusPill label="frozen" tone="border-rose-500/25 bg-rose-500/10 text-rose-300" />
            <StatusPill label="not public" tone="border-amber-500/25 bg-amber-500/10 text-amber-300" />
            <StatusPill label="not backtested" tone="border-amber-500/25 bg-amber-500/10 text-amber-300" />
            <StatusPill label="manual refresh only" tone="border-slate-700 bg-slate-900/70 text-slate-300" />
          </div>
        </HeroCard>

        <section className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
          <StatCard label="Product status" value="Paused" detail="No assist tips or fair-odds publication" tone="text-rose-300" />
          <StatCard label="Backtest" value="Missing" detail="No validated historical probability test" tone="text-amber-300" />
          <StatCard label="Settlement" value="Invalid for ROI" detail="FotMob extraction remains under review" tone="text-rose-300" />
          <StatCard label="Source layer" value="Preserved" detail="RotoWire roles plus FPL validation" tone="text-emerald-300" />
        </section>

        <section className="grid gap-5 lg:grid-cols-2">
          <SectionCard title="Why It Is Frozen" subtitle="The last shadow output is a diagnostic, not a track record.">
            <div className="space-y-3 text-sm leading-6 text-slate-300">
              <p>The model has no held-out historical backtest or calibrated market comparison.</p>
              <p>Bet365 exposes one-sided assist prices, so the old probability comparison did not remove bookmaker margin.</p>
              <p>The last reviewed sample was only 12 settled candidates: 1 win, 8 losses and 3 voids, with settlement still under review.</p>
              <p>No current candidates, P/L chart or ROI panel is shown because those numbers are not decision-grade.</p>
            </div>
          </SectionCard>

          <SectionCard title="Reactivation Gates" subtitle="Every gate must pass before this lane can return.">
            <ol className="space-y-3 text-sm leading-6 text-slate-300">
              <li><span className="font-semibold text-white">1.</span> Build a walk-forward historical assist backtest with held-out seasons.</li>
              <li><span className="font-semibold text-white">2.</span> Revalidate FotMob assist extraction and resettle the archived ledger.</li>
              <li><span className="font-semibold text-white">3.</span> Model confirmed lineups, expected minutes and set-piece role changes.</li>
              <li><span className="font-semibold text-white">4.</span> Calibrate against market prices and account for one-sided margin.</li>
              <li><span className="font-semibold text-white">5.</span> Collect at least 100–150 prospective signals with credible ROI and CLV evidence.</li>
            </ol>
          </SectionCard>
        </section>

        <div className="rounded-2xl border border-slate-800 bg-slate-950/55 px-5 py-4 text-sm leading-6 text-slate-400">
          The model scripts, source-role audit and historical artifacts remain in the repository. They can be refreshed only through an explicit manual research run; normal localhost startup and daily automation no longer refresh this lane.
        </div>
      </div>
    </main>
  );
}
