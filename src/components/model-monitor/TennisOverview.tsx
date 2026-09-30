import Link from "next/link";
import { readTennisEvidence } from "@/lib/tennis-evidence-reader";
import { object, tennisOverviewRows, type TennisOverviewRow } from "@/lib/tennis-monitor-overview";

const value = (n: number | null, suffix = "", digits = 0) => n === null ? "Unavailable" : `${n.toFixed(digits)}${suffix}`;
const tone = (n: number | null) => n === null ? "text-slate-400" : n < 0 ? "text-rose-300" : "text-emerald-300";
function ModelCard({ row }: { row: TennisOverviewRow }) {
  return <article className="rounded-2xl border border-slate-700 bg-slate-900 p-5">
    <div className="flex flex-wrap items-start justify-between gap-2"><h3 className="text-lg font-semibold">{row.name}</h3><span className="rounded-full border border-slate-600 px-3 py-1 text-xs text-cyan-200">{row.status}</span></div>
    <p className="mt-3 min-h-12 text-sm leading-6 text-slate-300">{row.note}</p>
    <dl className="mt-4 grid grid-cols-2 gap-4 sm:grid-cols-3">
      <div><dt className="text-xs text-slate-400">ROI</dt><dd className={`text-xl font-semibold ${tone(row.roi)}`}>{value(row.roi, "%", 2)}</dd></div>
      <div><dt className="text-xs text-slate-400">Profit / loss</dt><dd className={tone(row.pnl)}>{value(row.pnl, "u", 2)}</dd></div>
      <div><dt className="text-xs text-slate-400">Settled selections</dt><dd>{value(row.settled)}</dd></div>
      <div><dt className="text-xs text-slate-400">Wins / losses</dt><dd>{row.wins === null || row.losses === null ? "Unavailable" : `${row.wins} / ${row.losses}`}</dd></div>
      <div><dt className="text-xs text-slate-400">Pending observations</dt><dd>{value(row.pending)}</dd></div>
      <div><dt className="text-xs text-slate-400">Closing-price rows</dt><dd>{value(row.closes)}</dd></div>
    </dl>
    {row.fixtures !== null && <p className="mt-4 text-sm text-amber-200">{row.fixtures} independent fixtures in the paired experiment</p>}
    <div className="mt-4 border-t border-slate-800 pt-3 text-xs leading-5 text-slate-400"><p>Report cutoff: {row.date ?? "not supplied"}{row.stake !== null ? ` · ${value(row.stake, "u", 2)} recorded stakes` : ""}</p>{row.reportDate && <p>Report generated: {row.reportDate}</p>}{row.cohort && <p>Cohort: {row.cohort === "clean" ? "current-policy reporting period" : row.cohort}. A cutoff is not the latest match date.</p>}</div>
  </article>;
}
export default async function TennisOverview() {
  const { snapshot, checkedAt } = await readTennisEvidence();
  const generated = typeof snapshot?.generated_at === "string" ? snapshot.generated_at : null;
  const age = generated ? (checkedAt - Date.parse(generated)) / 36e5 : Infinity;
  const stale = !Number.isFinite(age) || age > 36;
  const rows = snapshot ? tennisOverviewRows(snapshot) : [];
  const sections = object(snapshot?.sections);
  const health = object(sections.tennis_props_pipeline_health);
  return <main className="min-h-screen bg-slate-950 px-4 py-8 text-slate-100"><div className="mx-auto max-w-6xl">
    <p className="text-xs font-semibold uppercase tracking-widest text-emerald-300">Private model monitor</p>
    <h1 className="mt-3 text-3xl font-semibold">Tennis models, clearly separated</h1>
    <p className="mt-3 max-w-3xl text-slate-300">See what is tracked, what is being tested and what is blocked. These are model records, separate from the website’s published picks. A fresh report can still contain old results.</p>
    <nav className="my-6 flex flex-wrap gap-3 text-sm text-emerald-200" aria-label="Model monitor navigation"><Link href="/model-monitor">All models</Link><a href="#tracked">Established trackers</a><a href="#research">Research results</a><a href="#blocked">Blocked work</a><Link href="/model-monitor/tennis?view=diagnostics">Detailed ledgers</Link><Link href="/model-monitor/tennis-props?tab=projections">Props projections</Link></nav>
    <div className={`mb-6 rounded-xl border p-4 ${stale ? "border-amber-700 text-amber-200" : "border-slate-700 text-slate-300"}`}>
      <p>{snapshot ? `Evidence snapshot: ${generated ?? "unknown"}${stale ? ". Needs refresh." : "."}` : "Evidence unavailable. Missing data is not zero profit or zero signals."}</p>
      {typeof health.state === "string" && <p className="mt-2 text-sm">Props feed: {health.state.replaceAll("_", " ").toLowerCase()}. Latest capture: {String(health.latest_capture_utc ?? "unknown")}.</p>}
    </div>
    {([ ["tracked", "Established trackers"], ["research", "Research results"] ] as const).map(([group, title]) => <section key={group} id={group} className="mb-9 scroll-mt-24"><h2 className="mb-4 text-xl font-semibold">{title}</h2><div className="grid gap-4 lg:grid-cols-2">{rows.filter(row => row.group === group).map(row => <ModelCard key={row.id} row={row} />)}</div></section>)}
    <section id="blocked" className="mb-9 scroll-mt-24"><details className="rounded-xl border border-amber-900/70 p-5"><summary className="cursor-pointer text-lg font-semibold text-amber-200">Blocked or not connected ({rows.filter(row => row.group === "blocked").length})</summary><p className="mt-3 text-sm text-slate-400">These are outstanding research tasks, not active betting recommendations.</p><div className="mt-4 divide-y divide-slate-800">{rows.filter(row => row.group === "blocked").map(row => <article key={row.id} className="py-4"><div className="flex flex-wrap justify-between gap-2"><h3 className="font-semibold">{row.name}</h3><span className="text-sm text-amber-200">{row.status}</span></div><p className="mt-2 text-sm leading-6 text-slate-300">{row.note}</p>{row.reportDate && <p className="mt-2 text-xs text-slate-400">Report generated: {row.reportDate}</p>}</article>)}</div></details></section>
    <details className="rounded-xl border border-slate-800 p-4 text-sm text-slate-400"><summary className="cursor-pointer text-slate-200">Inactive models and record definitions</summary><p className="mt-3">Old vNext experiments, the invalidated hard-court calibration, the original Challenger batch and paused CPI research are excluded from this dashboard’s current results. Grass and clay seasonal histories remain in the detailed ledgers. Historical files are retained for audit.</p><p className="mt-3">One unit is a standard stake. ROI is profit divided by recorded stakes. Research profits are hypothetical. Void or pushed selections can make settled totals differ from wins plus losses. Missing metrics remain unavailable.</p></details>
  </div></main>;
}
