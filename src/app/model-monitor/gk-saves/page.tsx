import { notFound } from "next/navigation";
import GoalkeeperSavesPanel, {
  type GoalkeeperCaptureStatus,
  type GoalkeeperReport,
  type GoalkeeperSettlementStatus,
} from "@/components/model-monitor/GoalkeeperSavesPanel";
import { parseMonitorCsv } from "@/lib/monitor-csv";
import {
  inspectTeamShotsLiveSource,
  readTeamShotsLiveFile,
  readTeamShotsLiveJson,
} from "@/lib/team-shots-live-files";
import { FootballLaneNav, HeroCard, MODEL_MONITOR_ENABLED, MonitorNav } from "../shared";

export const dynamic = "force-dynamic";

const SIGNALS_PATH = "data/goalkeeper-saves/gk-saves-v1-shadow-signals.csv";

export default async function GoalkeeperSavesMonitorPage() {
  if (!MODEL_MONITOR_ENABLED) notFound();

  const [report, capture, settlement, signals, candidates, provisional, source] = await Promise.all([
    readTeamShotsLiveJson<GoalkeeperReport>("data/goalkeeper-saves/gk-saves-v1-shadow-report.json"),
    readTeamShotsLiveJson<GoalkeeperCaptureStatus>("data/goalkeeper-saves/gk-saves-capture-status.json"),
    readTeamShotsLiveJson<GoalkeeperSettlementStatus>("data/goalkeeper-saves/gk-saves-v1-settlement-status.json"),
    readTeamShotsLiveFile(SIGNALS_PATH),
    readTeamShotsLiveFile("data/goalkeeper-saves/gk-saves-v1-candidates.csv"),
    readTeamShotsLiveFile("data/goalkeeper-saves/gk-saves-v1-provisional.csv"),
    inspectTeamShotsLiveSource(SIGNALS_PATH),
  ]);

  return (
    <div className="min-h-screen bg-[#080d16] px-3 py-6 text-slate-200 sm:px-6 sm:py-10">
      <main className="mx-auto flex max-w-7xl flex-col gap-4">
        <MonitorNav current="gk-saves" />
        <FootballLaneNav current="gk-saves" />
        <HeroCard title="Goalkeeper Saves v1" eyebrow="Current 2026/27 evidence">
          <span className="text-slate-300">A dedicated ledger for goalkeeper saves, current ladders and settlement evidence.</span>{" "}
          <span className="text-slate-500">The early return is visible but remains highly concentrated and not promoted.</span>
        </HeroCard>
        <GoalkeeperSavesPanel
          report={report}
          capture={capture}
          settlement={settlement}
          signals={parseMonitorCsv(signals)}
          candidates={parseMonitorCsv(candidates)}
          provisional={parseMonitorCsv(provisional)}
          source={source.source}
        />
      </main>
    </div>
  );
}
