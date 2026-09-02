import { notFound } from "next/navigation";
import FootballVnextShadowPanel, { type FootballVnextGate } from "@/components/model-monitor/FootballVnextShadowPanel";
import {
  inspectCornersLiveSource,
  readCornersLiveFile,
  readCornersLiveJson,
} from "@/lib/corners-live-files";
import { parseMonitorCsv } from "@/lib/monitor-csv";
import { FootballLaneNav, HeroCard, MODEL_MONITOR_ENABLED, MonitorNav } from "../shared";

export const dynamic = "force-dynamic";

type GatePayload = {
  generated_at?: string;
  corners_v3?: FootballVnextGate;
};

const LEDGER_PATH = "data/football-form/corners-v3-shadow-clv.csv";

export default async function CornersMonitorPage() {
  if (!MODEL_MONITOR_ENABLED) notFound();

  const [ledgerCsv, candidatesCsv, gate, source] = await Promise.all([
    readCornersLiveFile(LEDGER_PATH),
    readCornersLiveFile("data/football-form/football-counts-vnext-candidates.csv"),
    readCornersLiveJson<GatePayload>("data/football-form/football-counts-vnext-gate.json"),
    inspectCornersLiveSource(LEDGER_PATH),
  ]);

  return (
    <div className="min-h-screen bg-[#080d16] px-3 py-6 text-slate-200 sm:px-6 sm:py-10">
      <main className="mx-auto flex max-w-7xl flex-col gap-4">
        <MonitorNav current="corners" />
        <FootballLaneNav current="corners" />
        <HeroCard title="Corners v3" eyebrow="Current 2026/27 evidence">
          <span className="text-slate-300">Current-season prospective tracking is the primary view.</span>{" "}
          <span className="text-slate-500">Pre-2026/27 controls no longer obscure this lane.</span>
        </HeroCard>
        <FootballVnextShadowPanel
          title="Corners v3 evidence ledger"
          model="corners_v3"
          rows={parseMonitorCsv(ledgerCsv)}
          candidates={parseMonitorCsv(candidatesCsv)}
          gate={gate?.corners_v3 ?? null}
          source={{ source: source.source, generatedAt: gate?.generated_at ?? source.hostedFileMtime ?? source.localFileMtime }}
        />
      </main>
    </div>
  );
}
