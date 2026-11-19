import { monitorFamilies } from "@/lib/monitor-families";
import MonitorFragment from "@/components/model-monitor/MonitorFragment";
import GoalscorerModelCards from "@/components/model-monitor/GoalscorerModelCards";
import { Suspense } from "react";
import SkylineModelCards from "@/components/model-monitor/SkylineModelCards";
import { redirect } from "next/navigation";
import ShotsCalibrationPanel from "@/components/model-monitor/ShotsCalibrationPanel";
import MatchShapePanel from "@/components/model-monitor/MatchShapePanel";
import BreakPointPaperPanel from "@/components/model-monitor/BreakPointPaperPanel";
import Sisal5050Panel from "@/components/model-monitor/Sisal5050Panel";
import ModelProfitChart from "@/components/model-monitor/ModelProfitChart";
import type { ProfitHistory } from "@/lib/model-profit-history";
import { isAdminSession } from "@/lib/admin-auth";
import { readAdminModels } from "@/lib/admin-model-reader";
import { snapshotAge, type ModelRow } from "@/lib/admin-model-summary";

export const dynamic = "force-dynamic";
export const fetchCache = "force-no-store";
export const metadata = { title: "Private model monitor", robots: { index: false, follow: false } };
const format = (n: number | null, digits = 0) => n === null ? "Not supplied" : n.toLocaleString("en-GB", {maximumFractionDigits: digits});
const signed = (n: number | null, suffix: string) => n === null ? "Not available" : `${n > 0 ? "+" : ""}${format(n, 2)}${suffix}`;
const tone = (n: number | null) => n === null || n === 0 ? "text-slate-200" : n > 0 ? "text-emerald-300" : "text-rose-300";
function date(value: string | null) {
  return value && Number.isFinite(Date.parse(value)) ? new Date(value).toLocaleString("en-GB", {timeZone: "Europe/London", dateStyle: "medium", timeStyle: "short"}) : "Date unavailable";
}
const recordLinks: Record<string,string> = {
 strict:'model=tennis&view=tennis-strict-archive', volume_200:'model=tennis&view=tennis-volume200-archive',challenger:'model=tennis&view=tennis-challenger-ml-v2-archive',spread_v1:'model=handicaps&view=tennis-spreadv1-archive',
 props:'model=props',gk:'model=saves',team_shots_v4:'model=shots',team_shots_opponent:'model=opponent',corners_v3:'model=corners',astra:'model=astra',tennis_astrissimo:'model=astrissimo',tennis_hardcourt_scout:'model=scout',tennis_indoor_paper:'model=indoor',tennis_indoor_expansion:'model=indoor-expansion','aces-v4':'model=aces4'
};
function ModelCard({r, now, history}: {r: ModelRow; now: number; history?: ProfitHistory}) {
  const age = snapshotAge(r.date, now);
  return <article id={`model-${r.id}`} className="scroll-mt-24 min-w-0 rounded-2xl border border-slate-700/70 bg-slate-900/60 p-5">
    <div className="flex flex-wrap items-start justify-between gap-2"><h3 className="text-lg font-semibold text-white">{r.name}</h3><span className="rounded-full border border-slate-700 px-2 py-1 text-[11px] text-slate-300">{r.cohort}</span></div>
    <dl className="mt-5 grid grid-cols-2 gap-4"><div><dt className="text-xs text-slate-400">ROI</dt><dd className={`mt-1 text-2xl font-semibold tabular-nums ${tone(r.roi)}`}>{signed(r.roi, "%")}</dd></div><div><dt className="text-xs text-slate-400">Profit</dt><dd className={`mt-1 text-2xl font-semibold tabular-nums ${tone(r.profit)}`}>{signed(r.profit, "u")}</dd></div>
      <div><dt className="text-xs text-slate-400">Settled selections</dt><dd className="mt-1 tabular-nums">{format(r.settled)}</dd></div><div><dt className="text-xs text-slate-400">Awaiting settlement</dt><dd className="mt-1 tabular-nums">{r.pending!==null&&r.pending>0&&recordLinks[r.id]?<a className="inline-flex min-h-11 items-center text-emerald-200 underline underline-offset-4" href={`/admin/models/signals?${recordLinks[r.id]}&status=pending`} aria-label={`View ${r.pending} unsettled ${r.name} selections`}>{format(r.pending)} →</a>:format(r.pending)}</dd></div></dl>
    <ModelProfitChart history={history ?? {days:[],settled:0,profit:0,omitted:0,message:r.settled===0 ? "Awaiting qualifying settled paper selections." : "Dated selection history unavailable in this report."}} name={r.name} />
    {r.calibration && <div className="mt-3 flex flex-wrap gap-x-4 gap-y-1 text-xs text-slate-300">{Object.entries(r.calibration).filter(([key,v])=>["brier","log_loss","logloss","bias_pct","model_brier","model_ll","candidate_brier","brier_delta"].includes(key)&&typeof v==="number"&&Number.isFinite(v)).map(([key,v])=><span key={key}>{({brier:"Brier",log_loss:"Log loss",logloss:"Log loss",bias_pct:"Count bias %",model_brier:"Model Brier",model_ll:"Model log loss",candidate_brier:"Candidate Brier",brier_delta:"Paired Brier difference"} as Record<string,string>)[key]}: {Number(v).toFixed(key==="bias_pct"?2:4)}</span>)}</div>}
    {(r.overdue!=null||r.fixtures!=null)&&<p className="mt-2 text-xs text-slate-400">{r.fixtures!=null?`${r.fixtures} settled fixtures · `:""}{r.overdue!=null?`${r.overdue} overdue selections`:""}</p>}
    {r.capture_at&&<p className="mt-2 text-xs text-slate-400">Capture checked {date(r.capture_at)} UK</p>}
    <details className="mt-4 border-t border-slate-700/70 pt-3"><summary className="cursor-pointer text-sm text-emerald-200 focus-visible:outline focus-visible:outline-emerald-300">Record details</summary><dl className="mt-3 grid grid-cols-2 gap-3 text-sm"><div><dt className="text-slate-400">Wins / losses</dt><dd>{format(r.wins)} / {format(r.losses)}</dd></div><div><dt className="text-slate-400">Settled stake</dt><dd>{r.stake === null ? "Not supplied" : `${format(r.stake, 2)}u`}</dd></div></dl><p className="mt-3 text-xs leading-relaxed text-slate-300">{r.note}</p>{r.status && r.status !== "OK" && <p className="mt-2 break-words text-xs text-slate-400">Reported status: {r.status.replaceAll("_", " ").toLowerCase()}</p>}</details>
    {r.id.startsWith("provisional")?<p className="mt-4 text-xs text-slate-400">Summary available. Individual provisional selections are not included in the hosted snapshot yet.</p>:<a className="mt-4 inline-flex min-h-11 items-center text-sm font-semibold text-emerald-200" href={r.link || (recordLinks[r.id] ? `/admin/models/signals?${recordLinks[r.id]}` : `#model-${r.id}`)}>{r.id.startsWith("props-") ? "Open combined props record →" : r.link || recordLinks[r.id] ? "Open selections & results →" : "Paper record shown above"}</a>}<p className={`mt-2 text-xs ${age === "Recent" ? "text-slate-400" : "text-amber-200"}`}>{age} report · {date(r.date)} UK</p>
  </article>;
}
export default async function AdminModels({ searchParams }: { searchParams: Promise<{ sisalPage?: string }> }) {
  if (!await isAdminSession()) redirect("/admin");
  const data = await readAdminModels();
  const params = await searchParams;
  const families = monitorFamilies(data.rows);
  const card = (r: ModelRow) => <ModelCard key={r.id} r={r} now={data.checkedAt} history={data.histories[r.id]} />;
  const panels: Record<string, React.ReactNode> = {
    shape: <MatchShapePanel value={data.matchShape} />,
    breaks: data.breakpointC ? <BreakPointPaperPanel value={data.breakpointC} /> : <p>Awaiting a break-point report.</p>,
    sisal: data.sisal5050 ? <Sisal5050Panel value={data.sisal5050} page={Number(params.sisalPage) || 1} /> : <p>Awaiting a Sisal report.</p>,
    shots: <ShotsCalibrationPanel />,
    skyline: <><a href="/model-monitor/skyline" className="inline-flex min-h-11 items-center text-sm text-cyan-200">Open Skyline paper monitor →</a><Suspense fallback={<p>Loading Skyline records…</p>}><SkylineModelCards /></Suspense></>,
    goals: <Suspense fallback={<p>Loading goalscorer records…</p>}><GoalscorerModelCards /></Suspense>,
  };
  return <main className="min-h-screen bg-[#0f1117] px-4 py-8 text-slate-100 sm:px-6"><div className="mx-auto max-w-6xl">
    <header className="flex flex-wrap items-start justify-between gap-4"><div><p className="text-xs font-semibold uppercase tracking-widest text-emerald-300">Il Margine · Private</p><h1 className="mt-2 text-3xl font-bold">Model monitor</h1><p className="mt-3 max-w-2xl text-sm leading-relaxed text-slate-300">Every running model and active paper comparison in one place. Retired and paused experiments are not listed. Results stay separate; nothing here promotes a model or changes stakes.</p></div><nav aria-label="Monitor actions" className="flex flex-wrap gap-2"><a href="/admin/models/price-moves" className="rounded-xl border border-slate-600 px-4 py-3 text-sm hover:bg-slate-800">Tennis price moves</a><a href="/admin" className="rounded-xl border border-slate-600 px-4 py-3 text-sm hover:bg-slate-800">Back to Admin</a><a href="/admin/penalties" className="rounded-xl border border-slate-600 px-4 py-3 text-sm hover:bg-slate-800">Penalty reviews</a><a href="/admin/models" className="rounded-xl border border-emerald-400/40 bg-emerald-400/10 px-4 py-3 text-sm text-emerald-200 hover:bg-emerald-400/20">Refresh records</a></nav></header>
    <a href="/admin/models/signals" className="my-6 inline-flex min-h-12 items-center rounded-xl border border-emerald-400/40 bg-emerald-400/10 px-5 py-3 font-semibold text-emerald-200">Browse signals &amp; results →</a>
    <nav aria-label="Tennis forecasts" className="mb-6 grid gap-3 sm:grid-cols-2"><a href="/admin/models/signals?model=props&view=props-board" className="min-w-0 rounded-xl border border-cyan-400/30 bg-cyan-400/5 p-4"><strong className="text-cyan-100">Aces forecasts</strong><span className="mt-1 block text-sm text-slate-300">Expected aces per player and match total &rarr;</span></a><a href="/admin/models/signals?model=mostaces&view=most-aces-current" className="min-w-0 rounded-xl border border-slate-600 p-4"><strong>Most Aces 1X2</strong><span className="mt-1 block text-sm text-slate-300">Three fair odds, bookmaker prices and paper research &rarr;</span></a></nav>
    <MonitorFragment />
    {!data.activeAvailable && <p className="mb-4 text-sm text-amber-200">The expanded running-model snapshot is unavailable. The latest available records are shown below.</p>}
    {data.activeWarnings.length>0&&<p className="mb-4 rounded-xl border border-amber-700 p-4 text-sm text-amber-200">Model display needs attention: {data.activeWarnings.join(", ")}. Other model records remain available.</p>}
    <p className="mb-6 text-xs leading-relaxed text-slate-400">ROI is profit divided by settled stake. Records remain separate because models can select the same match. A unit is the recorded reference stake.</p>
    {(["Tennis", "Football", "Other"] as const).map(sport => {
      const items = families.filter(family => family.sport === sport);
      if (!items.length) return null;
      return <section key={sport} className="mb-8" aria-label={sport}>
        <h2 className="mb-3 text-xl font-semibold">{sport}</h2>
        <div className="space-y-2">{items.map(family => {
          const breakdowns = family.rows.filter(r => r.id.startsWith("props-"));
          const cards = family.rows.filter(r => !r.id.startsWith("props-"));
          const attention = family.rows.filter(r => (r.overdue ?? 0) > 0).length;
          return <details key={family.id} id={`family-${family.id}`} data-model-family={family.id}
            open={family.id === "sisal" && Boolean(params.sisalPage) || undefined}
            className="group/family scroll-mt-24 rounded-xl border border-slate-700/80 bg-slate-900/40">
            <summary className="flex min-h-14 cursor-pointer list-none items-center justify-between gap-3 rounded-xl px-4 py-3 hover:bg-slate-800/60 focus-visible:outline focus-visible:outline-emerald-300 [&::-webkit-details-marker]:hidden">
              <span className="min-w-0 font-semibold">{family.label}</span>
              <span className="flex shrink-0 items-center gap-3">
                {attention > 0 && <span className="text-xs text-amber-200" title="Model records with overdue settlements">Overdue · {attention}</span>}
                <span aria-hidden="true" className="inline-block text-lg text-emerald-200 transition-transform group-open/family:rotate-90">›</span>
              </span>
            </summary>
            <div className="min-w-0 border-t border-slate-700/70 p-3 sm:p-4">
              {family.aliases.map(id => <span key={id} id={id} className="block scroll-mt-24" />)}
              {cards.length > 0 && <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">{cards.map(card)}</div>}
              {breakdowns.length > 0 && <section id="props-breakdowns" className="mt-5 scroll-mt-24">
                <h3 className="font-semibold">Aces &amp; double faults · separate records</h3>
                <p className="mb-3 mt-1 text-sm text-slate-400">Market and tour breakdowns cover overlapping selections.</p>
                <div className="grid gap-4 md:grid-cols-2">{breakdowns.map(card)}</div>
              </section>}
              {panels[family.id]}
            </div>
          </details>;
        })}</div>
      </section>;
    })}
    <details className="rounded-2xl border border-slate-700 p-5"><summary className="cursor-pointer text-sm text-slate-300">Data freshness</summary><div className="mt-4 space-y-3">{data.sources.map(s=>{const d=typeof s.date==='string'?s.date:null;return <p key={s.name} className="text-sm text-slate-400">{s.name}: {!s.available?'Unavailable':snapshotAge(d,data.checkedAt)} · {date(d)} UK</p>;})}</div><p className="mt-3 text-xs text-slate-400">A recent report does not confirm every capture or settlement is current.</p></details>
    <aside className="mt-6 text-sm leading-relaxed text-slate-400">This dashboard reads existing private snapshots only. Refreshing it does not run a model or send alerts. Use the existing tennis run control in Admin to queue a forecast; the Windows machine must be awake for local OnCourt processing. Older local diagnostics remain available on your PC.</aside>
  </div></main>;
}