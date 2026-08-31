import type { SegmentStats } from "@/components/bookmakers/segment-stats";
import { formatMargin } from "@/components/bookmakers/segment-stats";

export default function MarginBenchmarkStrip({ stats }: { stats: SegmentStats }) {
  const cheapestCount = stats.rows.filter((row) => row.gapToBest < 0.005).length;
  const dearestCount = stats.rows.filter(
    (row) => Math.abs(row.normalized_hold_pct - stats.dearest.normalized_hold_pct) < 0.005,
  ).length;
  const benchmarks = [
    {
      label: "Cheapest",
      value: formatMargin(stats.cheapest.normalized_hold_pct),
      detail: cheapestCount > 1 ? `${cheapestCount} books tied` : stats.cheapest.name,
      className: "text-emerald-200",
    },
    {
      label: "Median",
      value: formatMargin(stats.median),
      detail: `${stats.rows.length} books measured`,
      className: "text-cyan-100",
    },
    {
      label: "Dearest",
      value: formatMargin(stats.dearest.normalized_hold_pct),
      detail: dearestCount > 1 ? `${dearestCount} books tied` : stats.dearest.name,
      className: "text-amber-100",
    },
    {
      label: "Market spread",
      value: `${stats.spread.toFixed(2)}pp`,
      detail: "cheapest to dearest",
      className: "text-white",
    },
  ];

  return (
    <dl className="grid grid-cols-2 gap-px overflow-hidden rounded-2xl border border-white/[0.08] bg-white/[0.08] lg:grid-cols-4">
      {benchmarks.map((benchmark) => (
        <div key={benchmark.label} className="min-w-0 bg-[#0a1016] px-4 py-4 sm:px-5">
          <dt className="text-[9px] font-semibold uppercase tracking-[0.19em] text-slate-500">
            {benchmark.label}
          </dt>
          <dd className={`mt-2 font-mono text-xl font-semibold tabular-nums sm:text-2xl ${benchmark.className}`}>
            {benchmark.value}
          </dd>
          <dd className="mt-1 truncate text-[11px] text-slate-400" title={benchmark.detail}>
            {benchmark.detail}
          </dd>
        </div>
      ))}
    </dl>
  );
}
