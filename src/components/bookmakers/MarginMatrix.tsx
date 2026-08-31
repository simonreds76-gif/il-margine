import type { MarginSegment } from "@/lib/bookmakers/margin-index";
import { deriveSegmentStats, formatMargin } from "@/components/bookmakers/segment-stats";

function toneFor(value: number, minimum: number, maximum: number) {
  if (maximum === minimum) return "bg-slate-800/60 text-slate-200";
  const relative = (value - minimum) / (maximum - minimum);
  if (relative <= 0.33) return "bg-emerald-300/[0.09] text-emerald-100";
  if (relative >= 0.67) return "bg-amber-300/[0.08] text-amber-100";
  return "bg-slate-800/60 text-slate-300";
}

export default function MarginMatrix({ segments, sportLabel }: { segments: MarginSegment[]; sportLabel: string }) {
  if (segments.length < 2) return null;

  const operators = Array.from(new Set(
    segments.flatMap((segment) => segment.operators.map((operator) => operator.name)),
  )).sort((left, right) => left.localeCompare(right));
  const statsByMarket = new Map(
    segments.map((segment) => [segment.market_family, deriveSegmentStats(segment)]),
  );

  return (
    <details className="mt-5 overflow-hidden rounded-2xl border border-white/[0.08] bg-white/[0.02]">
      <summary className="flex min-h-12 cursor-pointer list-none items-center justify-between gap-3 px-4 py-3 text-sm font-semibold text-slate-200 focus:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-cyan-300/70 sm:px-5">
        <span>Compare books across every {sportLabel.toLowerCase()} market</span>
        <span className="text-[10px] font-semibold uppercase tracking-[0.14em] text-cyan-300">Open matrix</span>
      </summary>
      <div className="border-t border-white/[0.07] p-3 sm:p-4">
        <p className="mb-3 text-xs leading-5 text-slate-400">
          The same bookmaker can be cheap in one market and expensive in another. Colours show position inside each market only.
        </p>
        <div className="overflow-x-auto rounded-xl border border-white/[0.07]">
          <table className="min-w-[720px] w-full border-collapse text-xs">
            <caption className="sr-only">Cross-market margin matrix for {sportLabel}</caption>
            <thead className="bg-[#0d141b] text-[9px] uppercase tracking-[0.13em] text-slate-400">
              <tr>
                <th scope="col" className="sticky left-0 z-10 bg-[#0d141b] px-3 py-3 text-left font-semibold">Bookmaker</th>
                {segments.map((segment) => (
                  <th key={segment.market_family} scope="col" className="px-3 py-3 text-right font-semibold">{segment.market_family}</th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-white/[0.05]">
              {operators.map((name) => (
                <tr key={name}>
                  <th scope="row" className="sticky left-0 z-10 whitespace-nowrap bg-[#090e14] px-3 py-2.5 text-left font-semibold text-slate-200">{name}</th>
                  {segments.map((segment) => {
                    const operator = segment.operators.find((item) => item.name === name);
                    const stats = statsByMarket.get(segment.market_family);
                    return (
                      <td key={segment.market_family} className="px-1.5 py-1.5 text-right">
                        {operator && stats ? (
                          <span className={`inline-block min-w-[4.2rem] rounded-md px-2 py-1.5 font-mono tabular-nums ${toneFor(operator.normalized_hold_pct, stats.cheapest.normalized_hold_pct, stats.dearest.normalized_hold_pct)}`}>
                            {formatMargin(operator.normalized_hold_pct)}
                          </span>
                        ) : (
                          <span className="px-2 text-slate-600">-</span>
                        )}
                      </td>
                    );
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </details>
  );
}
