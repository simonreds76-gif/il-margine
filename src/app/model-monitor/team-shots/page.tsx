import { notFound } from "next/navigation";
import FootballVnextShadowPanel, { type FootballVnextGate } from "@/components/model-monitor/FootballVnextShadowPanel";
import { parseMonitorCsv } from "@/lib/monitor-csv";
import {
  inspectTeamShotsLiveSource,
  readTeamShotsLiveFile,
  readTeamShotsLiveJson,
} from "@/lib/team-shots-live-files";
import { FootballLaneNav, HeroCard, MODEL_MONITOR_ENABLED, MonitorNav } from "../shared";
import lifecycle from "../../../../config/model-monitor-lifecycle.json";

export const dynamic = "force-dynamic";

type GatePayload = {
  generated_at?: string;
  team_shots_v4?: FootballVnextGate;
};
type PairedStatus = {
  generated_at?: string;
  paired_fixtures?: number;
  models?: Record<string, { hypothetical_selections?: { settled?: number; wins?: number; losses?: number; pnl_units?: number; roi?: number | null; pending?: number } }>;
};

const LEDGER_PATH = "data/football-form/team-shots-v4-shadow-clv.csv";

export default async function TeamShotsMonitorPage() {
  if (!MODEL_MONITOR_ENABLED) notFound();

  const [ledgerCsv, candidatesCsv, gate, source, opponentLedger, opponentCandidates, opponentStatus, paired, historicalCsv] = await Promise.all([
    readTeamShotsLiveFile(LEDGER_PATH),
    readTeamShotsLiveFile("data/football-form/football-counts-vnext-candidates.csv"),
    readTeamShotsLiveJson<GatePayload>("data/football-form/football-counts-vnext-gate.json"),
    inspectTeamShotsLiveSource(LEDGER_PATH),
    readTeamShotsLiveFile("data/football-form/team-shots-opponent-shadow.csv"),
    readTeamShotsLiveFile("data/football-form/team-shots-opponent-candidates.csv"),
    readTeamShotsLiveJson<FootballVnextGate & { generated_at?: string }>("data/football-form/team-shots-opponent-status.json"),
    readTeamShotsLiveJson<PairedStatus>("data/football-form/team-shots-paired-reference-status.json"),
    readTeamShotsLiveFile("data/football-form/team-shots-v3-ema20-clv-monitor.csv"),
  ]);
  const calibration = paired?.models?.shots_market_offset_v1?.hypothetical_selections;
  let historical: ReturnType<typeof parseMonitorCsv> = [];
  try { historical = parseMonitorCsv(historicalCsv).filter((row) => row.confidence_guard_applied === "false" && row.current_model_would_have_priced === "true" && ["won", "lost"].includes(row.result) && Number.isFinite(Number(row.pnl_units))); }
  catch { /* An unreadable archive must not interrupt the current model. */ }
  const historicalProfit = historical.reduce((total, row) => total + Number(row.pnl_units || 0), 0);
  const historicalWins = historical.filter((row) => row.result === "won").length;
  const historicalDates = historical.map((row) => row.match_date).sort();

  return (
    <div className="min-h-screen bg-[#080d16] px-3 py-6 text-slate-200 sm:px-6 sm:py-10">
      <main className="mx-auto flex max-w-7xl flex-col gap-4">
        <MonitorNav current="team-shots" />
        <FootballLaneNav current="team-shots" />
        <HeroCard title={lifecycle.team_shots.current_alert_label} eyebrow="Current Telegram model">
          <span className="text-slate-300">This is the model used for your daily Team Shots alerts. It tracks paper selections at zero real stake.</span>{" "}
          <span className="text-slate-400">The input refresh and Kambi coverage repair did not change its weights. Research alternatives are kept below.</span>
        </HeroCard>
        <FootballVnextShadowPanel
          title="Team Shots v4 | Current alert model"
          model="team_shots_v4"
          rows={parseMonitorCsv(ledgerCsv)}
          candidates={parseMonitorCsv(candidatesCsv)}
          gate={gate?.team_shots_v4 ?? null}
          source={{ source: source.source, generatedAt: gate?.generated_at ?? source.hostedFileMtime ?? source.localFileMtime }}
        />
        <details className="rounded-2xl border border-slate-800 p-4 sm:p-5">
          <summary className="cursor-pointer font-semibold text-cyan-200">Research comparisons | not the current Telegram model</summary>
          <section className="my-4 rounded-xl border border-cyan-500/20 bg-cyan-500/5 p-4">
            <h2 className="font-semibold text-slate-100">Market offset calibration v1</h2>
            <p className="mt-2 text-sm leading-6 text-slate-300">Uses the Opponent Shots forecast, then adjusts its probability towards the recorded market. This is our own fixed experiment, not a verified copy of StatsHub. No individual bet alerts or real stakes.</p>
            <p className="mt-3 text-sm text-slate-200">{calibration ? `${calibration.wins ?? 0}W / ${calibration.losses ?? 0}L · ${calibration.settled ?? 0} settled · ${(calibration.pnl_units ?? 0) >= 0 ? "+" : ""}${(calibration.pnl_units ?? 0).toFixed(3)}u · ROI ${calibration.roi == null ? "not yet available" : `${(calibration.roi * 100).toFixed(2)}%`} · ${calibration.pending ?? 0} pending` : "Current comparison evidence unavailable."}</p>
            <p className="mt-2 text-xs text-slate-400">{paired?.paired_fixtures ?? 0} independently settled fixtures in the paired comparison. Different models can select different bets; their ROI samples are not interchangeable. Updated {paired?.generated_at || "unavailable"}.</p>
          </section>
          <section id="opponent-shots" className="space-y-3">
          <p className="px-1 text-sm leading-6 text-slate-300">Opponent-adjusted candidate: fixed weights, active forward tracking. ROI below uses hypothetical 1u selections registered before kickoff. Historical backtests are excluded; real stake is zero.</p>
          <FootballVnextShadowPanel
            title="Opponent Shots | forward shadow"
            model="team_shots_opponent"
            rows={parseMonitorCsv(opponentLedger)}
            candidates={parseMonitorCsv(opponentCandidates)}
            gate={opponentStatus}
            source={{ source: source.source, generatedAt: opponentStatus?.generated_at }}
          />
          </section>
        </details>
        <details className="rounded-2xl border border-slate-800 p-4 sm:p-5">
          <summary className="cursor-pointer font-semibold text-slate-300">Previous season | EMA20 v3 archive</summary>
          <p className="mt-3 text-sm leading-6 text-slate-300">The older profitable record is retained here. V1 and v2 are retired; v3 is no longer a standalone alert model. Its formula remains a fixed reference in the research comparison.</p>
          {historical.length ? <p className="mt-3 text-sm text-slate-200">{historicalDates[0]} to {historicalDates.at(-1)}: {historicalWins}W / {historical.length - historicalWins}L, {historical.length} settled, {historical.length}u staked, {historicalProfit >= 0 ? "+" : ""}{historicalProfit.toFixed(2)}u, ROI {(100 * historicalProfit / historical.length).toFixed(2)}%.</p> : <p className="mt-3 text-sm text-slate-400">Historical record unavailable.</p>}
          <p className="mt-2 text-xs leading-5 text-slate-400">Recorded Bet365 prices and hypothetical 1u stakes. Includes every eligible archived selection; excludes rows blocked by the recorded confidence guard. Retained historical ledger, not a rerun or proof of performance with today&apos;s prices.</p>
        </details>
      </main>
    </div>
  );
}
