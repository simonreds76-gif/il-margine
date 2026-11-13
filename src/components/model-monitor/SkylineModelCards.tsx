import { readSkylineMonitorReport } from "@/lib/goalscorer-monitor-snapshot";
import { reportSelectionHistory } from "@/lib/model-profit-history";
import ModelProfitChart from "./ModelProfitChart";

export default async function SkylineModelCards() {
  const report = await readSkylineMonitorReport();
  const variants = [["baseline", "Skyline"], ["delivery", "Skyline + delivery"], ["height", "Skyline + height"], ["combined", "Skyline + both"]] as const;
  return <section id="skyline" className="my-8 scroll-mt-24"><h2 className="text-xl font-semibold">Skyline · active paper versions</h2><p className="mt-2 mb-4 text-sm text-slate-400">Same first recorded confirmed forecasts and prices. One paper unit per selection. Each version keeps its own record.</p><div className="grid gap-4 md:grid-cols-2">{variants.map(([id,label]) => {
    const stats=report?.stats[id];
    const entries=report?.ledger.filter(r=>r.selections[id]).map(r=>({id:r.key,start:r.kickoff,status:r.status,profit:r.status==="win" ? r.odds-1 : r.status==="loss" ? -1 : null}));
    return <article key={id} className="min-w-0 rounded-2xl border border-slate-700 p-5"><h3 className="font-semibold">{label}</h3><p className="mt-3 text-xl font-semibold tabular-nums">{stats?.roi==null ? "Awaiting results" : `${stats.roi.toFixed(2)}% ROI`} <span className="text-sm text-slate-400">· {stats ? `${stats.profit.toFixed(2)}u` : "Report unavailable"}</span></p><p className="mt-2 text-xs text-slate-400">{stats ? `${stats.wins}W / ${stats.losses}L · ${stats.pending} pending · ${stats.overdue} overdue · ${stats.settled_stake}u settled` : "Missing evidence is not zero profit."}</p><ModelProfitChart name={label} history={reportSelectionHistory(entries,{settled:stats?.settled??null,profit:stats?.profit??null})}/><p className="mt-3 text-xs text-slate-400">Brier {stats?.brier?.toFixed(4)??"Unavailable"} · log loss {stats?.log_loss?.toFixed(4)??"Unavailable"} · {stats?.accuracy_n??0} scored forecasts</p><p className="mt-2 text-xs text-slate-400">Updated {report?.generated_at??"unavailable"}</p></article>;
  })}</div><a className="mt-3 inline-flex min-h-11 items-center text-sm text-cyan-200" href="/model-monitor/skyline">Skyline selections and contracts →</a></section>;
}
