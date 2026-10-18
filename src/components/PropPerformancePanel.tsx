"use client";

import { useMemo, useState } from "react";
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
    {ordered.length ? <div className="mt-5 grid grid-cols-2 gap-2.5 lg:grid-cols-3 xl:grid-cols-4">
      {ordered.map(item => <button key={item.key} type="button" aria-pressed={active?.key === item.key} aria-controls="prop-selections" onClick={() => { setSelected(item.key); setLimit(20); requestAnimationFrame(() => document.getElementById("prop-selections")?.scrollIntoView({ behavior: window.matchMedia("(prefers-reduced-motion: reduce)").matches ? "instant" : "smooth", block: "start" })); }} className={`min-w-0 rounded-xl border p-3 text-left transition-colors focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-emerald-300 sm:p-4 ${active?.key === item.key ? "border-emerald-300/70 bg-emerald-300/[0.07]" : "border-slate-700/70 bg-slate-900/50 hover:border-slate-500"}`}>
        <span className="flex min-h-10 items-start justify-between gap-2 text-sm max-[360px]:text-xs font-medium text-slate-200"><span>{item.label}</span><span aria-hidden="true" className="text-slate-500 max-[360px]:hidden">↗</span></span>
        <span className={`mt-2 flex flex-wrap items-baseline gap-x-1 font-mono text-2xl font-semibold tracking-tight sm:text-3xl ${tone(item.roi)}`}>{item.roi == null ? "N/A" : `${signed(item.roi, 1)}%`}<span className="font-sans text-[10px] font-normal tracking-normal text-slate-500">ROI</span></span>
        <span className="mt-3 flex flex-wrap items-center justify-between gap-x-2 gap-y-1 text-xs tabular-nums"><span className={tone(item.profit)}>{signed(item.profit)}u</span><span className="text-slate-400">{item.rows.length} settled</span></span>
        <span className="mt-2 block text-[11px] leading-4 text-slate-500">{item.rows.length < 50 ? "Small sample" : "View selections"}{item.pending.length ? ` · ${item.pending.length} pending` : ""}</span>
      </button>)}
    </div> : <p className="mt-5 rounded-xl border border-slate-800 p-5 text-sm text-slate-400">No recorded selections for this league yet.</p>}
    <div id="prop-selections" className="mt-5 scroll-mt-24" aria-live="polite">
      {active ? <div className="rounded-xl border border-slate-700/80 bg-slate-900/40 p-3 sm:p-5">
        <div className="flex items-start justify-between gap-3"><div><h3 className="text-lg font-semibold text-white">{active.label}</h3><p className="mt-1 text-xs leading-5 text-slate-400">{leagueName} · {active.wins} wins / {active.losses} losses · {active.stake.toFixed(2)}u staked</p></div><button type="button" onClick={() => setSelected(null)} className="min-h-11 shrink-0 rounded-lg border border-slate-700 px-3 text-xs text-slate-300 hover:bg-slate-800">Close</button></div>
        {active.pending.length ? <div className="mt-4"><p className="mb-2 text-xs font-semibold uppercase tracking-wider text-amber-300">Pending · excluded from ROI</p>{active.pending.map(row => <Selection key={row.id} row={row} />)}</div> : null}
        <div className="mt-4 divide-y divide-slate-800">{active.rows.slice(0, limit).map(row => <Selection key={row.id} row={row} />)}</div>
        {active.rows.length > limit ? <button type="button" onClick={() => setLimit(limit + 20)} className="mt-4 min-h-11 w-full rounded-lg border border-slate-600 px-4 text-sm text-slate-200 hover:bg-slate-800">Show 20 more · {active.rows.length - limit} remaining</button> : null}
        {!active.rows.length ? <p className="mt-4 text-sm text-slate-400">No settled selections for this prop yet.</p> : null}
      </div> : selected ? <p className="text-sm text-slate-400">No selections for this prop in {leagueName}. Choose another prop or league.</p> : <p className="text-xs text-slate-500">Tap a prop above to open its selections.</p>}
    </div>
    <p className="mt-4 text-xs leading-5 text-slate-500">ROI is profit divided by settled stakes. Pending and void bets do not enter these figures. Team and match markets are kept separate. A high ROI from a few bets is not a reliable ranking.</p>
  </section>;
}

function Selection({ row }: { row: PropRow }) {
  // Preserve older entries where the player and selection fields were reversed.
  const reversed = /^(over|under) \d/i.test(row.player || "") && !/^(over|under) \d/i.test(row.selection);
  return <article className="min-w-0 py-3.5">
    <div className="flex items-start justify-between gap-3"><div className="min-w-0"><p className="break-words text-sm font-medium text-slate-100">{reversed ? row.selection : row.player || "Selection"}</p><p className="mt-1 break-words text-sm text-slate-300">{reversed ? row.player : row.selection}{row.odds && row.odds > 1 ? <span className="ml-2 whitespace-nowrap font-mono text-slate-100">@ {row.odds.toFixed(2)}</span> : null}</p></div><span className={`shrink-0 rounded-md border px-2 py-1 text-[11px] font-semibold ${row.status === "won" ? "border-emerald-300/20 text-emerald-300" : row.status === "lost" ? "border-rose-300/20 text-rose-300" : "border-amber-300/20 text-amber-300"}`}>{row.status === "won" ? "Won" : row.status === "lost" ? "Lost" : "Pending"}</span></div>
    <p className="mt-2 break-words text-xs leading-5 text-slate-500">{row.event} · {dateLabel(row.date || row.match_date)}</p>
    <div className="mt-1 flex flex-wrap gap-x-4 gap-y-1 text-xs tabular-nums"><span className="text-slate-400">Stake {row.stake.toFixed(2)}u</span>{row.status !== "pending" && row.profit_loss != null ? <span className={tone(row.profit_loss)}>Profit {signed(row.profit_loss)}u</span> : null}</div>
  </article>;
}
