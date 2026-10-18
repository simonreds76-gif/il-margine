"use client";

import { useMemo, useState } from "react";
import PropSelectionCard from "@/components/PropSelectionCard";
import PropMarketIcon from "@/components/PropMarketIcon";
import { buildPropPerformance, type PropKey, type PropRow } from "@/lib/prop-performance";

const tone = (n: number | null) => n == null || n === 0 ? "text-slate-300" : n > 0 ? "text-emerald-300" : "text-rose-300";
const signed = (n: number, digits = 2) => `${n > 0 ? "+" : ""}${n.toFixed(digits)}`;
const dateLabel = (value?: string | null) => value ? new Date(value.slice(0, 10) + "T12:00:00Z").toLocaleDateString("en-GB", { day: "numeric", month: "short", year: "numeric", timeZone: "UTC" }) : "Date unavailable";

export default function PropPerformancePanel({ rows, pending, league, leagues, onLeagueChange }: {
  rows: PropRow[]; pending: PropRow[]; league: string; leagues: { id: string; name: string }[]; onLeagueChange: (league: string) => void;
}) {
  const [selected, setSelected] = useState<PropKey | null>(null);
  const [sort, setSort] = useState("bets");
  const [limit, setLimit] = useState(20);
  const groups = useMemo(() => buildPropPerformance(rows, pending), [rows, pending]);
  const ordered = [...groups].sort((a, b) => {
    const difference = sort === "roi" ? (b.roi ?? -Infinity) - (a.roi ?? -Infinity) : sort === "profit" ? b.profit - a.profit : b.rows.length - a.rows.length;
    return difference || a.label.localeCompare(b.label);
  });
  const active = groups.find(item => item.key === selected);
  const dates = rows.map(row => row.date).filter((date): date is string => Boolean(date)).sort();
  const leagueName = leagues.find(item => item.id === league)?.name || "Selected league";
  return <section id="prop-performance" aria-labelledby="prop-performance-title" className="mt-10 scroll-mt-24 rounded-2xl border border-slate-700/70 bg-slate-950/50 p-4 sm:p-6">
    <div className="flex flex-col gap-5 md:flex-row md:items-end md:justify-between">
      <div className="max-w-xl">
        <p className="mb-2 text-xs font-semibold uppercase tracking-[0.16em] text-emerald-300">The record by market</p>
        <h2 id="prop-performance-title" className="text-2xl font-semibold tracking-tight text-white sm:text-3xl">Performance by prop</h2>
        <p className="mt-2 text-sm leading-6 text-slate-400">Compare returns across our published selections. Choose a prop to inspect its bets.</p>
      </div>
      <div className="grid grid-cols-2 gap-3 md:min-w-80">
        <label className="min-w-0 text-xs text-slate-400">League
          <select aria-label="Performance league" value={league} onChange={event => { onLeagueChange(event.target.value); setLimit(20); }} className="mt-1.5 block min-h-11 w-full rounded-lg border border-slate-600 bg-slate-900 px-2 text-sm text-slate-100 focus-visible:outline-2 focus-visible:outline-emerald-300">
            {leagues.map(item => <option key={item.id} value={item.id}>{item.name}</option>)}
          </select>
        </label>
        <label className="min-w-0 text-xs text-slate-400">Sort by
          <select aria-label="Sort prop performance" value={sort} onChange={event => setSort(event.target.value)} className="mt-1.5 block min-h-11 w-full rounded-lg border border-slate-600 bg-slate-900 px-2 text-sm text-slate-100 focus-visible:outline-2 focus-visible:outline-emerald-300">
            <option value="bets">Settled bets</option><option value="roi">Highest ROI</option><option value="profit">Highest profit</option>
          </select>
        </label>
      </div>
    </div>
    <p className="mt-4 text-xs leading-5 text-slate-500">{leagueName}{dates.length ? ` · ${dateLabel(dates[0])} to ${dateLabel(dates.at(-1))}` : ""}. Individual recorded bets only. Earlier aggregate totals are excluded from this breakdown.</p>
    {ordered.length ? <div className="mt-5 grid grid-cols-2 gap-3 lg:grid-cols-3 xl:grid-cols-4">
      {ordered.map(item => <button key={item.key} type="button" aria-pressed={active?.key === item.key} aria-controls="prop-selections" onClick={() => { setSelected(item.key); setLimit(20); requestAnimationFrame(() => document.getElementById("prop-selections")?.scrollIntoView({ behavior: window.matchMedia("(prefers-reduced-motion: reduce)").matches ? "instant" : "smooth", block: "start" })); }} className={`group relative min-w-0 overflow-hidden rounded-2xl border p-3.5 text-left transition-colors focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-emerald-300 sm:p-4 ${active?.key === item.key ? "border-emerald-300/70 bg-gradient-to-b from-emerald-300/[0.10] to-slate-900/80 ring-1 ring-emerald-300/20" : "border-slate-700/60 bg-gradient-to-b from-slate-800/40 to-slate-950/70 hover:border-emerald-300/40 hover:from-slate-800/70"}`}>
        <span className="mb-3 flex items-center justify-between gap-2">
          <span className={`flex h-11 w-11 shrink-0 items-center justify-center rounded-xl border ${active?.key === item.key ? "border-emerald-300/40 bg-emerald-300/15 text-emerald-200" : "border-slate-600/50 bg-slate-800/70 text-emerald-200/90"}`}><PropMarketIcon market={item.key} /></span>
          <svg className={`h-4 w-4 shrink-0 ${active?.key === item.key ? "text-emerald-200" : "text-slate-500 group-hover:text-emerald-200"}`} viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.5" aria-hidden="true"><path d={active?.key === item.key ? "m4 10 4 4 8-8" : "M4 10h12m-5-5 5 5-5 5"} /></svg>
        </span>
        <span className="block min-h-10 text-sm font-medium leading-5 text-slate-100 max-[360px]:text-xs">{item.label}</span>
        <span className={`mt-1 flex flex-wrap items-baseline gap-x-1.5 font-mono text-2xl font-semibold tracking-tight sm:text-3xl ${tone(item.roi)}`}>{item.roi == null ? "N/A" : `${signed(item.roi, 1)}%`}<span className="font-sans text-[10px] font-medium tracking-wider text-slate-400">ROI</span></span>
        <span className="mt-3 flex flex-wrap items-center justify-between gap-x-2 gap-y-1 border-t border-slate-700/50 pt-3 text-xs tabular-nums"><span className={tone(item.profit)}>{signed(item.profit)}u</span><span className="text-slate-400">{item.rows.length} {item.rows.length === 1 ? "bet" : "bets"}</span></span>
        <span className="mt-2 flex flex-wrap items-center gap-x-2 gap-y-1 text-[11px] leading-4 text-slate-400">{item.rows.length < 50 ? "Small sample" : "Settled selections"}{item.pending.length ? <span className="text-amber-200/90">{item.pending.length} pending</span> : null}</span>
      </button>)}
    </div> : <p className="mt-5 rounded-xl border border-slate-800 p-5 text-sm text-slate-400">No recorded selections for this league yet.</p>}
    <div id="prop-selections" className="mt-5 scroll-mt-24" aria-live="polite">
      {active ? <div className="overflow-hidden rounded-2xl border border-slate-700/80 bg-slate-950/60">
        <div className="border-b border-slate-700/60 bg-gradient-to-br from-slate-800/65 to-slate-900/20 p-4 sm:p-5">
          <div className="flex items-start justify-between gap-3">
            <div className="flex min-w-0 items-center gap-3">
              <span className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl border border-emerald-300/20 bg-emerald-300/10 text-emerald-200"><PropMarketIcon market={active.key} className="h-7 w-7" /></span>
              <div className="min-w-0"><h3 className="text-lg font-semibold leading-6 text-white">{active.label}</h3><p className="mt-1 text-xs text-slate-400">{leagueName} · Latest first</p></div>
            </div>
            <button type="button" aria-label="Close prop selections" onClick={() => setSelected(null)} className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl border border-slate-600/60 text-slate-300 hover:bg-slate-800 focus-visible:outline-2 focus-visible:outline-emerald-300"><svg viewBox="0 0 24 24" className="h-5 w-5" fill="none" stroke="currentColor" strokeWidth="1.5" aria-hidden="true"><path d="m6 6 12 12M18 6 6 18" /></svg></button>
          </div>
          <dl className="mt-4 grid grid-cols-3 gap-2 rounded-xl border border-slate-700/50 bg-slate-950/50 p-3 sm:p-4">
            <div><dt className="text-[10px] font-medium uppercase tracking-wider text-slate-400">ROI</dt><dd className={`mt-1 font-mono text-lg font-semibold sm:text-2xl ${tone(active.roi)}`}>{active.roi == null ? "N/A" : `${signed(active.roi, 1)}%`}</dd></div>
            <div><dt className="text-[10px] font-medium uppercase tracking-wider text-slate-400">Profit</dt><dd className={`mt-1 font-mono text-lg font-semibold sm:text-2xl ${tone(active.profit)}`}>{signed(active.profit)}<span className="text-xs">u</span></dd></div>
            <div><dt className="text-[10px] font-medium uppercase tracking-wider text-slate-400">Settled</dt><dd className="mt-1 font-mono text-lg font-semibold text-slate-100 sm:text-2xl">{active.rows.length}</dd></div>
          </dl>
          <p className="mt-3 text-xs leading-5 text-slate-400">{active.wins} wins · {active.losses} losses · {active.stake.toFixed(2)}u staked</p>
        </div>
        <div className="p-3 sm:p-5">
          {active.pending.length ? <div className="mb-5"><h4 className="mb-3 flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-amber-200"><span className="h-1.5 w-1.5 rounded-full bg-amber-300" />Awaiting result · {active.pending.length}</h4><div className="grid gap-3 lg:grid-cols-2">{active.pending.map(row => <PropSelectionCard key={row.id} row={row} market={active.key} />)}</div></div> : null}
          <h4 className="mb-3 text-xs font-semibold uppercase tracking-wider text-slate-400">Settled selections</h4>
          <div className="grid gap-3 lg:grid-cols-2">{active.rows.slice(0, limit).map(row => <PropSelectionCard key={row.id} row={row} market={active.key} />)}</div>
          {active.rows.length > limit ? <button type="button" onClick={() => setLimit(value => value + 20)} className="mt-4 min-h-11 w-full rounded-xl border border-slate-600 px-4 py-2 text-sm text-slate-200 hover:bg-slate-800 focus-visible:outline-2 focus-visible:outline-emerald-300">Show 20 more · {active.rows.length - limit} remaining</button> : null}
          {!active.rows.length ? <p className="mt-4 text-sm text-slate-400">No settled selections for this prop yet.</p> : null}
        </div>
      </div> : selected ? <p className="text-sm text-slate-400">No selections for this prop in {leagueName}. Choose another prop or league.</p> : <p className="text-xs text-slate-500">Tap a prop above to open its selections.</p>}
    </div>
    <p className="mt-4 text-xs leading-5 text-slate-500">ROI is profit divided by settled stakes. Pending and void bets do not enter these figures. Team and match markets are kept separate. A high ROI from a few bets is not a reliable ranking.</p>
  </section>;
}

