"use client";

export default function AssumptionsCallout() {
  const assumptions = [
    "Based on historical ROI, not a prediction.",
    "Assumes unit discipline (e.g. 1 to 2% per unit).",
    "Variance not modelled; short-term results will differ.",
  ];

  return (
    <details className="rounded-xl border border-slate-700/50 bg-slate-800/40 overflow-hidden group">
      <summary className="list-none cursor-pointer px-5 py-4 text-left font-medium text-slate-200 hover:bg-slate-700/30 transition-colors focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-emerald-500">
        <span className="flex items-center gap-2">
          Assumptions
          <span className="text-slate-500 transition-transform group-open:rotate-180" aria-hidden>
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
            </svg>
          </span>
        </span>
      </summary>
      <div className="border-t border-slate-700/50 px-5 py-4 bg-slate-800/30">
        <ul className="space-y-2 text-sm text-slate-400">
          {assumptions.map((item, i) => (
            <li key={i} className="flex items-start gap-2">
              <span className="text-emerald-400/80 mt-0.5">•</span>
              {item}
            </li>
          ))}
        </ul>
      </div>
    </details>
  );
}
