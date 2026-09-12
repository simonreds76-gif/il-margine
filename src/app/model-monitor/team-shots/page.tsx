import { notFound } from "next/navigation";
import FootballVnextShadowPanel, { type FootballVnextGate } from "@/components/model-monitor/FootballVnextShadowPanel";
import { parseMonitorCsv } from "@/lib/monitor-csv";
import {
  inspectTeamShotsLiveSource,
  readTeamShotsLiveFile,
  readTeamShotsLiveJson,
} from "@/lib/team-shots-live-files";
import { FootballLaneNav, HeroCard, MODEL_MONITOR_ENABLED, MonitorNav } from "../shared";

export const dynamic = "force-dynamic";

type GatePayload = {
  generated_at?: string;
  team_shots_v4?: FootballVnextGate;
};

const LEDGER_PATH = "data/football-form/team-shots-v4-shadow-clv.csv";

export default async function TeamShotsMonitorPage() {
  if (!MODEL_MONITOR_ENABLED) notFound();

  const [ledgerCsv, candidatesCsv, gate, source, opponentLedger, opponentCandidates, opponentStatus] = await Promise.all([
    readTeamShotsLiveFile(LEDGER_PATH),
    readTeamShotsLiveFile("data/football-form/football-counts-vnext-candidates.csv"),
    readTeamShotsLiveJson<GatePayload>("data/football-form/football-counts-vnext-gate.json"),
    inspectTeamShotsLiveSource(LEDGER_PATH),
    readTeamShotsLiveFile("data/football-form/team-shots-opponent-shadow.csv"),
    readTeamShotsLiveFile("data/football-form/team-shots-opponent-candidates.csv"),
    readTeamShotsLiveJson<FootballVnextGate & { generated_at?: string }>("data/football-form/team-shots-opponent-status.json"),
  ]);

  return (
    <div className="min-h-screen bg-[#080d16] px-3 py-6 text-slate-200 sm:px-6 sm:py-10">
      <main className="mx-auto flex max-w-7xl flex-col gap-4">
        <MonitorNav current="team-shots" />
        <FootballLaneNav current="team-shots" />
        <HeroCard title="Team Shots" eyebrow="Current 2026/27 evidence">
          <span className="text-slate-300">One registered research selection per fixture, including matchday 1-3 rows.</span>{" "}
          <span className="text-slate-500">Results, total staked, P/L and ROI stay visible while promotion remains gated.</span>
        </HeroCard>
        <section id="opponent-shots" className="space-y-3">
          <p className="px-1 text-sm leading-6 text-slate-300">Opponent-adjusted candidate: fixed weights, active forward tracking. ROI below uses hypothetical 1u selections registered before kickoff. Historical backtests are excluded; real stake is zero.</p>
          <FootballVnextShadowPanel
            title="Opponent Shots — forward shadow"
            model="team_shots_opponent"
            rows={parseMonitorCsv(opponentLedger)}
            candidates={parseMonitorCsv(opponentCandidates)}
            gate={opponentStatus}
            source={{ source: source.source, generatedAt: opponentStatus?.generated_at }}
          />
        </section>
        <FootballVnextShadowPanel
          title="Team Shots v4 evidence ledger"
          model="team_shots_v4"
          rows={parseMonitorCsv(ledgerCsv)}
          candidates={parseMonitorCsv(candidatesCsv)}
          gate={gate?.team_shots_v4 ?? null}
          source={{ source: source.source, generatedAt: gate?.generated_at ?? source.hostedFileMtime ?? source.localFileMtime }}
        />
      </main>
    </div>
  );
}
