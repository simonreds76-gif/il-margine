import { promises as fs } from "fs";
import path from "path";
import { Fragment } from "react";
import { notFound } from "next/navigation";
import Link from "next/link";
import {
  MODEL_MONITOR_ENABLED,
  MonitorNav,
  HeroCard,
  SectionCard,
  StatCard,
  StatusPill,
  EmptyState,
  cn,
} from "../shared";

export const dynamic = "force-dynamic";

type CsvRow = Record<string, string>;
type JsonRecord = Record<string, unknown>;
type ProjectionSortKey = "schedule" | "aces" | "dfs" | "match_tb" | "first_tb" | "breaks";
type MostAcesSortKey = "schedule" | "favourite" | "closest";
type MonitorTab = "decision" | "projections";
type SearchParamsInput = Promise<Record<string, string | string[] | undefined>>;
type TournamentRoundLog = {
  date?: string;
  round?: string;
  opponent?: string;
  result?: string;
  aces?: string;
  dfs?: string;
  breaks_for?: string;
  broken?: string;
  total_breaks?: string;
  first_set_tiebreak?: string;
  match_tiebreak?: string;
  svpt?: string;
};

const ROOT = process.cwd();
const PROPS_DIR = path.join(ROOT, "data", "tennis-props");
const BOARD_PATH = path.join(PROPS_DIR, "player-props-board.csv");
const BASELINE_PATH = path.join(PROPS_DIR, "player-props-baseline.csv");
const FACTORS_PATH = path.join(PROPS_DIR, "slam-venue-factors.csv");
const INBOX_DIR = path.join(PROPS_DIR, "inbox");
const SHADOW_DIR = path.join(PROPS_DIR, "shadow");
const SHADOW_SIGNALS_PATH = path.join(SHADOW_DIR, "aces-dfs-shadow-signals.csv");
const SHADOW_PERFORMANCE_PATH = path.join(SHADOW_DIR, "aces-dfs-shadow-performance.txt");
const V3_SHADOW_SIGNALS_PATH = path.join(SHADOW_DIR, "aces-v3-shadow-signals.csv");
const V4_OBSERVATIONS_PATH = path.join(SHADOW_DIR, "aces-over-v4-observations.csv");
const V4_REPORT_PATH = path.join(PROPS_DIR, "backtest", "aces-over-v4-weekly-report.json");
const MOST_ACES_BOARD_PATH = path.join(SHADOW_DIR, "most-aces-1x2-board.csv");
const MOST_ACES_DIRECT_BOARD_PATH = path.join(SHADOW_DIR, "most-aces-direct-1x2-board.csv");
const MOST_ACES_OBSERVATIONS_PATH = path.join(SHADOW_DIR, "most-aces-1x2-observations.csv");
const MOST_ACES_STAGE0_PATH = path.join(PROPS_DIR, "backtest", "most-aces-1x2-stage0.json");
const MOST_ACES_DIRECT_RESULT_PATH = path.join(PROPS_DIR, "experiments", "most-aces-direct-1x2", "result.json");
const MOST_ACES_DIRECT_PARITY_PATH = path.join(SHADOW_DIR, "most-aces-direct-1x2-live-parity.json");
const MOST_ACES_FORECASTS_PATH = path.join(SHADOW_DIR, "most-aces-1x2-forecasts.csv");
const MOST_ACES_FORECAST_REPORT_PATH = path.join(SHADOW_DIR, "most-aces-1x2-forecast-report.json");
const MARKET_OBSERVATIONS_PATH = path.join(SHADOW_DIR, "market-observations.csv");
const MARKET_OBSERVATIONS_REPORT_PATH = path.join(SHADOW_DIR, "market-observations-report.txt");
const MODEL_SUMMARY_PATH = path.join(PROPS_DIR, "model-monitor-summary.csv");
const MODEL_REPORT_PATH = path.join(PROPS_DIR, "model-monitor-report.txt");
const TOTALS_GATE_PATH = path.join(PROPS_DIR, "backtest", "aces-dfs-totals-gate.json");
const PROPS_V2_GATE_PATH = path.join(PROPS_DIR, "backtest", "aces-dfs-v2-rung1-gate.json");
const SERVICE_POINTS_GATE_PATH = path.join(PROPS_DIR, "backtest", "aces-dfs-service-points-gate.json");
const OPPONENT_RETURN_GATE_PATH = path.join(PROPS_DIR, "backtest", "aces-opponent-return-gate.json");
const RATE_RECENCY_GATE_PATH = path.join(PROPS_DIR, "backtest", "aces-dfs-rate-recency-gate.json");
const PROPS_V3_GATE_PATH = path.join(PROPS_DIR, "backtest", "aces-dfs-v3-all-tour-gate.json");
const DERIVATIVES_STATUS_PATH = path.join(ROOT, "data", "vnext", "tennis-derivatives-evidence-status.json");

function parseCsv(text: string): CsvRow[] {
  const rows: string[][] = [];
  let row: string[] = [];
  let field = "";
  let inQuotes = false;

  for (let i = 0; i < text.length; i++) {
    const ch = text[i];
    const next = text[i + 1];
    if (ch === '"') {
      if (inQuotes && next === '"') {
        field += '"';
        i++;
      } else {
        inQuotes = !inQuotes;
      }
      continue;
    }
    if (ch === "," && !inQuotes) {
      row.push(field);
      field = "";
      continue;
    }
    if ((ch === "\n" || ch === "\r") && !inQuotes) {
      if (ch === "\r" && next === "\n") i++;
      row.push(field);
      if (row.some((value) => value.trim())) rows.push(row);
      row = [];
      field = "";
      continue;
    }
    field += ch;
  }
  if (field || row.length) {
    row.push(field);
    if (row.some((value) => value.trim())) rows.push(row);
  }
  if (rows.length < 2) return [];
  const headers = rows[0].map((header) => header.trim());
  return rows.slice(1).map((values) => {
    const parsed: CsvRow = {};
    headers.forEach((header, index) => {
      parsed[header] = (values[index] ?? "").trim();
    });
    return parsed;
  });
}

async function readCsv(filePath: string): Promise<CsvRow[]> {
  try {
    return parseCsv(await fs.readFile(filePath, "utf8"));
  } catch {
    return [];
  }
}

async function fileStamp(filePath: string): Promise<string> {
  try {
    const stat = await fs.stat(filePath);
    return stat.mtime.toLocaleString("en-GB", { timeZone: "Europe/London" });
  } catch {
    return "missing";
  }
}

async function fileAgeHours(filePath: string): Promise<number | null> {
  try {
    const stat = await fs.stat(filePath);
    return (Date.now() - stat.mtimeMs) / 36e5;
  } catch {
    return null;
  }
}

async function latestCsv(prefix: string): Promise<string | null> {
  try {
    const files = await fs.readdir(prefix === "comparison" ? PROPS_DIR : INBOX_DIR);
    const dir = prefix === "comparison" ? PROPS_DIR : INBOX_DIR;
    const matches = files
      .filter((file) => (
        file.startsWith(`${prefix}-`)
        && file.endsWith(".csv")
        && !(prefix === "comparison" && file.endsWith("-unmatched.csv"))
        && !(prefix === "bet365-lines" && file.startsWith("bet365-lines-history-"))
      ))
      .map((file) => path.join(dir, file));
    if (!matches.length) return null;
    const stamped = await Promise.all(
      matches.map(async (file) => ({
        file,
        mtime: (await fs.stat(file)).mtimeMs,
      })),
    );
    return stamped.sort((a, b) => b.mtime - a.mtime)[0]?.file ?? null;
  } catch {
    return null;
  }
}

function n(value: string | undefined): number {
  const parsed = Number.parseFloat(value ?? "");
  return Number.isFinite(parsed) ? parsed : 0;
}

function fmt(value: string | number | undefined, digits = 1): string {
  const parsed = typeof value === "number" ? value : Number.parseFloat(value ?? "");
  return Number.isFinite(parsed) ? parsed.toFixed(digits) : "-";
}

function hasNumeric(value: string | undefined): boolean {
  const parsed = Number.parseFloat(value ?? "");
  return Number.isFinite(parsed) && parsed > 0;
}

function normalizedText(...parts: (string | undefined)[]): string {
  return parts.join(" ").toLowerCase();
}

function isMainTourProjectionRow(row: CsvRow): boolean {
  const tour = (row.tour || "").toUpperCase();
  if (tour !== "ATP" && tour !== "WTA") return false;
  const text = normalizedText(row.tournament, row.round, row.source, row.player, row.opponent);
  if (/junior|boys|girls|qualifying|qualifier|challenger|itf|doubles/.test(text)) return false;
  return true;
}

function effectiveLineQuality(row: CsvRow): string {
  if (row.line_quality) return row.line_quality;
  if (
    hasNumeric(row.over_odds)
    && hasNumeric(row.under_odds)
    && hasNumeric(row.fair_over_odds)
    && hasNumeric(row.fair_under_odds)
  ) {
    return "complete";
  }
  if (row.matched_board === "yes") return "partial";
  return "unmatched";
}

function isTrustedComparisonRow(row: CsvRow): boolean {
  return row.matched_board === "yes" && (
    effectiveLineQuality(row) === "complete"
    || row.decision_mode === "over_only_raw_ev"
  );
}

function isMatchTotalComparisonRow(row: CsvRow): boolean {
  return row.scope === "match_total" || row.market === "match_aces" || row.market === "match_double_faults";
}

function isUsefulComparisonRow(row: CsvRow): boolean {
  if (isMatchTotalComparisonRow(row)) return true;
  return ["aces", "double_faults", "player_breaks", "match_breaks"].includes(row.market || "");
}

function isBettableComparisonRow(row: CsvRow): boolean {
  return row.bettable === "true" || (Boolean(row.recommended_side) && isTrustedComparisonRow(row));
}

function isHardHiddenLine(row: CsvRow): boolean {
  if (row.best_available_line === "true") return false;
  const quality = effectiveLineQuality(row);
  return quality === "one_sided" || quality === "deep_alt" || row.matched_board !== "yes";
}

function validMonitorTab(value: string | string[] | undefined): MonitorTab {
  const raw = Array.isArray(value) ? value[0] : value;
  return raw === "projections" ? "projections" : "decision";
}

function pctText(value: string | number | undefined, digits = 1): string {
  const parsed = typeof value === "number" ? value : Number.parseFloat(value ?? "");
  return Number.isFinite(parsed) ? `${parsed.toFixed(digits)}%` : "-";
}

function factorMove(value: string | undefined, digits = 1): string {
  const parsed = Number.parseFloat(value ?? "");
  if (!Number.isFinite(parsed) || parsed <= 0) return "-";
  const pct = (parsed - 1) * 100;
  if (Math.abs(pct) < 0.05) return "flat";
  return `${pct > 0 ? "+" : ""}${pct.toFixed(digits)}%`;
}

function factorProductMove(first: string | undefined, second: string | undefined, digits = 1): string {
  const a = Number.parseFloat(first ?? "");
  const b = Number.parseFloat(second ?? "");
  const product = (Number.isFinite(a) && a > 0 ? a : 1) * (Number.isFinite(b) && b > 0 ? b : 1);
  return factorMove(String(product), digits);
}

function confidenceTone(value: string | undefined): string {
  if (value === "HIGH") return "border-emerald-500/25 bg-emerald-500/10 text-emerald-300";
  if (value === "MED") return "border-amber-500/25 bg-amber-500/10 text-amber-300";
  return "border-slate-700/70 bg-slate-800/60 text-slate-400";
}

function recTone(value: string | undefined): string {
  if (value === "OVER" || value === "UNDER") return "border-cyan-500/25 bg-cyan-500/10 text-cyan-200";
  return "border-slate-700/70 bg-slate-800/60 text-slate-500";
}

function maxValue(row: CsvRow): number {
  if (row.matched_board !== "yes") return 0;
  return Math.max(n(row.value_over_pct), n(row.value_under_pct));
}

function boardSort(a: CsvRow, b: CsvRow): number {
  const aConf = a.ace_confidence === "HIGH" ? 2 : a.ace_confidence === "MED" ? 1 : 0;
  const bConf = b.ace_confidence === "HIGH" ? 2 : b.ace_confidence === "MED" ? 1 : 0;
  return bConf - aConf || n(b.projected_aces) - n(a.projected_aces);
}

function comparisonSort(a: CsvRow, b: CsvRow): number {
  const aRec = a.recommended_side ? 1 : 0;
  const bRec = b.recommended_side ? 1 : 0;
  return bRec - aRec || maxValue(b) - maxValue(a);
}

function shadowSort(a: CsvRow, b: CsvRow): number {
  const statusRank = (row: CsvRow) => row.settlement_status === "pending" ? 0 : row.settlement_status === "settled" ? 1 : 2;
  return statusRank(a) - statusRank(b) || (b.date || "").localeCompare(a.date || "") || n(b.value_pct) - n(a.value_pct);
}

function shadowStats(rows: CsvRow[]): { settled: number; pending: number; voided: number; pnl: number; roi: number; clvCount: number; meanClv: number; positiveClv: number } {
  const settledRows = rows.filter((row) => row.settlement_status === "settled");
  const pnl = settledRows.reduce((sum, row) => sum + n(row.pnl), 0);
  const clvRows = settledRows.filter((row) => row.clv_pct !== "" && Number.isFinite(Number.parseFloat(row.clv_pct || "")));
  const meanClv = clvRows.length ? clvRows.reduce((sum, row) => sum + n(row.clv_pct), 0) / clvRows.length : 0;
  return {
    settled: settledRows.length,
    pending: rows.filter((row) => row.settlement_status === "pending").length,
    voided: rows.filter((row) => row.settlement_status === "void").length,
    pnl,
    roi: settledRows.length ? (pnl / settledRows.length) * 100 : 0,
    clvCount: clvRows.length,
    meanClv,
    positiveClv: clvRows.length ? clvRows.filter((row) => n(row.clv_pct) > 0).length / clvRows.length * 100 : 0,
  };
}

function meanNumeric(rows: CsvRow[], field: string): number | null {
  const values = rows
    .map((row) => Number.parseFloat(row[field] || ""))
    .filter(Number.isFinite);
  return values.length ? values.reduce((sum, value) => sum + value, 0) / values.length : null;
}

function benchmarkStats(rows: CsvRow[]) {
  const settled = rows.filter((row) => row.settlement_status === "settled");
  const scored = settled.filter((row) => row.outcome_over === "0" || row.outcome_over === "1");
  const modelBrier = meanNumeric(scored, "model_brier");
  const marketBrier = meanNumeric(scored, "observed_market_brier");
  return {
    observations: rows.length,
    settled: settled.length,
    scored: scored.length,
    pending: rows.filter((row) => row.settlement_status === "pending").length,
    modelMae: meanNumeric(settled, "model_count_abs_error"),
    marketMae: meanNumeric(settled, "observed_market_count_abs_error"),
    closeMae: meanNumeric(settled, "closing_market_count_abs_error"),
    modelBrier,
    marketBrier,
    closeBrier: meanNumeric(scored, "closing_market_brier"),
    brierDelta: modelBrier != null && marketBrier != null ? marketBrier - modelBrier : null,
  };
}

function countBy(rows: CsvRow[], field: string, value: string): number {
  return rows.filter((row) => row[field] === value).length;
}

function topCounts(rows: CsvRow[], field: string, limit = 8): { label: string; count: number }[] {
  const counts = new Map<string, number>();
  for (const row of rows) {
    const label = row[field] || "missing";
    counts.set(label, (counts.get(label) ?? 0) + 1);
  }
  return [...counts.entries()]
    .map(([label, count]) => ({ label, count }))
    .sort((a, b) => b.count - a.count || a.label.localeCompare(b.label))
    .slice(0, limit);
}

function firstBlockReason(row: CsvRow): string {
  return (row.block_reasons || row.blocked_reason || "not blocked").split("|").find(Boolean) || "not blocked";
}

function topBlockReasons(rows: CsvRow[], limit = 8): { label: string; count: number }[] {
  const counts = new Map<string, number>();
  for (const row of rows) {
    const label = firstBlockReason(row);
    counts.set(label, (counts.get(label) ?? 0) + 1);
  }
  return [...counts.entries()]
    .map(([label, count]) => ({ label: blockReasonLabel(label), count }))
    .sort((a, b) => b.count - a.count || a.label.localeCompare(b.label))
    .slice(0, limit);
}

function londonDateIso(value = new Date()): string {
  const parts = new Intl.DateTimeFormat("en-GB", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    timeZone: "Europe/London",
  }).formatToParts(value);
  const part = (type: Intl.DateTimeFormatPartTypes) => parts.find((item) => item.type === type)?.value ?? "";
  return `${part("year")}-${part("month")}-${part("day")}`;
}

async function readJson(filePath: string): Promise<JsonRecord> {
  try {
    const payload: unknown = JSON.parse(await fs.readFile(filePath, "utf8"));
    return payload && typeof payload === "object" && !Array.isArray(payload) ? payload as JsonRecord : {};
  } catch {
    return {};
  }
}

function record(value: unknown): JsonRecord {
  return value && typeof value === "object" && !Array.isArray(value) ? value as JsonRecord : {};
}

function gateMarket(gate: JsonRecord, market: string): JsonRecord {
  return record(record(gate.markets)[market]);
}

function gateTour(gate: JsonRecord, market: string, tour: "ATP" | "WTA"): JsonRecord {
  return record(record(gateMarket(gate, market).tours)[tour]);
}

function gateNumber(row: JsonRecord, key: string): number {
  const value = Number(row[key]);
  return Number.isFinite(value) ? value : 0;
}

