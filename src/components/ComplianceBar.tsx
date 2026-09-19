/** Compact support links within the existing footer; no separate page strip. */
export default function ComplianceBar() {
  return (
    <div aria-label="Responsible gambling support" className="flex flex-wrap items-center justify-center gap-x-3 gap-y-2 text-xs text-slate-400 md:justify-end">
      <span title="For adults aged 18 and over" className="inline-flex h-9 w-9 shrink-0 items-center justify-center rounded-full border border-slate-500/70 bg-slate-800/30 text-[11px] font-bold tracking-tight text-slate-200">18+</span>
      <a href="https://www.begambleaware.org" target="_blank" rel="noopener noreferrer" className="group inline-flex min-h-11 items-center gap-2 rounded-lg px-2 font-semibold text-slate-200 transition-colors hover:bg-emerald-300/5 hover:text-emerald-200 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-emerald-300" aria-label="GambleAware — advice, tools and support (opens in a new tab)">
        <svg aria-hidden="true" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" className="text-emerald-300/70"><path strokeLinecap="round" strokeLinejoin="round" d="M12 3 4 6v6c0 4.5 8 9 8 9s8-4.5 8-9V6l-8-3Z"/><path strokeLinecap="round" strokeLinejoin="round" d="m8.5 12 2.5 2.5 4.5-5"/></svg>
        GambleAware <span aria-hidden="true" className="text-slate-500 group-hover:text-emerald-300">↗</span>
      </a>
      <span className="whitespace-nowrap text-[11px]">Gamble responsibly</span>
    </div>
  );
}
