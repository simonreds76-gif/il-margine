import Link from "next/link";
import { redirect } from "next/navigation";
import { isAdminSession } from "@/lib/admin-auth";
import { getSupabaseAdmin } from "@/lib/supabase-server";

export const dynamic = "force-dynamic";
export const metadata = { title: "StatsHub Daily | Il Margine Admin", robots: { index: false, follow: false } };

type Check = { status: string; at: string; note: string; odds?: number; book?: string };
type Pick = {
  id: string; fixture: string; league: string; ko: string; label: string; odds: number; book: string;
  at: string; minimum: number; why: string; risk: string; check?: Check; ready?: Check;
  result?: string; readyResult?: string;
};
type Day = { picks: Pick[]; fixtures: number; coverage: string; at: string; final: boolean };
type Report = { status: string; updated: string; days: Record<string, Day>; summary?: string };
const uk = (date: string) => new Intl.DateTimeFormat("en-GB", {
  timeZone: "Europe/London", day: "numeric", month: "short", hour: "2-digit", minute: "2-digit",
}).format(new Date(date));

export default async function StatsHubDaily() {
  if (!(await isAdminSession())) redirect("/admin");
  let report: Report | undefined;
  try {
    const { data, error } = await getSupabaseAdmin().storage.from("statshub-daily-private").download("daily/report.json");
    if (data && !error) report = JSON.parse(await data.text()) as Report;
  } catch { /* Render an explicit availability state below. */ }
  const days = Object.entries(report?.days ?? {}).sort(([a], [b]) => b.localeCompare(a));
  return <main className="mx-auto max-w-4xl space-y-5 px-4 py-8 text-slate-100">
    <Link className="text-sm text-emerald-300" href="/admin">← Admin</Link>
    <header><h1 className="text-3xl font-bold">StatsHub Daily</h1>
      <p className="mt-2 text-sm text-slate-400">Private football shortlist · 20–23 November · UK times · 1u paper tracking</p>
    </header>
    {!report ? <p role="status">The private report is unavailable. Refresh to try again.</p> :
      <><p className="text-sm text-slate-300">{report.status} · Updated {uk(report.updated)}</p>
      {report.summary && <p className="whitespace-pre-line rounded-xl border border-slate-700 p-4 text-sm">{report.summary}</p>}
      {!days.length && <p className="rounded-xl border border-slate-800 p-4">First shortlist due Friday 20 November at 10am London time.</p>}
      {days.map(([day, board]) => <section key={day} className="space-y-3">
        <div><h2 className="text-xl font-semibold">{day}</h2>
          <p className="text-sm text-slate-400">{board.fixtures} fixtures · {board.picks.length} candidates · {board.final ? "Screen complete" : "In progress"}</p>
          <p className="mt-1 whitespace-pre-line text-sm text-slate-400">{board.coverage}</p></div>
        {board.final && !board.picks.length && <p className="rounded-xl border border-slate-800 p-4">No verified selection from the assessed markets.</p>}
        {board.picks.map(p => <article key={p.id} className="space-y-2 rounded-xl border border-slate-700 bg-slate-900/50 p-4">
          <p className="text-xs text-slate-400">{p.league} · {uk(p.ko)} · {p.fixture}</p>
          <h3 className="font-semibold text-emerald-200">{p.label}</h3>
          <p className="text-sm"><strong>{p.odds.toFixed(2)} {p.book}</strong> · floor {p.minimum.toFixed(2)} · checked {uk(p.at)}</p>
          <p className="text-sm">{p.why}</p><p className="text-sm text-slate-400">{p.risk}</p>
          <p className="border-t border-slate-800 pt-2 text-sm">{p.check ? <><strong>{p.check.status.toUpperCase()}</strong> · {uk(p.check.at)} · {p.check.note}{p.check.odds ? ` · ${p.check.odds.toFixed(2)} ${p.check.book}` : ""}</> : "Pre-kickoff recheck pending"}</p>
          {p.ready && <p className="text-xs text-slate-400">First verified price {p.ready.odds?.toFixed(2)} {p.ready.book}</p>}
          <p className="text-xs text-slate-400">Morning result {p.result ?? "pending"}{p.ready ? ` · Rechecked result ${p.readyResult ?? "pending"}` : ""}</p>
        </article>)}
      </section>)}</>}
  </main>;
}
