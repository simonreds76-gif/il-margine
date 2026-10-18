import { redirect } from "next/navigation";
import { isAdminSession } from "@/lib/admin-auth";
import SkylinePanel from "@/components/model-monitor/SkylinePanel";
import { readSkylineMonitorReport } from "@/lib/goalscorer-monitor-snapshot";
import { HeroCard } from "../shared";

export const dynamic = "force-dynamic";

export default async function SkylinePage() {
  if (process.env.NODE_ENV !== "development" && !await isAdminSession()) redirect("/admin");
  const report = await readSkylineMonitorReport();
  return <div className="min-h-screen bg-[#080d16] px-3 py-6 text-slate-200 sm:px-6 sm:py-10"><main className="mx-auto flex max-w-7xl flex-col gap-4">
    <nav aria-label="Private monitor" className="flex flex-wrap gap-2 text-sm"><a className="rounded-xl border border-slate-700 px-4 py-3" href="/admin/models">All models</a><a className="rounded-xl border border-slate-700 px-4 py-3" href="/admin/models/signals">Signals and results</a><a className="rounded-xl border border-slate-700 px-4 py-3" href="/admin">Admin</a></nav>
    <HeroCard title="Skyline" eyebrow="Headed shots on target · Paper model v1"><span className="text-slate-300">Compare our estimated chances with Bet365. Track each version on the same matches, with fixed paper stakes and transparent results.</span></HeroCard>
    <SkylinePanel report={report} />
  </main></div>;
}
