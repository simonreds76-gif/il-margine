import { redirect } from "next/navigation";
import EloRebuildPanel from "@/components/model-monitor/EloRebuildPanel";
import Sisal5050Panel from "@/components/model-monitor/Sisal5050Panel";
import { isAdminSession } from "@/lib/admin-auth";
import { readAdminModels } from "@/lib/admin-model-reader";
import { snapshotAge, obj, type ModelRow } from "@/lib/admin-model-summary";

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
 props:'model=props',gk:'model=saves',team_shots_v4:'model=shots',corners_v3:'model=corners',astra:'model=astra',tennis_astrissimo:'model=astrissimo',tennis_hardcourt_scout:'model=scout','aces-v4':'model=aces4'
};
function ModelCard({r, now}: {r: ModelRow; now: number}) {
  const age = snapshotAge(r.date, now);
  return <article className="min-w-0 rounded-2xl border border-slate-700/70 bg-slate-900/60 p-5">
    <div className="flex flex-wrap items-start justify-between gap-2"><h3 className="text-lg font-semibold text-white">{r.name}</h3><span className="rounded-full border border-slate-700 px-2 py-1 text-[11px] text-slate-300">{r.cohort}</span></div>
    <dl className="mt-5 grid grid-cols-2 gap-4"><div><dt className="text-xs text-slate-400">ROI</dt><dd className={`mt-1 text-2xl font-semibold tabular-nums ${tone(r.roi)}`}>{signed(r.roi, "%")}</dd></div><div><dt className="text-xs text-slate-400">Profit</dt><dd className={`mt-1 text-2xl font-semibold tabular-nums ${tone(r.profit)}`}>{signed(r.profit, "u")}</dd></div>
      <div><dt className="text-xs text-slate-400">Settled selections</dt><dd className="mt-1 tabular-nums">{format(r.settled)}</dd></div><div><dt className="text-xs text-slate-400">Awaiting settlement</dt><dd className="mt-1 tabular-nums">{r.pending!==null&&r.pending>0&&recordLinks[r.id]?<a className="inline-flex min-h-11 items-center text-emerald-200 underline underline-offset-4" href={`/admin/models/signals?${recordLinks[r.id]}&status=pending`} aria-label={`View ${r.pending} unsettled ${r.name} selections`}>{format(r.pending)} →</a>:format(r.pending)}</dd></div></dl>
    <details className="mt-4 border-t border-slate-700/70 pt-3"><summary className="cursor-pointer text-sm text-emerald-200 focus-visible:outline focus-visible:outline-emerald-300">Record details</summary><dl className="mt-3 grid grid-cols-2 gap-3 text-sm"><div><dt className="text-slate-400">Wins / losses</dt><dd>{format(r.wins)} / {format(r.losses)}</dd></div><div><dt className="text-slate-400">Settled stake</dt><dd>{r.stake === null ? "Not supplied" : `${format(r.stake, 2)}u`}</dd></div></dl><p className="mt-3 text-xs leading-relaxed text-slate-300">{r.note}</p>{r.status && r.status !== "OK" && <p className="mt-2 break-words text-xs text-slate-400">Reported status: {r.status.replaceAll("_", " ").toLowerCase()}</p>}</details>
    {r.id.startsWith("provisional")?<p className="mt-4 text-xs text-slate-400">Summary available. Individual provisional selections are not included in the hosted snapshot yet.</p>:<a className="mt-4 inline-flex min-h-11 items-center text-sm font-semibold text-emerald-200" href={`/admin/models/signals?${recordLinks[r.id] || "model=props"}`}>Open selections &amp; results →</a>}<p className={`mt-2 text-xs ${age === "Recent" ? "text-slate-400" : "text-amber-200"}`}>{age} report · {date(r.date)} UK</p>
  </article>;
}
export default async function AdminModels({ searchParams }: { searchParams: Promise<{ sisalPage?: string }> }) {
  if (!await isAdminSession()) redirect("/admin");
  const data = await readAdminModels();
  const inputHealth = obj(data.inputHealth);
  const inputChecked = typeof inputHealth.checked_at === 'string' ? inputHealth.checked_at : null;
  const count = (key: string) => typeof inputHealth[key] === 'number' && Number.isFinite(inputHealth[key]) ? format(inputHealth[key]) : 'Not supplied';
  const params = await searchParams;
  const researchIds=new Set(['astra','tennis_astrissimo','tennis_hardcourt_scout','aces-v4']);
  const current=data.rows.filter(r=>!researchIds.has(r.id)&&!r.id.startsWith('props-'));
  const groups=[...new Set(current.map(r=>r.group))];
  return <main className="min-h-screen bg-[#0f1117] px-4 py-8 text-slate-100 sm:px-6"><div className="mx-auto max-w-6xl">
    <header className="flex flex-wrap items-start justify-between gap-4"><div><p className="text-xs font-semibold uppercase tracking-widest text-emerald-300">Il Margine · Private</p><h1 className="mt-2 text-3xl font-bold">Model monitor</h1><p className="mt-3 max-w-2xl text-sm leading-relaxed text-slate-300">Choose a current model to inspect its selections, prices and results. Research trials have their own section below.</p></div><nav aria-label="Monitor actions" className="flex flex-wrap gap-2"><a href="/admin" className="rounded-xl border border-slate-600 px-4 py-3 text-sm hover:bg-slate-800">Back to Admin</a><a href="/admin/penalties" className="rounded-xl border border-slate-600 px-4 py-3 text-sm hover:bg-slate-800">Penalty reviews</a><a href="/admin/models" className="rounded-xl border border-emerald-400/40 bg-emerald-400/10 px-4 py-3 text-sm text-emerald-200 hover:bg-emerald-400/20">Refresh records</a></nav></header>
    <section aria-labelledby="tennis-input-health" className="mt-6 rounded-2xl border border-amber-400/40 bg-amber-400/5 p-4 sm:p-5">
      <h2 id="tennis-input-health" className="text-base font-semibold text-amber-100">Tennis input checks</h2>
      <p className="mt-2 text-sm leading-relaxed text-slate-200">Elo refresh lineage is unverified. Fresh bookmaker odds do not confirm that player ratings are current. Pricing formulas remain unchanged.</p>
      <p className="mt-2 text-xs text-amber-200">{inputChecked ? `${snapshotAge(inputChecked, data.checkedAt)} check · ${date(inputChecked)} UK` : 'Health check unavailable'} · {typeof inputHealth.status === 'string' ? inputHealth.status.replaceAll('_', ' ') : 'UNKNOWN'}</p>
      <dl className="mt-4 grid grid-cols-1 gap-3 text-sm sm:grid-cols-3">
        <div><dt className="text-slate-400">Stored forecasts checked</dt><dd className="mt-1 font-semibold tabular-nums">{count('stored_forecast_count')}</dd></div>
        <div><dt className="text-slate-400">Stored forecasts missing Elo</dt><dd className="mt-1 font-semibold tabular-nums">{count('stored_forecasts_missing_elo')}</dd></div>
        <div><dt className="text-slate-400">Unpriced candidates missing Elo</dt><dd className="mt-1 font-semibold tabular-nums">{count('unpriced_candidates_missing_elo')} / {count('unpriced_export_candidates')}</dd></div>
      </dl>
      <details className="mt-4 text-sm"><summary className="min-h-11 cursor-pointer py-3 text-amber-100">What this check covers</summary><p className="mt-2 leading-relaxed text-slate-300">Checks run around each existing daily or on-demand forecast. They observe stored inputs before and after the run; they are not an atomic trace of the exact reads inside the pricing engine. Missing inputs expose existing fallback behaviour. A present row is not proof of freshness.</p><ul className="mt-3 space-y-1 text-slate-300">{Object.entries(obj(inputHealth.checks)).map(([key, value]) => <li key={key}>{key.replaceAll('_', ' ')}: {typeof value === 'string' ? value.replaceAll('_', ' ').toLowerCase() : 'unavailable'}</li>)}</ul></details>
    </section>
    <a href="/admin/models/signals" className="my-6 inline-flex min-h-12 items-center rounded-xl border border-emerald-400/40 bg-emerald-400/10 px-5 py-3 font-semibold text-emerald-200">Browse signals &amp; results →</a>
    <nav aria-label="Tennis forecasts" className="mb-6 grid gap-3 sm:grid-cols-2"><a href="/admin/models/signals?model=props&view=props-board" className="min-w-0 rounded-xl border border-cyan-400/30 bg-cyan-400/5 p-4"><strong className="text-cyan-100">Aces forecasts</strong><span className="mt-1 block text-sm text-slate-300">Expected aces per player and match total &rarr;</span></a><a href="/admin/models/signals?model=mostaces&view=most-aces-current" className="min-w-0 rounded-xl border border-slate-600 p-4"><strong>Most Aces 1X2</strong><span className="mt-1 block text-sm text-slate-300">Three fair odds, bookmaker prices and paper research &rarr;</span></a></nav>
    <a href="/model-monitor/skyline" className="mb-6 flex flex-wrap items-center justify-between gap-3 rounded-2xl border border-cyan-400/30 bg-cyan-400/5 p-5"><span><strong className="text-lg text-cyan-200">Skyline</strong><span className="mt-1 block text-sm text-slate-300">Headed shots on target · Bet365 comparison · Paper ROI</span></span><span className="text-sm text-cyan-200">Open paper monitor →</span></a>
    <p className="mb-6 text-xs leading-relaxed text-slate-400">ROI is profit divided by settled stake. Records remain separate because models can select the same match. A unit is the recorded reference stake.</p>
    {groups.map((g,i)=><section key={g} id={`group-${i}`} className="mb-9"><h2 className="mb-4 text-xl font-semibold">{g==='Football research'?'Football models':g}</h2><div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">{current.filter(r=>r.group===g).map(r=><ModelCard key={r.id} r={r} now={data.checkedAt}/>)}</div></section>)}
    <EloRebuildPanel value={data.eloRebuild} />
    <Sisal5050Panel value={data.sisal5050} page={Number(params.sisalPage) || 1} />
    <details className="mb-6 rounded-2xl border border-slate-700 p-5"><summary className="cursor-pointer text-xl font-semibold">Research trials <span className="ml-2 text-sm font-normal text-slate-400">Paper only</span></summary><p className="mt-3 text-sm text-slate-400">Separate experiments. Their results do not replace the current models.</p><div className="mt-5 grid gap-4 md:grid-cols-2">{data.rows.filter(r=>researchIds.has(r.id)).map(r=><ModelCard key={r.id} r={r} now={data.checkedAt}/>)}</div></details>
    <details className="rounded-2xl border border-slate-700 p-5"><summary className="cursor-pointer text-sm text-slate-300">Data freshness and market breakdowns</summary><div className="mt-4 space-y-3">{data.sources.map(s=>{const d=typeof s.date==='string'?s.date:null;return <p key={s.name} className="text-sm text-slate-400">{s.name}: {!s.available?'Unavailable':snapshotAge(d,data.checkedAt)} · {date(d)} UK</p>;})}</div><p className="mt-3 text-xs text-slate-400">A recent report does not confirm every capture or settlement is current.</p><div className="mt-5 grid gap-4 md:grid-cols-2">{data.rows.filter(r=>r.id.startsWith('props-')).map(r=><ModelCard key={r.id} r={r} now={data.checkedAt}/>)}</div></details>
    <aside className="mt-6 text-sm leading-relaxed text-slate-400">This dashboard reads existing private snapshots only. Refreshing it does not run a model or send alerts. Use the existing tennis run control in Admin to queue a forecast; the Windows machine must be awake for local OnCourt processing. Older local diagnostics remain available on your PC.</aside>
  </div></main>;
}
