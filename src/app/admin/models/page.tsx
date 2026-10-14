import { redirect } from "next/navigation";
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
function ModelCard({r, now}: {r: ModelRow; now: number}) {
  const age = snapshotAge(r.date, now);
  return <article className="min-w-0 rounded-2xl border border-slate-700/70 bg-slate-900/60 p-5">
    <div className="flex flex-wrap items-start justify-between gap-2"><h3 className="text-lg font-semibold text-white">{r.name}</h3><span className="rounded-full border border-slate-700 px-2 py-1 text-[11px] text-slate-300">{r.cohort}</span></div>
    <dl className="mt-5 grid grid-cols-2 gap-4"><div><dt className="text-xs text-slate-400">ROI</dt><dd className={`mt-1 text-2xl font-semibold tabular-nums ${tone(r.roi)}`}>{signed(r.roi, "%")}</dd></div><div><dt className="text-xs text-slate-400">Profit</dt><dd className={`mt-1 text-2xl font-semibold tabular-nums ${tone(r.profit)}`}>{signed(r.profit, "u")}</dd></div>
      <div><dt className="text-xs text-slate-400">Settled selections</dt><dd className="mt-1 tabular-nums">{format(r.settled)}</dd></div><div><dt className="text-xs text-slate-400">Pending selections</dt><dd className="mt-1 tabular-nums">{format(r.pending)}</dd></div></dl>
    <details className="mt-4 border-t border-slate-700/70 pt-3"><summary className="cursor-pointer text-sm text-emerald-200 focus-visible:outline focus-visible:outline-emerald-300">Record details</summary><dl className="mt-3 grid grid-cols-2 gap-3 text-sm"><div><dt className="text-slate-400">Wins / losses</dt><dd>{format(r.wins)} / {format(r.losses)}</dd></div><div><dt className="text-slate-400">Settled stake</dt><dd>{r.stake === null ? "Not supplied" : `${format(r.stake, 2)}u`}</dd></div></dl><p className="mt-3 text-xs leading-relaxed text-slate-300">{r.note}</p>{r.status && r.status !== "OK" && <p className="mt-2 break-words text-xs text-slate-400">Reported status: {r.status.replaceAll("_", " ").toLowerCase()}</p>}</details>
    <p className={`mt-4 text-xs ${age === "Recent" ? "text-slate-400" : "text-amber-200"}`}>{age} report · {date(r.date)} UK</p>
  </article>;
}
export default async function AdminModels() {
  if (!await isAdminSession()) redirect("/admin");
  const data = await readAdminModels();
  const groups = [...new Set(data.rows.map(r => r.group))];
  return <main className="min-h-screen bg-[#0f1117] px-4 py-8 text-slate-100 sm:px-6"><div className="mx-auto max-w-6xl">
    <header className="flex flex-wrap items-start justify-between gap-4"><div><p className="text-xs font-semibold uppercase tracking-widest text-emerald-300">Il Margine · Private</p><h1 className="mt-2 text-3xl font-bold">Model monitor</h1><p className="mt-3 max-w-2xl text-sm leading-relaxed text-slate-300">Your saved model records, available without starting the local website. Refresh this page to read the latest uploaded summaries.</p></div><nav aria-label="Monitor actions" className="flex flex-wrap gap-2"><a href="/admin" className="rounded-xl border border-slate-600 px-4 py-3 text-sm hover:bg-slate-800">Back to Admin</a><a href="/admin/penalties" className="rounded-xl border border-slate-600 px-4 py-3 text-sm hover:bg-slate-800">Penalty reviews</a><a href="/admin/models" className="rounded-xl border border-emerald-400/40 bg-emerald-400/10 px-4 py-3 text-sm text-emerald-200 hover:bg-emerald-400/20">Refresh records</a></nav></header>
    <a href="/admin/models/signals" className="my-6 block rounded-2xl border border-emerald-400/40 bg-emerald-400/10 p-5"><strong className="text-lg text-emerald-200">Open signals and full records →</strong><span className="mt-2 block text-sm text-slate-300">Tennis, aces, double faults, goalkeeper saves, team shots, corners and goalscorers. Search individual selections, outcomes, prices and model reports.</span></a><section aria-label="Source freshness" className="my-7 grid gap-3 sm:grid-cols-2">{data.sources.map(s => {const d = typeof s.date === "string" ? s.date : null; const age = snapshotAge(d, data.checkedAt); return <div key={s.name} className="rounded-xl border border-slate-700 bg-slate-900/40 p-4"><p className="text-sm font-semibold">{s.name} <span className={`ml-2 text-xs ${s.available && age === "Recent" ? "text-emerald-300" : "text-amber-200"}`}>{!s.available ? "Unavailable" : age}</span></p><p className="mt-1 text-xs text-slate-400">{date(d)} UK</p></div>;})}</section>
    <p className="mb-6 text-sm leading-relaxed text-slate-400">ROI is profit divided by settled stake. A unit is the recorded reference stake. Separate models can select the same match, so do not add their records together. Report freshness means a summary was generated within 48 hours; it does not confirm every capture or settlement is current.</p>
    <nav aria-label="Model groups" className="mb-8 flex flex-wrap gap-2">{groups.map((g,i)=><a key={g} href={`#group-${i}`} className="rounded-lg border border-slate-700 px-3 py-2 text-sm hover:border-emerald-400/50">{g}</a>)}</nav>
    {groups.map((g,i)=><section key={g} id={`group-${i}`} className="mb-9 scroll-mt-6"><h2 className="mb-4 text-xl font-semibold">{g}</h2><div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">{data.rows.filter(r=>r.group===g).map(r=><ModelCard key={r.id} r={r} now={data.checkedAt}/>)}</div></section>)}
    <section className="rounded-2xl border border-slate-700 p-5"><h2 className="text-xl font-semibold">Recent saved research selections</h2><p className="mt-2 text-sm text-slate-400">Hardcourt Scout and Astrissimo include individual selections in their snapshot. Other models currently supply summaries here.</p><div className="mt-4 space-y-3">{data.selections.length ? data.selections.map((s,i)=><article key={`${s.model}-${s.player}-${s.kickoff}-${i}`} className="rounded-xl bg-slate-900 p-4"><p className="text-xs text-emerald-200">{s.model} · {s.status}</p><h3 className="mt-1 font-semibold">{s.player} vs {s.opponent}</h3><p className="mt-2 text-sm text-slate-300">Recorded odds {format(s.odds, 2)} · Profit {signed(s.profit,"u")}</p><p className="mt-1 text-xs text-slate-400">Scheduled: {date(s.kickoff)} UK</p></article>) : <p className="text-sm text-slate-300">No individual selections supplied in the current snapshots.</p>}</div></section>
    <aside className="mt-6 text-sm leading-relaxed text-slate-400">This dashboard reads existing private snapshots only. Refreshing it does not run a model or send alerts. Use the existing tennis run control in Admin to queue a forecast; the Windows machine must be awake for local OnCourt processing. Older local diagnostics remain available on your PC.</aside>
  </div></main>;
}