function projectionFocusDate(rows: CsvRow[]): string {
  const dates = [...new Set(rows.map((row) => row.date).filter(Boolean))].sort();
  const today = londonDateIso();
  if (dates.includes(today)) return today;
  return dates.find((value) => value > today) ?? dates.at(-1) ?? "-";
}

function dateLabel(value: string): string {
  if (!value) return "Date missing";
  const parsed = new Date(`${value}T12:00:00Z`);
  if (Number.isNaN(parsed.getTime())) return value;
  return new Intl.DateTimeFormat("en-GB", {
    weekday: "short",
    day: "2-digit",
    month: "short",
    timeZone: "Europe/London",
  }).format(parsed);
}

function groupRowsByDate(rows: CsvRow[]): { date: string; rows: CsvRow[] }[] {
  const grouped = new Map<string, CsvRow[]>();
  for (const row of rows) {
    const key = row.date || "unscheduled";
    grouped.set(key, [...(grouped.get(key) ?? []), row]);
  }
  const today = londonDateIso();
  return [...grouped.entries()]
    .sort(([a], [b]) => {
      if (a === "unscheduled") return 1;
      if (b === "unscheduled") return -1;
      if (a === today) return -1;
      if (b === today) return 1;
      const aFuture = a > today;
      const bFuture = b > today;
      if (aFuture !== bFuture) return aFuture ? -1 : 1;
      return aFuture ? a.localeCompare(b) : b.localeCompare(a);
    })
    .map(([date, groupedRows]) => ({ date, rows: groupedRows }));
}

function validProjectionSort(value: string | string[] | undefined): ProjectionSortKey {
  const raw = Array.isArray(value) ? value[0] : value;
  if (raw === "aces" || raw === "dfs" || raw === "match_tb" || raw === "first_tb" || raw === "breaks") return raw;
  return "schedule";
}

function projectionSortValue(rows: CsvRow[], sortKey: ProjectionSortKey): number {
  if (sortKey === "aces") return Math.max(...rows.map((row) => n(row.projected_aces)));
  if (sortKey === "dfs") return Math.max(...rows.map((row) => n(row.projected_dfs)));
  if (sortKey === "match_tb") return Math.max(...rows.map((row) => n(row.match_tiebreak_pct)));
  if (sortKey === "first_tb") return Math.max(...rows.map((row) => n(row.first_set_tiebreak_pct)));
  if (sortKey === "breaks") return Math.max(...rows.map((row) => n(row.projected_total_breaks)));
  return 0;
}

function matchKey(row: CsvRow): string {
  const players = [row.player || "", row.opponent || ""].sort((a, b) => a.localeCompare(b)).join(" v ");
  return [row.date || "", row.tour || "", row.tournament || "", players].join("|");
}

function fixtureName(rows: CsvRow[]): string {
  const first = rows[0] ?? {};
  return `${first.player || "-"} vs ${first.opponent || "-"}`;
}

function groupRowsByDateAndMatch(rows: CsvRow[], sortKey: ProjectionSortKey): { date: string; matches: { key: string; rows: CsvRow[] }[] }[] {
  return groupRowsByDate(rows).map((dateGroup) => {
    const matchMap = new Map<string, CsvRow[]>();
    for (const row of dateGroup.rows) {
      const key = matchKey(row);
      matchMap.set(key, [...(matchMap.get(key) ?? []), row]);
    }
    const matches = [...matchMap.entries()].map(([key, matchRows]) => ({
      key,
      rows: [...matchRows].sort((a, b) => (a.player || "").localeCompare(b.player || "")),
    }));
    matches.sort((a, b) => {
      if (sortKey !== "schedule") {
        return projectionSortValue(b.rows, sortKey) - projectionSortValue(a.rows, sortKey)
          || fixtureName(a.rows).localeCompare(fixtureName(b.rows));
      }
      return fixtureName(a.rows).localeCompare(fixtureName(b.rows));
    });
    return { date: dateGroup.date, matches };
  });
}

function parseTournamentRoundLog(value: string | undefined): TournamentRoundLog[] {
  if (!value) return [];
  try {
    const parsed = JSON.parse(value);
    return Array.isArray(parsed) ? parsed : [];
  } catch {
    return [];
  }
}

type BreakFairOddsRow = {
  line: number;
  over_pct: number;
  under_pct: number;
  fair_over: number;
  fair_under: number;
};

function parseBreakFairOdds(value: string | undefined): BreakFairOddsRow[] {
  if (!value) return [];
  try {
    const parsed = JSON.parse(value);
    if (!Array.isArray(parsed)) return [];
    return parsed.filter((row) => row && Number.isFinite(Number(row.line))) as BreakFairOddsRow[];
  } catch {
    return [];
  }
}

function MiniBadge({ label, tone }: { label: string; tone: string }) {
  return (
    <span className={cn("inline-flex rounded-full border px-2 py-0.5 text-[10px] font-semibold uppercase tracking-[0.14em]", tone)}>
      {label}
    </span>
  );
}

function factorTone(value: string | undefined): string {
  const parsed = Number.parseFloat(value ?? "");
  if (!Number.isFinite(parsed)) return "border-slate-700 bg-slate-900 text-slate-500";
  if (parsed >= 1.03) return "border-emerald-500/25 bg-emerald-500/10 text-emerald-300";
  if (parsed <= 0.97) return "border-rose-500/25 bg-rose-500/10 text-rose-300";
  return "border-slate-700/70 bg-slate-800/60 text-slate-400";
}

function factorProductTone(first: string | undefined, second: string | undefined): string {
  const a = Number.parseFloat(first ?? "");
  const b = Number.parseFloat(second ?? "");
  const product = (Number.isFinite(a) && a > 0 ? a : 1) * (Number.isFinite(b) && b > 0 ? b : 1);
  return factorTone(String(product));
}

function NoteBadges({ value }: { value: string }) {
  const notes = value
    .split("|")
    .map((note) => note.trim())
    .filter(Boolean)
    .slice(0, 5);
  if (!notes.length) return <span className="text-xs text-slate-600">clear</span>;
  return (
    <div className="flex max-w-[300px] flex-wrap gap-1.5">
      {notes.map((note) => (
        <span key={note} className="rounded-full border border-slate-800 bg-slate-950/70 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-[0.08em] text-slate-500">
          {note.replaceAll("_", " ")}
        </span>
      ))}
    </div>
  );
}

