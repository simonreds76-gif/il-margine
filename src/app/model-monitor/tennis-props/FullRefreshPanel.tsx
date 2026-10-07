import path from "node:path";
import { readTennisPropsMonitorFile } from "@/lib/tennis-props-live-files";

type Arm = { bets: number; wins: number; losses: number; pushes: number; pnl_units: number; roi_pct: number | null; count_mae: number | null; count_samples: number; brier: number | null };
type Market = { registered: number; registered_fixtures: number; settled: number; pending: number; overdue: number; void: number; independent_fixtures: number; control: Arm; candidate: Arm };
type Pending = { id: string; player: string; opponent: string; market: string; line: string; start: string; bookmaker: string; control_side: string | null; candidate_side: string | null };
type MilestoneArm = { selected: number; settled: number; wins: number; losses: number; pushes: number; pending: number; void: number; stake_units: number; pnl_units: number; roi_pct: number | null };
type Milestone = { market: string; tour: string; side: string; line: number; label: string; quoted: number; fixtures: number; control: MilestoneArm; candidate: MilestoneArm };
type Report = { revision_note?: string; archived_revisions?: Array<{ implementation_revision: string; markets: Record<string, Market> }>; generated_at: string; status: string; error?: string | null; health: Record<string, number>; markets: Record<string, Market>; pending_rows: Pending[]; quote_cohorts?: Record<string, Record<string, { registered: number }>> };
const number = (value: number | null | undefined, digits = 2) => typeof value === "number" && Number.isFinite(value) ? value.toFixed(digits) : "Awaiting results";
const time = (value: string) => new Date(value).toLocaleString("en-GB", { timeZone: "Europe/London", day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit" });

export async function FullRefreshPanel() {
  const raw = await readTennisPropsMonitorFile(path.join(process.cwd(), "data/tennis-props/shadow/full-refresh-v1/report.json"));
  let parsed: Report | null = null;
  try { parsed = raw ? JSON.parse(raw) as Report : null; } catch { /* Show unavailable, never invented zero performance. */ }
  const report = parsed?.markets && parsed.generated_at ? parsed : null;
  let milestones: Milestone[] = [];
  try {
    const rawMilestones = await readTennisPropsMonitorFile(path.join(process.cwd(), "data/tennis-props/shadow/full-refresh-v1/milestones.json"));
    const grouped = rawMilestones ? JSON.parse(rawMilestones) : null;
    if (grouped?.generated_at === report?.generated_at && Array.isArray(grouped?.milestones)) milestones = grouped.milestones;
  } catch { /* Missing or stale summaries must not appear as zero ROI. */ }
  // This async server component evaluates evidence age once per request.
  const stale = report && Date.now() - Date.parse(report.generated_at) > 36 * 3600000;
  return <section id="full-refresh" className="scroll-mt-24 rounded-2xl border border-emerald-400/30 bg-slate-950/70 p-5 sm:p-6">
    <div className="flex flex-wrap items-start justify-between gap-3">
      <div><p className="text-xs font-bold uppercase tracking-widest text-emerald-300">Fresh inputs · same models</p><h2 className="mt-2 text-xl font-bold text-white">Full input refresh comparison</h2></div>
      <span className="rounded-full border border-amber-400/30 px-3 py-1 text-xs text-amber-200">Research only · no live stakes</span>
    </div>
    <p className="mt-3 max-w-4xl text-sm leading-6 text-slate-300">Does refreshing the full player history improve our ace and double fault forecasts? Both versions use the same captured Bet365 prices. The refreshed version includes newer serve, return and workload data, with the recent-form multiplier switched off.</p>
    <p className="mt-2 text-xs leading-5 text-slate-400">ATP aces use the existing v3 model. WTA aces and double faults use the canonical model. Hard and clay courts only. This is separate from Astra’s recent-rate experiment below.</p>
    {!report ? <p className="mt-4 text-amber-200">The collector report is unavailable. Performance cannot be verified.</p> : <>
      <div className="mt-4 flex flex-wrap gap-3 text-xs text-slate-400"><span>Updated {time(report.generated_at)} UK</span><span>{report.status === "BLOCKED" ? "Collector needs attention" : "Paired capture connected"}</span><span>Review: 200 settled matches per market, 4 tournaments and 56 days</span></div>
      {(report.error || stale) && <p role="status" className="mt-3 rounded-lg border border-amber-400/30 bg-amber-400/5 p-3 text-sm text-amber-200">{report.error ? `Capture warning: ${report.error}` : "Report is older than 36 hours. Check the daily pipeline before relying on its capture status."}</p>}
      {report.revision_note && <p className="mt-3 text-sm leading-6 text-slate-300">{report.revision_note}</p>}
      {!!report.archived_revisions?.length && <details className="mt-4 rounded-xl border border-slate-700 p-4">
        <summary className="cursor-pointer font-semibold text-emerald-200">Earlier versions and their results</summary>
        <p className="mt-2 text-xs leading-5 text-slate-400">These forecasts keep the prices and predictions recorded at the time. Their results are separate from the current version below.</p>
        {report.archived_revisions.map(archive => <div key={archive.implementation_revision} className="mt-4 border-t border-slate-800 pt-3">
          <h3 className="text-sm font-semibold text-white">{archive.implementation_revision === "original" ? "Before the tournament data repair" : "Completed matches with separate draw phases"}</h3>
          {Object.entries(archive.markets).map(([market, m]) => <div key={market} className="mt-2 text-xs leading-5 text-slate-400">
            <p>{market === "aces" ? "Aces" : "Double faults"}: {m.registered} quoted lines, {m.settled} settled, {m.pending} pending.</p>
            {(["control", "candidate"] as const).map(arm => <p key={arm}>{arm === "control" ? "Current history" : "Refreshed history"}: {m[arm].roi_pct == null ? "No settled selections" : `${number(m[arm].roi_pct, 1)}% ROI · ${number(m[arm].pnl_units)}u from ${m[arm].bets} settled selections`}</p>)}
          </div>)}
        </div>)}
      </details>}
      <div className="mt-5 grid gap-4 xl:grid-cols-2">{Object.entries(report.markets).map(([market, m]) => <article key={market} className="min-w-0 rounded-xl border border-slate-700/70 bg-slate-900/40 p-4">
        <h3 className="font-semibold text-white">{market === "aces" ? "Aces" : "Double faults"}</h3>
        <p className="mt-2 text-xs leading-5 text-slate-400">{m.registered_fixtures} matches registered · {m.registered} quoted lines · {m.settled} settled · {m.pending} pending · {m.overdue} overdue · {m.void} void</p>
        <div className="mt-4 grid grid-cols-2 gap-3">{(["control", "candidate"] as const).map(arm => <div key={arm} className={`rounded-lg border p-3 ${arm === "candidate" ? "border-emerald-400/30 bg-emerald-400/5" : "border-slate-700"}`}>
          <h4 className={`text-sm font-semibold ${arm === "candidate" ? "text-emerald-200" : "text-slate-200"}`}>{arm === "candidate" ? "Refreshed history" : "Current history"}</h4>
          <p className="mt-3 text-xl font-bold tabular-nums text-white">{m[arm].roi_pct == null ? "No settled picks" : `${number(m[arm].roi_pct, 1)}% ROI`}</p>
          <dl className="mt-3 space-y-2 text-xs text-slate-400">
            <div><dt>Paper profit</dt><dd className="text-slate-200">{number(m[arm].pnl_units)}u from {m[arm].bets} selected lines</dd></div>
            <div><dt>Wins / losses / pushes</dt><dd className="text-slate-200">{m[arm].wins} / {m[arm].losses} / {m[arm].pushes}</dd></div>
            <div><dt>Average count error · lower is better</dt><dd className="text-slate-200">{number(m[arm].count_mae)} · {m[arm].count_samples} player matches</dd></div>
            <div><dt>Probability error · lower is better</dt><dd className="text-slate-200">{number(m[arm].brier, 4)}</dd></div>
          </dl>
        </div>)}</div>
        <p className="mt-3 text-xs leading-5 text-slate-500">{m.independent_fixtures} distinct settled matches. Over-only quotes: {report.quote_cohorts?.over_only?.[market]?.registered ?? 0}. Two-way quotes: {report.quote_cohorts?.two_way?.[market]?.registered ?? 0}.</p>
      </article>)}</div>
      <p className="mt-4 text-xs leading-5 text-slate-400">One paper unit per selected line at a minimum 3% estimated edge. Several milestones from the same player are correlated, so quoted lines are not independent matches. Count accuracy uses one observation per player and match. Historical replay results are excluded. No automatic promotion.</p>
      <details open className="mt-5 rounded-xl border border-emerald-400/20 p-4">
        <summary className="cursor-pointer font-semibold text-emerald-200">Milestone results</summary>
        <p className="mt-2 text-xs leading-5 text-slate-400">3+ means at least three aces or double faults. ROI is paper profit divided by settled stake. One unit is the same hypothetical stake on each selected line. Pending and void bets do not enter ROI. A whole-number line returns the stake when the count equals the line.</p>
        {!milestones.length ? <p className="mt-3 text-sm text-amber-200">Milestone summary is unavailable or awaiting the latest collector report.</p> : <div className="mt-4 grid gap-4 lg:grid-cols-2">{["aces", "double_faults"].map(market => <div key={market} className="min-w-0">
          <h3 className="mb-3 font-semibold text-white">{market === "aces" ? "Ace milestones" : "Double fault milestones"}</h3>
          <div className="max-h-[32rem] space-y-3 overflow-y-auto pr-1">{milestones.filter(r => r.market === market).map(r => <article key={`${r.tour}-${r.side}-${r.line}`} className="rounded-lg border border-slate-700/60 bg-slate-900/50 p-3">
            <div className="flex flex-wrap items-center justify-between gap-2"><h4 className="font-bold text-white">{r.tour} · {r.label}</h4><span className="text-xs text-slate-400">{r.fixtures} matches · {r.quoted} quotes</span></div>
            <div className="mt-3 grid grid-cols-2 gap-3">{(["control", "candidate"] as const).map(arm => <div key={arm} className="min-w-0 text-xs leading-5">
              <p className={arm === "candidate" ? "font-semibold text-emerald-200" : "font-semibold text-slate-300"}>{arm === "control" ? "Current" : "Refreshed"}</p>
              <p className="mt-1 text-base font-bold text-white">{r[arm].roi_pct == null ? (r[arm].selected ? "Awaiting results" : "No selections") : `${number(r[arm].roi_pct, 1)}% ROI`}</p>
              <p className="text-slate-300">{number(r[arm].pnl_units)}u profit · {r[arm].stake_units}u settled</p>
              <p className="text-slate-400">{r[arm].wins}W / {r[arm].losses}L / {r[arm].pushes} pushes</p>
              <p className="text-slate-400">{r[arm].pending} pending · {r[arm].void} void</p>
            </div>)}</div>
          </article>)}</div>
        </div>)}</div>}
        <p className="mt-3 text-xs leading-5 text-slate-500">All captured thresholds are shown, including those with no selections. Several thresholds can refer to the same match; more lines do not mean more independent evidence.</p>
      </details>
      <details className="mt-4 rounded-xl border border-slate-800 p-4"><summary className="cursor-pointer text-sm font-semibold text-emerald-200">Pending comparisons</summary><p className="mt-2 text-xs text-slate-500">First 80 pending observations. These are frozen research selections, not current betting advice.</p><ul className="mt-3 max-h-72 space-y-2 overflow-auto">{report.pending_rows.map(r => <li key={r.id} className="rounded-lg bg-slate-900/70 p-3 text-xs leading-5 text-slate-300"><strong>{r.player}</strong> vs {r.opponent} · {time(r.start)} UK<br />{r.market === "aces" ? "Aces" : "Double faults"} {r.line} · {r.bookmaker}<br />Current: {r.control_side ?? "No selection"} · Refreshed: {r.candidate_side ?? "No selection"}</li>)}</ul></details>
      <details className="mt-3 text-xs text-slate-400"><summary className="cursor-pointer">Collector checks</summary><ul className="mt-2 space-y-1">{Object.entries(report.health).map(([reason, count]) => <li key={reason}>{reason.replaceAll("_", " ")}: {count}</li>)}</ul></details>
    </>}
  </section>;
}
