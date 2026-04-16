import { redirect } from "next/navigation";
import { isAdminSession } from "@/lib/admin-auth";
import { getSupabaseAdmin } from "@/lib/supabase-server";

export const dynamic = "force-dynamic";

type PipelineHealthRow = {
  pipeline: string;
  host: string | null;
  trigger_kind: string | null;
  last_status: string | null;
  last_started_at: string | null;
  last_finished_at: string | null;
  last_duration_seconds: number | null;
  last_rows_out: number | null;
  last_error_type: string | null;
  last_error_message: string | null;
  runs_24h: number | null;
  ok_24h: number | null;
  failed_24h: number | null;
  running_24h: number | null;
};

type StuckRunRow = {
  pipeline: string;
  host: string | null;
  trigger_kind: string | null;
  run_id: string;
  started_at: string;
  age_seconds: number | null;
};

type SilentPipelineRow = {
  pipeline: string;
  expected_interval: string | null;
  grace_interval: string | null;
  last_started_at: string | null;
  last_finished_at: string | null;
  seconds_since_last_start: number | null;
};

function formatDateTime(value: string | null): string {
  if (!value) return "â€”";
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return value;
  return parsed.toLocaleString("en-GB", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    hour12: false,
    timeZone: "Europe/London",
  });
}

function formatSeconds(value: number | null): string {
  if (value == null || !Number.isFinite(value)) return "â€”";
  if (value < 60) return `${Math.round(value)}s`;
  if (value < 3600) return `${(value / 60).toFixed(1)}m`;
  if (value < 86400) return `${(value / 3600).toFixed(1)}h`;
  return `${(value / 86400).toFixed(1)}d`;
}

function statusTone(status: string | null): string {
  switch ((status || "").toLowerCase()) {
    case "ok":
      return "text-emerald-300";
    case "running":
      return "text-amber-300";
    case "failed":
    case "timeout":
    case "aborted":
      return "text-rose-300";
    default:
      return "text-slate-300";
  }
}

