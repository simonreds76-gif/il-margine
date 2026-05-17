import Link from "next/link";
import { notFound } from "next/navigation";

import {
  readGoalscorerLiveFile,
  readGoalscorerLiveMtime,
} from "@/lib/goalscorer-live-files";

type CsvRow = Record<string, string>;

const MODEL_MONITOR_PUBLIC =
  process.env.MODEL_MONITOR_PUBLIC === "1" ||
  process.env.NEXT_PUBLIC_ENABLE_MODEL_MONITOR === "1";
const MODEL_MONITOR_ENABLED =
  MODEL_MONITOR_PUBLIC || process.env.VERCEL_ENV === "preview";

const SIGNALS_PATH = "data/assist-value/assist-value-shadow-signals.csv";
const SHADOW_REPORT_PATH = "data/assist-value/assist-value-shadow-report.txt";
const MODEL_REPORT_PATH = "data/assist-value/assist-value-model-report.txt";

function parseCsvLine(line: string): string[] {
  const cells: string[] = [];
  let current = "";
  let quoted = false;
  for (let index = 0; index < line.length; index += 1) {
    const char = line[index];
    if (char === '"' && quoted && line[index + 1] === '"') {
      current += '"';
      index += 1;
      continue;
    }
    if (char === '"') {
      quoted = !quoted;
      continue;
    }
    if (char === "," && !quoted) {
      cells.push(current);
      current = "";
      continue;
    }
    current += char;
  }
  cells.push(current);
  return cells.map((cell) => cell.trim());
}

function parseCsv(text: string | null): CsvRow[] {
  const lines = (text ?? "").split(/\r?\n/).filter(Boolean);
  if (lines.length < 2) return [];
  const headers = parseCsvLine(lines[0]);
  return lines.slice(1).map((line) => {
    const values = parseCsvLine(line);
    const row: CsvRow = {};
    headers.forEach((header, index) => {
      row[header] = values[index] ?? "";
    });
    return row;
  });
}

function numeric(row: CsvRow, key: string): number | null {
  const value = Number(row[key]);
  return Number.isFinite(value) ? value : null;
}

function fmt(value: number | null, digits = 1): string {
  if (value === null) return "-";
  return value.toFixed(digits);
}

function pct(value: number | null, digits = 1): string {
  if (value === null) return "-";
  return `${value.toFixed(digits)}%`;
}

function odds(value: number | null): string {
  if (value === null) return "-";
  return value.toFixed(value >= 10 ? 1 : 2);
}

function reportValue(report: string | null, label: string): string {
  const match = (report ?? "").match(new RegExp(`${label}:\\s*([^\\n\\r]+)`));
  return match?.[1]?.trim() ?? "-";
}

function maxValue(rows: CsvRow[], key: string): string {
  return rows.map((row) => row[key]).filter(Boolean).sort().at(-1) ?? "-";
}

function confidenceTone(confidence: string): string {
  if (confidence.toLowerCase() === "high") return "border-emerald-400/30 bg-emerald-400/10 text-emerald-200";
  if (confidence.toLowerCase() === "medium") return "border-amber-400/30 bg-amber-400/10 text-amber-200";
  return "border-slate-700 bg-slate-900 text-slate-300";
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-2xl border border-slate-800 bg-slate-950/60 p-4">
      <div className="text-[11px] font-bold uppercase tracking-[0.18em] text-slate-500">{label}</div>
      <div className="mt-2 text-2xl font-black tracking-tight text-white">{value}</div>
    </div>
  );
}

