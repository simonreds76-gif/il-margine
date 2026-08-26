import { notFound } from "next/navigation";
import FootballVnextShadowPanel, { type FootballVnextGate } from "@/components/model-monitor/FootballVnextShadowPanel";
import GoalkeeperSavesPanel from "@/components/model-monitor/GoalkeeperSavesPanel";
import { parseMonitorCsv } from "@/lib/monitor-csv";
import { readTeamShotsLiveFile, readTeamShotsLiveJson } from "@/lib/team-shots-live-files";
import { HeroCard, MODEL_MONITOR_ENABLED, MonitorNav, StatCard } from "../shared";

export const dynamic = "force-dynamic";

type FootballCountsGatePayload = {
  generated_at?: string;
  team_shots_v4?: FootballVnextGate;
};

type GoalkeeperReport = {
  status?: string;
  generated_at?: string;
  selection_rule?: string;
  count_model?: string;
  current?: { priced_lines?: number; eligible_lines?: number; provisional_lines?: number; signals_added?: number; blocker_counts?: Record<string, number> };
  evidence?: { signals?: number; settled?: number; pending?: number; pnl_units?: number; roi?: number | null; clv?: number | null; clv_matched?: number };
  promotion?: { status?: string; settled_required?: number };
};

type GoalkeeperCapture = {
  status?: string;
  generated_at?: string;
  events?: number;
  rows?: number;
  message?: string;
};

type GoalkeeperSettlement = {
  status?: string;
  generated_at?: string;
  pending_total?: number;
  pending_due?: number;
  deferred_not_due?: number;
  settled?: number;
  requests_used?: number;
  max_requests?: number;
  reason_counts?: Record<string, number>;
  api_errors?: string[];
};

type FoulsReport = {
  generated_at?: string;
  status?: string;
  sample_matches?: number;
  decision?: { status?: string; count_gate_pass?: boolean; signals_authorized?: boolean };
};

type FoulsCoverage = {
  status?: string;
  api_football?: { comparable_team_values?: number; within_one_pct?: number };
  fotmob?: { comparable_team_values?: number; within_one_pct?: number };
};

export default async function TeamShotsMonitorPage() {
  if (!MODEL_MONITOR_ENABLED) notFound();

  const [
    ledgerCsv,
    candidatesCsv,
    gate,
    goalkeeperReport,
    goalkeeperCapture,
    goalkeeperSettlement,
    goalkeeperSignalsCsv,
    goalkeeperCandidatesCsv,
    goalkeeperProvisionalCsv,
    foulsF1,
    foulsF2,
    foulsCoverage,
  ] = await Promise.all([
    readTeamShotsLiveFile("data/football-form/team-shots-v4-shadow-clv.csv"),
    readTeamShotsLiveFile("data/football-form/football-counts-vnext-candidates.csv"),
    readTeamShotsLiveJson<FootballCountsGatePayload>("data/football-form/football-counts-vnext-gate.json"),
    readTeamShotsLiveJson<GoalkeeperReport>("data/goalkeeper-saves/gk-saves-v1-shadow-report.json"),
    readTeamShotsLiveJson<GoalkeeperCapture>("data/goalkeeper-saves/gk-saves-capture-status.json"),
    readTeamShotsLiveJson<GoalkeeperSettlement>("data/goalkeeper-saves/gk-saves-v1-settlement-status.json"),
    readTeamShotsLiveFile("data/goalkeeper-saves/gk-saves-v1-shadow-signals.csv"),
    readTeamShotsLiveFile("data/goalkeeper-saves/gk-saves-v1-candidates.csv"),
    readTeamShotsLiveFile("data/goalkeeper-saves/gk-saves-v1-provisional.csv"),
    readTeamShotsLiveJson<FoulsReport>("data/football-form/team-fouls-v1-fold-report.json"),
    readTeamShotsLiveJson<FoulsReport>("data/football-form/team-fouls-f2-fold-report.json"),
    readTeamShotsLiveJson<FoulsCoverage>("data/football-form/team-fouls-definition-agreement.json"),
  ]);

  const ledger = parseMonitorCsv(ledgerCsv);
  const candidates = parseMonitorCsv(candidatesCsv);

  return (
    <div className="min-h-screen bg-[#0a0f19] px-4 py-8 text-slate-200 sm:px-6 sm:py-10">
      <div className="mx-auto flex max-w-7xl flex-col gap-4">
        <MonitorNav current="team-shots" />
        <HeroCard title="Football Counts Monitor" eyebrow="Current 2026/27 Evidence">
          <span className="text-slate-300">Team Shots v4, Goalkeeper Saves v1 and Team Fouls research in one current-season view.</span>
          <span className="mx-2 text-slate-700">|</span>
          <span className="text-slate-500">Every registered selection is retained for settlement, P/L and ROI.</span>
        </HeroCard>

        <FootballVnextShadowPanel
          title="Team Shots v4 - Current 2026/27 Lane"
          model="team_shots_v4"
          rows={ledger}
          candidates={candidates}
          gate={gate?.team_shots_v4 ?? null}
        />

        <GoalkeeperSavesPanel
          report={goalkeeperReport}
          capture={goalkeeperCapture}
          settlement={goalkeeperSettlement}
          signals={parseMonitorCsv(goalkeeperSignalsCsv)}
          candidates={parseMonitorCsv(goalkeeperCandidatesCsv)}
          provisional={parseMonitorCsv(goalkeeperProvisionalCsv)}
        />

        <section className="rounded-2xl border border-slate-800 bg-slate-950/35 p-4 sm:p-5">
          <div className="mb-3">
            <h2 className="text-lg font-semibold text-white">Team Fouls Research</h2>
            <p className="mt-1 text-xs text-slate-500">Count validation is visible here, but no price-backed signal ledger exists until both the count and market gates pass.</p>
          </div>
          <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-4">
            <StatCard label="F1 status" value={foulsF1?.decision?.status ?? foulsF1?.status ?? "NOT RUN"} detail={`${foulsF1?.sample_matches ?? 0} matches`} />
            <StatCard label="F2 status" value={foulsF2?.decision?.status ?? foulsF2?.status ?? "NOT RUN"} detail={`${foulsF2?.sample_matches ?? 0} matches`} />
            <StatCard label="Signals authorized" value={foulsF2?.decision?.signals_authorized ? "YES" : "NO"} detail={foulsF2?.decision?.count_gate_pass ? "count gate passed" : "count gate blocked"} />
            <StatCard label="External agreement" value={foulsCoverage?.status ?? "WAITING"} detail={`API ${foulsCoverage?.api_football?.comparable_team_values ?? 0} · FotMob ${foulsCoverage?.fotmob?.comparable_team_values ?? 0}`} />
          </div>
        </section>
      </div>
    </div>
  );
}
