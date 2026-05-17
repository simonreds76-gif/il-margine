import { promises as fs } from "node:fs";

import { notFound } from "next/navigation";

import { tryGetKnownProjectFilePath } from "@/lib/project-file-paths";

import {
  EmptyState,
  HeroCard,
  LeagueLabel,
  MatchLabel,
  MODEL_MONITOR_ENABLED,
  MonitorNav,
  SectionCard,
  StatCard,
  StatusPill,
  formatDateTimeLabel,
  formatOdds,
  toneClass,
} from "../shared";

export const dynamic = "force-dynamic";

type CsvRow = Record<string, string>;

const SIGNALS_PATH = "data/assist-value/assist-value-shadow-signals.csv";
const MODEL_REPORT_PATH = "data/assist-value/assist-value-model-report.txt";
const SHADOW_REPORT_PATH = "data/assist-value/assist-value-shadow-report.txt";
const SOURCE_AUDIT_PATH = "data/assist-value/setpiece-source-audit.md";

function parseCsvLine(line: string): string[] {
  const cells: string[] = [];
  let current = "";
  let quoted = false;

  for (let i = 0; i < line.length; i += 1) {
    const ch = line[i];
    const next = line[i + 1];
    if (ch === '"' && quoted && next === '"') {
      current += '"';
      i += 1;
      continue;
    }
    if (ch === '"') {
      quoted = !quoted;
      continue;
    }
    if (ch === "," && !quoted) {
      cells.push(current);
      current = "";
      continue;
    }
    current += ch;
  }

  cells.push(current);
  return cells.map((cell) => cell.trim());
}

function parseCsv(text?: string | null): CsvRow[] {
  const lines = (text ?? "")
    .split(/\r?\n/)
    .map((line) => line.trimEnd())
    .filter(Boolean);
  if (lines.length <= 1) return [];
  const headers = parseCsvLine(lines[0]);
  return lines.slice(1).map((line) => {
    const cells = parseCsvLine(line);
    const row: CsvRow = {};
    headers.forEach((header, index) => {
      row[header] = cells[index] ?? "";
    });
    return row;
  });
}

async function readKnownText(relativePath: string): Promise<string> {
  const absolutePath = tryGetKnownProjectFilePath(relativePath);
  if (!absolutePath) return "";
  try {
    return await fs.readFile(absolutePath, "utf8");
  } catch {
    return "";
  }
}

async function readKnownMtime(relativePath: string): Promise<string> {
  const absolutePath = tryGetKnownProjectFilePath(relativePath);
  if (!absolutePath) return "";
  try {
    const stat = await fs.stat(absolutePath);
    return stat.mtime.toISOString();
  } catch {
    return "";
  }
}

function numberValue(row: CsvRow, key: string): number | null {
  const raw = row[key]?.trim();
  if (!raw) return null;
  const parsed = Number(raw);
  return Number.isFinite(parsed) ? parsed : null;
}

function maxString(values: string[]): string {
  return values.filter(Boolean).sort().at(-1) ?? "";
}

function pct(value: number | null, digits = 1): string {
  if (value === null || !Number.isFinite(value)) return "-";
  return `${value.toFixed(digits)}%`;
}

function probPct(value: number | null): string {
  return value === null ? "-" : pct(value * 100, 1);
}

function signedPp(value: number | null): string {
  if (value === null || !Number.isFinite(value)) return "-";
  return `${value > 0 ? "+" : ""}${value.toFixed(2)} pp`;
}

function statusTone(status?: string | null): string {
  const normalized = (status ?? "").toLowerCase();
  if (normalized === "shadow_signal") return "bg-cyan-500/10 text-cyan-300 border-cyan-500/20";
  if (normalized === "watch") return "bg-amber-500/10 text-amber-300 border-amber-500/20";
  if (normalized === "no_edge") return "bg-slate-700/40 text-slate-400 border-slate-600/40";
  if (normalized.includes("disabled")) return "bg-rose-500/10 text-rose-300 border-rose-500/20";
  return "bg-slate-700/40 text-slate-300 border-slate-600/40";
}

