"use client";
import { useState } from "react";
import type { SkylineReport, SkylineRow, SkylineVariant } from "@/lib/skyline-types";

const variants: { id: SkylineVariant; label: string }[] = [
  { id: "baseline", label: "Baseline" }, { id: "delivery", label: "+ Delivery" },
  { id: "height", label: "+ Height" }, { id: "combined", label: "+ Both" },
];
const time = (s: string) => new Date(s).toLocaleString("en-GB", { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit", timeZone: "Europe/London" });
const number = (n: number | null | undefined, digits = 2) => n == null ? "Not settled yet" : n.toFixed(digits);
const tone = (n: number) => n > 0 ? "text-emerald-300" : n < 0 ? "text-rose-300" : "text-slate-200";

export default function SkylinePanel({ report }: { report: SkylineReport | null }) {
  const [variant, setVariant] = useState<SkylineVariant>("baseline");
  const [onlyQualifying, setOnlyQualifying] = useState(true);
  const [showAll, setShowAll] = useState(false);
  const [showLedger, setShowLedger] = useState(false);
  if (!report) return <div className="rounded-2xl border border-slate-700 p-5 text-slate-300">Skyline is waiting for its first private snapshot. No results have been assumed.</div>;
  const stats = report.stats[variant];
  const board = report.board.filter(r => r.predictions[variant] != null && (!onlyQualifying || r.selections[variant]))
    .sort((a, b) => (b.predictions[variant]! * b.odds) - (a.predictions[variant]! * a.odds));
  const ledger = report.ledger.filter(r => r.selections[variant]);
  const stale = Date.now() - Date.parse(report.generated_at) > 3 * 3600_000;
  function card(row: SkylineRow, recorded: boolean) {
    const p = row.predictions[variant]!;
    const ev = 100 * (p * row.odds - 1);
    const pnl = row.status === "win" ? row.odds - 1 : row.status === "loss" ? -1 : 0;
    return <article key={row.key} className="min-w-0 rounded-2xl border border-slate-700/80 bg-slate-950/60 p-4">
      <div className="flex flex-wrap items-center justify-between gap-2 text-xs text-slate-400"><span>{time(row.kickoff)} UK</span><span className="rounded-full border border-slate-700 px-2 py-1">{recorded ? row.status : row.lineup === "confirmed" ? "Confirmed XI" : "Expected XI · preview"}</span></div>
      <p className="mt-3 text-lg font-semibold text-white">{row.player}</p><p className="mt-1 break-words text-sm text-slate-400">{row.match}</p>
      <p className="mt-3 text-sm text-cyan-200">1+ headed shot on target</p>
      <div className="mt-3 grid grid-cols-3 gap-2 rounded-xl bg-slate-900 p-3 text-center">
        <div><p className="text-[11px] text-slate-400">Bet365</p><p className="mt-1 font-mono text-lg text-white">{row.odds.toFixed(2)}</p></div>
        <div><p className="text-[11px] text-slate-400">Model fair</p><p className="mt-1 font-mono text-lg text-white">{(1 / p).toFixed(2)}</p></div>
        <div><p className="text-[11px] text-slate-400">Estimated EV</p><p className={`mt-1 font-mono text-lg ${tone(ev)}`}>{ev > 0 ? "+" : ""}{ev.toFixed(1)}%</p></div>
      </div>
      <p className="mt-3 text-xs leading-5 text-slate-400">Chance {(p * 100).toFixed(1)}% · Expected minutes {row.expected_minutes.toFixed(0)}<br />Price captured {time(row.price_at)} UK</p>
      {recorded ? <p className={`mt-2 text-sm ${tone(pnl)}`}>{row.status === "win" || row.status === "loss" ? `${pnl > 0 ? "+" : ""}${pnl.toFixed(2)}u · ${row.headed_sot} headed SOT` : row.status === "void" ? "Voided · 0u profit" : "1u paper selection · awaiting verified outcome"}</p> : <p className="mt-2 text-xs text-slate-500">{row.lineup === "confirmed" ? "First verified forecast is locked in the ledger." : "No paper stake until the official XI and a fresh matched price."}</p>}
    </article>;
  }
  return <div className="space-y-5">
    <div className="flex flex-wrap gap-2" role="group" aria-label="Model comparison">
      {variants.map(v => <button key={v.id} type="button" aria-pressed={variant === v.id} onClick={() => { setVariant(v.id); setShowAll(false); }} className={`rounded-xl border px-4 py-3 text-sm font-semibold ${variant === v.id ? "border-cyan-400/50 bg-cyan-400/10 text-cyan-200" : "border-slate-700 text-slate-300 hover:bg-slate-800"}`}>{v.label}{v.id === "baseline" ? " · Primary" : ""}</button>)}
    </div>
    <p className={`text-sm ${stale || report.status === "FAILED" ? "text-amber-300" : "text-slate-400"}`}>Updated {time(report.generated_at)} UK · {report.forecasts} confirmed forecasts · {report.paired_forward_count} settled comparisons across all four versions{stale ? " · Snapshot needs refreshing" : ""}{report.status === "FAILED" ? " · Latest capture failed" : ""}</p>
    <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
      {[{ label: "Paper ROI", value: stats.roi == null ? "Awaiting results" : `${stats.roi > 0 ? "+" : ""}${stats.roi.toFixed(1)}%`, color: tone(stats.roi ?? 0) },
        { label: "Paper profit", value: `${stats.profit > 0 ? "+" : ""}${stats.profit.toFixed(2)}u`, color: tone(stats.profit) },
        { label: "Wins / losses", value: `${stats.wins} / ${stats.losses}`, color: "text-white" },
        { label: "Pending / void", value: `${stats.pending} / ${stats.void}`, color: "text-white" }].map(m => <div key={m.label} className="min-w-0 rounded-2xl border border-slate-700 bg-slate-900/60 p-4"><p className="text-xs text-slate-400">{m.label}</p><p className={`mt-2 break-words text-xl font-semibold ${m.color}`}>{m.value}</p></div>)}
    </div>
    <p className="text-sm leading-6 text-slate-400">Fixed 1u paper stake per qualifying player. {stats.settled_stake}u settled across {stats.fixtures} selected fixtures. Multiple players from one match are correlated. No real money is staked.{stats.overdue > 0 && <span className="text-amber-300"> {stats.overdue} outcomes overdue.</span>}</p>
    <section className="space-y-3"><div className="flex flex-wrap items-center justify-between gap-3"><h2 className="text-xl font-semibold text-white">Upcoming price comparisons</h2><label className="flex items-center gap-2 text-sm text-slate-300"><input type="checkbox" checked={onlyQualifying} onChange={e => { setOnlyQualifying(e.target.checked); setShowAll(false); }} />Paper qualifiers only</label></div>
      <p className="text-sm text-slate-400">Frozen screen: estimated EV at least 10%, chance at least 8%, odds 1.50 to 20.00 and expected minutes at least 60. These estimates are experimental.</p>
      {board.length ? <><div className="grid gap-3 md:grid-cols-2">{(showAll ? board : board.slice(0, 12)).map(r => card(r, false))}</div>{board.length > 12 && <button type="button" onClick={() => setShowAll(!showAll)} className="rounded-xl border border-slate-600 px-4 py-3 text-sm">{showAll ? "Show fewer" : `Show all ${board.length} comparisons`}</button>}</> : <div className="rounded-xl border border-dashed border-slate-700 p-5 text-slate-400">No current priced players pass this view. Uncheck the filter to inspect all available comparisons.</div>}
    </section>
    <section className="space-y-3"><h2 className="text-xl font-semibold text-white">Locked paper selections</h2><p className="text-sm text-slate-400">The first confirmed forecast and price stay fixed. Results update when the exact match outcome is available.</p>
      {ledger.length ? <><div className="grid gap-3 md:grid-cols-2">{(showLedger ? ledger : ledger.slice(0, 12)).map(r => card(r, true))}</div>{ledger.length > 12 && <button type="button" onClick={() => setShowLedger(!showLedger)} className="rounded-xl border border-slate-600 px-4 py-3 text-sm">{showLedger ? "Show fewer" : "Show all loaded selections"}</button>}</> : <p className="rounded-xl border border-dashed border-slate-700 p-5 text-slate-400">No qualifying confirmed paper selections yet. Preview candidates are not counted as bets.</p>}
      {report.ledger_total > report.ledger.length && <p className="text-xs text-slate-500">Latest {report.ledger.length} forecasts loaded. Headline statistics use the full retained ledger.</p>}
    </section>
    <details className="rounded-2xl border border-slate-700 p-4"><summary className="cursor-pointer font-semibold text-white">Does height or delivery improve the model?</summary><div className="mt-4 space-y-4 text-sm text-slate-400">
      <p>Chronological historical test, separate from forward paper ROI. Lower Brier and log loss are better. All four versions use the same test appearances.</p>
      {Object.entries(report.research.periods).map(([period, data]) => <div key={period}><p className="mb-2 text-slate-200">{period === "test" ? "Held-out test" : "Validation"} · {data.start} to {data.end} · {data.common_rows.toLocaleString()} appearances</p><div className="overflow-x-auto"><table className="w-full text-left text-xs"><thead><tr className="text-slate-500"><th className="py-2">Version</th><th>Brier</th><th>Log loss</th></tr></thead><tbody>{variants.map(v => <tr key={v.id} className="border-t border-slate-800"><td className="py-2">{v.label}</td><td>{data.models[v.id].brier.toFixed(5)}</td><td>{data.models[v.id].log_loss.toFixed(5)}</td></tr>)}</tbody></table></div></div>)}
      <p>Small historical improvements do not establish an advantage: the fixture-level uncertainty intervals include zero. Historical heights and defender roles use the current registry, so the height replay is an approximation. Forward forecasts retain the inputs actually available before kickoff.</p>
      <p>Historical ROI is unavailable because this replay has no verified historical headed-market prices. Forward ROI uses captured Bet365 prices.</p>
      <p className="text-slate-200">Forward comparison on identical forecasts · {report.paired_settled_fixtures} settled fixtures{report.paired_settled_fixtures >= 50 ? " · Review milestone reached" : " · First review at 50 fixtures"}</p>
      <div className="overflow-x-auto"><table className="w-full text-left text-xs"><thead><tr><th className="py-2">Version</th><th>Brier</th><th>Log loss</th><th>Paper ROI</th></tr></thead><tbody>{variants.map(v => { const s = report.paired_stats[v.id]; return <tr key={v.id} className="border-t border-slate-800"><td className="py-2">{v.label}</td><td>{s.brier?.toFixed(5) ?? "Pending"}</td><td>{s.log_loss?.toFixed(5) ?? "Pending"}</td><td>{s.roi == null ? "Pending" : `${s.roi.toFixed(1)}%`}</td></tr>; })}</tbody></table></div>
      <p>Forward probability checks for this version: {stats.accuracy_n} settled forecasts · Brier {number(stats.brier, 5)} · Log loss {number(stats.log_loss, 5)}. All forecasts are scored, including those that were not selections.</p>
    </div></details>
    <details className="rounded-2xl border border-slate-700 p-4 text-sm text-slate-400"><summary className="cursor-pointer text-slate-200">Method, coverage and settlement</summary><div className="mt-3 space-y-3 leading-6"><p>The baseline combines prior headed attempts per 90, prior on-target conversion and expected starting minutes. Small samples are pulled towards league averages. A fixed logistic calibration turns the initial count estimate into a probability. The alternatives add prior team corner and cross delivery, player height relative to the opposing defenders, or both.</p><p>{report.settlement_policy}</p><p>Missing or conflicting outcomes remain unresolved. Profit excludes voids; ROI divides profit by settled paper stakes. Neither historical replay nor paper monitoring is a record of placed bets.</p><p>Current exclusions: {Object.entries(report.exclusions).map(([k, v]) => `${k.replaceAll("_", " ")}: ${v}`).join("; ") || "None"}.</p></div></details>
  </div>;
}
