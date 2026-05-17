import Link from "next/link";
import { notFound } from "next/navigation";

const MODEL_MONITOR_PUBLIC =
  process.env.MODEL_MONITOR_PUBLIC === "1" ||
  process.env.NEXT_PUBLIC_ENABLE_MODEL_MONITOR === "1";
const MODEL_MONITOR_ENABLED =
  MODEL_MONITOR_PUBLIC || process.env.VERCEL_ENV === "preview";

const MONITOR_LINKS = [
  {
    href: "/model-monitor/goalscorer",
    title: "Goalscorer Fair Odds",
    description: "Live goalscorer pipeline, lineups, penalty-review state, and public/shadow split.",
    tone: "border-emerald-500/30 bg-emerald-500/10 text-emerald-100",
  },
  {
    href: "/model-monitor/assist-value",
    title: "Assist Value Shadow",
    description: "Private assist odds + set-piece-role research board. Not public Fair Odds output.",
    tone: "border-sky-500/30 bg-sky-500/10 text-sky-100",
  },
];

export default function ModelMonitorIndexPage() {
  if (process.env.NODE_ENV === "production" && !MODEL_MONITOR_ENABLED) {
    notFound();
  }

  return (
    <main className="min-h-screen bg-[#061014] px-4 py-8 text-slate-100 sm:px-6 lg:px-10">
      <div className="mx-auto max-w-5xl">
        <div className="rounded-3xl border border-slate-800 bg-slate-950/80 p-6 shadow-2xl shadow-black/30">
          <p className="text-xs font-semibold uppercase tracking-[0.22em] text-emerald-300">Internal Monitor</p>
          <h1 className="mt-3 text-3xl font-black tracking-tight text-white sm:text-4xl">Model Monitor</h1>
          <p className="mt-3 max-w-3xl text-sm leading-6 text-slate-400">
            Private operational pages only. Public Fair Odds output remains controlled by the separate lab/publish pipeline.
          </p>
          <div className="mt-6 grid gap-4 md:grid-cols-2">
            {MONITOR_LINKS.map((item) => (
              <Link
                key={item.href}
                href={item.href}
                className={`rounded-2xl border p-5 transition hover:-translate-y-0.5 hover:border-white/30 ${item.tone}`}
              >
                <div className="text-lg font-bold text-white">{item.title}</div>
                <p className="mt-2 text-sm leading-6 text-slate-300">{item.description}</p>
                <div className="mt-4 text-xs font-semibold uppercase tracking-[0.18em] text-white/70">Open monitor</div>
              </Link>
            ))}
          </div>
        </div>
      </div>
    </main>
  );
}