function RoundHistoryTable({ row }: { row: CsvRow }) {
  const logs = parseTournamentRoundLog(row.tournament_round_log);
  return (
    <div className="rounded-2xl border border-slate-800/80 bg-slate-950/55 p-3">
      <div className="mb-2 flex flex-wrap items-baseline justify-between gap-2">
        <h4 className="font-black text-slate-100">{row.player || "Player"}</h4>
        <span className="text-[10px] font-bold uppercase tracking-[0.14em] text-slate-600">completed rounds</span>
      </div>
      {logs.length ? (
        <div className="overflow-x-auto">
          <table className="min-w-[600px] text-[11px]">
            <thead className="text-left uppercase tracking-[0.12em] text-slate-600">
              <tr>
                <th className="py-1 pr-3 font-semibold">Round</th>
                <th className="py-1 pr-3 font-semibold">Opponent</th>
                <th className="py-1 pr-3 font-semibold">Aces</th>
                <th className="py-1 pr-3 font-semibold">DFs</th>
                <th className="py-1 pr-3 font-semibold">Brk+</th>
                <th className="py-1 pr-3 font-semibold">Brk-</th>
                <th className="py-1 pr-3 font-semibold">Tot brk</th>
                <th className="py-1 pr-3 font-semibold">1st TB</th>
                <th className="py-1 pr-3 font-semibold">Match TB</th>
                <th className="py-1 pr-3 font-semibold">Result</th>
              </tr>
            </thead>
            <tbody>
              {logs.map((log, index) => (
                <tr key={`${log.date}-${log.round}-${log.opponent}-${index}`} className="border-t border-slate-900">
                  <td className="py-1 pr-3 font-mono text-slate-300">{log.round || "-"}</td>
                  <td className="py-1 pr-3 text-slate-400">{log.opponent || "-"}</td>
                  <td className="py-1 pr-3 font-mono text-emerald-300">{log.aces || "0"}</td>
                  <td className="py-1 pr-3 font-mono text-rose-300">{log.dfs || "0"}</td>
                  <td className="py-1 pr-3 font-mono text-cyan-300">{log.breaks_for || "0"}</td>
                  <td className="py-1 pr-3 font-mono text-amber-300">{log.broken || "0"}</td>
                  <td className="py-1 pr-3 font-mono text-slate-300">{log.total_breaks || "0"}</td>
                  <td className="py-1 pr-3 font-mono text-violet-300">{log.first_set_tiebreak === "1" ? "Y" : "N"}</td>
                  <td className="py-1 pr-3 font-mono text-violet-300">{log.match_tiebreak === "1" ? "Y" : "N"}</td>
                  <td className="py-1 pr-3 font-mono text-slate-500">{log.result || "-"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <div className="text-[11px] leading-relaxed text-slate-600">
          No completed same-tournament stat row found yet.
        </div>
      )}
    </div>
  );
}

function MatchRoundHistory({ rows }: { rows: CsvRow[] }) {
  return (
    <details open className="group border-t border-slate-800/80 bg-slate-950/30 p-4 sm:p-5">
      <summary className="cursor-pointer list-none rounded-2xl border border-emerald-500/20 bg-emerald-500/10 px-4 py-3 text-xs font-black uppercase tracking-[0.15em] text-emerald-200">
        Round-by-round comparison · aces / DFs / breaks / tiebreaks
      </summary>
      <div className="mt-3 grid gap-3 xl:grid-cols-2">
        {rows.map((row, index) => (
          <RoundHistoryTable key={`${row.player}-${row.opponent}-${index}`} row={row} />
        ))}
      </div>
      <p className="mt-3 text-[11px] leading-relaxed text-slate-600">
        1st TB marks a first-set tiebreak. Match TB marks a tiebreak in any set. Every row belongs to the named player above it.
      </p>
    </details>
  );
}

function ProjectionSortControls({ active }: { active: ProjectionSortKey }) {
  const options: { key: ProjectionSortKey; label: string }[] = [
    { key: "schedule", label: "Schedule" },
    { key: "match_tb", label: "Highest match TB" },
    { key: "first_tb", label: "Highest 1st-set TB" },
    { key: "aces", label: "Highest aces" },
    { key: "dfs", label: "Highest DFs" },
    { key: "breaks", label: "Highest breaks" },
  ];
  return (
    <div className="mb-4 flex flex-wrap gap-2">
      {options.map((option) => (
        <Link
          key={option.key}
          href={`/model-monitor/tennis-props?tab=projections&propsSort=${option.key}`}
          className={cn(
            "rounded-full border px-3 py-1.5 text-xs font-bold uppercase tracking-[0.12em] transition",
            active === option.key
              ? "border-emerald-400/40 bg-emerald-500/15 text-emerald-200"
              : "border-slate-800 bg-slate-950/70 text-slate-400 hover:border-slate-600 hover:text-slate-200",
          )}
        >
          {option.label}
        </Link>
      ))}
    </div>
  );
}

function MetricTile({ label, value, sub, tone }: { label: string; value: string; sub?: string; tone: string }) {
  return (
    <div className="min-w-0 rounded-2xl border border-slate-800/80 bg-slate-950/70 p-3">
      <div className="text-[10px] font-black uppercase tracking-[0.16em] text-slate-500">{label}</div>
      <div className={cn("mt-1 break-words font-mono text-xl font-black leading-none sm:text-2xl", tone)}>{value}</div>
      {sub ? <div className="mt-1 text-[11px] leading-snug text-slate-500">{sub}</div> : null}
    </div>
  );
}

function BreakFairOddsPanel({
  title,
  mean,
  ladderJson,
  distribution,
  status,
}: {
  title: string;
  mean: string | undefined;
  ladderJson: string | undefined;
  distribution: string | undefined;
  status: string | undefined;
}) {
  const ladder = parseBreakFairOdds(ladderJson);
  return (
    <div className="rounded-2xl border border-cyan-500/20 bg-cyan-500/[0.06] p-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <div className="text-[10px] font-black uppercase tracking-[0.16em] text-cyan-300">{title}</div>
          <div className="mt-1 font-mono text-lg font-black text-slate-100">mean {fmt(mean, 1)}</div>
        </div>
        <MiniBadge
          label={status === "OUTCOME_PASS_PRICE_FEED_MISSING" ? "outcome model passed" : "research only"}
          tone={status === "OUTCOME_PASS_PRICE_FEED_MISSING" ? "border-emerald-500/25 bg-emerald-500/10 text-emerald-200" : "border-amber-500/25 bg-amber-500/10 text-amber-200"}
        />
      </div>
      {ladder.length ? (
        <div className="mt-3 overflow-x-auto">
          <table className="min-w-full text-xs">
            <thead className="text-left uppercase tracking-[0.12em] text-slate-600">
              <tr><th className="pb-1 pr-3">Line</th><th className="pb-1 pr-3">Over fair</th><th className="pb-1 pr-3">Under fair</th><th className="pb-1">Over %</th></tr>
            </thead>
            <tbody>
              {ladder.map((row) => (
                <tr key={`${title}-${row.line}`} className="border-t border-slate-800/70">
                  <td className="py-1.5 pr-3 font-mono font-black text-slate-200">{row.line.toFixed(1)}</td>
                  <td className="py-1.5 pr-3 font-mono font-black text-emerald-300">{row.fair_over.toFixed(2)}</td>
                  <td className="py-1.5 pr-3 font-mono font-black text-rose-300">{row.fair_under.toFixed(2)}</td>
                  <td className="py-1.5 font-mono text-slate-400">{row.over_pct.toFixed(1)}%</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : <div className="mt-2 text-xs text-slate-600">No validated ladder available.</div>}
      <div className="mt-2 text-[10px] uppercase tracking-[0.1em] text-slate-600">
        {String(distribution || "poisson").replaceAll("_", " ")} · compare captured prices on the decision board · zero-stake research
      </div>
    </div>
  );
}

function CountList({ title, rows, tone = "text-slate-200" }: { title: string; rows: { label: string; count: number }[]; tone?: string }) {
  return (
    <div className="rounded-2xl border border-slate-800/80 bg-slate-950/70 p-3">
      <div className="mb-2 text-[10px] font-black uppercase tracking-[0.16em] text-slate-500">{title}</div>
      {rows.length ? (
        <div className="space-y-1.5">
          {rows.map((row) => (
            <div key={`${title}-${row.label}`} className="flex items-center justify-between gap-3 text-xs">
              <span className="truncate text-slate-400">{row.label.replaceAll("_", " ").toLowerCase()}</span>
              <span className={cn("font-mono font-black", tone)}>{row.count}</span>
            </div>
          ))}
        </div>
      ) : (
        <div className="text-xs text-slate-600">No rows</div>
      )}
    </div>
  );
}

function FactorCluster({ row }: { row: CsvRow }) {
  return (
    <div className="grid gap-2 text-[11px] sm:grid-cols-2">
      <div className="rounded-xl border border-slate-800 bg-slate-950/70 p-2">
        <div className="mb-1 font-black uppercase tracking-[0.14em] text-emerald-300">Aces</div>
        <div className="flex flex-wrap gap-1.5">
          <MiniBadge label={`venue ${factorMove(row.venue_ace_factor)}`} tone={factorTone(row.venue_ace_factor)} />
          <MiniBadge label={`live ${factorMove(row.current_env_ace_factor)}`} tone={factorTone(row.current_env_ace_factor)} />
          <MiniBadge label={`net ${factorProductMove(row.venue_ace_factor, row.current_env_ace_factor)}`} tone={factorProductTone(row.venue_ace_factor, row.current_env_ace_factor)} />
        </div>
      </div>
      <div className="rounded-xl border border-slate-800 bg-slate-950/70 p-2">
        <div className="mb-1 font-black uppercase tracking-[0.14em] text-rose-300">Double faults</div>
        <div className="flex flex-wrap gap-1.5">
          <MiniBadge label={`venue ${factorMove(row.venue_df_factor)}`} tone={factorTone(row.venue_df_factor)} />
          <MiniBadge label={`live ${factorMove(row.current_env_df_factor)}`} tone={factorTone(row.current_env_df_factor)} />
          <MiniBadge label={`net ${factorProductMove(row.venue_df_factor, row.current_env_df_factor)}`} tone={factorProductTone(row.venue_df_factor, row.current_env_df_factor)} />
        </div>
      </div>
      <div className="rounded-xl border border-slate-800 bg-slate-950/70 p-2">
        <div className="mb-1 font-black uppercase tracking-[0.14em] text-cyan-300">Breaks</div>
        <div className="flex flex-wrap gap-1.5">
          <MiniBadge label={`live ${factorMove(row.current_env_break_factor)}`} tone={factorTone(row.current_env_break_factor)} />
          <MiniBadge label={`for +${row.same_tournament_breaks_for || "0"}`} tone="border-cyan-500/25 bg-cyan-500/10 text-cyan-200" />
          <MiniBadge label={`against -${row.same_tournament_broken || "0"}`} tone="border-amber-500/25 bg-amber-500/10 text-amber-200" />
        </div>
      </div>
      <div className="rounded-xl border border-slate-800 bg-slate-950/70 p-2">
        <div className="mb-1 font-black uppercase tracking-[0.14em] text-violet-300">Tie-breaks</div>
        <div className="flex flex-wrap gap-1.5">
          <MiniBadge label={`1st venue ${factorMove(row.venue_first_set_tiebreak_factor)}`} tone={factorTone(row.venue_first_set_tiebreak_factor)} />
          <MiniBadge label={`1st live ${factorMove(row.current_env_first_set_tiebreak_factor)}`} tone={factorTone(row.current_env_first_set_tiebreak_factor)} />
          <MiniBadge label={`match venue ${factorMove(row.venue_match_tiebreak_factor)}`} tone={factorTone(row.venue_match_tiebreak_factor)} />
          <MiniBadge label={`match live ${factorMove(row.current_env_match_tiebreak_factor)}`} tone={factorTone(row.current_env_match_tiebreak_factor)} />
        </div>
      </div>
    </div>
  );
}

function ProjectionPlayerCard({ row }: { row: CsvRow }) {
  return (
    <article className="rounded-3xl border border-slate-800/80 bg-[linear-gradient(145deg,rgba(15,23,42,0.92),rgba(2,6,23,0.92))] p-4 shadow-2xl shadow-black/20">
      <div className="mb-4 flex flex-wrap items-start justify-between gap-3">
        <div>
          <div className="flex flex-wrap items-center gap-2">
            <MiniBadge label={row.tour || "-"} tone={row.tour === "WTA" ? "border-fuchsia-500/25 bg-fuchsia-500/10 text-fuchsia-200" : "border-cyan-500/25 bg-cyan-500/10 text-cyan-200"} />
            <span className="text-[11px] font-bold uppercase tracking-[0.14em] text-slate-500">{row.tournament || "Tennis"} {row.round ? `- ${row.round}` : ""}</span>
          </div>
          <h4 className="mt-2 text-xl font-black tracking-tight text-slate-50">{row.player || "-"}</h4>
          <p className="text-sm text-slate-400">vs {row.opponent || "-"}</p>
        </div>
        <div className="flex flex-wrap gap-1.5">
          <MiniBadge label={`ACES ${row.ace_confidence || "LOW"}`} tone={confidenceTone(row.ace_confidence)} />
          <MiniBadge label={`DFS ${row.df_confidence || "LOW"}`} tone={confidenceTone(row.df_confidence)} />
          <MiniBadge label={`BREAKS ${row.break_confidence || "LOW"}`} tone={confidenceTone(row.break_confidence)} />
        </div>
      </div>

      <div className="grid gap-3 sm:grid-cols-2">
        <MetricTile label="Aces projection" value={fmt(row.projected_aces, 1)} sub={`sample ${row.player_surface_matches || "0"}m / ${row.player_surface_svpt_sample || "0"} svpt`} tone="text-emerald-300" />
        <MetricTile label="Double faults" value={fmt(row.projected_dfs, 1)} sub={`same event ${row.same_tournament_matches || "0"}m`} tone="text-rose-300" />
        <MetricTile label="Projected breaks won" value={fmt(row.projected_breaks_for, 1)} sub="player-specific" tone="text-cyan-300" />
        <MetricTile label="Projected times broken" value={fmt(row.projected_broken, 1)} sub="player-specific" tone="text-amber-300" />
      </div>

      <div className="mt-3">
        <BreakFairOddsPanel
          title={`${row.player || "Player"} breaks won`}
          mean={row.projected_breaks_for}
          ladderJson={row.player_break_fair_odds_json}
          distribution={row.player_break_distribution}
          status={row.player_break_model_status}
        />
      </div>

      <div className="mt-4">
          <details className="group rounded-2xl border border-slate-800/80 bg-slate-950/55 p-3">
            <summary className="cursor-pointer list-none text-xs font-black uppercase tracking-[0.14em] text-slate-400 transition group-open:text-emerald-300">
              How this projection was built
            </summary>
            <div className="mt-3 space-y-3">
              <div className="grid gap-2 text-xs text-slate-400 sm:grid-cols-2">
                <div className="rounded-xl border border-slate-800 bg-slate-950/70 p-2">
                  <div className="font-mono text-emerald-300">expected games {fmt(row.expected_match_games, 1)}</div>
                  <div className="mt-1 text-[11px] uppercase tracking-[0.1em] text-slate-600">{row.expected_match_games_source || "fallback"}{row.expected_match_games_confidence ? ` / ${row.expected_match_games_confidence}` : ""}</div>
                </div>
                <div className="rounded-xl border border-slate-800 bg-slate-950/70 p-2">
                  <div className="font-mono text-slate-300">current event {row.current_env_matches || "0"} matches</div>
                  <div className="mt-1 text-[11px] uppercase tracking-[0.1em] text-slate-600">live weight {fmt(row.current_env_weight, 2)}</div>
                </div>
              </div>
              <FactorCluster row={row} />
              <NoteBadges value={[row.notes, row.break_notes, row.tiebreak_notes].filter(Boolean).join("|")} />
            </div>
          </details>
      </div>
    </article>
  );
}

function ProjectionTable({ rows, sortKey }: { rows: CsvRow[]; sortKey: ProjectionSortKey }) {
  if (!rows.length) return <EmptyState message="No aces/DF projection board found. Run python scripts/run-tennis-props-daily.py after OnCourt extract." />;
  const groupedRows = groupRowsByDateAndMatch(rows, sortKey);
  return (
    <div className="space-y-4">
      <ProjectionSortControls active={sortKey} />
      {groupedRows.map((group) => (
        <section key={group.date} className="space-y-3">
          <div className="flex flex-wrap items-center justify-between gap-2 rounded-2xl border border-slate-800 bg-slate-950/70 px-4 py-3">
            <span className="text-xs font-black uppercase tracking-[0.18em] text-emerald-300">{dateLabel(group.date)}</span>
            <span className="font-mono text-[11px] uppercase tracking-[0.12em] text-slate-500">{group.matches.length} matches / {group.matches.reduce((sum, match) => sum + match.rows.length, 0)} player rows</span>
          </div>
          {group.matches.map((match) => {
            const first = match.rows[0] ?? {};
            const aceLeader = match.rows.reduce((best, row) => n(row.projected_aces) > n(best.projected_aces) ? row : best, first);
            const dfLeader = match.rows.reduce((best, row) => n(row.projected_dfs) > n(best.projected_dfs) ? row : best, first);
            const matchTbFair = Math.min(...match.rows.map((row) => n(row.match_tiebreak_fair_yes)).filter((value) => value > 0));
            const firstSetFair = Math.min(...match.rows.map((row) => n(row.first_set_tiebreak_fair_yes)).filter((value) => value > 0));
            return (
              <details key={`${group.date}-${match.key}`} open className="group rounded-[2rem] border border-slate-800/80 bg-slate-950/55 shadow-2xl shadow-black/20">
                <summary className="cursor-pointer list-none p-4 sm:p-5">
                  <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
                    <div>
                      <div className="mb-2 flex flex-wrap items-center gap-2">
                        <MiniBadge label={first.tour || "-"} tone={first.tour === "WTA" ? "border-fuchsia-500/25 bg-fuchsia-500/10 text-fuchsia-200" : "border-cyan-500/25 bg-cyan-500/10 text-cyan-200"} />
                        <span className="text-[11px] font-bold uppercase tracking-[0.16em] text-slate-500">{first.tournament || "Tennis"} {first.round ? `- ${first.round}` : ""}</span>
                      </div>
                      <h3 className="text-2xl font-black tracking-tight text-slate-50">{fixtureName(match.rows)}</h3>
                      <p className="mt-1 text-sm text-slate-500">Click to collapse. Aces, double faults, breaks and tie-break pricing stay grouped by match.</p>
                    </div>
                    <div className="grid grid-cols-2 gap-2 sm:grid-cols-5 lg:min-w-[680px]">
                      <MetricTile label="Any-set TB fair odds" value={Number.isFinite(matchTbFair) ? matchTbFair.toFixed(2) : "-"} sub={`${fmt(first.match_tiebreak_pct, 1)}% · hist ${pctText(first.venue_match_tiebreak_actual_pct)} · live ${pctText(first.current_env_match_tiebreak_actual_pct)}`} tone="text-fuchsia-200" />
                      <MetricTile label="1st-set TB fair odds" value={Number.isFinite(firstSetFair) ? firstSetFair.toFixed(2) : "-"} sub={`${fmt(first.first_set_tiebreak_pct, 1)}% · hist ${pctText(first.venue_first_set_tiebreak_actual_pct)} · live ${pctText(first.current_env_first_set_tiebreak_actual_pct)}`} tone="text-violet-200" />
                      <MetricTile label="Highest aces" value={fmt(aceLeader.projected_aces, 1)} sub={aceLeader.player || "-"} tone="text-emerald-300" />
                      <MetricTile label="Highest DFs" value={fmt(dfLeader.projected_dfs, 1)} sub={dfLeader.player || "-"} tone="text-rose-300" />
                      <MetricTile label="Total match breaks" value={fmt(first.projected_total_breaks, 1)} sub="shared match estimate" tone="text-cyan-300" />
                    </div>
                  </div>
                </summary>
                <div className="border-t border-slate-800/80 px-4 pt-4 sm:px-5 sm:pt-5">
                  <BreakFairOddsPanel
                    title="Match total service breaks"
                    mean={first.projected_total_breaks}
                    ladderJson={first.match_break_fair_odds_json}
                    distribution={first.match_break_distribution}
                    status={first.match_break_model_status}
                  />
                </div>
                <div className="grid gap-4 border-t border-slate-800/80 p-4 sm:p-5 xl:grid-cols-2">
                  {match.rows.map((row, index) => (
                    <ProjectionPlayerCard key={`${group.date}-${row.tour}-${row.player}-${row.opponent}-${index}`} row={row} />
                  ))}
                </div>
                <MatchRoundHistory rows={match.rows} />
              </details>
            );
          })}
        </section>
      ))}
    </div>
  );
}

function resultTone(value: string | undefined): string {
  if (value === "win") return "border-emerald-500/25 bg-emerald-500/10 text-emerald-300";
  if (value === "loss") return "border-rose-500/25 bg-rose-500/10 text-rose-300";
  if (value === "push" || value === "void") return "border-slate-600/70 bg-slate-800/60 text-slate-400";
  return "border-amber-500/25 bg-amber-500/10 text-amber-300";
}

function ShadowEvidenceTable({ rows }: { rows: CsvRow[] }) {
  if (!rows.length) {
    return <EmptyState message="No shadow signals yet. Add Bet365 aces/DF lines, run the comparison, then run python scripts/tennis-props-shadow-tracker.py." />;
  }
  const groupedRows = groupRowsByDate(rows.slice(0, 80));
  return (
    <div className="overflow-x-auto">
      <table className="min-w-full text-sm">
        <thead>
          <tr className="border-b border-slate-800 text-left text-[11px] uppercase tracking-[0.16em] text-slate-500">
            <th className="px-3 py-3 font-semibold">Status</th>
            <th className="px-3 py-3 font-semibold">Player</th>
            <th className="px-3 py-3 font-semibold">Market</th>
            <th className="px-3 py-3 font-semibold">Line</th>
            <th className="px-3 py-3 font-semibold">Side</th>
            <th className="px-3 py-3 font-semibold">Odds</th>
            <th className="px-3 py-3 font-semibold">Close</th>
            <th className="px-3 py-3 font-semibold">CLV</th>
            <th className="px-3 py-3 font-semibold">Value</th>
            <th className="px-3 py-3 font-semibold">Actual</th>
            <th className="px-3 py-3 font-semibold">PnL</th>
            <th className="px-3 py-3 font-semibold">Conf</th>
          </tr>
        </thead>
        <tbody>
          {groupedRows.map((group) => (
            <Fragment key={group.date}>
              <tr className="border-y border-slate-800 bg-slate-950/80">
                <td colSpan={12} className="px-3 py-3">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <span className="text-xs font-black uppercase tracking-[0.18em] text-amber-300">{dateLabel(group.date)}</span>
                    <span className="font-mono text-[11px] uppercase tracking-[0.12em] text-slate-500">{group.rows.length} shadow rows</span>
                  </div>
                </td>
              </tr>
              {group.rows.map((row, index) => (
                <tr key={`${row.signal_id}-${index}`} className="border-b border-slate-900/80 text-slate-300">
                  <td className="px-3 py-3"><MiniBadge label={row.result || row.settlement_status || "pending"} tone={resultTone(row.result || row.settlement_status)} /></td>
                  <td className="px-3 py-3">
                    <div className="font-semibold text-slate-100">{row.player}</div>
                    <div className="text-xs text-slate-500">vs {row.opponent}</div>
                  </td>
                  <td className="px-3 py-3 text-slate-300">{row.market}</td>
                  <td className="px-3 py-3 font-mono text-slate-100">{fmt(row.line, 1)}</td>
                  <td className="px-3 py-3"><MiniBadge label={row.side || "-"} tone="border-cyan-500/25 bg-cyan-500/10 text-cyan-200" /></td>
                  <td className="px-3 py-3 font-mono text-slate-300">{fmt(row.selected_odds, 2)}</td>
                  <td className="px-3 py-3 font-mono text-slate-300">{row.closing_odds ? fmt(row.closing_odds, 2) : "-"}</td>
                  <td className={cn("px-3 py-3 font-mono", n(row.clv_pct) > 0 ? "text-emerald-300" : n(row.clv_pct) < 0 ? "text-rose-300" : "text-slate-500")}>{row.clv_pct ? `${n(row.clv_pct) >= 0 ? "+" : ""}${fmt(row.clv_pct, 1)}%` : "-"}</td>
                  <td className="px-3 py-3 font-mono text-emerald-300">{fmt(row.value_pct, 1)}%</td>
                  <td className="px-3 py-3 font-mono text-slate-300">{row.actual || "-"}</td>
                  <td className={cn("px-3 py-3 font-mono", n(row.pnl) > 0 ? "text-emerald-300" : n(row.pnl) < 0 ? "text-rose-300" : "text-slate-500")}>{row.pnl ? `${n(row.pnl).toFixed(2)}u` : "-"}</td>
                  <td className="px-3 py-3"><MiniBadge label={row.confidence || "LOW"} tone={confidenceTone(row.confidence)} /></td>
                </tr>
              ))}
            </Fragment>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function comparisonMatchKey(row: CsvRow): string {
  const players = [row.player || "", row.opponent || ""].sort((a, b) => a.localeCompare(b)).join(" v ");
  return [row.date || "", row.tour || "", row.tournament || "", players].join("|");
}

function groupComparisonByMatch(rows: CsvRow[]): { date: string; matches: { key: string; rows: CsvRow[] }[] }[] {
  return groupRowsByDate(rows).map((dateGroup) => {
    const matchMap = new Map<string, CsvRow[]>();
    for (const row of dateGroup.rows) {
      const key = comparisonMatchKey(row);
      matchMap.set(key, [...(matchMap.get(key) ?? []), row]);
    }
    const matches = [...matchMap.entries()].map(([key, matchRows]) => ({
      key,
      rows: [...matchRows].sort((a, b) => maxValue(b) - maxValue(a) || (a.market || "").localeCompare(b.market || "")),
    }));
    matches.sort((a, b) => Math.max(...b.rows.map(maxValue)) - Math.max(...a.rows.map(maxValue)) || fixtureName(a.rows).localeCompare(fixtureName(b.rows)));
    return { date: dateGroup.date, matches };
  });
}

function ComparisonLineCard({ row }: { row: CsvRow }) {
  const quality = effectiveLineQuality(row);
  const trustedLine = isTrustedComparisonRow(row);
  const overOnlyMode = row.decision_mode === "over_only_raw_ev";
  const bestSide = overOnlyMode ? "OVER" : n(row.value_under_pct) > n(row.value_over_pct) ? "UNDER" : "OVER";
  const bestValue = trustedLine ? (overOnlyMode ? n(row.value_over_pct) : Math.max(n(row.value_over_pct), n(row.value_under_pct))) : 0;
  const bestNovigEdge = bestSide === "UNDER" ? n(row.edge_under_novig_pct) : n(row.edge_over_novig_pct);
  const blockedReason = row.blocked_reason || rowRejectionReason(row);
  const lineStatus = row.main_line === "true" ? "main line" : row.best_available_line === "true" ? "best available" : quality;
  const lineTone = row.main_line === "true"
    ? "border-emerald-500/25 bg-emerald-500/10 text-emerald-300"
    : row.best_available_line === "true"
      ? "border-cyan-500/25 bg-cyan-500/10 text-cyan-200"
      : quality === "complete"
        ? "border-cyan-500/25 bg-cyan-500/10 text-cyan-200"
        : "border-amber-500/25 bg-amber-500/10 text-amber-300";
  return (
    <div className="rounded-2xl border border-slate-800/80 bg-slate-950/70 p-3">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <div className="flex flex-wrap items-center gap-2">
            <MiniBadge label={row.bettable === "true" ? "BET NOW" : row.recommended_side || "watch"} tone={row.bettable === "true" ? "border-emerald-400/35 bg-emerald-500/15 text-emerald-200" : recTone(row.recommended_side)} />
            <MiniBadge label={row.matched_board === "yes" ? "matched" : "unmatched"} tone={row.matched_board === "yes" ? "border-emerald-500/25 bg-emerald-500/10 text-emerald-300" : "border-rose-500/25 bg-rose-500/10 text-rose-300"} />
            <MiniBadge label={lineStatus} tone={lineTone} />
            {row.price_pair_status ? <MiniBadge label={row.price_pair_status.replaceAll("_", " ")} tone="border-slate-700/70 bg-slate-800/60 text-slate-300" /> : null}
            <MiniBadge label={row.confidence || "LOW"} tone={confidenceTone(row.confidence)} />
            {!row.recommended_side && blockedReason ? <MiniBadge label={blockedReason.replaceAll("_", " ")} tone="border-amber-500/25 bg-amber-500/10 text-amber-300" /> : null}
          </div>
          <div className="mt-2 font-semibold text-slate-100">{row.player || "-"} - {marketLabel(row)} {fmt(row.line, 1)}</div>
          <div className="text-xs text-slate-500">
            projection {fmt(row.projection_mean, 1)} - {row.distribution || "model"}
            {row.totals_alpha ? ` (alpha ${fmt(row.totals_alpha, 3)})` : ""}
            {row.line_rank ? ` - rank ${row.line_rank}/${row.complete_line_count || row.group_line_count}` : ""}
          </div>
        </div>
        <div className="text-right">
          <div className="text-[10px] font-black uppercase tracking-[0.14em] text-slate-500">{trustedLine ? (overOnlyMode ? "raw Over EV" : "best value") : "audit only"}</div>
          <div className={cn("font-mono text-2xl font-black", trustedLine && bestValue > 0 ? "text-emerald-300" : "text-slate-500")}>
            {trustedLine ? `${bestSide} ${fmt(bestValue, 1)}%` : quality.replaceAll("_", " ")}
          </div>
          {trustedLine ? <div className="mt-1 font-mono text-[11px] text-slate-500">{overOnlyMode ? "under price unavailable" : `no-vig edge ${bestNovigEdge > 0 ? "+" : ""}${fmt(bestNovigEdge, 1)}%`}</div> : null}
        </div>
      </div>
      <div className="mt-3 grid grid-cols-2 gap-2 sm:grid-cols-4">
        <MetricTile label="Over price" value={fmt(row.over_odds, 2)} sub={`fair ${fmt(row.fair_over_odds, 2)}`} tone="text-slate-100" />
        <MetricTile label="Under price" value={fmt(row.under_odds, 2)} sub={`fair ${fmt(row.fair_under_odds, 2)}`} tone="text-slate-100" />
        <MetricTile label="Over value" value={trustedLine ? `${fmt(row.value_over_pct, 1)}%` : "audit"} sub={trustedLine ? (overOnlyMode ? "raw EV at offered price" : `no-vig ${n(row.edge_over_novig_pct) > 0 ? "+" : ""}${fmt(row.edge_over_novig_pct, 1)}%`) : undefined} tone={trustedLine && n(row.value_over_pct) > 0 ? "text-emerald-300" : "text-slate-500"} />
        <MetricTile label="Under value" value={overOnlyMode ? "not supplied" : trustedLine ? `${fmt(row.value_under_pct, 1)}%` : "audit"} sub={!overOnlyMode && trustedLine ? `no-vig ${n(row.edge_under_novig_pct) > 0 ? "+" : ""}${fmt(row.edge_under_novig_pct, 1)}%` : undefined} tone={trustedLine && !overOnlyMode && n(row.value_under_pct) > 0 ? "text-emerald-300" : "text-slate-500"} />
      </div>
      {row.line_quality_reason || row.raw_market_name ? (
        <div className="mt-2 rounded-xl border border-slate-800 bg-slate-950/70 px-3 py-2 text-[11px] leading-relaxed text-slate-500">
          {row.line_quality_reason ? <div><span className="font-bold uppercase tracking-[0.12em] text-slate-400">Line shape:</span> {row.line_quality_reason.replaceAll("_", " ").toLowerCase()}</div> : null}
          {row.raw_market_name ? <div><span className="font-bold uppercase tracking-[0.12em] text-slate-400">Raw market:</span> {row.raw_market_name}</div> : null}
        </div>
      ) : null}
      {row.model_market_gap_pp ? <div className="mt-2 text-[11px] text-slate-500">Model-market gap: {fmt(row.model_market_gap_pp, 1)}pp. Rows above the guard are blocked, even if raw EV looks large.</div> : null}
      {n(row.fair_p_push) > 0 ? <div className="mt-2 text-[11px] text-amber-300/80">Integer-line push mass: {(n(row.fair_p_push) * 100).toFixed(1)}%</div> : null}
    </div>
  );
}

function ComparisonTable({ rows, hasLinesFile }: { rows: CsvRow[]; hasLinesFile: boolean }) {
  if (!rows.length) {
    return (
      <EmptyState
        message={
          hasLinesFile
            ? "No matched Bet365 player-prop rows for the current board. Betting decision: NO BET. Check the scraper/audit CSV before trusting any raw line."
            : "No Bet365 aces/DF lines available yet. The API audit can run daily, but a manual CSV drop may be needed if the provider does not expose tennis player props."
        }
      />
    );
  }
  const groupedRows = groupComparisonByMatch(rows);
  return (
    <div className="space-y-4">
      {groupedRows.map((group) => (
        <section key={group.date} className="space-y-3">
          <div className="flex flex-wrap items-center justify-between gap-2 rounded-2xl border border-slate-800 bg-slate-950/70 px-4 py-3">
            <span className="text-xs font-black uppercase tracking-[0.18em] text-cyan-300">{dateLabel(group.date)}</span>
            <span className="font-mono text-[11px] uppercase tracking-[0.12em] text-slate-500">{group.matches.length} matches / {group.matches.reduce((sum, match) => sum + match.rows.length, 0)} line rows</span>
          </div>
          {group.matches.map((match) => {
            const first = match.rows[0] ?? {};
            const recommended = match.rows.filter((row) => row.recommended_side).length;
            const matched = match.rows.filter((row) => row.matched_board === "yes").length;
            const maxEdge = Math.max(...match.rows.map(maxValue));
            return (
              <details key={`${group.date}-${match.key}`} open={recommended > 0 || maxEdge > 0} className="group rounded-[2rem] border border-slate-800/80 bg-slate-950/55">
                <summary className="cursor-pointer list-none p-4 sm:p-5">
                  <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
                    <div>
                      <div className="mb-2 flex flex-wrap items-center gap-2">
                        <MiniBadge label={first.tour || "-"} tone={first.tour === "WTA" ? "border-fuchsia-500/25 bg-fuchsia-500/10 text-fuchsia-200" : "border-cyan-500/25 bg-cyan-500/10 text-cyan-200"} />
                        <span className="text-[11px] font-bold uppercase tracking-[0.16em] text-slate-500">{first.tournament || "Tennis"}</span>
                      </div>
                      <h3 className="text-xl font-black tracking-tight text-slate-50">{fixtureName(match.rows)}</h3>
                    </div>
                    <div className="flex flex-wrap gap-2">
                      <MiniBadge label={`${recommended} rec`} tone={recommended ? "border-emerald-500/25 bg-emerald-500/10 text-emerald-300" : "border-slate-700/70 bg-slate-800/60 text-slate-400"} />
                      <MiniBadge label={`${matched}/${match.rows.length} matched`} tone={matched === match.rows.length ? "border-emerald-500/25 bg-emerald-500/10 text-emerald-300" : "border-amber-500/25 bg-amber-500/10 text-amber-300"} />
                      <MiniBadge label={`top ${fmt(maxEdge, 1)}%`} tone={maxEdge > 0 ? "border-cyan-500/25 bg-cyan-500/10 text-cyan-200" : "border-slate-700/70 bg-slate-800/60 text-slate-400"} />
                    </div>
                  </div>
                </summary>
                <div className="grid gap-3 border-t border-slate-800/80 p-4 sm:p-5 lg:grid-cols-2">
                  {match.rows.map((row, index) => <ComparisonLineCard key={`${match.key}-${row.player}-${row.market}-${row.line}-${index}`} row={row} />)}
                </div>
              </details>
            );
          })}
        </section>
      ))}
    </div>
  );
}


function rowBestSide(row: CsvRow): string {
  if (row.decision_mode === "over_only_raw_ev") return "OVER";
  return n(row.value_under_pct) > n(row.value_over_pct) ? "UNDER" : "OVER";
}

function rowBestValue(row: CsvRow): number {
  if (row.decision_mode === "over_only_raw_ev") return n(row.value_over_pct);
  return Math.max(n(row.value_over_pct), n(row.value_under_pct));
}

function blockReasonLabel(value: string | undefined): string {
  const first = String(value || "").split("|").find(Boolean) || "gate blocked";
  if (first === "TOTALS_STAGE0_BLOCKED") return "totals holdout gate blocked";
  return first.replaceAll("_", " ").toLowerCase();
}

function rowRejectionReason(row: CsvRow): string {
  if (row.block_reasons) return blockReasonLabel(row.block_reasons);
  if (row.blocked_reason) return blockReasonLabel(row.blocked_reason);
  const confidence = (row.confidence || "LOW").toUpperCase();
  if (confidence !== "HIGH") return `confidence ${confidence}`;
  const quality = effectiveLineQuality(row);
  if (quality !== "complete") return `line is ${quality}`;
  if (row.notes) return "notes flag present";
  return "gate did not pass";
}

function marketLabel(row: CsvRow): string {
  if (row.market === "match_aces") return "Match aces";
  if (row.market === "match_double_faults") return "Match double faults";
  if (row.market === "match_breaks") return "Match service breaks";
  if (row.market === "player_breaks") return "Player service breaks";
  return row.market?.replaceAll("_", " ") || "market";
}

function TotalsStage0Panel({ gate, stamp }: { gate: JsonRecord; stamp: string }) {
  const marketRows = [
    { key: "match_aces", label: "Match aces" },
    { key: "match_double_faults", label: "Match double faults" },
  ];
  const holdoutYear = String(gate.holdout_year ?? "-");
  return (
    <SectionCard
      title="Totals Model Gate"
      subtitle={`Historical count validation before any Bet365 shadow signal. Train seasons stay before the untouched ${holdoutYear} holdout.`}
    >
      <div className="grid gap-3 lg:grid-cols-2">
        {marketRows.map(({ key, label }) => {
          const market = gateMarket(gate, key);
          const marketPassed = market.passed === true;
          return (
            <article key={key} className="rounded-2xl border border-slate-800/80 bg-slate-950/70 p-4">
              <div className="flex items-center justify-between gap-3">
                <div>
                  <div className="text-[10px] font-black uppercase tracking-[0.16em] text-slate-500">Stage 0</div>
                  <h3 className="mt-1 text-lg font-black text-slate-100">{label}</h3>
                </div>
                <MiniBadge
                  label={marketPassed ? "HOLDOUT PASS" : "BLOCKED"}
                  tone={marketPassed ? "border-emerald-500/30 bg-emerald-500/10 text-emerald-300" : "border-rose-500/30 bg-rose-500/10 text-rose-300"}
                />
              </div>
              <div className="mt-4 grid gap-2 sm:grid-cols-2">
                {(["ATP", "WTA"] as const).map((tour) => {
                  const row = gateTour(gate, key, tour);
                  const passed = row.passed === true;
                  return (
                    <div key={tour} className="rounded-xl border border-slate-800 bg-slate-900/55 p-3">
                      <div className="flex items-center justify-between gap-2">
                        <span className="font-black text-slate-200">{tour}</span>
                        <span className={cn("text-[10px] font-black uppercase tracking-[0.12em]", passed ? "text-emerald-300" : "text-rose-300")}>{passed ? "pass" : "blocked"}</span>
                      </div>
                      <div className="mt-2 font-mono text-xs text-slate-400">
                        n {gateNumber(row, "total_matches").toFixed(0)} · alpha {gateNumber(row, "model_alpha").toFixed(3)}
                      </div>
                      <div className="mt-1 text-[11px] text-slate-500">
                        Holdout MAE {gateNumber(row, "model_mae").toFixed(2)} vs naive {gateNumber(row, "naive_mae").toFixed(2)}
                      </div>
                    </div>
                  );
                })}
              </div>
            </article>
          );
        })}
      </div>
      <p className="mt-3 text-xs leading-relaxed text-slate-500">
        Pass means the historical total-count model beat its naive baseline. It permits shadow tracking only; sell/live status still requires settled Bet365 ROI and CLV evidence. Gate file updated {stamp}.
      </p>
    </SectionCard>
  );
}

function TabLink({ active, href, label, detail }: { active: boolean; href: string; label: string; detail: string }) {
  return (
    <Link
      href={href}
      className={cn(
        "rounded-2xl border px-4 py-3 transition",
        active
          ? "border-emerald-400/40 bg-emerald-500/15 text-emerald-100 shadow-[0_0_24px_rgba(16,185,129,0.12)]"
          : "border-slate-800 bg-slate-950/60 text-slate-400 hover:border-slate-600 hover:text-slate-200",
      )}
    >
      <span className="block text-sm font-black uppercase tracking-[0.14em]">{label}</span>
      <span className="mt-1 block text-xs text-slate-500">{detail}</span>
    </Link>
  );
}

function RecommendationPanel({
  actionableRows,
  watchRows,
  matchedCount,
  totalCount,
}: {
  actionableRows: CsvRow[];
  watchRows: CsvRow[];
  matchedCount: number;
  totalCount: number;
}) {
  if (actionableRows.length) {
    return (
      <SectionCard
        title="BET NOW: Bet365 Match-Total Props"
        subtitle="Two-way prices require raw plus no-vig edge. Bet365 Over-only prices use the central ladder quote and a stricter raw-EV gate; an under price is not required to evaluate the offered Over."
      >
        <div className="grid gap-3 lg:grid-cols-2">
          {actionableRows.slice(0, 8).map((row, index) => <ComparisonLineCard key={`${row.player}-${row.market}-${row.line}-${index}`} row={row} />)}
        </div>
      </SectionCard>
    );
  }

  return (
    <SectionCard
      title="Betting Decision: NO BET"
      subtitle="This is the actual decision layer, above the audit board. If this says no bet, the rows below are research only."
    >
      <div className="rounded-[2rem] border border-amber-500/25 bg-[radial-gradient(circle_at_top_left,rgba(245,158,11,0.16),transparent_34%),rgba(15,23,42,0.84)] p-5">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
          <div>
            <div className="text-[11px] font-black uppercase tracking-[0.18em] text-amber-300">Official decision</div>
            <h3 className="mt-2 text-3xl font-black tracking-tight text-slate-50">NO BET SUGGESTED</h3>
            <p className="mt-2 max-w-3xl text-sm leading-relaxed text-slate-300">
              Bet365 is being compared now: {matchedCount} of {totalCount} line rows matched the board. None pass the full gate, so anything below is watch/audit only, not a bet.
            </p>
          </div>
          <div className="grid grid-cols-2 gap-2 sm:grid-cols-4 lg:min-w-[520px]">
            <MetricTile label="Recommended" value="0" sub="official bets" tone="text-slate-400" />
            <MetricTile label="Matched lines" value={`${matchedCount}`} sub={`${totalCount} captured`} tone="text-cyan-300" />
            <MetricTile label="Required conf" value="MED+" sub="800 svpt sample" tone="text-emerald-300" />
            <MetricTile label="Line type" value="priced" sub="two-way or central Over" tone="text-amber-300" />
          </div>
        </div>
        <div className="mt-4 flex flex-wrap gap-2">
          <MiniBadge label="needs MED+ confidence" tone="border-emerald-500/25 bg-emerald-500/10 text-emerald-300" />
          <MiniBadge label="main two-way or central Over" tone="border-cyan-500/25 bg-cyan-500/10 text-cyan-200" />
          <MiniBadge label="no board warnings" tone="border-slate-700/70 bg-slate-800/60 text-slate-300" />
          <MiniBadge label="two-way: raw + no-vig | Over-only: raw EV 15%+" tone="border-amber-500/25 bg-amber-500/10 text-amber-300" />
        </div>
      </div>
      {watchRows.length ? (
        <div className="mt-4">
          <div className="mb-2 text-xs font-black uppercase tracking-[0.16em] text-slate-500">Rejected audit examples, not bets</div>
          <div className="grid gap-3 lg:grid-cols-3">
            {watchRows.slice(0, 3).map((row, index) => (
              <div key={`${row.player}-${row.market}-${row.line}-${index}`} className="rounded-2xl border border-slate-800/80 bg-slate-950/70 p-3">
                <div className="flex flex-wrap items-center gap-2">
                  <MiniBadge label="rejected" tone="border-rose-500/25 bg-rose-500/10 text-rose-300" />
                  <MiniBadge label={row.confidence || "LOW"} tone={confidenceTone(row.confidence)} />
                </div>
                <div className="mt-2 font-semibold text-slate-100">{row.player} {rowBestSide(row)} {row.line} {marketLabel(row)}</div>
                <div className="mt-1 text-xs text-slate-500">vs {row.opponent} - projection {fmt(row.projection_mean, 1)}</div>
                <div className="mt-3 text-xs font-black uppercase tracking-[0.14em] text-rose-300">Blocked: {rowRejectionReason(row)}</div>
                <div className="mt-1 text-[11px] text-slate-500">Raw model edge {rowBestValue(row).toFixed(1)}%, kept audit-only.</div>
              </div>
            ))}
          </div>
        </div>
      ) : null}
    </SectionCard>
  );
}

function BreakRecommendationPanel({ rows }: { rows: CsvRow[] }) {
  const matched = rows.filter((row) => row.matched_board === "yes");
  const watchlist = matched
    .filter((row) => row.trackable_shadow === "true" && ["OVER", "UNDER"].includes((row.shadow_side || "").toUpperCase()))
    .sort((a, b) => rowBestValue(b) - rowBestValue(a));
  const blocked = matched
    .filter((row) => row.trackable_shadow !== "true")
    .sort((a, b) => rowBestValue(b) - rowBestValue(a));

  return (
    <SectionCard
      title="Service Breaks v1: Price-Backed Watchlist"
      subtitle="Player and match break totals are priced only when a real Bet365 or BetsBK line matches the registered projection. These remain zero-stake research until prospective ROI and CLV gates pass."
    >
      <div className="grid gap-2 sm:grid-cols-4">
        <MetricTile label="Captured" value={String(rows.length)} sub="break price rows" tone={rows.length ? "text-cyan-300" : "text-rose-300"} />
        <MetricTile label="Matched" value={String(matched.length)} sub="joined to projections" tone={matched.length ? "text-emerald-300" : "text-slate-400"} />
        <MetricTile label="Watchlist" value={String(watchlist.length)} sub="8%+ edge, MED+" tone={watchlist.length ? "text-amber-300" : "text-slate-400"} />
        <MetricTile label="Official stake" value="0.0u" sub="evidence gate not passed" tone="text-slate-400" />
      </div>
      {watchlist.length ? (
        <div className="mt-4 grid gap-3 lg:grid-cols-2">
          {watchlist.slice(0, 12).map((row, index) => <ComparisonLineCard key={`break-watch-${row.event_id}-${row.player}-${row.line}-${index}`} row={row} />)}
        </div>
      ) : rows.length === 0 ? (
        <div className="mt-4 rounded-2xl border border-rose-500/25 bg-rose-500/10 p-4 text-sm leading-6 text-rose-100">
          <strong className="block uppercase tracking-[0.12em] text-rose-200">No live service-break price captured</strong>
          The projection and fair-odds ladders exist, but no recommendation can be calculated without a bookmaker line. This is a feed-coverage result, not a no-edge verdict.
        </div>
      ) : (
        <div className="mt-4">
          <div className="mb-2 text-xs font-black uppercase tracking-[0.14em] text-slate-500">Best blocked break rows</div>
          <div className="grid gap-3 lg:grid-cols-3">
            {blocked.slice(0, 6).map((row, index) => <ComparisonLineCard key={`break-blocked-${row.event_id}-${row.player}-${row.line}-${index}`} row={row} />)}
          </div>
        </div>
      )}
    </SectionCard>
  );
}

function FeedDiagnosticsPanel({
  lineRows,
  auditRows,
  decisionRows,
  matchedRows,
}: {
  lineRows: CsvRow[];
  auditRows: CsvRow[];
  decisionRows: CsvRow[];
  matchedRows: CsvRow[];
}) {
  const bestAvailable = matchedRows.filter((row) => row.best_available_line === "true").length;
  const mainLines = matchedRows.filter((row) => row.main_line === "true").length;
  const twoWayRows = matchedRows.filter((row) => row.price_pair_status === "two_way").length;
  const rawMarketRows = auditRows.filter((row) => row.market_name);
  const unsupportedLadder = twoWayRows > 0 && mainLines === 0;
  return (
    <SectionCard
      title="Why No Bet? Feed Diagnostics"
      subtitle="This is the feed-quality layer: raw Bet365 inventory, parsed line shapes, and blocker counts before any model opinion is trusted."
    >
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
        <MetricTile label="Raw lines" value={String(lineRows.length)} sub="rows from Bet365 parser" tone="text-cyan-300" />
        <MetricTile label="Decision rows" value={String(decisionRows.length)} sub={`${matchedRows.length} matched board`} tone="text-slate-100" />
        <MetricTile label="Two-way rows" value={String(twoWayRows)} sub="over + under present" tone={twoWayRows ? "text-emerald-300" : "text-amber-300"} />
        <MetricTile label="Best available" value={String(bestAvailable)} sub="closest ladder row per market" tone="text-cyan-300" />
        <MetricTile label="Usable main" value={String(mainLines)} sub="strict gate candidate" tone={mainLines ? "text-emerald-300" : "text-amber-300"} />
      </div>
      {unsupportedLadder ? (
        <div className="mt-3 rounded-2xl border border-amber-500/25 bg-amber-500/10 px-4 py-3 text-xs leading-relaxed text-amber-100">
          <span className="font-black uppercase tracking-[0.12em] text-amber-200">Unsupported alternate ladder:</span>{" "}
          Bet365 supplied two-way thresholds, but none resembles a balanced main line. Deep alternates remain blocked; the system will not manufacture a recommendation from them.
        </div>
      ) : null}
      <div className="mt-3 grid gap-3 lg:grid-cols-4">
        <CountList title="Blockers" rows={topBlockReasons(matchedRows)} tone="text-amber-300" />
        <CountList title="Line quality" rows={topCounts(matchedRows, "line_quality")} tone="text-cyan-300" />
        <CountList title="Price pair" rows={topCounts(matchedRows, "price_pair_status")} tone="text-emerald-300" />
        <CountList title="Parsed market" rows={topCounts(lineRows, "market")} tone="text-slate-200" />
      </div>
      <details className="group mt-3 rounded-2xl border border-slate-800/80 bg-slate-950/60">
        <summary className="cursor-pointer list-none px-4 py-3 text-xs font-black uppercase tracking-[0.16em] text-slate-400 transition group-open:text-cyan-200">
          Raw Bet365 market inventory ({rawMarketRows.length} market rows)
        </summary>
        <div className="border-t border-slate-800/80 p-4">
          {rawMarketRows.length ? (
            <div className="overflow-x-auto">
              <table className="min-w-[880px] text-left text-xs">
                <thead className="uppercase tracking-[0.12em] text-slate-600">
                  <tr>
                    <th className="px-3 py-2 font-semibold">Book</th>
                    <th className="px-3 py-2 font-semibold">Event</th>
                    <th className="px-3 py-2 font-semibold">Market</th>
                    <th className="px-3 py-2 font-semibold">Outcomes</th>
                    <th className="px-3 py-2 font-semibold">Sample labels</th>
                  </tr>
                </thead>
                <tbody>
                  {rawMarketRows.slice(0, 18).map((row, index) => (
                    <tr key={`${row.event_id}-${row.market_name}-${index}`} className="border-t border-slate-900">
                      <td className="px-3 py-2 text-slate-300">{row.bookmaker || "-"}</td>
                      <td className="px-3 py-2 text-slate-400">{row.home || "-"} vs {row.away || "-"}</td>
                      <td className="px-3 py-2 text-slate-200">{row.market_name || "-"}</td>
                      <td className="px-3 py-2 font-mono text-cyan-300">{row.odds_count || "-"}</td>
                      <td className="max-w-[420px] truncate px-3 py-2 text-slate-500">{row.sample_labels || "-"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <EmptyState message="No raw market-audit CSV found yet. Run the Bet365 scraper once to populate bet365-tennis-market-audit-YYYY-MM-DD.csv." />
          )}
        </div>
      </details>
    </SectionCard>
  );
}

function latestSummaryRows(rows: CsvRow[]): CsvRow[] {
  const out: CsvRow[] = [];
  for (const periodType of ["day", "week", "month"]) {
    const subset = rows
      .filter((row) => row.period_type === periodType)
      .sort((a, b) => (b.period || "").localeCompare(a.period || ""));
    if (subset[0]) out.push(subset[0]);
  }
  return out;
}

function ModelTrackerPanel({ rows, stamp }: { rows: CsvRow[]; stamp: string }) {
  const latest = latestSummaryRows(rows);
  return (
    <SectionCard
      title="Model Change Tracker"
      subtitle={`Weekly/monthly diagnostics generated from every comparison CSV. Latest report: ${stamp}.`}
    >
      {latest.length ? (
        <div className="grid gap-3 lg:grid-cols-3">
          {latest.map((row) => (
            <div key={`${row.period_type}-${row.period}`} className="rounded-[1.5rem] border border-slate-800/80 bg-slate-950/70 p-4">
              <div className="flex items-start justify-between gap-3">
                <div>
                  <div className="text-[10px] font-black uppercase tracking-[0.18em] text-emerald-300">{row.period_type}</div>
                  <h3 className="mt-1 font-mono text-2xl font-black text-slate-50">{row.period || "-"}</h3>
                  <div className="mt-1 text-xs text-slate-500">{row.first_date || "-"} to {row.last_date || "-"}</div>
                </div>
                <MiniBadge label={`${row.bettable_rows || 0} bettable`} tone={n(row.bettable_rows) > 0 ? "border-emerald-500/25 bg-emerald-500/10 text-emerald-300" : "border-amber-500/25 bg-amber-500/10 text-amber-300"} />
              </div>
              <div className="mt-4 grid grid-cols-2 gap-2">
                <MetricTile label="Rows" value={row.line_rows || "0"} sub={`${row.matched_rows || 0} matched`} tone="text-slate-100" />
                <MetricTile label="Two-way" value={row.two_way_rows || "0"} sub={`${row.one_sided_rows || 0} one-sided`} tone="text-cyan-300" />
                <MetricTile label="Best avail" value={row.best_available_rows || "0"} sub={`${row.main_line_rows || 0} usable main`} tone="text-emerald-300" />
                <MetricTile label="Shadow" value={`${row.shadow_pnl_units || "0.00"}u`} sub={`${row.shadow_settled || 0} settled / ROI ${row.shadow_roi_pct || "0.0"}%`} tone={n(row.shadow_pnl_units) >= 0 ? "text-emerald-300" : "text-rose-300"} />
              </div>
              <div className="mt-3 rounded-xl border border-slate-800 bg-slate-950/70 px-3 py-2 text-[11px] text-slate-500">
                Top blocker: <span className="font-semibold text-amber-300">{(row.top_blocker || "none").replaceAll("_", " ").toLowerCase()}</span>
              </div>
            </div>
          ))}
        </div>
      ) : (
        <EmptyState message="No model monitor summary yet. Run python scripts/tennis-props-model-report.py or the daily tennis props job." />
      )}
    </SectionCard>
  );
}

function MarketBenchmarkPanel({ rows, stamp }: { rows: CsvRow[]; stamp: string }) {
  const overall = benchmarkStats(rows);
  const groups = ["match_aces", "match_double_faults"].map((market) => ({
    market,
    stats: benchmarkStats(rows.filter((row) => row.market === market)),
  }));
  const metric = (value: number | null, digits: number) => value == null ? "-" : value.toFixed(digits);
  const deltaTone = overall.brierDelta == null
    ? "text-slate-400"
    : overall.brierDelta > 0
      ? "text-emerald-300"
      : "text-rose-300";

  return (
    <SectionCard
      title="Model vs Bet365 Benchmark"
      subtitle={`Every clean Bet365 main line is observed and settled, even when the official decision is NO BET. Updated ${stamp}.`}
    >
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
        <MetricTile label="Observed lines" value={String(overall.observations)} sub={`${overall.settled} settled / ${overall.pending} pending`} tone="text-cyan-300" />
        <MetricTile label="Count MAE" value={metric(overall.modelMae, 2)} sub={`Bet365 open ${metric(overall.marketMae, 2)}`} tone={overall.modelMae != null && overall.marketMae != null && overall.modelMae < overall.marketMae ? "text-emerald-300" : "text-slate-100"} />
        <MetricTile label="Model Brier" value={metric(overall.modelBrier, 3)} sub={`${overall.scored} non-push outcomes`} tone="text-slate-100" />
        <MetricTile label="Bet365 Brier" value={metric(overall.marketBrier, 3)} sub={`close ${metric(overall.closeBrier, 3)}`} tone="text-slate-100" />
        <MetricTile label="Brier edge" value={overall.brierDelta == null ? "-" : `${overall.brierDelta >= 0 ? "+" : ""}${overall.brierDelta.toFixed(3)}`} sub="positive = our model better" tone={deltaTone} />
      </div>
      <div className="mt-3 grid gap-3 lg:grid-cols-2">
        {groups.map(({ market, stats }) => (
          <div key={market} className="rounded-2xl border border-slate-800/80 bg-slate-950/60 p-4">
            <div className="text-[10px] font-black uppercase tracking-[0.16em] text-slate-500">{market.replaceAll("_", " ")}</div>
            <div className="mt-2 flex flex-wrap gap-x-5 gap-y-2 text-xs text-slate-400">
              <span><strong className="font-mono text-slate-100">{stats.settled}</strong> settled</span>
              <span>MAE <strong className="font-mono text-cyan-200">{metric(stats.modelMae, 2)}</strong> vs book <strong className="font-mono text-slate-200">{metric(stats.marketMae, 2)}</strong></span>
              <span>Brier delta <strong className={cn("font-mono", stats.brierDelta != null && stats.brierDelta > 0 ? "text-emerald-300" : "text-slate-200")}>{stats.brierDelta == null ? "-" : `${stats.brierDelta >= 0 ? "+" : ""}${stats.brierDelta.toFixed(3)}`}</strong></span>
            </div>
          </div>
        ))}
      </div>
      <p className="mt-3 text-xs leading-relaxed text-slate-500">
        Evidence gate: no automatic parameter change and no sellable claim before at least 100 settled clean lines. Actual counts remain the training target; Bet365 open/close is the benchmark challenger.
      </p>
    </SectionCard>
  );
}

function numeric(value: unknown): number {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : 0;
}

function validMostAcesSort(value: string | string[] | undefined): MostAcesSortKey {
  const raw = Array.isArray(value) ? value[0] : value;
  if (raw === "favourite" || raw === "closest") return raw;
  return "schedule";
}

function AcesOverV4Panel({
  rows,
  report,
  stamp,
}: {
  rows: CsvRow[];
  report: JsonRecord;
  stamp: string;
}) {
  const status = String(report.status || "NOT STARTED");
  const registered = numeric(report.rows_registered ?? rows.length);
  const settled = numeric(report.rows_settled);
  const scored = numeric(report.rows_scored);
  const target = numeric(report.minimum_prefit_settled || 200);
  const promotionSample = numeric(report.promotion_sample);
  const clvCoverage = numeric(report.clv_coverage);
  const clvMean = Number(report.clv_mean_pct);
  const acceptRate = Number(report.ladder_accept_rate_pct);
  const integrity = record(report.integrity);
  const progress = target > 0 ? Math.min(100, settled / target * 100) : 0;
  const recentFixtures = [...rows]
    .sort((a, b) => (b.registered_at_utc || "").localeCompare(a.registered_at_utc || ""))
    .reduce<Map<string, CsvRow[]>>((groups, row) => {
      const pair = [row.player || "", row.opponent || ""].sort().join("|");
      const key = row.event_id || `${row.date}|${row.tour}|${row.tournament}|${pair}`;
      groups.set(key, [...(groups.get(key) ?? []), row]);
      return groups;
    }, new Map());
  const recent = [...recentFixtures.entries()].slice(0, 4);

  return (
    <SectionCard
      title="ATP Aces Over v4"
      subtitle={`Registered market-anchored challenger. v3 remains frozen and live routing is unchanged. Updated ${stamp}.`}
    >
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-6">
        <MetricTile label="Status" value={status.replaceAll("_", " ")} sub="shadow only" tone={status === "PRE_FIT" ? "text-amber-300" : "text-cyan-300"} />
        <MetricTile label="Registered" value={String(registered)} sub={`${settled}/${target} settled before first fit`} tone="text-cyan-300" />
        <MetricTile label="Scored" value={String(scored)} sub={`${numeric(report.rows_pushed)} pushes / ${numeric(report.rows_pending)} pending`} tone="text-slate-100" />
        <MetricTile label="Ladder health" value={Number.isFinite(acceptRate) ? `${acceptRate.toFixed(1)}%` : "-"} sub={`${numeric(report.ladder_groups_accepted)}/${numeric(report.ladder_groups_seen)} accepted`} tone={acceptRate >= 95 ? "text-emerald-300" : "text-amber-300"} />
        <MetricTile label="Genuine CLV" value={Number.isFinite(clvMean) ? `${clvMean >= 0 ? "+" : ""}${clvMean.toFixed(2)}%` : "-"} sub={`${clvCoverage}/${registered} later closes`} tone={Number.isFinite(clvMean) && clvMean >= 0 ? "text-emerald-300" : "text-slate-400"} />
        <MetricTile label="Promotion sample" value={String(promotionSample)} sub="600 rows + all gates required" tone="text-slate-400" />
      </div>

      <div className="mt-4 h-2 overflow-hidden rounded-full bg-slate-900">
        <div className="h-full rounded-full bg-gradient-to-r from-amber-400 to-cyan-400" style={{ width: `${progress}%` }} />
      </div>
      <div className="mt-2 flex flex-wrap justify-between gap-2 text-[11px] text-slate-500">
        <span>PRE_FIT collection {progress.toFixed(1)}%</span>
        <span>Integrity: {numeric(integrity.player_key_collisions)} player collisions / {numeric(integrity.open_as_close_rows)} open-as-close</span>
      </div>

      {promotionSample > 0 ? (
        <div className="mt-4 grid gap-3 sm:grid-cols-3">
          <MetricTile label="v3 Brier" value={fmt(String(report.brier_v3), 4)} tone="text-slate-100" />
          <MetricTile label="v4 Brier" value={fmt(String(report.brier_v4), 4)} tone="text-cyan-300" />
          <MetricTile label="Market Brier" value={fmt(String(report.brier_market), 4)} tone="text-slate-100" />
        </div>
      ) : (
        <div className="mt-4 rounded-2xl border border-amber-500/20 bg-amber-500/8 px-4 py-3 text-xs leading-relaxed text-amber-100/80">
          No v4 tips and no v4 performance claim yet. Until 200 settled registrations, v4 is mathematically identical to v3; these rows establish an honest, frozen baseline for the later walk-forward test.
        </div>
      )}

      {recent.length ? (
        <div className="mt-4 grid gap-2 lg:grid-cols-2">
          {recent.map(([key, fixtureRows]) => {
            const first = fixtureRows[0];
            return (
              <article key={key} className="overflow-hidden rounded-2xl border border-slate-800/80 bg-slate-950/60">
                <div className="border-b border-slate-800/80 px-4 py-3">
                  <div className="font-bold text-slate-100">{first.player} <span className="font-normal text-slate-500">vs {first.opponent}</span></div>
                  <div className="mt-1 text-[11px] uppercase tracking-[0.12em] text-slate-500">
                    {first.tournament} / {dateLabel(first.date)} / {fixtureRows.length} player market{fixtureRows.length === 1 ? "" : "s"}
                  </div>
                </div>
                <div className="divide-y divide-slate-800/70">
                  {fixtureRows
                    .sort((a, b) => (a.player || "").localeCompare(b.player || ""))
                    .map((row) => (
                      <div key={row.observation_id} className="px-4 py-3">
                        <div className="flex items-start justify-between gap-3">
                          <div>
                            <div className="text-[10px] font-black uppercase tracking-[0.14em] text-cyan-300">{row.player} player market</div>
                            <div className="mt-1 font-mono text-sm font-black text-slate-100">Over {fmt(row.line, 1)} @ {fmt(row.selected_odds, 2)}</div>
                          </div>
                          <MiniBadge label={(row.settlement_status || "pending").toUpperCase()} tone={row.settlement_status === "settled" ? "border-emerald-500/25 bg-emerald-500/10 text-emerald-300" : "border-amber-500/25 bg-amber-500/10 text-amber-300"} />
                        </div>
                        <div className="mt-2 flex flex-wrap gap-x-4 gap-y-1 font-mono text-[11px] text-slate-400">
                          <span>v3 mean {fmt(row.mu_v3, 2)}</span>
                          <span>market mean {fmt(row.mu_mkt, 2)}</span>
                          <span>shape RMSE {fmt(row.ladder_shape_rmse, 3)}</span>
                          <span>{row.ladder_points} ladder points</span>
                        </div>
                      </div>
                    ))}
                </div>
              </article>
            );
          })}
        </div>
      ) : <EmptyState message="No eligible ATP Hard/Clay ace ladders have been registered yet." />}
    </SectionCard>
  );
}

function MostAcesPanel({
  rows,
  directRows,
  observations,
  forecasts,
  forecastReport,
  validation,
  directValidation,
  directParity,
  stamp,
  sortKey,
}: {
  rows: CsvRow[];
  directRows: CsvRow[];
  observations: CsvRow[];
  forecasts: CsvRow[];
  forecastReport: JsonRecord;
  validation: JsonRecord;
  directValidation: JsonRecord;
  directParity: JsonRecord;
  stamp: string;
  sortKey: MostAcesSortKey;
}) {
  const today = londonDateIso();
  const probability = (row: CsvRow) => Math.max(n(row.p_player1), n(row.p_draw), n(row.p_player2));
  const visible = rows.filter((row) => row.date >= today);
  visible.sort((a, b) => {
    if (sortKey === "favourite") return probability(b) - probability(a);
    if (sortKey === "closest") return Math.abs(n(a.player1_mean) - n(a.player2_mean)) - Math.abs(n(b.player1_mean) - n(b.player2_mean));
    return a.date.localeCompare(b.date)
      || a.tournament.localeCompare(b.tournament)
      || a.player1.localeCompare(b.player1);
  });
  const observationMap = new Map(
    observations.map((row) => [
      `${row.date}|${[row.player1, row.player2].sort().join("|")}`,
      row,
    ]),
  );
  const forecastMap = new Map(
    forecasts.map((row) => [
      `${row.date}|${[row.player1, row.player2].sort().join("|")}|${row.model}`,
      row,
    ]),
  );
  const directMap = new Map(
    directRows.map((row) => [
      `${row.date}|${[row.player1, row.player2].sort().join("|")}`,
      row,
    ]),
  );
  const correlated = record(validation.correlated);
  const outcomes = record(validation.outcomes);
  const modelSummaries = record(forecastReport.models);
  const controlForward = record(modelSummaries[rows[0]?.model || ""]);
  const directForward = record(modelSummaries.most_aces_direct_1x2_v1);
  const pairedForward = record(forecastReport.paired_comparison);
  const settled = numeric(controlForward.rows_settled);
  const accuracy = Number(controlForward.accuracy_pct);
  const forwardBrier = Number(controlForward.brier);
  const directResults = record(directValidation.results);
  const directSelection = record(directResults.selection_2025);
  const directDiagnostic = record(directResults.diagnostic_2026);
  const directSelectionComparison = record(directSelection.comparison);
  const directDiagnosticComparison = record(directDiagnostic.comparison);
  const directPassed = String(directValidation.status || "").toUpperCase() === "PASS";
  const directParityActive = String(directParity.status || "").toUpperCase() === "ACTIVE";
  const settledForecastRows = forecasts.filter((row) => row.settlement_status === "settled");
  const pendingForecastRows = forecasts.filter((row) => row.settlement_status === "pending");
  const voidForecastRows = forecasts.filter((row) => row.settlement_status === "void");
  const modelPriority = (model: string) => {
    if (model === "most_aces_direct_1x2_v1") return 4;
    if (model.includes("evidence_tiers")) return 3;
    if (model.includes("input_guard")) return 2;
    return 1;
  };
  const latestSettledByFixture = new Map<string, CsvRow>();
  for (const row of settledForecastRows) {
    const key = `${row.date}|${[row.player1, row.player2].sort().join("|")}`;
    const current = latestSettledByFixture.get(key);
    if (
      !current
      || modelPriority(row.model) > modelPriority(current.model)
      || (modelPriority(row.model) === modelPriority(current.model)
        && row.registered_at_utc > current.registered_at_utc)
    ) {
      latestSettledByFixture.set(key, row);
    }
  }
  const recentSettledForecasts = [...latestSettledByFixture.values()]
    .sort((a, b) => (b.settled_at_utc || b.date).localeCompare(a.settled_at_utc || a.date))
    .slice(0, 12);
  const modelLabel = (model: string) => model === "most_aces_direct_1x2_v1"
    ? "DIRECT V1"
    : model.includes("evidence_tiers")
      ? "A0 V3"
      : model.includes("input_guard")
        ? "A0 V2"
        : "A0 LEGACY";
  const sortOptions: { key: MostAcesSortKey; label: string }[] = [
    { key: "schedule", label: "Schedule" },
    { key: "favourite", label: "Strongest call" },
    { key: "closest", label: "Closest matchup" },
  ];

  return (
    <SectionCard
      title="BetMGM Most Aces 1X2"
      subtitle={`Correlated ATP Hard/Clay shadow pricer. Stage-0 ${String(validation.status || "MISSING")} on ${String(correlated.n || 0)} untouched matches; current artifact ${stamp}.`}
    >
      <div className="mb-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-7">
        <MetricTile label="Stage-0" value={String(validation.status || "MISSING")} sub={`${String(correlated.n || 0)} matches`} tone={String(validation.status || "").toUpperCase() === "PASS" ? "text-emerald-300" : "text-amber-300"} />
        <MetricTile label="Brier" value={Number(correlated.brier || 0).toFixed(4)} sub="correlated 1X2" tone="text-cyan-300" />
        <MetricTile label="Accuracy" value={`${Number(correlated.accuracy_pct || 0).toFixed(1)}%`} sub="three-way favourite" tone="text-slate-100" />
        <MetricTile label="Draws" value={String(outcomes.DRAW || 0)} sub="10.2% in holdout" tone="text-amber-300" />
        <MetricTile label="A0 forward settled" value={String(settled)} sub={`${numeric(controlForward.rows_registered)} registered`} tone={settled ? "text-cyan-300" : "text-slate-400"} />
        <MetricTile label="Forward score" value={Number.isFinite(accuracy) ? `${accuracy.toFixed(1)}%` : "-"} sub={Number.isFinite(forwardBrier) ? `Brier ${forwardBrier.toFixed(4)}` : "awaiting results"} tone={settled ? "text-emerald-300" : "text-slate-400"} />
        <MetricTile label="BetMGM prices" value={String(observations.length)} sub={observations.length ? "captured 1X2 quotes" : "FEED EMPTY - no ROI/CLV"} tone={observations.length ? "text-emerald-300" : "text-rose-300"} />
      </div>

      {Object.keys(directValidation).length ? (
        <div className={cn(
          "mb-4 rounded-2xl border px-4 py-4",
          directPassed
            ? "border-emerald-500/25 bg-emerald-500/10"
            : "border-amber-500/25 bg-amber-500/10",
        )}>
          <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
            <div>
              <div className="text-[10px] font-black uppercase tracking-[0.16em] text-emerald-300">
                Direct P1 / Draw / P2 experiment
              </div>
              <div className="mt-1 text-sm font-black text-slate-100">
                {directPassed ? "Passed retrospective gates - prospective shadow eligible" : "Retrospective gates blocked"}
              </div>
              <p className="mt-1 max-w-3xl text-xs leading-relaxed text-slate-400">
                Trained directly on the three-way Most Aces outcome with mirrored player order. Exact causal rank/activity feature parity is now used for the prospective shadow rows shown below.
              </p>
            </div>
            <div className="grid shrink-0 grid-cols-2 gap-2 sm:grid-cols-4">
              <MetricTile label="2025 Brier" value={fmt(String(directSelectionComparison.direct_brier), 4)} sub={`${fmt(String(Number(directSelectionComparison.brier_delta) * 1000), 1)} x10^-3 vs A0`} tone="text-emerald-300" />
              <MetricTile label="2025 log-loss" value={fmt(String(directSelectionComparison.direct_logloss), 4)} sub={`${fmt(String(Number(directSelectionComparison.logloss_delta) * 1000), 1)} x10^-3 vs A0`} tone="text-emerald-300" />
              <MetricTile label="2026 Brier" value={fmt(String(directDiagnosticComparison.direct_brier), 4)} sub={`${fmt(String(Number(directDiagnosticComparison.brier_delta) * 1000), 1)} x10^-3 vs A0`} tone="text-cyan-300" />
              <MetricTile
                label="Routing"
                value="SHADOW"
                sub={directParityActive ? `${numeric(directParity.scored_rows)} live rows` : "live parity blocked"}
                tone={directParityActive ? "text-emerald-300" : "text-amber-300"}
              />
            </div>
          </div>
          <div className="mt-3 grid gap-2 sm:grid-cols-3">
            <MetricTile label="Direct forward settled" value={String(numeric(directForward.rows_settled))} sub={`${numeric(directForward.rows_pending)} pending`} tone={numeric(directForward.rows_settled) ? "text-cyan-300" : "text-slate-400"} />
            <MetricTile label="Paired events" value={String(numeric(pairedForward.paired_events))} sub="same fixtures, A0 vs Direct" tone="text-slate-100" />
            <MetricTile
              label="Paired Brier delta"
              value={Number.isFinite(Number(pairedForward.brier_delta_direct_minus_control)) ? Number(pairedForward.brier_delta_direct_minus_control).toFixed(4) : "-"}
              sub="negative favours Direct"
              tone={Number(pairedForward.brier_delta_direct_minus_control) < 0 ? "text-emerald-300" : "text-slate-400"}
            />
          </div>
        </div>
      ) : null}

      <div className="mb-4 flex flex-col gap-3 rounded-2xl border border-amber-500/20 bg-amber-500/10 px-4 py-3 text-xs leading-relaxed text-amber-100/80 sm:flex-row sm:items-center sm:justify-between">
        <p>
          {observations.length
            ? `${observations.length} BetMGM market capture${observations.length === 1 ? "" : "s"} matched. Value and CLV remain shadow-only.`
            : "BetMGM lists Stat Bets on its site, but the configured odds feed has not exposed the three-way prices. Fair-odds forecasts are still registered and scored from actual ace counts; no ROI or value is claimed."}
        </p>
        <div className="flex shrink-0 flex-wrap gap-2">
          {sortOptions.map((option) => (
            <Link
              key={option.key}
              href={`/model-monitor/tennis-props?tab=decision&mostAcesSort=${option.key}`}
              className={cn(
                "rounded-full border px-3 py-1.5 text-[10px] font-black uppercase tracking-[0.12em] transition",
                sortKey === option.key
                  ? "border-cyan-400/40 bg-cyan-500/15 text-cyan-100"
                  : "border-slate-700 bg-slate-950/40 text-slate-400 hover:text-slate-100",
              )}
            >
              {option.label}
            </Link>
          ))}
        </div>
      </div>

      {visible.length ? (
        <div className="overflow-hidden rounded-2xl border border-slate-800 bg-slate-950/55">
          <div className="hidden grid-cols-[minmax(0,1.7fr)_110px_120px_repeat(3,72px)_110px] gap-3 border-b border-slate-800 bg-slate-900/70 px-4 py-3 text-[10px] font-black uppercase tracking-[0.14em] text-slate-500 lg:grid">
            <span>Fixture</span><span>Ace forecast</span><span>Model call</span>
            <span className="text-center">P1</span><span className="text-center">Draw</span><span className="text-center">P2</span><span>Outcome</span>
          </div>
          <div className="divide-y divide-slate-800/80">
            {visible.map((row) => {
              const key = `${row.date}|${[row.player1, row.player2].sort().join("|")}`;
              const observed = observationMap.get(key);
              const forecast = forecastMap.get(`${key}|${row.model}`);
              const direct = directMap.get(key);
              const directForecast = direct
                ? forecastMap.get(`${key}|${direct.model}`)
                : undefined;
              const quoteReady = row.quote_status === "READY";
              const historicalEstimate = row.quote_status === "HISTORICAL_ESTIMATE";
              const coverageGapEstimate = row.quote_status === "COVERAGE_GAP_ESTIMATE";
              const quoteVisible = quoteReady || historicalEstimate || coverageGapEstimate;
              const call = [
                { probability: n(row.p_player1), player: row.player1 },
                { probability: n(row.p_draw), player: "Draw" },
                { probability: n(row.p_player2), player: row.player2 },
              ].sort((a, b) => b.probability - a.probability)[0];
              return (
                <article key={key} className="px-4 py-4 transition hover:bg-slate-900/45">
                  <div className="grid gap-3 lg:grid-cols-[minmax(0,1.7fr)_110px_120px_repeat(3,72px)_110px] lg:items-center">
                    <div>
                      <div className="text-[10px] font-black uppercase tracking-[0.15em] text-cyan-300">{row.tournament} / {row.surface} / {dateLabel(row.date)}</div>
                      <h3 className="mt-1 font-black text-slate-100">{row.player1} vs {row.player2}</h3>
                    </div>
                    <div className="font-mono text-sm text-slate-300">
                      <span className="font-black text-slate-50">{fmt(row.player1_mean, 1)}</span><span className="mx-1 text-slate-600">-</span><span className="font-black text-slate-50">{fmt(row.player2_mean, 1)}</span>
                    </div>
                    <div><div className="text-xs font-black text-emerald-300">{call.player}</div><div className="font-mono text-[10px] text-slate-500">{(call.probability * 100).toFixed(1)}%</div></div>
                    {[
                      ["P1", row.fair_player1, observed?.open_player1_odds],
                      ["D", row.fair_draw, observed?.open_draw_odds],
                      ["P2", row.fair_player2, observed?.open_player2_odds],
                    ].map(([label, fair, market]) => (
                      <div key={label} className="rounded-xl border border-slate-800 bg-slate-900/70 px-2 py-2 text-center">
                        <div className="text-[9px] font-black uppercase tracking-[0.12em] text-slate-500">{label}</div>
                        <div className={cn("font-mono text-sm font-black", quoteReady ? "text-emerald-300" : historicalEstimate || coverageGapEstimate ? "text-amber-200" : "text-slate-600")}>
                          {quoteVisible ? fmt(fair, 2) : "-"}
                        </div>
                        {quoteReady && market ? <div className="font-mono text-[9px] text-cyan-300">MGM {fmt(market, 2)}</div> : null}
                      </div>
                    ))}
                    <div className="text-xs">
                      {forecast?.settlement_status === "settled" ? (
                        <>
                          <div className={cn("font-black", forecast.prediction_correct === "yes" ? "text-emerald-300" : "text-rose-300")}>
                            {forecast.actual_player1_aces}-{forecast.actual_player2_aces} / {forecast.prediction_correct === "yes" ? "correct" : "miss"}
                          </div>
                          <div className="text-[10px] text-slate-500">Brier {fmt(forecast.model_brier, 3)}</div>
                        </>
                      ) : (
                        <MiniBadge
                          label={coverageGapEstimate ? "ACTIVE / COVERAGE GAP" : historicalEstimate ? "STALE-FORM ESTIMATE" : !quoteReady ? "PRICE BLOCKED" : observed?.bet_eligible === "yes" ? "SHADOW VALUE" : "FORECAST"}
                          tone={historicalEstimate || coverageGapEstimate ? "border-amber-500/30 bg-amber-500/10 text-amber-200" : !quoteReady ? "border-rose-500/30 bg-rose-500/10 text-rose-200" : observed?.bet_eligible === "yes" ? "border-emerald-500/30 bg-emerald-500/10 text-emerald-200" : "border-slate-700 bg-slate-900 text-slate-400"}
                        />
                      )}
                    </div>
                  </div>
                  {direct ? (
                    <div className="mt-3 rounded-xl border border-cyan-500/20 bg-cyan-500/5 px-3 py-3">
                      <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
                        <div>
                          <div className="text-[9px] font-black uppercase tracking-[0.15em] text-cyan-300">
                            Direct 1X2 prospective shadow
                          </div>
                          <div className="mt-1 text-xs text-slate-400">
                            Frozen three-way classifier / exact live features / L1 probability change vs A0 {(n(direct.probability_l1_delta) * 100).toFixed(1)}pp
                          </div>
                        </div>
                        <div className="grid grid-cols-3 gap-2">
                          {[
                            ["P1", direct.fair_player1, direct.p_player1],
                            ["D", direct.fair_draw, direct.p_draw],
                            ["P2", direct.fair_player2, direct.p_player2],
                          ].map(([label, fair, probabilityValue]) => (
                            <div key={label} className="min-w-[72px] rounded-lg border border-cyan-500/15 bg-slate-950/55 px-2 py-1.5 text-center">
                              <div className="text-[8px] font-black uppercase tracking-[0.12em] text-slate-500">{label}</div>
                              <div className="font-mono text-sm font-black text-cyan-200">{fmt(fair, 2)}</div>
                              <div className="font-mono text-[9px] text-slate-500">{(n(probabilityValue) * 100).toFixed(1)}%</div>
                            </div>
                          ))}
                        </div>
                        <div className="min-w-[110px] text-xs">
                          {directForecast?.settlement_status === "settled" ? (
                            <>
                              <div className={cn("font-black", directForecast.prediction_correct === "yes" ? "text-emerald-300" : "text-rose-300")}>
                                {directForecast.actual_player1_aces}-{directForecast.actual_player2_aces} / {directForecast.prediction_correct === "yes" ? "correct" : "miss"}
                              </div>
                              <div className="text-[10px] text-slate-500">Brier {fmt(directForecast.model_brier, 3)}</div>
                            </>
                          ) : (
                            <MiniBadge label="TIMESTAMPED" tone="border-cyan-500/30 bg-cyan-500/10 text-cyan-200" />
                          )}
                        </div>
                      </div>
                    </div>
                  ) : null}
                  {coverageGapEstimate ? (
                    <div className="mt-3 break-all rounded-xl border border-amber-500/20 bg-amber-500/5 px-3 py-2 text-[10px] font-bold uppercase tracking-[0.08em] text-amber-200/80">
                      Active player, but recent lower-level performance is not yet level-adjusted. Research only: {row.quote_reason}
                    </div>
                  ) : historicalEstimate ? (
                    <div className="mt-3 break-all rounded-xl border border-amber-500/20 bg-amber-500/5 px-3 py-2 text-[10px] font-bold uppercase tracking-[0.08em] text-amber-200/80">
                      Historical estimate only, not bet-eligible: {row.quote_reason || "current-form sample below the registered minimum"}
                    </div>
                  ) : !quoteReady ? (
                    <div className="mt-3 break-all rounded-xl border border-amber-500/20 bg-amber-500/5 px-3 py-2 text-[10px] font-bold uppercase tracking-[0.08em] text-amber-200/80">
                      Fair price withheld: {row.quote_reason || "input quality below the registered minimum"}
                    </div>
                  ) : null}
                </article>
              );
            })}
          </div>
        </div>
      ) : <EmptyState message="No eligible ATP Hard/Clay Most Aces projections on the current board." />}

      <div className="mt-5 overflow-hidden rounded-2xl border border-slate-800 bg-slate-950/55">
        <div className="flex flex-col gap-2 border-b border-slate-800 bg-slate-900/70 px-4 py-4 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <div className="text-[10px] font-black uppercase tracking-[0.15em] text-cyan-300">Latest settled evidence</div>
            <div className="mt-1 text-sm font-black text-slate-100">Actual ace counts and forecast score</div>
          </div>
          <div className="flex flex-wrap gap-2 text-[10px] font-black uppercase tracking-[0.1em]">
            <span className="rounded-full border border-emerald-500/25 bg-emerald-500/10 px-3 py-1.5 text-emerald-300">{settledForecastRows.length} settled</span>
            <span className="rounded-full border border-amber-500/25 bg-amber-500/10 px-3 py-1.5 text-amber-300">{pendingForecastRows.length} pending</span>
            <span className="rounded-full border border-slate-700 bg-slate-900 px-3 py-1.5 text-slate-400">{voidForecastRows.length} void</span>
          </div>
        </div>
        {recentSettledForecasts.length ? (
          <div className="divide-y divide-slate-800/80">
            {recentSettledForecasts.map((row) => {
              const correct = row.prediction_correct === "yes";
              const predicted = row.predicted_outcome === "P1"
                ? row.player1
                : row.predicted_outcome === "P2"
                  ? row.player2
                  : "Draw";
              return (
                <div key={row.forecast_id} className="grid gap-3 px-4 py-3 sm:grid-cols-[90px_minmax(0,1.5fr)_minmax(0,1fr)_110px_90px] sm:items-center">
                  <div>
                    <div className="font-mono text-[11px] text-slate-400">{dateLabel(row.date)}</div>
                    <div className="mt-1 text-[9px] font-black uppercase tracking-[0.12em] text-cyan-300">{modelLabel(row.model)}</div>
                  </div>
                  <div>
                    <div className="text-xs font-black text-slate-100">{row.player1} vs {row.player2}</div>
                    <div className="mt-1 text-[10px] text-slate-500">{row.tournament} / {row.surface}</div>
                  </div>
                  <div className="text-xs">
                    <span className="text-slate-500">Call </span><span className="font-black text-slate-200">{predicted}</span>
                  </div>
                  <div className="font-mono text-sm font-black text-slate-100">{row.actual_player1_aces}-{row.actual_player2_aces} aces</div>
                  <div className="sm:text-right">
                    <div className={cn("text-xs font-black uppercase", correct ? "text-emerald-300" : "text-rose-300")}>{correct ? "Correct" : "Miss"}</div>
                    <div className="mt-1 font-mono text-[9px] text-slate-500">Brier {fmt(row.model_brier, 3)}</div>
                  </div>
                </div>
              );
            })}
          </div>
        ) : <div className="px-4 py-5 text-sm text-slate-500">No settled Most Aces forecasts yet.</div>}
        {pendingForecastRows.length ? (
          <div className="border-t border-amber-500/15 bg-amber-500/5 px-4 py-3 text-xs text-amber-100/80">
            Pending result lookup: {pendingForecastRows.slice(0, 3).map((row) => `${row.player1} vs ${row.player2}`).join("; ")}{pendingForecastRows.length > 3 ? ` +${pendingForecastRows.length - 3} more` : ""}.
          </div>
        ) : null}
      </div>
    </SectionCard>
  );
}
function ResearchGatesPanel({
  evidence,
  evidenceStamp,
  propsV2,
  propsV2Stamp,
  servicePointsGate,
  servicePointsStamp,
  opponentReturnGate,
  opponentReturnStamp,
  rateRecencyGate,
  rateRecencyStamp,
  propsV3Gate,
  propsV3Stamp,
  propsV3ShadowRows,
  propsV3ShadowStamp,
}: {
  evidence: JsonRecord;
  evidenceStamp: string;
  propsV2: JsonRecord;
  propsV2Stamp: string;
  servicePointsGate: JsonRecord;
  servicePointsStamp: string;
  opponentReturnGate: JsonRecord;
  opponentReturnStamp: string;
  rateRecencyGate: JsonRecord;
  rateRecencyStamp: string;
  propsV3Gate: JsonRecord;
  propsV3Stamp: string;
  propsV3ShadowRows: CsvRow[];
  propsV3ShadowStamp: string;
}) {
  const spread = record(evidence.spread_shape);
  const totals = record(evidence.total_games_shape);
  const props = record(evidence.aces_dfs);
  const propsCells = Array.isArray(propsV2.cells) ? propsV2.cells.map(record) : [];
  const propsPass = propsCells.filter((cell) => cell.passed === true).length;
  const recencyTours = record(rateRecencyGate.tours);
  const recencyCells = ["ATP", "WTA"].flatMap((tour) => {
    const markets = record(recencyTours[tour]);
    return [record(markets.aces), record(markets.dfs)];
  });
  const recencyPass = recencyCells.filter((cell) => cell.passed === true).length;
  const v3Sellability = record(propsV3Gate.sellability_gate);
  const v3Deployment = record(propsV3Gate.deployment_safe_aces);
  const v3Atp = record(v3Deployment.ATP);
  const v3Wta = record(v3Deployment.WTA);
  const v3Shadow = shadowStats(propsV3ShadowRows);
  const gateTone = (status: unknown) => {
    if (status === "PASS") return "text-emerald-300";
    if (status === "TESTED_AND_REJECTED") return "text-rose-300";
    return "text-amber-300";
  };
  const totalsRejected = totals.promotion_status === "TESTED_AND_REJECTED";
  const spreadShapeRejected = spread.shape_model_status === "TESTED_AND_REJECTED";
  const spreadSub = spreadShapeRejected
    ? `${numeric(spread.real_line_rows).toFixed(0)} scored | shape rejected: ROI ${numeric(spread.shape_roi_pct).toFixed(2)}% | CLV ${numeric(spread.shape_mean_clv_pct).toFixed(3)}% | Brier ${numeric(spread.shape_model_brier).toFixed(5)} vs market ${numeric(spread.shape_market_brier).toFixed(5)} | prospective ${numeric(spread.settled_shadow_bets).toFixed(0)}/200`
    : `${numeric(spread.real_line_rows).toFixed(0)}/600 scored | ${numeric(spread.captured_line_offers).toFixed(0)} captured | ${numeric(spread.settled_shadow_bets).toFixed(0)}/200 settled | CLV ${numeric(spread.mean_clv_pct) >= 0 ? "+" : ""}${numeric(spread.mean_clv_pct).toFixed(2)}%`;
  const totalsSub = totalsRejected
    ? `${numeric(totals.real_line_rows).toFixed(0)} scored | ROI ${numeric(totals.roi_pct).toFixed(2)}% | CLV ${numeric(totals.mean_clv_pct).toFixed(3)}% | Brier model ${numeric(totals.model_brier).toFixed(5)} vs market ${numeric(totals.market_brier).toFixed(5)}`
    : `${numeric(totals.real_line_rows).toFixed(0)}/600 scored | ${numeric(totals.captured_line_offers).toFixed(0)} captured complete offers`;

  return (
    <SectionCard
      title="Research Gates"
      subtitle={`Registered evidence only. Status ${evidenceStamp}; props v2 ${propsV2Stamp}; service points ${servicePointsStamp}; opponent return ${opponentReturnStamp}; recency ${rateRecencyStamp}; all-tour v3 ${propsV3Stamp}. No blocked lane changes live routing.`}
    >
      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4 2xl:grid-cols-8">
        <MetricTile
          label="Spread shape"
          value={String(spread.promotion_status || "BLOCKED")}
          sub={spreadSub}
          tone={gateTone(spread.promotion_status)}
        />
        <MetricTile
          label="Total-games shape"
          value={String(totals.promotion_status || "BLOCKED")}
          sub={totalsSub}
          tone={gateTone(totals.promotion_status)}
        />
        <MetricTile
          label="Bet365 aces / DFs"
          value={String(props.promotion_status || "BLOCKED")}
          sub={`${numeric(props.line_rows).toFixed(0)}/300 unique offers | ${numeric(props.snapshot_rows).toFixed(0)} snapshots | ${numeric(props.distinct_events).toFixed(0)}/100 events | ${numeric(props.settled_shadow_bets).toFixed(0)} settled`}
          tone={gateTone(props.promotion_status)}
        />
        <MetricTile
          label="Props v2 rung 1"
          value={String(propsV2.status || "MISSING")}
          sub={`${propsPass}/${propsCells.length || 4} tour-market cells passed | incumbent remains active`}
          tone={gateTone(propsV2.status)}
        />
        <MetricTile
          label="Service-point recursion"
          value={String(servicePointsGate.status || "MISSING")}
          sub={`Routing ${String(servicePointsGate.routing || "blocked").replaceAll("_", " ")} | incumbent unchanged`}
          tone={gateTone(servicePointsGate.status)}
        />
        <MetricTile
          label="Opponent-return ace rate"
          value={String(opponentReturnGate.status || "MISSING")}
          sub={`Routing ${String(opponentReturnGate.routing || "blocked").replaceAll("_", " ")} | exponent 0.60 retained`}
          tone={gateTone(opponentReturnGate.status)}
        />
        <MetricTile
          label="Player-rate recency"
          value={String(rateRecencyGate.status || "MISSING")}
          sub={`${recencyPass}/${recencyCells.length || 4} cells passed | L12M weight 1.0 retained`}
          tone={gateTone(rateRecencyGate.status)}
        />
        <MetricTile
          label="All-tour ace challenger"
          value={String(propsV3Gate.status || "MISSING")}
          sub={`Deployable ATP ${String(v3Atp.status || "MISSING")} | WTA ${String(v3Wta.status || "BLOCKED")} | ${v3Shadow.settled} settled / ${v3Shadow.pending} pending | ${String(v3Sellability.status || "BLOCKED")} for tips | ${propsV3ShadowStamp}`}
          tone={gateTone(propsV3Gate.status)}
        />
      </div>
      <p className="mt-3 text-xs text-slate-500">
        Current result: the richer all-main-tour v3 ace challenger beat the incumbent for ATP and WTA on untouched 2026 Hard/Clay data. The daily reproducible version passed only for ATP Hard/Clay, so that is the sole prospective shadow route. WTA, double faults and Grass remain blocked. Totals and the corrected spread-shape model were tested on real Pinnacle prices and rejected; the separate prospective spread lane remains evidence-blocked. With zero settled Bet365 shadow bets, no props tip is sellable yet. Synthetic odds never count as ROI evidence.
      </p>
    </SectionCard>
  );
}

export default async function TennisPropsMonitorPage({ searchParams }: { searchParams?: SearchParamsInput }) {
  if (!MODEL_MONITOR_ENABLED) notFound();
  const resolvedSearchParams: Record<string, string | string[] | undefined> = searchParams ? await searchParams : {};
  const projectionSortKey = validProjectionSort(resolvedSearchParams.propsSort);
  const mostAcesSortKey = validMostAcesSort(resolvedSearchParams.mostAcesSort);
  const activeTab = validMonitorTab(resolvedSearchParams.tab);
  const showAllLines = resolvedSearchParams.showAll === "1";
  const showHiddenLines = resolvedSearchParams.showHidden === "1";

  const [
    boardRows,
    boardStamp,
    boardAgeHours,
    baselineStamp,
    factorsStamp,
    latestComparisonPath,
    latestLinesPath,
    latestAuditPath,
    modelSummaryRows,
    modelSummaryStamp,
    modelReportStamp,
    shadowRows,
    shadowStamp,
    shadowPerformanceStamp,
    marketObservationRows,
    marketObservationStamp,
    marketObservationReportStamp,
    totalsGate,
    totalsGateStamp,
    derivativesEvidence,
    derivativesEvidenceStamp,
    propsV2Gate,
    propsV2GateStamp,
    servicePointsGate,
    servicePointsGateStamp,
    opponentReturnGate,
    opponentReturnGateStamp,
    rateRecencyGate,
    rateRecencyGateStamp,
    propsV3Gate,
    propsV3GateStamp,
    propsV3ShadowRows,
    propsV3ShadowStamp,
    propsV4Rows,
    propsV4Report,
    propsV4Stamp,
    mostAcesRows,
    mostAcesObservations,
    mostAcesForecasts,
    mostAcesForecastReport,
    mostAcesValidation,
    mostAcesDirectValidation,
    mostAcesDirectRows,
    mostAcesDirectParity,
    mostAcesReportStamp,
  ] = await Promise.all([
    readCsv(BOARD_PATH),
    fileStamp(BOARD_PATH),
    fileAgeHours(BOARD_PATH),
    fileStamp(BASELINE_PATH),
    fileStamp(FACTORS_PATH),
    latestCsv("comparison"),
    latestCsv("bet365-lines"),
    latestCsv("bet365-tennis-market-audit"),
    readCsv(MODEL_SUMMARY_PATH),
    fileStamp(MODEL_SUMMARY_PATH),
    fileStamp(MODEL_REPORT_PATH),
    readCsv(SHADOW_SIGNALS_PATH),
    fileStamp(SHADOW_SIGNALS_PATH),
    fileStamp(SHADOW_PERFORMANCE_PATH),
    readCsv(MARKET_OBSERVATIONS_PATH),
    fileStamp(MARKET_OBSERVATIONS_PATH),
    fileStamp(MARKET_OBSERVATIONS_REPORT_PATH),
    readJson(TOTALS_GATE_PATH),
    fileStamp(TOTALS_GATE_PATH),
    readJson(DERIVATIVES_STATUS_PATH),
    fileStamp(DERIVATIVES_STATUS_PATH),
    readJson(PROPS_V2_GATE_PATH),
    fileStamp(PROPS_V2_GATE_PATH),
    readJson(SERVICE_POINTS_GATE_PATH),
    fileStamp(SERVICE_POINTS_GATE_PATH),
    readJson(OPPONENT_RETURN_GATE_PATH),
    fileStamp(OPPONENT_RETURN_GATE_PATH),
    readJson(RATE_RECENCY_GATE_PATH),
    fileStamp(RATE_RECENCY_GATE_PATH),
    readJson(PROPS_V3_GATE_PATH),
    fileStamp(PROPS_V3_GATE_PATH),
    readCsv(V3_SHADOW_SIGNALS_PATH),
    fileStamp(V3_SHADOW_SIGNALS_PATH),
    readCsv(V4_OBSERVATIONS_PATH),
    readJson(V4_REPORT_PATH),
    fileStamp(V4_REPORT_PATH),
    readCsv(MOST_ACES_BOARD_PATH),
    readCsv(MOST_ACES_OBSERVATIONS_PATH),
    readCsv(MOST_ACES_FORECASTS_PATH),
    readJson(MOST_ACES_FORECAST_REPORT_PATH),
    readJson(MOST_ACES_STAGE0_PATH),
    readJson(MOST_ACES_DIRECT_RESULT_PATH),
    readCsv(MOST_ACES_DIRECT_BOARD_PATH),
    readJson(MOST_ACES_DIRECT_PARITY_PATH),
    fileStamp(MOST_ACES_FORECAST_REPORT_PATH),
  ]);

  const comparisonRows = latestComparisonPath ? await readCsv(latestComparisonPath) : [];
  const lineRows = latestLinesPath ? await readCsv(latestLinesPath) : [];
  const auditRows = latestAuditPath ? await readCsv(latestAuditPath) : [];
  const lineStamp = latestLinesPath ? await fileStamp(latestLinesPath) : "missing";
  const lineAgeHours = latestLinesPath ? await fileAgeHours(latestLinesPath) : null;
  const comparisonStamp = latestComparisonPath ? await fileStamp(latestComparisonPath) : "missing";
  const auditStamp = latestAuditPath ? await fileStamp(latestAuditPath) : "missing";
  const displayBoardRows = boardRows.filter(isMainTourProjectionRow);
  const sortedBoard = [...displayBoardRows].sort(boardSort);
  const usefulComparisonRows = comparisonRows.filter(isUsefulComparisonRow);
  const sortedComparison = [...usefulComparisonRows].sort(comparisonSort);
  const decisionRows = sortedComparison.filter(isMatchTotalComparisonRow);
  const breakRows = sortedComparison.filter((row) => row.market === "player_breaks" || row.market === "match_breaks");
  const matchedDecisionRows = decisionRows.filter((row) => row.matched_board === "yes");
  const bettableRows = matchedDecisionRows.filter(isBettableComparisonRow);
  const nearMissRows = matchedDecisionRows
    .filter((row) => !isBettableComparisonRow(row) && (
      (row.main_line === "true" && effectiveLineQuality(row) === "complete")
      || (row.best_available_line === "true" && row.price_pair_status === "over_only")
    ))
    .sort((a, b) => rowBestValue(b) - rowBestValue(a));
  const blockedExamples = matchedDecisionRows
    .filter((row) => !isBettableComparisonRow(row))
    .sort((a, b) => rowBestValue(b) - rowBestValue(a));
  const visibleAllLineRows = matchedDecisionRows.filter((row) => showHiddenLines || !isHardHiddenLine(row) || row.main_line === "true" || row.best_available_line === "true" || row.bettable === "true");
  const allLineRowsForPanel = showAllLines ? visibleAllLineRows : visibleAllLineRows.filter((row) => row.main_line === "true" || row.best_available_line === "true" || row.bettable === "true");
  const sortedShadowRows = [...shadowRows].sort(shadowSort);
  const shadow = shadowStats(shadowRows);
  const marketBenchmark = benchmarkStats(marketObservationRows);
  const todayIso = londonDateIso();
  const latestLinesDate = latestLinesPath ? path.basename(latestLinesPath).match(/bet365-lines-(\d{4}-\d{2}-\d{2})\.csv$/)?.[1] ?? "" : "";
  const hasTodayLines = latestLinesDate === todayIso;
  const boardStale = boardAgeHours == null || boardAgeHours > 24;
  const linesStale = lineAgeHours == null || lineAgeHours > 6;
  const lineStatus = !latestLinesPath ? "MISSING" : !hasTodayLines ? "NO TODAY CAPTURE" : linesStale ? "STALE" : "FRESH";
  const matchedRate = decisionRows.length ? (matchedDecisionRows.length / decisionRows.length) * 100 : 0;
  const hiddenCount = matchedDecisionRows.length - visibleAllLineRows.length;
  const todayBoardRows = sortedBoard.filter((row) => row.date === todayIso);
  const todayMatchCount = new Set(todayBoardRows.map(matchKey)).size;

  return (
    <div className="min-h-screen bg-[radial-gradient(circle_at_top_left,_rgba(16,185,129,0.12),_transparent_28%),radial-gradient(circle_at_top_right,_rgba(244,63,94,0.08),_transparent_24%),#0b0f14] text-slate-100">
      <div className="mx-auto max-w-7xl px-4 py-8 sm:px-6 lg:px-8">
        <div className="mb-6">
          <MonitorNav current="tennis-props" />
        </div>

        <HeroCard title="Tennis Props Decision Board" eyebrow="Aces / double faults / service breaks">
          <p className="text-slate-300">
            Decision first: bookmaker aces, double-fault and service-break lines are compared against the projection board. Breaks remain a zero-stake watchlist until prospective ROI and CLV gates pass.
          </p>
          <div className="mt-4 flex flex-wrap gap-2">
            <StatusPill label="Decision board default" tone="border-emerald-500/25 bg-emerald-500/10 text-emerald-300" />
            <StatusPill label="ATP + WTA projections" tone="border-cyan-500/25 bg-cyan-500/10 text-cyan-200" />
            <StatusPill label="Shadow only until settled" tone="border-amber-500/25 bg-amber-500/10 text-amber-300" />
          </div>
        </HeroCard>

        <section className="my-6 grid gap-4 sm:grid-cols-2 lg:grid-cols-7">
          <StatCard label="Verdict" value={bettableRows.length ? `${bettableRows.length} BET NOW` : "NO BET"} detail={`${nearMissRows.length} near miss / ${blockedExamples.length} blocked`} tone={bettableRows.length ? "text-emerald-300" : "text-amber-300"} />
          <StatCard label="Bet365 lines" value={String(decisionRows.length)} detail={`${matchedDecisionRows.length} matched / ${lineRows.length} raw rows`} tone={decisionRows.length ? "text-cyan-300" : "text-slate-400"} />
          <StatCard label="Match rate" value={`${matchedRate.toFixed(0)}%`} detail={`comparison ${comparisonStamp}`} tone={matchedRate >= 95 ? "text-emerald-300" : matchedRate ? "text-amber-300" : "text-slate-400"} />
          <StatCard label="Line freshness" value={lineStatus} detail={latestLinesPath ? `${latestLinesDate || "unknown date"} · ${lineStamp}` : "No Bet365 file found"} tone={lineStatus === "FRESH" ? "text-emerald-300" : "text-amber-300"} />
          <StatCard label="Projection rows" value={String(sortedBoard.length)} detail={`${countBy(sortedBoard, "tour", "ATP")} ATP / ${countBy(sortedBoard, "tour", "WTA")} WTA`} />
          <StatCard label="Shadow evidence" value={String(shadowRows.length)} detail={`${shadow.settled} settled / ${shadow.pending} pending`} tone={shadowRows.length ? "text-amber-300" : "text-slate-400"} />
          <StatCard label="Market benchmark" value={String(marketBenchmark.observations)} detail={`${marketBenchmark.settled} settled / ${marketBenchmark.pending} pending`} tone={marketBenchmark.observations ? "text-cyan-300" : "text-slate-400"} />
        </section>

        <div className="mb-6">
          <TotalsStage0Panel gate={totalsGate} stamp={totalsGateStamp} />
        </div>

        <section className="mb-6 grid gap-3 rounded-2xl border border-slate-800 bg-slate-950/40 p-4 text-xs text-slate-400 md:grid-cols-4">
          <div><span className="text-slate-500">Board:</span> <span className="text-slate-200">{boardStamp}</span></div>
          <div><span className="text-slate-500">Bet365 lines:</span> <span className="text-slate-200">{lineStamp}</span></div>
          <div><span className="text-slate-500">Bet365 audit:</span> <span className="text-slate-200">{auditStamp}</span></div>
          <div><span className="text-slate-500">Comparison:</span> <span className="text-slate-200">{comparisonStamp}</span></div>
          <div><span className="text-slate-500">Venue factors:</span> <span className="text-slate-200">{factorsStamp}</span></div>
          <div><span className="text-slate-500">Baseline:</span> <span className="text-slate-200">{baselineStamp}</span></div>
          <div><span className="text-slate-500">Model report:</span> <span className="text-slate-200">{modelReportStamp}</span></div>
          <div><span className="text-slate-500">Shadow:</span> <span className="text-slate-200">{shadowStamp}</span></div>
          <div><span className="text-slate-500">Shadow perf:</span> <span className="text-slate-200">{shadowPerformanceStamp}</span></div>
          <div><span className="text-slate-500">Market benchmark:</span> <span className="text-slate-200">{marketObservationStamp}</span></div>
          <div><span className="text-slate-500">Benchmark report:</span> <span className="text-slate-200">{marketObservationReportStamp}</span></div>
        </section>

        {boardStale ? (
          <section className="mb-6 rounded-2xl border border-amber-500/30 bg-amber-500/10 p-4 text-sm text-amber-100">
            Projection board is stale or missing. Run <span className="font-mono text-amber-50">python scripts/run-tennis-props-daily.py</span> after the OnCourt extract before trusting today&apos;s props board.
          </section>
        ) : null}

        <nav className="mb-6 grid gap-3 sm:grid-cols-3">
          <TabLink active={activeTab === "decision"} href="/model-monitor/tennis-props?tab=decision" label="Decision Board" detail="BET NOW / near miss / blocked lines" />
          <TabLink active={activeTab === "projections"} href="/model-monitor/tennis-props?tab=projections" label="Projections" detail="Aces, DFs, breaks, tie-break simulation" />
          <TabLink active={false} href="/model-monitor/tennis-props?tab=decision#most-aces-evidence" label="Most Aces Evidence" detail="Fair odds, settled scores, model accuracy" />
        </nav>

        {activeTab === "decision" && todayBoardRows.length ? (
          <section className="mb-6 flex flex-col gap-4 rounded-[2rem] border border-cyan-500/25 bg-[radial-gradient(circle_at_top_left,rgba(6,182,212,0.16),transparent_38%),rgba(15,23,42,0.82)] p-5 sm:flex-row sm:items-center sm:justify-between">
            <div>
              <div className="text-[11px] font-black uppercase tracking-[0.18em] text-cyan-300">Today&apos;s projections are ready</div>
              <h2 className="mt-2 text-2xl font-black text-slate-50">{todayMatchCount} matches / {todayBoardRows.length} player estimates</h2>
              <p className="mt-1 text-sm text-slate-400">
                {linesStale
                  ? "The projection board is current, but Bet365 prices are stale or missing. That means estimates are available while the official betting decision remains NO BET."
                  : "Open the projection board for aces, double faults, breaks and tie-break estimates. The betting decision above remains the official gate."}
              </p>
            </div>
            <Link href="/model-monitor/tennis-props?tab=projections" className="shrink-0 rounded-full border border-cyan-400/35 bg-cyan-500/15 px-5 py-3 text-center text-xs font-black uppercase tracking-[0.15em] text-cyan-100 transition hover:bg-cyan-500/25">
              View today&apos;s matches
            </Link>
          </section>
        ) : null}

        {!hasTodayLines ? (
          <section className="mb-6 rounded-2xl border border-rose-500/30 bg-rose-500/10 p-4 text-sm text-rose-100">
            <div className="font-black uppercase tracking-[0.12em] text-rose-200">No Bet365 capture for {todayIso}</div>
            <p className="mt-1 text-rose-100/80">
              The projections are current, but the latest available prices are from {latestLinesDate || "an earlier date"}. Old prices remain visible for audit only and the betting gate stays blocked until a current capture is synced.
            </p>
          </section>
        ) : null}

        {activeTab === "decision" ? (
          <div className="grid gap-6">
            <RecommendationPanel
              actionableRows={bettableRows}
              watchRows={nearMissRows.length ? nearMissRows : blockedExamples}
              matchedCount={matchedDecisionRows.length}
              totalCount={decisionRows.length}
            />

            <BreakRecommendationPanel rows={breakRows} />

            <div id="most-aces-evidence" className="scroll-mt-6">
              <MostAcesPanel
                rows={mostAcesRows}
                directRows={mostAcesDirectRows}
                observations={mostAcesObservations}
                forecasts={mostAcesForecasts}
                forecastReport={mostAcesForecastReport}
                validation={mostAcesValidation}
                directValidation={mostAcesDirectValidation}
                directParity={mostAcesDirectParity}
                stamp={mostAcesReportStamp}
                sortKey={mostAcesSortKey}
              />
            </div>

            <ModelTrackerPanel rows={modelSummaryRows} stamp={modelSummaryStamp} />

            <AcesOverV4Panel rows={propsV4Rows} report={propsV4Report} stamp={propsV4Stamp} />

            <MarketBenchmarkPanel rows={marketObservationRows} stamp={marketObservationReportStamp} />

            <ResearchGatesPanel
              evidence={derivativesEvidence}
              evidenceStamp={derivativesEvidenceStamp}
              propsV2={propsV2Gate}
              propsV2Stamp={propsV2GateStamp}
              servicePointsGate={servicePointsGate}
              servicePointsStamp={servicePointsGateStamp}
              opponentReturnGate={opponentReturnGate}
              opponentReturnStamp={opponentReturnGateStamp}
              rateRecencyGate={rateRecencyGate}
              rateRecencyStamp={rateRecencyGateStamp}
              propsV3Gate={propsV3Gate}
              propsV3Stamp={propsV3GateStamp}
              propsV3ShadowRows={propsV3ShadowRows}
              propsV3ShadowStamp={propsV3ShadowStamp}
            />

            <FeedDiagnosticsPanel
              lineRows={lineRows}
              auditRows={auditRows}
              decisionRows={decisionRows}
              matchedRows={matchedDecisionRows}
            />

            <SectionCard
              title="Near Misses"
              subtitle="Complete main lines that fail one gate. If there are none, the examples shown are the best blocked audit rows. Still not bets."
            >
              {nearMissRows.length || blockedExamples.length ? (
                <div className="grid gap-3 lg:grid-cols-3">
                  {(nearMissRows.length ? nearMissRows : blockedExamples).slice(0, 6).map((row, index) => <ComparisonLineCard key={`near-${row.player}-${row.market}-${row.line}-${index}`} row={row} />)}
                </div>
              ) : <EmptyState message="No near-miss rows. Either no Bet365 rows were captured, or nothing matched the board." />}
            </SectionCard>

            <SectionCard
              title="All Captured Lines"
              subtitle={`${matchedDecisionRows.length} matched rows. ${hiddenCount} one-sided/deep-alt rows hidden unless opened.`}
              collapsible
              defaultOpen={showAllLines}
            >
              <div className="mb-3 flex flex-wrap gap-2">
                <Link href="/model-monitor/tennis-props?tab=decision&showAll=1" className="rounded-full border border-cyan-500/25 bg-cyan-500/10 px-3 py-1.5 text-xs font-bold uppercase tracking-[0.12em] text-cyan-200">Open audit rows</Link>
                <Link href="/model-monitor/tennis-props?tab=decision&showAll=1&showHidden=1" className="rounded-full border border-amber-500/25 bg-amber-500/10 px-3 py-1.5 text-xs font-bold uppercase tracking-[0.12em] text-amber-200">Show one-sided/deep-alt</Link>
              </div>
              <ComparisonTable rows={allLineRowsForPanel} hasLinesFile={lineRows.length > 0} />
            </SectionCard>

            <SectionCard
              title="Settled Sample"
              subtitle={`Append-only match-total Bet365 paper record. OnCourt settlement with Sackmann fallback. Closing-price coverage ${shadow.clvCount}/${shadow.settled}; mean CLV ${shadow.meanClv >= 0 ? "+" : ""}${shadow.meanClv.toFixed(2)}%.`}
            >
              <ShadowEvidenceTable rows={sortedShadowRows} />
            </SectionCard>

            <SectionCard title="Ops Footer" subtitle="Files this page reads directly from disk on localhost.">
              <div className="grid gap-2 text-xs text-slate-400 md:grid-cols-2">
                <div><span className="text-slate-500">Board:</span> data/tennis-props/player-props-board.csv</div>
                <div><span className="text-slate-500">Lines:</span> {latestLinesPath ? path.basename(latestLinesPath) : "missing"}</div>
                <div><span className="text-slate-500">Comparison:</span> {latestComparisonPath ? path.basename(latestComparisonPath) : "missing"}</div>
                <div><span className="text-slate-500">Shadow:</span> data/tennis-props/shadow/aces-dfs-shadow-signals.csv</div>
                <div><span className="text-slate-500">Market benchmark:</span> data/tennis-props/shadow/market-observations.csv</div>
                <div><span className="text-slate-500">Aces Over v4:</span> data/tennis-props/shadow/aces-over-v4-observations.csv</div>
                <div><span className="text-slate-500">Most Aces:</span> data/tennis-props/shadow/most-aces-1x2-observations.csv</div>
              </div>
            </SectionCard>
          </div>
        ) : (
          <div className="grid gap-6">
            <SectionCard
              title={`Projection Board (${dateLabel(projectionFocusDate(sortedBoard))} first)`}
              subtitle="Expected aces, double faults, breaks and tie-break probabilities for each scheduled player. Sort controls are for scanning, not bet recommendations."
            >
              <ProjectionTable rows={sortedBoard} sortKey={projectionSortKey} />
            </SectionCard>

            <SectionCard
              title="Shadow Evidence"
              subtitle={`Append-only Bet365 line evidence. ROI is research-only until 300+ settled lines. Current shadow PnL ${shadow.pnl >= 0 ? "+" : ""}${shadow.pnl.toFixed(2)}u / ROI ${shadow.roi >= 0 ? "+" : ""}${shadow.roi.toFixed(1)}%.`}
            >
              <ShadowEvidenceTable rows={sortedShadowRows} />
            </SectionCard>
          </div>
        )}
      </div>
    </div>
  );
}