function confidenceTone(confidence?: string | null): string {
  const normalized = (confidence ?? "").toLowerCase();
  if (normalized === "high") return "bg-emerald-500/10 text-emerald-300 border-emerald-500/20";
  if (normalized === "medium") return "bg-amber-500/10 text-amber-300 border-amber-500/20";
  if (normalized === "low") return "bg-slate-700/40 text-slate-400 border-slate-600/40";
  return "bg-slate-700/40 text-slate-300 border-slate-600/40";
}

function statusLabel(status?: string | null): string {
  return (status || "unknown").replace(/_/g, " ");
}

function topByEdge(rows: CsvRow[], status: string, limit: number): CsvRow[] {
  return rows
    .filter((row) => row.signal_status === status)
    .sort((a, b) => (numberValue(b, "edge_pp") ?? -Infinity) - (numberValue(a, "edge_pp") ?? -Infinity))
    .slice(0, limit);
}

function byLeague(rows: CsvRow[]): Array<[string, number]> {
  const counts = new Map<string, number>();
  rows.forEach((row) => {
    const key = row.league_key || row.competition || "unknown";
    counts.set(key, (counts.get(key) ?? 0) + 1);
  });
  return Array.from(counts.entries()).sort((a, b) => b[1] - a[1]);
}

function renderSignalRow(row: CsvRow) {
  const edge = numberValue(row, "edge_pp");
  const ev = numberValue(row, "ev_pct");
  const modelProb = numberValue(row, "model_prob");
  const setpieceShare = numberValue(row, "setpiece_share_last5_pct");
  const cornerShare = numberValue(row, "corner_share_last5_pct");
  const fkShare = numberValue(row, "fk_share_last5_pct");
  const expectedMinutes = numberValue(row, "expected_minutes");

  return (
    <tr key={`${row.kickoff_at}-${row.player_name}-${row.market_odds}`} className="border-t border-slate-800/70">
      <td className="py-3 pr-4 align-top">
        <div className="font-semibold text-slate-100">{row.player_name || "-"}</div>
        <div className="mt-1 flex flex-wrap items-center gap-1.5 text-xs text-slate-500">
          <span>{row.position || "pos -"}</span>
          <span>|</span>
          <span>{row.player_team || "team -"}</span>
          <span>|</span>
          <span>{expectedMinutes === null ? "mins -" : `${expectedMinutes.toFixed(0)} mins`}</span>
        </div>
      </td>
      <td className="py-3 pr-4 align-top">
        <div className="flex flex-col gap-1">
          <LeagueLabel league={row.league_key} label={row.competition} />
          <MatchLabel league={row.league_key} homeTeam={row.home_team} awayTeam={row.away_team} />
          <span className="text-xs text-slate-500">{formatDateTimeLabel(row.kickoff_at)}</span>
        </div>
      </td>
      <td className="py-3 pr-4 align-top tabular-nums text-slate-200">{formatOdds(numberValue(row, "fair_odds"), 3)}</td>
      <td className="py-3 pr-4 align-top tabular-nums text-slate-200">{formatOdds(numberValue(row, "market_odds"), 3)}</td>
      <td className="py-3 pr-4 align-top tabular-nums">
        <span className={toneClass(edge)}>{signedPp(edge)}</span>
        <div className="mt-1 text-xs text-slate-500">EV {ev === null ? "-" : `${ev.toFixed(2)}%`}</div>
      </td>
      <td className="py-3 pr-4 align-top tabular-nums text-slate-300">{probPct(modelProb)}</td>
      <td className="py-3 pr-4 align-top">
        <div className="flex flex-wrap gap-1.5">
          <StatusPill label={statusLabel(row.signal_status)} tone={statusTone(row.signal_status)} />
          <StatusPill label={row.confidence || "unknown"} tone={confidenceTone(row.confidence)} />
        </div>
        <div className="mt-1 text-xs leading-5 text-slate-500">
          Set pieces {pct(setpieceShare)}
          {cornerShare !== null || fkShare !== null ? ` | CK ${pct(cornerShare)} | FK ${pct(fkShare)}` : ""}
        </div>
      </td>
    </tr>
  );
}

