import { readGoalscorerMonitorSnapshot } from "@/lib/goalscorer-monitor-snapshot";
import { getSupabaseAdmin } from "@/lib/supabase-server";
import { signalCsv } from "@/lib/admin-signal-format";
import { reportSelectionHistory } from "@/lib/model-profit-history";
import ModelProfitChart from "./ModelProfitChart";

const leagues = ["serie-a", "epl", "la-liga", "bundesliga", "ligue-1"] as const;

export default async function GoalscorerModelCards() {
  // Read the retained hosted ledger directly. A deployment's checkout mtime
  // must not make its old bundled CSV appear fresher than the scheduled source.
  const [snapshot, saved] = await Promise.all([
    readGoalscorerMonitorSnapshot(),
    (async () => {
      try {
        const fields=leagues.map((league,i)=>`f${i}:payload->files->"data/goalscorer/${league === "serie-a" ? "goalscorer" : league}-shadow-signals.csv"`);
        const {data,error}=await getSupabaseAdmin().from("goalscorer_live_snapshot").select(fields.join(",")).eq("snapshot_key","live_state").abortSignal(AbortSignal.timeout(10000)).maybeSingle();
        return error ? null : data as unknown as Record<string, {content?:string} | string> | null;
      } catch {return null;}
    })(),
  ]);
  const ledgers=leagues.map((_,i)=>{const v=saved?.[`f${i}`];return typeof v==="string"?v:v?.content;});
  return <section id="goalscorers" className="my-8 scroll-mt-24">
    <h2 className="text-xl font-semibold">Goalscorers · five running league models</h2>
    <p className="my-3 text-sm text-slate-400">Full shadow selection records, including losing picks. League records and historical input versions stay separate. Original reporting treats voids as zero-profit settlements. The retained ledger can contain repeated captures of a fixture; no rows are deduplicated or regraded for this chart. These are research figures, not placed bets.</p>
    <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">{leagues.map((league, index) => {
      const stats = snapshot?.shadow_summary.by_league.find(r => r.key === league);
      let entries: Array<{id:string;start:unknown;status:string;profit:number|null}> | undefined;
      try {
        entries = typeof ledgers[index] === "string" ? signalCsv(ledgers[index]).filter(r => ["1", "true", "yes", "settled"].includes(String(r.settled).toLowerCase())).map((r, originalRow) => ({
          id: `${league}:${originalRow}`, start: r.kickoff || r.date, status: "settled",
          profit: r.pnl_units === "" || r.pnl_units == null || !Number.isFinite(Number(r.pnl_units)) ? null : Number(r.pnl_units),
        })) : undefined;
      } catch { /* Keep figures visible; never substitute an invented curve. */ }
      const history = reportSelectionHistory(entries, {settled: stats?.settled ?? null, profit: stats?.pnl_units ?? null});
      return <article key={league} className="min-w-0 rounded-2xl border border-slate-700 p-5">
        <h3 className="font-semibold">Goalscorer v2 · {stats?.label || league}</h3>
        <p className="mt-3 text-xl font-semibold tabular-nums">{stats ? `${stats.roi.toFixed(2)}% ROI · ${stats.pnl_units.toFixed(2)}u` : "Report unavailable"}</p>
        <p className="mt-2 text-xs text-slate-400">{stats ? `${stats.wins}W / ${stats.losses}L · ${stats.voids} void · ${stats.open} unresolved` : "Missing evidence is not zero profit."}</p>
        <ModelProfitChart name={`Goalscorer ${stats?.label || league}`} history={history}/>
        <p className="mt-3 text-xs text-slate-400">Probability calibration is not supplied by this selection report. Updated {snapshot?.generated_at || "unavailable"}.</p>
      </article>;
    })}</div>
  </section>;
}
