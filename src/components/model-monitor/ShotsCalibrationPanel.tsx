import { readTeamShotsLiveJson } from "@/lib/team-shots-live-files";
import { monitorRequestTime } from "@/lib/monitor-request-time";

type Selection = { settled: number; wins: number; losses: number; pnl_units: number; roi: number | null; pending: number; overdue: number; stake_units: number; unavailable_contracts: number };
type Score = { brier: number | null; log_loss: number | null; market_brier: number | null; hypothetical_selections: Selection };
type Snapshot = { version: string; generated_at: string; status: string; contracts: number; paired_fixtures: number; latest_archived_capture: string | null; conflicting_results: number; models: Record<string, Score> };
const names = [["shots_market_offset_v1", "Calibrated Team Shots"], ["opponent", "Opponent Shots"], ["v4", "Team Shots v4"], ["ema20_v3", "EMA20 v3 reference"]] as const;
const number = (v: number | null | undefined, digits = 0, suffix = "") => typeof v === "number" && Number.isFinite(v) ? `${v.toFixed(digits)}${suffix}` : "Awaiting evidence";

export default async function ShotsCalibrationPanel() {
  const [data, checkedAt] = await Promise.all([readTeamShotsLiveJson<Snapshot>("data/football-form/team-shots-paired-reference-status.json"), monitorRequestTime()]);
  const current = data?.version === "paired-market-offset-20260930-v2" ? data : null;
  const stale = !current || !Number.isFinite(Date.parse(current.generated_at)) || checkedAt - Date.parse(current.generated_at) > 36 * 3600000;
  return <section className="rounded-2xl border border-emerald-900 bg-slate-900/70 p-5 sm:p-6" aria-labelledby="calibrated-shots-title">
    <p className="text-xs font-semibold uppercase tracking-wider text-emerald-300">Fixed forward comparison · Zero real stake</p>
    <h2 id="calibrated-shots-title" className="mt-2 text-2xl font-semibold text-white">Calibrated Team Shots</h2>
    <p className="mt-3 max-w-4xl text-sm leading-6 text-slate-300">The frozen calibration is compared with three existing models using the same fresh prices. Only predictions saved before kickoff belong here. The earlier historical test is excluded from these results.</p>
    <p className={`mt-3 text-sm ${stale ? "text-amber-200" : "text-emerald-200"}`}>{!current ? "Current comparison snapshot unavailable." : `${current.status === "WAITING_FOR_FRESH_PAIRED_MARKETS" ? "Collector checked. Waiting for fresh paired markets." : "Collecting forward evidence."} ${stale ? "Snapshot needs refresh. " : ""}Last scan: ${current.generated_at}`}</p>
    {current && <><p className="mt-2 text-xs text-slate-400">{current.contracts} registered contracts · {current.paired_fixtures} independent settled fixtures with all models · Latest archived quote: {current.latest_archived_capture ?? "unavailable"}</p>
      {current.conflicting_results > 0 && <p className="mt-2 text-sm text-amber-200">{current.conflicting_results} conflicting results remain unresolved.</p>}
      <div className="mt-5 grid gap-4 sm:grid-cols-2">{names.map(([id, name]) => {
        const score = current.models[id]; const picks = score?.hypothetical_selections;
        return <article key={id} className={`rounded-xl border p-4 ${id === "shots_market_offset_v1" ? "border-emerald-500/60 bg-emerald-950/30" : "border-slate-700"}`}>
          <h3 className="font-semibold text-white">{name}</h3>
          <dl className="mt-3 grid grid-cols-2 gap-3 text-sm">
            <div><dt className="text-slate-400">Forward ROI</dt><dd className="text-lg font-semibold">{number(picks?.roi == null ? null : picks.roi * 100, 2, "%")}</dd></div>
            <div><dt className="text-slate-400">Hypothetical P/L</dt><dd>{number(picks?.pnl_units, 2, "u")}</dd></div>
            <div><dt className="text-slate-400">Wins / losses</dt><dd>{number(picks?.wins)} / {number(picks?.losses)}</dd></div>
            <div><dt className="text-slate-400">Settled / stake</dt><dd>{number(picks?.settled)} / {number(picks?.stake_units, 0, "u")}</dd></div>
            <div><dt className="text-slate-400">Pending / overdue</dt><dd>{number(picks?.pending)} / {number(picks?.overdue)}</dd></div>
            <div><dt className="text-slate-400">Unavailable forecasts</dt><dd>{number(picks?.unavailable_contracts)}</dd></div>
          </dl>
          <p className="mt-3 border-t border-slate-700 pt-3 text-xs leading-5 text-slate-400">Paired Brier: {number(score?.brier, 4)} · Market: {number(score?.market_brier, 4)}<br/>Log loss: {number(score?.log_loss, 4)}</p>
        </article>;
      })}</div></>}
    <p className="mt-4 text-xs leading-5 text-slate-400">Lower Brier and log loss mean more accurate probabilities. Each fixture counts once in these scores; selections can differ between models. A hypothetical unit is one equal test stake. Review at 50 and 150 settled fixtures. Closing-price comparison and StatsHub capture are not connected. No automatic promotion.</p>
  </section>;
}
