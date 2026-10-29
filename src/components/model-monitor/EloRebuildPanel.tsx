import { obj } from "@/lib/admin-model-summary";

const n = (value: unknown, digits = 2) => typeof value === "number" && Number.isFinite(value)
  ? value.toLocaleString("en-GB", { maximumFractionDigits: digits }) : "—";
const text = (value: unknown) => typeof value === "string" ? value : "Unavailable";
const rows = (value: unknown) => Array.isArray(value) ? value.map(obj) : [];
const date = (value: unknown) => typeof value === "string" && Number.isFinite(Date.parse(value))
  ? new Date(value).toLocaleString("en-GB", { timeZone: "Europe/London", dateStyle: "medium", timeStyle: "short" }) : "Unavailable";

/** Authenticated server-rendered snapshot; no extra queries, polling or model execution. */
export default function EloRebuildPanel({ value }: { value: unknown }) {
  const r = obj(value), health = obj(r.capture_health), atp = obj(obj(r.cohorts).ATP);
  const historical = obj(r.historical), history = obj(historical.overall);
  const prices = rows(r.current_prices).filter(p => p.category !== "Challenger");
  const records = rows(r.record);
  return <section id="elo-rebuild" className="mb-6 min-w-0 rounded-2xl border border-sky-400/25 bg-slate-900/60 p-4 sm:p-5">
    <div className="flex flex-wrap items-center justify-between gap-3"><h2 className="text-xl font-semibold text-white">Elo Rebuild</h2><span className="rounded-full border border-sky-400/30 px-3 py-1 text-xs text-sky-200">ATP paper comparison</span></div>
    <p className="mt-3 max-w-3xl text-sm leading-relaxed text-slate-300">A reproducible ratings candidate tested inside the existing match model. Live pricing stays unchanged. No betting alerts or real stakes.</p>
    {!r.version ? <p className="mt-4 text-amber-200">Research snapshot unavailable.</p> : <>
      <p className="mt-3 text-xs leading-relaxed text-slate-400">History through {text(r.history_through)} · {n(r.history_matches, 0)} matches · Captured {date(r.last_capture)} UK</p>
      {health.status === "failed" && <p className="mt-3 break-words rounded-lg bg-amber-400/10 p-3 text-sm text-amber-200">Capture needs attention: {text(health.error)}</p>}
      <div className="mt-5 grid gap-4 sm:grid-cols-2">{(["baseline", "candidate"] as const).map(arm => {
        const m = obj(atp[arm]);
        const roi = typeof m.roi_pct === "number" ? m.roi_pct : null;
        return <article key={arm} className="min-w-0 rounded-xl border border-slate-700 p-4">
          <h3 className="font-semibold">{arm === "baseline" ? "Current model · paired reference" : "Rebuilt ratings · candidate"}</h3>
          <dl className="mt-4 grid grid-cols-2 gap-4 text-sm">
            <div><dt className="text-slate-400">Forward paper ROI</dt><dd className={`mt-1 text-lg font-semibold tabular-nums ${roi === null || roi === 0 ? "text-slate-200" : roi > 0 ? "text-emerald-300" : "text-rose-300"}`}>{roi === null ? "Not established" : `${n(roi)}%`}</dd></div>
            <div><dt className="text-slate-400">Profit / settled stake</dt><dd className="mt-1 tabular-nums">{n(m.profit)}u / {n(m.stake)}u</dd></div>
            <div><dt className="text-slate-400">Wins / losses</dt><dd className="mt-1 tabular-nums">{n(m.wins, 0)} / {n(m.losses, 0)}</dd></div>
            <div><dt className="text-slate-400">Pending paper bets</dt><dd className="mt-1 tabular-nums">{n(m.pending_bets, 0)}</dd></div>
          </dl>
          <p className="mt-3 text-xs text-slate-400">{n(m.settled_fixtures, 0)} settled priced forecasts · log loss {n(m.log_loss, 4)} · games MAE {n(m.games_mae)}</p>
        </article>;
      })}</div>
      <p className="mt-3 text-xs leading-relaxed text-slate-400">One hypothetical unit per qualifying selection under the fixed comparison rules. A captured forecast is not necessarily a bet. Review at 300 settled priced ATP fixtures; negative or inconclusive evidence ends this version. No automatic promotion.</p>
      <details className="mt-5 border-t border-slate-700 pt-2"><summary className="min-h-11 cursor-pointer py-3 font-semibold text-sky-200">Compare current ATP fair prices ({prices.length})</summary>
        <p className="mb-3 text-xs text-slate-400">First / second player decimal odds. These are research forecasts, not new signals. Missing prices and unverified start times cannot contribute betting returns.</p>
        <div className="grid gap-3 md:grid-cols-2">{prices.map(p => { const a = obj(p.baseline), b = obj(p.candidate); return <article key={text(p.key)} className="min-w-0 rounded-xl border border-slate-700 p-3">
          <h3 className="break-words font-medium">{text(p.match)}</h3><p className="mt-1 text-xs text-slate-400">{text(p.tournament)}</p>
          <div className="mt-3 grid grid-cols-2 gap-3 text-sm"><div><p className="text-xs text-slate-400">Current fair odds</p><p className="mt-1 tabular-nums">{n(a.fair1)} / {n(a.fair2)}</p><p className="mt-1 text-xs text-slate-400">Games {n(a.games, 1)}</p></div><div><p className="text-xs text-slate-400">Rebuilt fair odds</p><p className="mt-1 tabular-nums">{n(b.fair1)} / {n(b.fair2)}</p><p className="mt-1 text-xs text-slate-400">Games {n(b.games, 1)}</p></div></div>
        </article>; })}</div>
      </details>
      <details className="mt-3 border-t border-slate-700 pt-2"><summary className="min-h-11 cursor-pointer py-3 font-semibold text-sky-200">Captured fixtures &amp; selections ({records.length})</summary>
        <p className="mb-3 text-xs text-slate-400">Latest {n(r.record_limit, 0)} records; full local ledger retained. Initial Challenger observations are preserved but no new ones are collected.</p>
        <div className="space-y-3">{records.map(p => <article key={text(p.key)} className="rounded-xl border border-slate-700 p-3 text-sm">
          <div className="flex flex-wrap justify-between gap-2"><strong className="break-words">{text(p.match)}</strong><span className="text-slate-400">{text(p.result)}{p.score ? ` · ${text(p.score)}` : ""}</span></div>
          <p className="mt-1 text-xs text-slate-400">Kickoff {date(p.kickoff)} UK · Recorded Pinnacle {n(obj(p.quote).odds1)} / {n(obj(p.quote).odds2)}</p>
          <div className="mt-2 grid gap-2 sm:grid-cols-2">{["baseline", "candidate"].map(arm => { const s = obj(obj(p[arm]).selection); return <p key={arm}><span className="text-slate-400">{arm === "baseline" ? "Current" : "Rebuilt"}: </span>{s.side ? `${s.side === "P1" ? "First" : "Second"} player · 1u paper` : "No qualifying selection"}</p>; })}</div>
        </article>)}</div>
      </details>
      <details className="mt-3 border-t border-slate-700 pt-2"><summary className="min-h-11 cursor-pointer py-3 text-sm font-semibold text-slate-300">Historical test: why this is staying paper only</summary>
        <p className="mt-2 text-sm leading-relaxed text-slate-300">The Challenger reconstruction failed: {n(history.fixtures, 0)} fixtures across {n(history.editions, 0)} editions. Reference {n(obj(history.baseline).roi_pct)}% ROI ({n(obj(history.baseline).bets, 0)} bets); candidate {n(obj(history.candidate).roi_pct)}% ({n(obj(history.candidate).bets, 0)} bets). Both were behind the margin-adjusted market on prediction accuracy.</p>
        <p className="mt-3 text-xs leading-relaxed text-slate-400">This is retrospective research, not the actual live record. Competition coverage, surface update size and within-day ordering differ between ratings. Opus independently reproduced the calculations. Challenger v1 is closed to new captures. Forward ATP evidence stays separate.</p>
      </details>
    </>}
  </section>;
}
