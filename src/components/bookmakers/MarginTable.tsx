import BookmakerMark from "@/components/bookmakers/BookmakerMark";
import { Fragment } from "react";
import MarginScaleBar from "@/components/bookmakers/MarginScaleBar";
import {
  MEANINGFUL_GAP_PP,
  formatGap,
  formatMargin,
  type DerivedMarginOperator,
  type MarginSortKey,
  type SegmentStats,
  type SortDirection,
} from "@/components/bookmakers/segment-stats";

type MarginTableProps = {
  rows: DerivedMarginOperator[];
  stats: SegmentStats;
  expandedName: string | null;
  onToggleExpanded: (name: string) => void;
  onSort: (key: MarginSortKey) => void;
  sortKey: MarginSortKey;
  sortDirection: SortDirection;
  marketLabel: string;
};

const HEADERS: Array<{ key: MarginSortKey; label: string; align?: "right" }> = [
  { key: "name", label: "Bookmaker" },
  { key: "margin", label: "Margin", align: "right" },
  { key: "gapBest", label: "vs cheapest", align: "right" },
  { key: "gapMedian", label: "vs median", align: "right" },
];

function gapClass(value: number) {
  return Math.abs(value) >= MEANINGFUL_GAP_PP ? "text-amber-100" : "text-slate-400";
}

export default function MarginTable({
  rows,
  stats,
  expandedName,
  onToggleExpanded,
  onSort,
  sortKey,
  sortDirection,
  marketLabel,
}: MarginTableProps) {
  return (
    <div className="hidden overflow-hidden rounded-2xl border border-white/[0.08] bg-[#080d12] lg:block">
      <table className="w-full border-collapse text-sm">
        <caption className="sr-only">
          Fixed-odds bookmaker margins for {marketLabel}. Lower margin is better.
        </caption>
        <thead className="sticky top-0 z-10 bg-[#0d141b]">
          <tr className="border-b border-white/[0.08] text-[10px] uppercase tracking-[0.14em] text-slate-400">
            <th scope="col" className="w-14 px-4 py-3 text-center font-semibold">Rank</th>
            {HEADERS.map((header) => (
              <th
                key={header.key}
                scope="col"
                aria-sort={sortKey === header.key ? (sortDirection === "asc" ? "ascending" : "descending") : "none"}
                className={`px-3 py-3 font-semibold ${header.align === "right" ? "text-right" : "text-left"}`}
              >
                <button
                  type="button"
                  onClick={() => onSort(header.key)}
                  className="inline-flex min-h-8 items-center gap-1.5 rounded-md px-1 text-inherit transition-colors hover:text-white focus:outline-none focus-visible:ring-2 focus-visible:ring-cyan-300/70"
                >
                  {header.label}
                  <span aria-hidden="true" className={sortKey === header.key ? "text-cyan-300" : "text-slate-600"}>
                    {sortKey === header.key ? (sortDirection === "asc" ? "↑" : "↓") : "↕"}
                  </span>
                </button>
              </th>
            ))}
            <th scope="col" className="w-44 px-4 py-3 text-left font-semibold">Market range</th>
            <th
              scope="col"
              aria-sort={sortKey === "samples" ? (sortDirection === "asc" ? "ascending" : "descending") : "none"}
              className="w-16 px-4 py-3 text-right font-semibold"
            >
              <button
                type="button"
                onClick={() => onSort("samples")}
                className="inline-flex min-h-8 items-center gap-1 rounded-md px-1 focus:outline-none focus-visible:ring-2 focus-visible:ring-cyan-300/70"
              >
                n
                <span aria-hidden="true" className={sortKey === "samples" ? "text-cyan-300" : "text-slate-600"}>
                  {sortKey === "samples" ? (sortDirection === "asc" ? "↑" : "↓") : "↕"}
                </span>
              </button>
            </th>
          </tr>
        </thead>
        <tbody className="divide-y divide-white/[0.055]">
          {rows.map((operator) => {
            const cheapest = operator.gapToBest < 0.005;
            const expanded = expandedName === operator.name;
            return (
              <Fragment key={operator.name}>
                <tr className={cheapest ? "bg-emerald-300/[0.045]" : "hover:bg-white/[0.025]"}>
                  <td className="px-4 py-2.5 text-center font-mono text-xs tabular-nums text-slate-500">
                    {operator.tied ? "=" : ""}{operator.displayRank}
                  </td>
                  <td className={`border-l-2 px-3 py-2.5 ${cheapest ? "border-emerald-300" : "border-transparent"}`}>
                    <button
                      type="button"
                      aria-expanded={expanded}
                      onClick={() => onToggleExpanded(operator.name)}
                      className="flex min-h-9 w-full items-center gap-2 rounded-md text-left font-semibold text-slate-100 focus:outline-none focus-visible:ring-2 focus-visible:ring-cyan-300/70"
                    >
                      <BookmakerMark name={operator.name} /><span className="truncate">{operator.name}</span>
                      {cheapest && (
                        <span className="rounded-full border border-emerald-300/25 bg-emerald-300/10 px-2 py-0.5 text-[9px] uppercase tracking-[0.13em] text-emerald-200">
                          Cheapest
                        </span>
                      )}
                      <span aria-hidden="true" className={`ml-auto text-slate-500 transition-transform motion-reduce:transition-none ${expanded ? "rotate-180" : ""}`}>
                        ▾
                      </span>
                    </button>
                  </td>
                  <td className="px-3 py-2.5 text-right font-mono text-base font-semibold tabular-nums text-cyan-100">
                    {formatMargin(operator.normalized_hold_pct)}
                  </td>
                  <td className={`px-3 py-2.5 text-right font-mono text-xs tabular-nums ${gapClass(operator.gapToBest)}`}>
                    {cheapest ? "best" : formatGap(operator.gapToBest)}
                  </td>
                  <td className={`px-3 py-2.5 text-right font-mono text-xs tabular-nums ${gapClass(operator.gapToMedian)}`}>
                    {formatGap(operator.gapToMedian)}
                  </td>
                  <td className="px-4 py-2.5">
                    <MarginScaleBar
                      valuePct={operator.scalePct}
                      medianTickPct={stats.medianTickPct}
                      cheapest={cheapest}
                    />
                  </td>
                  <td className="px-4 py-2.5 text-right font-mono text-xs tabular-nums text-slate-400">
                    {operator.samples}
                  </td>
                </tr>
                {expanded && (
                  <tr className="bg-cyan-300/[0.035]">
                    <td colSpan={7} className="px-6 py-3">
                      <div className="flex flex-wrap gap-x-8 gap-y-2 text-xs text-slate-400">
                        <span>Raw overround <strong className="font-mono font-semibold text-slate-200">{formatMargin(operator.raw_overround_pct)}</strong></span>
                        <span>Normalized hold <strong className="font-mono font-semibold text-slate-200">{formatMargin(operator.normalized_hold_pct)}</strong></span>
                        <span>Complete price sets <strong className="font-mono font-semibold text-slate-200">{operator.samples}</strong></span>
                      </div>
                    </td>
                  </tr>
                )}
              </Fragment>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
