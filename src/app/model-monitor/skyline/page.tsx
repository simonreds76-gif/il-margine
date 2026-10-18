import { notFound } from "next/navigation";
import SkylinePanel from "@/components/model-monitor/SkylinePanel";
import { readGoalscorerMonitorSnapshot } from "@/lib/goalscorer-monitor-snapshot";
import { FootballLaneNav, HeroCard, MODEL_MONITOR_ENABLED, MonitorNav } from "../shared";

export const dynamic = "force-dynamic";

export default async function SkylinePage() {
  if (!MODEL_MONITOR_ENABLED) notFound();
  const snapshot = await readGoalscorerMonitorSnapshot();
  return <div className="min-h-screen bg-[#080d16] px-3 py-6 text-slate-200 sm:px-6 sm:py-10"><main className="mx-auto flex max-w-7xl flex-col gap-4">
    <MonitorNav current="skyline" /><FootballLaneNav current="skyline" />
    <HeroCard title="Skyline" eyebrow="Headed shots on target · Paper model v1"><span className="text-slate-300">Compare our estimated chances with Bet365. Track each version on the same matches, with fixed paper stakes and transparent results.</span></HeroCard>
    <SkylinePanel report={snapshot?.skyline ?? null} />
  </main></div>;
}
