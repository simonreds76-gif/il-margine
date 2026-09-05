import BookmakerMark from "@/components/bookmakers/BookmakerMark";
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

type MarginRowListProps = {
  rows: DerivedMarginOperator[];
  stats: SegmentStats;
  expandedName: string | null;
  onToggleExpanded: (name: string) => void;
  sortKey: MarginSortKey;
  sortDirection: SortDirection;
  onSortChange: (key: MarginSortKey, direction: SortDirection) => void;
};

const SORT_OPTIONS: Array<{ value: string; label: string; key: MarginSortKey; direction: SortDirection }> = [
  { value: "margin-asc", label: "Lowest margin", key: "margin", direction: "asc" },
  { value: "margin-desc", label: "Highest margin", key: "margin", direction: "desc" },
  { value: "name-asc", label: "Bookmaker A-Z", key: "name", direction: "asc" },
  { value: "medianDistance-asc", label: "Closest to median", key: "medianDistance", direction: "asc" },
];

export default function MarginRowList({
  rows,
  stats,
  expandedName,
  onToggleExpanded,
  sortKey,
  sortDirection,
  onSortChange,
}: MarginRowListProps) {
  return (
    <div className="lg:hidden">
      <div className="mb-3 flex items-center justify-between gap-3">
        <label htmlFor="margin-mobile-sort" className="text-[10px] font-semibold uppercase tracking-[0.16em] text-slate-400">
          Sort ranking
        </label>
        <select
          id="margin-mobile-sort"
          value={`${sortKey}-${sortDirection}`}
          onChange={(event) => {
            const option = SORT_OPTIONS.find((item) => item.value === event.target.value);
            if (option) onSortChange(option.key, option.direction);
          }}
          className="min-h-11 rounded-xl border border-white/10 bg-[#0b1118] px-3 text-sm text-slate-200 focus:outline-none focus-visible:ring-2 focus-visible:ring-cyan-300/70"
        >
          {SORT_OPTIONS.map((option) => (
            <option key={option.value} value={option.value}>{option.label}</option>
          ))}
        </select>
      </div>

      <div className="overflow-hidden rounded-2xl border border-white/[0.08] bg-[#080d12] divide-y divide-white/[0.06]">
        {rows.map((operator) => {
          const cheapest = operator.gapToBest < 0.005;
          const expanded = expandedName === operator.name;
          const meaningfulGap = operator.gapToBest >= MEANINGFUL_GAP_PP;
          return (
            <div key={operator.name} className={cheapest ? "bg-emerald-300/[0.045]" : ""}>
              <button
                type="button"
                aria-expanded={expanded}
                onClick={() => onToggleExpanded(operator.name)}
                className={`w-full border-l-2 px-3 py-3 text-left focus:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-cyan-300/70 ${cheapest ? "border-emerald-300" : "border-transparent"}`}
              >
                <span className="flex items-center gap-2">
                  <span className="w-7 shrink-0 font-mono text-[11px] tabular-nums text-slate-500">
                    {operator.tied ? "=" : ""}{operator.displayRank}
                  </span>
                  <BookmakerMark name={operator.name} /><span className="min-w-0 flex-1 truncate text-sm font-semibold text-slate-100">{operator.name}</span>
                  {cheapest && <span className="text-[9px] font-semibold uppercase tracking-[0.12em] text-emerald-200">Best</span>}
                  <span className="font-mono text-lg font-semibold tabular-nums text-cyan-100">{formatMargin(operator.normalized_hold_pct)}</span>
                </span>
                <span className="mt-2 flex items-center gap-3 pl-9">
                  <span className="min-w-0 flex-1">
                    <MarginScaleBar valuePct={operator.scalePct} medianTickPct={stats.medianTickPct} cheapest={cheapest} />
                  </span>
                  <span className={`w-[4.75rem] text-right font-mono text-[10px] tabular-nums ${meaningfulGap ? "text-amber-100" : "text-slate-400"}`}>
                    {cheapest ? "best" : formatGap(operator.gapToBest)}
                  </span>
                </span>
              </button>
              {expanded && (
                <div className="grid grid-cols-3 gap-2 border-t border-white/[0.05] bg-cyan-300/[0.025] px-4 py-3 text-center">
                  <div><p className="text-[9px] uppercase tracking-[0.13em] text-slate-500">Raw</p><p className="mt-1 font-mono text-xs text-slate-200">{formatMargin(operator.raw_overround_pct)}</p></div>
                  <div><p className="text-[9px] uppercase tracking-[0.13em] text-slate-500">vs median</p><p className="mt-1 font-mono text-xs text-slate-200">{formatGap(operator.gapToMedian)}</p></div>
                  <div><p className="text-[9px] uppercase tracking-[0.13em] text-slate-500">samples</p><p className="mt-1 font-mono text-xs text-slate-200">{operator.samples}</p></div>
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
