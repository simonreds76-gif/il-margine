import { obj } from "@/lib/admin-model-summary";

const n = (v: unknown, digits = 2) => typeof v === "number" && Number.isFinite(v) ? v.toLocaleString("en-GB", { maximumFractionDigits: digits }) : "—";
const rows = (v: unknown) => Array.isArray(v) ? v.map(obj) : [];
const text = (v: unknown) => typeof v === "string" ? v : "Unavailable";
const tone = (v: unknown) => typeof v !== "number" || v === 0 ? "text-slate-200" : v > 0 ? "text-emerald-300" : "text-rose-300";
const time = (v: unknown) => typeof v === "string" && Number.isFinite(Date.parse(v)) ? new Date(v).toLocaleString("en-GB", { timeZone: "Europe/London", dateStyle: "medium", timeStyle: "short" }) : "Unavailable";

/** Existing authenticated snapshot only. No new requests, polling, client JS or alerts. */
export default function HardcourtScoutPanel({ value }: { value: unknown }) {
  const r = obj(value), c = obj(r.fable_comparison), arms = obj(c.arms), accuracy = obj(c.accuracy), coverage = obj(c.coverage), health = obj(c.capture);
  return <section id="hardcourt-scout" className="mb-6 min-w-0 scroll-mt-6 rounded-2xl border border-cyan-400/25 bg-slate-900/60 p-4 sm:p-5">
    <div className="flex flex-wrap items-center justify-between gap-3"><h2 className="text-xl font-semibold">Hardcourt Scout</h2><span className="rounded-full border border-cyan-400/30 px-3 py-1 text-xs text-cyan-200">Outdoor hard · Challenger · Paper only</span></div>
    <p className="mt-3 text-sm leading-relaxed text-slate-300">Fable’s frozen opponent-strength correction shares Scout’s captures, recorded Pinnacle prices and settlements. Live pricing stays unchanged. No additional alerts.</p>
    <p className="mt-3 text-sm text-slate-300">Existing Scout record: <strong className={tone(r.roi_pct)}>{n(r.roi_pct)}% ROI</strong> · {n(r.wins,0)}W / {n(r.losses,0)}L · {n(r.pnl_units)}u on {n(r.stake_units)}u. <a href="/admin/models/signals?model=scout" className="inline-flex min-h-11 items-center text-cyan-200 underline underline-offset-4">Open original selections →</a></p>
    {!c.version ? <p className="mt-4 text-amber-200">Comparison snapshot unavailable. Existing records are retained.</p> : <>
      <p className="mt-3 text-xs leading-relaxed text-slate-400">Comparison starts {time(c.effective_at)} UK. Both columns use the same new captures; earlier Scout results and historical backtests are excluded.</p>
      <p className={`mt-3 break-words text-sm ${health.state === "BLOCKED" || health.state === "PARTIAL" ? "text-amber-200" : "text-slate-400"}`}>Capture: {text(health.state).replaceAll("_", " ").toLowerCase()} · checked {time(health.checked_at)} UK{health.reason ? ` · ${text(health.reason)}` : ""}.</p>
      <div className="mt-5 grid min-w-0 gap-4 md:grid-cols-2">{(["baseline", "fable"] as const).map(arm => {
        const m = obj(arms[arm]), a = obj(accuracy[arm]);
        return <article key={arm} className="min-w-0 rounded-xl border border-slate-700 p-4">
          <h3 className="font-semibold text-cyan-100">{arm === "baseline" ? "Scout · paired reference" : "Scout + Fable correction"}</h3>
          <dl className="mt-4 grid grid-cols-2 gap-4 text-sm">
            <div><dt className="text-slate-400">Forward paper ROI</dt><dd className={`mt-1 text-xl font-semibold tabular-nums ${tone(m.roi_pct)}`}>{m.roi_pct == null ? "Awaiting settlement" : `${n(m.roi_pct)}%`}</dd></div>
            <div><dt className="text-slate-400">Profit / settled stake</dt><dd className={`mt-1 tabular-nums ${tone(m.pnl_units)}`}>{n(m.pnl_units)}u / {n(m.stake_units)}u</dd></div>
            <div><dt className="text-slate-400">Wins / losses</dt><dd className="mt-1 tabular-nums">{n(m.wins,0)} / {n(m.losses,0)}</dd></div>
            <div><dt className="text-slate-400">Pending / void</dt><dd className="mt-1 tabular-nums">{n(m.pending,0)} / {n(m.void,0)}</dd></div>
            <div><dt className="text-slate-400">Brier score</dt><dd className="mt-1 tabular-nums">{n(a.brier,4)}</dd></div>
            <div><dt className="text-slate-400">Log loss</dt><dd className="mt-1 tabular-nums">{n(a.log_loss,4)}</dd></div>
          </dl>
          <p className="mt-3 text-xs text-slate-400">{n(m.overdue,0)} overdue · {n(m.quarantined,0)} quarantined. Lower Brier and log loss are better.</p>
          <details className="mt-4 border-t border-slate-700 pt-1"><summary className="min-h-11 cursor-pointer py-3 text-sm font-semibold text-cyan-200">Selections &amp; results ({n(m.selections_total,0)})</summary>
            {rows(m.selections).length === 0 ? <p className="text-sm text-slate-400">No qualifying selections captured for this comparison yet.</p> : <><p className="mb-3 text-xs text-slate-400">Latest 100 shown; summary uses the full record. One hypothetical unit per bet, zero real stake.</p><div className="space-y-3">{rows(m.selections).map(b => <div key={text(b.fixture_key)} className="min-w-0 rounded-lg border border-slate-700 p-3 text-sm"><p className="break-words font-semibold">{text(b.player)} <span className="font-normal text-slate-400">vs {text(b.opponent)}</span></p><p className="mt-1 break-words text-xs text-slate-400">{text(b.tournament)} · {time(b.kickoff)} UK</p><div className="mt-3 grid grid-cols-2 gap-2 tabular-nums"><span>Pinnacle {n(b.odds,3)}</span><span>Fair {typeof b.probability === "number" && b.probability > 0 ? n(1/b.probability) : "—"}</span><span>{text(b.status)}{b.status === "settled" ? b.won ? " · won" : " · lost" : ""}</span><span className={tone(b.pnl_units)}>{b.pnl_units == null ? "Unsettled" : `${n(b.pnl_units)}u`}</span></div>{b.score ? <p className="mt-2 text-xs text-slate-400">{text(b.score)}</p> : null}</div>)}</div></>}
          </details>
        </article>;
      })}</div>
      <p className="mt-3 text-xs leading-relaxed text-slate-400">{n(c.paired_settled_fixtures,0)} identical settled fixtures for accuracy, including forecasts that did not qualify as bets. {n(coverage.baseline_fallback ?? 0,0)} missing-history fallbacks; {n(coverage.unavailable ?? 0,0)} unavailable comparisons. Review at 50 and 100 paired fixtures. No automatic promotion.</p>
      <details className="mt-4 border-t border-slate-700 pt-1"><summary className="min-h-11 cursor-pointer py-3 font-semibold text-cyan-200">Calibration: predicted chances versus results</summary><p className="mb-3 text-xs text-slate-400">Same first-player orientation and settled fixtures for each version. Small bins are uncertain; better calibration does not establish profit. Market Brier {n(obj(accuracy.market).brier,4)} · log loss {n(obj(accuracy.market).log_loss,4)}.</p>
        <div className="grid gap-4 md:grid-cols-2">{(["baseline","fable"] as const).map(arm => <div key={arm} className="min-w-0"><h3 className="mb-2 text-sm font-semibold">{arm === "baseline" ? "Scout reference" : "Fable correction"}</h3>{rows(obj(accuracy[arm]).bins).length === 0 ? <p className="text-sm text-slate-400">Awaiting settled fixtures.</p> : <table className="w-full text-left text-xs tabular-nums"><thead className="text-slate-400"><tr><th className="py-2">Range</th><th>Matches</th><th>Predicted</th><th>Observed</th></tr></thead><tbody>{rows(obj(accuracy[arm]).bins).map(b => <tr key={String(b.from)} className="border-t border-slate-800"><td className="py-2">{n(Number(b.from)*100,0)}–{n(Number(b.to)*100,0)}%</td><td>{n(b.n,0)}</td><td>{n(Number(b.predicted)*100,1)}%</td><td>{n(Number(b.observed)*100,1)}%</td></tr>)}</tbody></table>}</div>)}</div>
      </details>
    </>}
  </section>;
}