export default async function OpsStatusPage() {
  if (!(await isAdminSession())) {
    redirect("/admin");
  }

  const supabase = getSupabaseAdmin();

  const [healthRes, stuckRes, silentRes] = await Promise.all([
    supabase.from("v_pipeline_health").select("*").order("pipeline"),
    supabase.from("v_stuck_runs").select("*").order("started_at", { ascending: true }),
    supabase.from("v_silent_pipelines").select("*").order("pipeline"),
  ]);

  const health = (healthRes.data || []) as PipelineHealthRow[];
  const stuck = (stuckRes.data || []) as StuckRunRow[];
  const silent = (silentRes.data || []) as SilentPipelineRow[];

  const hardError =
    healthRes.error?.message ||
    stuckRes.error?.message ||
    silentRes.error?.message ||
    null;

  const okCount = health.filter((row) => (row.last_status || "").toLowerCase() === "ok").length;
  const runningCount = health.filter((row) => (row.last_status || "").toLowerCase() === "running").length;
  const failedCount = health.filter((row) => ["failed", "timeout", "aborted"].includes((row.last_status || "").toLowerCase())).length;

  return (
    <main className="min-h-screen bg-slate-950 text-slate-100">
      <div className="mx-auto max-w-7xl px-4 py-8 sm:px-6 lg:px-8">
        <div className="mb-8 flex flex-col gap-3">
          <p className="text-xs uppercase tracking-[0.24em] text-slate-500">Ops</p>
          <div>
            <h1 className="text-3xl font-semibold tracking-tight">Pipeline Status</h1>
            <p className="mt-2 max-w-3xl text-sm text-slate-400">
              Read-only view over <code>run_status</code> and its health views. This is the first pass:
              latest status, silent pipelines, and stuck runs.
            </p>
          </div>
        </div>

        {hardError ? (
          <div className="mb-6 rounded-2xl border border-rose-900/60 bg-rose-950/30 px-4 py-3 text-sm text-rose-200">
            Could not load ops data: {hardError}
          </div>
        ) : null}

        <section className="mb-8 grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
          <div className="rounded-2xl border border-slate-800 bg-slate-900/60 p-5">
            <p className="text-xs uppercase tracking-[0.2em] text-slate-500">Pipelines</p>
            <p className="mt-3 text-3xl font-semibold">{health.length}</p>
            <p className="mt-2 text-sm text-slate-400">Currently wired into run status</p>
          </div>
          <div className="rounded-2xl border border-slate-800 bg-slate-900/60 p-5">
            <p className="text-xs uppercase tracking-[0.2em] text-slate-500">Healthy</p>
            <p className="mt-3 text-3xl font-semibold text-emerald-300">{okCount}</p>
            <p className="mt-2 text-sm text-slate-400">Latest run ended with status `ok`</p>
          </div>
          <div className="rounded-2xl border border-slate-800 bg-slate-900/60 p-5">
            <p className="text-xs uppercase tracking-[0.2em] text-slate-500">Running</p>
            <p className="mt-3 text-3xl font-semibold text-amber-300">{runningCount}</p>
            <p className="mt-2 text-sm text-slate-400">Latest seen state is still `running`</p>
          </div>
          <div className="rounded-2xl border border-slate-800 bg-slate-900/60 p-5">
            <p className="text-xs uppercase tracking-[0.2em] text-slate-500">Attention</p>
            <p className="mt-3 text-3xl font-semibold text-rose-300">{failedCount + stuck.length + silent.length}</p>
            <p className="mt-2 text-sm text-slate-400">Failed latest runs, stuck rows, or silent pipelines</p>
          </div>
        </section>

        <section className="mb-8 grid gap-6 xl:grid-cols-2">
          <div className="rounded-2xl border border-slate-800 bg-slate-900/60 p-5">
            <div className="mb-4 flex items-center justify-between gap-4">
              <div>
                <h2 className="text-lg font-semibold">Silent Pipelines</h2>
                <p className="text-sm text-slate-400">No recent start within the configured grace window.</p>
              </div>
              <span className="rounded-full border border-slate-700 px-3 py-1 text-xs text-slate-300">
                {silent.length}
              </span>
            </div>
            {silent.length === 0 ? (
              <p className="text-sm text-slate-400">None.</p>
            ) : (
              <div className="space-y-3">
                {silent.map((row) => (
                  <div key={row.pipeline} className="rounded-xl border border-slate-800/80 bg-slate-950/50 px-4 py-3">
                    <div className="flex flex-wrap items-center justify-between gap-3">
                      <div>
                        <p className="font-medium">{row.pipeline}</p>
                        <p className="text-xs text-slate-400">
                          Expected {row.expected_interval || "â€”"} | Grace {row.grace_interval || "â€”"}
                        </p>
                      </div>
                      <div className="text-right text-sm">
                        <p className="text-rose-300">{formatSeconds(row.seconds_since_last_start)}</p>
                        <p className="text-xs text-slate-500">since last start</p>
                      </div>
                    </div>
                    <p className="mt-2 text-xs text-slate-500">
                      Last started: {formatDateTime(row.last_started_at)} | Last finished: {formatDateTime(row.last_finished_at)}
                    </p>
                  </div>
                ))}
              </div>
            )}
          </div>

          <div className="rounded-2xl border border-slate-800 bg-slate-900/60 p-5">
            <div className="mb-4 flex items-center justify-between gap-4">
              <div>
                <h2 className="text-lg font-semibold">Stuck Runs</h2>
                <p className="text-sm text-slate-400">Rows still marked `running` after 15 minutes.</p>
              </div>
              <span className="rounded-full border border-slate-700 px-3 py-1 text-xs text-slate-300">
                {stuck.length}
              </span>
            </div>
            {stuck.length === 0 ? (
              <p className="text-sm text-slate-400">None.</p>
            ) : (
              <div className="space-y-3">
                {stuck.map((row) => (
                  <div key={row.run_id} className="rounded-xl border border-slate-800/80 bg-slate-950/50 px-4 py-3">
                    <div className="flex flex-wrap items-center justify-between gap-3">
                      <div>
                        <p className="font-medium">{row.pipeline}</p>
                        <p className="text-xs text-slate-400">
                          {row.host || "unknown host"} | {row.trigger_kind || "unknown trigger"}
                        </p>
                      </div>
                      <div className="text-right text-sm">
                        <p className="text-amber-300">{formatSeconds(row.age_seconds)}</p>
                        <p className="text-xs text-slate-500">current age</p>
                      </div>
                    </div>
                    <p className="mt-2 text-xs text-slate-500">Started: {formatDateTime(row.started_at)}</p>
                  </div>
                ))}
              </div>
            )}
          </div>
        </section>

        <section className="rounded-2xl border border-slate-800 bg-slate-900/60 p-5">
          <div className="mb-4">
            <h2 className="text-lg font-semibold">Pipeline Health</h2>
            <p className="text-sm text-slate-400">
              Latest run per pipeline plus simple 24-hour counts from <code>v_pipeline_health</code>.
            </p>
          </div>

          <div className="overflow-x-auto">
            <table className="min-w-full text-left text-sm">
              <thead className="border-b border-slate-800 text-xs uppercase tracking-[0.18em] text-slate-500">
                <tr>
                  <th className="px-3 py-3">Pipeline</th>
                  <th className="px-3 py-3">Host</th>
                  <th className="px-3 py-3">Status</th>
                  <th className="px-3 py-3">Last Started</th>
                  <th className="px-3 py-3">Duration</th>
                  <th className="px-3 py-3">Rows Out</th>
                  <th className="px-3 py-3">24h</th>
                  <th className="px-3 py-3">Last Error</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800/80">
                {health.map((row) => (
                  <tr key={row.pipeline} className="align-top">
                    <td className="px-3 py-3">
                      <div className="font-medium text-slate-100">{row.pipeline}</div>
                      <div className="mt-1 text-xs text-slate-500">{row.trigger_kind || "â€”"}</div>
                    </td>
                    <td className="px-3 py-3 text-slate-300">{row.host || "â€”"}</td>
                    <td className={`px-3 py-3 font-medium ${statusTone(row.last_status)}`}>{row.last_status || "â€”"}</td>
                    <td className="px-3 py-3 text-slate-300">{formatDateTime(row.last_started_at)}</td>
                    <td className="px-3 py-3 text-slate-300">{formatSeconds(row.last_duration_seconds)}</td>
                    <td className="px-3 py-3 text-slate-300">{row.last_rows_out ?? "â€”"}</td>
                    <td className="px-3 py-3 text-xs text-slate-400">
                      <div>{row.runs_24h ?? 0} runs</div>
                      <div>{row.ok_24h ?? 0} ok / {row.failed_24h ?? 0} failed / {row.running_24h ?? 0} running</div>
                    </td>
                    <td className="px-3 py-3 text-xs text-slate-400">
                      {row.last_error_type ? (
                        <div>
                          <div className="text-rose-300">{row.last_error_type}</div>
                          <div className="mt-1 max-w-md whitespace-pre-wrap break-words text-slate-500">
                            {row.last_error_message || "â€”"}
                          </div>
                        </div>
                      ) : (
                        "â€”"
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      </div>
    </main>
  );
}