export default async function AssistValueMonitorPage() {
  if (!MODEL_MONITOR_ENABLED) notFound();

  const [signalsText, modelReport, shadowReport, sourceAudit, signalsMtime] = await Promise.all([
    readKnownText(SIGNALS_PATH),
    readKnownText(MODEL_REPORT_PATH),
    readKnownText(SHADOW_REPORT_PATH),
    readKnownText(SOURCE_AUDIT_PATH),
    readKnownMtime(SIGNALS_PATH),
  ]);

  const rows = parseCsv(signalsText);
  const allSignalRows = rows.filter((row) => row.signal_status === "shadow_signal");
  const signalRows = topByEdge(rows, "shadow_signal", 25);
  const watchRows = topByEdge(rows, "watch", 15);
  const noEdgeRows = rows.filter((row) => row.signal_status === "no_edge").length;
  const highSignals = allSignalRows.filter((row) => row.confidence === "high").length;
  const mediumSignals = allSignalRows.filter((row) => row.confidence === "medium").length;
  const latestGeneratedAt = maxString(rows.map((row) => row.generated_at));
  const latestCapturedAt = maxString(rows.map((row) => row.captured_at));

  return (
    <main className="min-h-screen bg-slate-950 text-slate-300">
      <div className="mx-auto max-w-7xl px-4 py-8 sm:px-6 lg:px-8">
        <div className="mb-6 flex flex-wrap items-center justify-between gap-3">
          <MonitorNav current="assist-value" />
          <StatusPill label="private shadow only" tone="bg-cyan-500/10 text-cyan-300 border-cyan-500/20" />
        </div>

        <HeroCard eyebrow="Assist Value Lab" title="Assist Value Monitor">
          <div className="flex flex-col gap-3 text-slate-400">
            <p>
              Private assist fair-odds candidates built from Bet365 assist prices, player assist/xA rates, team attack
              scale, and set-piece role share. This page is monitor-only: no Fair Odds Lab publication, no settlement
              claim, and no production signal lane.
            </p>
            <div className="flex flex-wrap gap-2">
              <StatusPill label="model enabled shadow v0" tone="bg-amber-500/10 text-amber-300 border-amber-500/20" />
              <StatusPill label="public disabled" tone="bg-rose-500/10 text-rose-300 border-rose-500/20" />
              <StatusPill label="not backtested" tone="bg-slate-700/40 text-slate-300 border-slate-600/40" />
            </div>
          </div>
        </HeroCard>

        <section className="mt-6 grid gap-4 sm:grid-cols-2 lg:grid-cols-5">
          <StatCard label="Priced rows" value={rows.length.toLocaleString("en-GB")} detail="Bet365 assist rows scored" />
          <StatCard label="Shadow signals" value={allSignalRows.length.toString()} tone="text-cyan-300" detail={`${highSignals} high, ${mediumSignals} medium`} />
          <StatCard label="Watch rows" value={watchRows.length.toString()} tone="text-amber-300" detail={`${noEdgeRows.toLocaleString("en-GB")} no-edge rows`} />
          <StatCard label="Latest capture" value={latestCapturedAt ? formatDateTimeLabel(latestCapturedAt) : "-"} detail={`CSV mtime ${signalsMtime ? formatDateTimeLabel(signalsMtime) : "-"}`} />
          <StatCard label="Generated" value={latestGeneratedAt ? formatDateTimeLabel(latestGeneratedAt) : "-"} detail="Pipeline timestamp" />
        </section>

        <section className="mt-6 grid gap-6 lg:grid-cols-[1fr_360px]">
          <SectionCard title="Current Shadow Signals" subtitle="Sorted by model edge against Bet365 assist odds">
            {signalRows.length > 0 ? (
              <div className="overflow-x-auto">
                <table className="min-w-full text-left text-sm">
                  <thead className="text-[10px] uppercase tracking-[0.16em] text-slate-500">
                    <tr>
                      <th className="pb-2 pr-4 font-semibold">Player</th>
                      <th className="pb-2 pr-4 font-semibold">Fixture</th>
                      <th className="pb-2 pr-4 font-semibold">Fair</th>
                      <th className="pb-2 pr-4 font-semibold">Market</th>
                      <th className="pb-2 pr-4 font-semibold">Edge</th>
                      <th className="pb-2 pr-4 font-semibold">Model</th>
                      <th className="pb-2 pr-4 font-semibold">Role</th>
                    </tr>
                  </thead>
                  <tbody>{signalRows.map(renderSignalRow)}</tbody>
                </table>
              </div>
            ) : (
              <EmptyState message="No assist shadow signals in the latest artifact." />
            )}
          </SectionCard>

          <div className="space-y-6">
            <SectionCard title="Signal Mix" subtitle="Current shadow candidates by league">
              {byLeague(allSignalRows).length > 0 ? (
                <div className="space-y-2">
                  {byLeague(allSignalRows).map(([league, count]) => (
                    <div key={league} className="flex items-center justify-between rounded-xl border border-slate-800/70 bg-slate-950/40 px-3 py-2">
                      <LeagueLabel league={league} />
                      <span className="text-sm font-semibold tabular-nums text-slate-100">{count}</span>
                    </div>
                  ))}
                </div>
              ) : (
                <EmptyState message="No league-level signal mix yet." />
              )}
            </SectionCard>

            <SectionCard title="Guardrail" subtitle="Why this is not public">
              <div className="space-y-3 text-sm leading-6 text-slate-400">
                <p>
                  The page is deliberately parked under model monitor. It helps us inspect the live assist model, but it
                  does not authorize publication until settlement/backtest gates exist.
                </p>
                <ul className="list-disc space-y-1 pl-5 text-slate-500">
                  <li>No Fair Odds Lab exposure.</li>
                  <li>No public signal lane.</li>
                  <li>No staking or action label.</li>
                  <li>No backtest claim yet.</li>
                </ul>
              </div>
            </SectionCard>
          </div>
        </section>

        <section className="mt-6 grid gap-6 lg:grid-cols-2">
          <SectionCard title="Watch Rows" subtitle="Near-miss assist candidates" collapsible defaultOpen={false}>
            {watchRows.length > 0 ? (
              <div className="overflow-x-auto">
                <table className="min-w-full text-left text-sm">
                  <thead className="text-[10px] uppercase tracking-[0.16em] text-slate-500">
                    <tr>
                      <th className="pb-2 pr-4 font-semibold">Player</th>
                      <th className="pb-2 pr-4 font-semibold">Fixture</th>
                      <th className="pb-2 pr-4 font-semibold">Fair</th>
                      <th className="pb-2 pr-4 font-semibold">Market</th>
                      <th className="pb-2 pr-4 font-semibold">Edge</th>
                      <th className="pb-2 pr-4 font-semibold">Model</th>
                      <th className="pb-2 pr-4 font-semibold">Role</th>
                    </tr>
                  </thead>
                  <tbody>{watchRows.map(renderSignalRow)}</tbody>
                </table>
              </div>
            ) : (
              <EmptyState message="No watch rows in the latest artifact." />
            )}
          </SectionCard>

          <SectionCard title="Model Report" subtitle="Raw report written by scripts/build-assist-value-model.py" collapsible defaultOpen={false}>
            {modelReport ? (
              <pre className="max-h-[520px] overflow-auto whitespace-pre-wrap rounded-xl border border-slate-800/70 bg-slate-950/60 p-4 text-xs leading-5 text-slate-300">
                {modelReport}
              </pre>
            ) : (
              <EmptyState message="Model report is missing." />
            )}
          </SectionCard>
        </section>

        <section className="mt-6 grid gap-6 lg:grid-cols-2">
          <SectionCard title="Shadow Pipeline Report" subtitle="Live scrape and board-build summary" collapsible defaultOpen={false}>
            {shadowReport ? (
              <pre className="max-h-[520px] overflow-auto whitespace-pre-wrap rounded-xl border border-slate-800/70 bg-slate-950/60 p-4 text-xs leading-5 text-slate-300">
                {shadowReport}
              </pre>
            ) : (
              <EmptyState message="Shadow report is missing." />
            )}
          </SectionCard>

          <SectionCard title="Set-Piece Source Audit" subtitle="Role-source status used by the assist model" collapsible defaultOpen={false}>
            {sourceAudit ? (
              <pre className="max-h-[520px] overflow-auto whitespace-pre-wrap rounded-xl border border-slate-800/70 bg-slate-950/60 p-4 text-xs leading-5 text-slate-300">
                {sourceAudit}
              </pre>
            ) : (
              <EmptyState message="Set-piece source audit is missing." />
            )}
          </SectionCard>
        </section>
      </div>
    </main>
  );
}
