import type { SegmentStats } from "@/components/bookmakers/segment-stats";
import { formatMargin } from "@/components/bookmakers/segment-stats";
import BookmakerMark from "@/components/bookmakers/BookmakerMark";
import EditorialIcon from "@/components/EditorialIcon";

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
      book: cheapestCount === 1 ? stats.cheapest.name : null,
    },
    {
      label: "Median",
      value: formatMargin(stats.median),
      detail: `${stats.rows.length} books measured`,
      className: "text-cyan-100",
      book: null,
    },
    {
      label: "Dearest",
      value: formatMargin(stats.dearest.normalized_hold_pct),
      detail: dearestCount > 1 ? `${dearestCount} books tied` : stats.dearest.name,
      className: "text-amber-100",
      book: dearestCount === 1 ? stats.dearest.name : null,
    },
    {
      label: "Market spread",
      value: `${stats.spread.toFixed(2)}pp`,
      detail: "cheapest to dearest",
      className: "text-white",
      book: null,
    },
  ];

  return (
    <dl className="grid grid-cols-2 gap-px overflow-hidden rounded-2xl border border-white/[0.08] bg-white/[0.08] lg:grid-cols-4">
      {benchmarks.map((benchmark) => (
        <div key={benchmark.label} className="min-w-0 bg-[#0a1016] px-4 py-4 sm:px-5">
          <dt className="flex items-center gap-2 text-[10px] font-semibold uppercase tracking-[0.13em] text-slate-400">
            {benchmark.book ? <BookmakerMark name={benchmark.book} /> : <EditorialIcon name={benchmark.label === "Median" ? "analysis" : "compare"} className="h-7 w-7" />}
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