export default async function AssistValueMonitorPage() {
  if (process.env.NODE_ENV === "production" && !MODEL_MONITOR_ENABLED) {
    notFound();
  }

  const [signalsText, shadowReport, modelReport, signalsMtime] = await Promise.all([
    readGoalscorerLiveFile(SIGNALS_PATH),
    readGoalscorerLiveFile(SHADOW_REPORT_PATH),
    readGoalscorerLiveFile(MODEL_REPORT_PATH),
    readGoalscorerLiveMtime(SIGNALS_PATH),
  ]);
  const rows = parseCsv(signalsText);
  const shadowRows = rows.filter((row) => row.signal_status === "shadow_signal");
  const watchRows = rows.filter((row) => row.signal_status === "watch");
  const sortedSignals = [...shadowRows].sort((a, b) => (numeric(b, "edge_pp") ?? -999) - (numeric(a, "edge_pp") ?? -999));
  const generatedAt = maxValue(rows, "generated_at");
  const roleMatchRate = reportValue(shadowReport, "role_match_rate_pct");

  return (
    <main className="min-h-screen bg-[#061014] px-4 py-8 text-slate-100 sm:px-6 lg:px-10">
      <div className="mx-auto max-w-7xl">
        <div className="mb-5 flex flex-wrap items-center justify-between gap-3">
          <Link href="/model-monitor" className="text-sm font-semibold text-emerald-300 hover:text-emerald-200">
            ← Model monitor
          </Link>
          <span className="rounded-full border border-amber-400/30 bg-amber-400/10 px-3 py-1 text-xs font-bold uppercase tracking-[0.16em] text-amber-200">
            Private shadow only
          </span>
        </div>

        <section className="rounded-3xl border border-slate-800 bg-slate-950/80 p-6 shadow-2xl shadow-black/30">
          <p className="text-xs font-bold uppercase tracking-[0.22em] text-sky-300">Assist Value Lab</p>
          <h1 className="mt-3 text-3xl font-black tracking-tight text-white sm:text-4xl">Assist Value Shadow Monitor</h1>
          <p className="mt-3 max-w-4xl text-sm leading-6 text-slate-400">
            Bet365 assist odds enriched with set-piece-role data. This is not public Fair Odds output, not an authorised betting lane,
            and not wired into the public lab.
          </p>
          <div className="mt-6 grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
            <Stat label="Rows" value={`${rows.length}`} />
            <Stat label="Shadow Signals" value={`${shadowRows.length}`} />
            <Stat label="Watch Rows" value={`${watchRows.length}`} />
            <Stat label="Role Match" value={roleMatchRate === "-" ? "-" : `${roleMatchRate}%`} />
            <Stat label="Generated" value={generatedAt === "-" ? signalsMtime ?? "-" : generatedAt} />
          </div>
        </section>

        <section className="mt-6 grid gap-4 lg:grid-cols-[1fr_360px]">
          <div className="rounded-3xl border border-slate-800 bg-slate-950/70 p-5">
            <div className="mb-4 flex items-center justify-between gap-3">
              <div>
                <h2 className="text-xl font-black text-white">Top Shadow Signals</h2>
                <p className="mt-1 text-sm text-slate-500">Sorted by model edge versus market assist odds.</p>
              </div>
            </div>
            {sortedSignals.length === 0 ? (
              <div className="rounded-2xl border border-slate-800 bg-slate-900/50 p-5 text-sm text-slate-400">
                No shadow signals in the hosted assist artifact yet.
              </div>
            ) : (
              <div className="space-y-3">
                {sortedSignals.slice(0, 20).map((row, index) => (
                  <div
                    key={`${row.player_name}-${row.home_team}-${row.away_team}-${row.kickoff_at}-${index}`}
                    className="rounded-2xl border border-slate-800 bg-slate-900/55 p-4"
                  >
                    <div className="flex flex-wrap items-start justify-between gap-3">
                      <div>
                        <div className="text-lg font-black text-white">{row.player_name}</div>
                        <div className="mt-1 text-sm text-slate-400">
                          {row.home_team} vs {row.away_team} · {row.competition}
                        </div>
                        <div className="mt-1 text-xs text-slate-500">{row.kickoff_at || row.match_date}</div>
                      </div>
                      <div className="flex flex-wrap gap-2">
                        <span className={`rounded-full border px-2 py-1 text-[11px] font-bold uppercase tracking-[0.14em] ${confidenceTone(row.confidence)}`}>
                          {row.confidence || "unrated"}
                        </span>
                        <span className="rounded-full border border-sky-400/30 bg-sky-400/10 px-2 py-1 text-[11px] font-bold uppercase tracking-[0.14em] text-sky-200">
                          {row.signal_status || "shadow"}
                        </span>
                      </div>
                    </div>
                    <div className="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
                      <Stat label="Fair Odds" value={odds(numeric(row, "fair_odds"))} />
                      <Stat label="Market" value={odds(numeric(row, "market_odds"))} />
                      <Stat label="Edge" value={`${fmt(numeric(row, "edge_pp"), 2)} pp`} />
                      <Stat label="EV" value={pct(numeric(row, "ev_pct"), 1)} />
                      <Stat label="Set Pieces" value={pct(numeric(row, "setpiece_share_last5_pct"), 1)} />
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>

          <aside className="space-y-4">
            <div className="rounded-3xl border border-slate-800 bg-slate-950/70 p-5">
              <h2 className="text-lg font-black text-white">Shadow Report</h2>
              <div className="mt-4 space-y-3 text-sm text-slate-300">
                <div>status: {reportValue(shadowReport, "shadow_status")}</div>
                <div>public: {reportValue(shadowReport, "public_signal_status")}</div>
                <div>model: {reportValue(shadowReport, "model_status")}</div>
                <div>fair odds: {reportValue(shadowReport, "fair_odds_status")}</div>
              </div>
            </div>
            <div className="rounded-3xl border border-slate-800 bg-slate-950/70 p-5">
              <h2 className="text-lg font-black text-white">Model Report</h2>
              <pre className="mt-4 max-h-[460px] overflow-auto whitespace-pre-wrap rounded-2xl bg-black/30 p-4 text-xs leading-5 text-slate-300">
                {modelReport || "No assist model report found in hosted artifacts."}
              </pre>
            </div>
          </aside>
        </section>
      </div>
    </main>
  );
}
