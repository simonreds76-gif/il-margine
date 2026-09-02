import Link from "next/link";
import { promises as fs } from "fs";
import { notFound } from "next/navigation";
import { tryGetKnownProjectFilePath } from "@/lib/project-file-paths";

type CsvRow = Record<string, string>;

type PerfSnapshot = {
  combinedAll?: CsvRow;
  combinedWindow?: CsvRow;
  mlAll?: CsvRow;
  handicapAll?: CsvRow;
  mlWindow?: CsvRow;
  handicapWindow?: CsvRow;
};

type ClvSummary = {
  rawRows?: number;
  settledMlAudited?: number;
  matchedMl?: number;
  matchedMlTotal?: number;
  historyRows?: number;
  avgClvPct?: number;
  medianClvPct?: number;
  positiveClvCount?: number;
  positiveClvTotal?: number;
  positiveClvSharePct?: number;
  avgOddsMovePct?: number;
  signalDateRange?: string;
  matchDateRange?: string;
  closingDateRange?: string;
  warning?: string;
};

type SpreadThresholdStatus = {
  threshold_pct?: number;
  settled?: number;
  staked_units?: number;
  pnl_units?: number;
  roi_pct?: number;
  rolling_20_roi_pct?: number;
  clv_matched?: number;
  clv_match_rate_pct?: number;
  avg_clv_pct?: number;
  median_clv_pct?: number;
  positive_clv_share_pct?: number;
  line_bucket_dominance_share?: number;
  live_ready?: boolean;
};

type SpreadOrientationSummary = {
  settled?: number;
  wins?: number;
  losses?: number;
  staked_units?: number;
  pnl_units?: number;
  roi_pct?: number;
  clv_matched?: number;
  clv_match_rate_pct?: number;
  avg_clv_pct?: number;
  rolling_20_roi_pct?: number;
};

type SpreadSurfaceStatus = {
  settled_total?: number;
  recommended_threshold_pct?: number | null;
  promotion_status?: string;
  threshold_results?: SpreadThresholdStatus[];
  orientation_breakout?: Record<string, SpreadOrientationSummary>;
  current_threshold_pct?: number | null;
  current?: SpreadThresholdStatus;
};

type SpreadV1Status = {
  generated_at?: string;
  tracked?: number;
  settled?: number;
  open?: number;
  clv_rows?: number;
  last_spread_capture_at?: string;
  calibration?: {
    valid?: boolean;
    reason?: string;
    line_source_used?: string;
    fit_timestamp?: string;
    base_calibration_valid?: boolean;
    base_calibration_reason?: string;
    correction_valid?: boolean;
    correction_reason?: string;
    warning?: string;
  };
  surfaces?: {
    hard?: SpreadSurfaceStatus;
    clay?: SpreadSurfaceStatus;
  };
};

type ClayMlAnalysis = {
  generatedAt?: string;
  holdoutEce?: number;
  logLossDelta?: number;
  verdict?: string;
};

type SpreadCalibrationParams = {
  generated_at_utc?: string;
  fit_timestamp?: string;
  line_source_used?: string;
  surface_filter?: string;
  calibration_valid?: boolean;
  calibration_reason?: string;
};

type GrandSlamEvalSummary = {
  bets?: number;
  wins?: number;
  losses?: number;
  avg_value_pct?: number;
  flat_roi_pct?: number;
  tier_staked_units?: number;
  tier_pnl_units?: number;
  tier_roi_pct?: number;
};

type GrandSlamEvalRow = GrandSlamEvalSummary & {
  key?: string;
  label?: string;
  surface?: string;
  tournament?: string;
  status?: string;
  status_reasons?: string[];
  yearly?: Array<GrandSlamEvalSummary & { year?: string }>;
  confidence_breakdown?: Record<string, GrandSlamEvalSummary>;
};

type GrandSlamEvalReport = {
  generated_at_utc?: string;
  years?: number[];
  criteria?: {
    min_bets?: number;
    min_tier_roi_pct?: number;
    min_positive_years?: number;
    latest_year_tier_roi_min_pct?: number;
  };
  rows?: GrandSlamEvalRow[];
};

type ProfileSummary = {
  name: string;
  bets?: number;
  avgPerYear?: number;
  winRatePct?: number;
  avgValuePct?: number;
  flatRoiPct?: number;
  tierRoiPct?: number;
  tierPnL?: number;
  tierStaked?: number;
  years: Array<{ year: string; bets?: number; tierRoiPct?: number }>;
};

type MonitorSignalRow = {
  date: string;
  timeUtc: string;
  matchDate: string;
  player1: string;
  player2: string;
  surface: string;
  league: string;
  series: string;
  confidence: string;
  side: string;
  valuePct?: number;
  claySpeedTier: string;
  tournamentSpeedSignal?: number;
  betType: string;
  spreadLine?: number;
  spreadOdds?: number;
  pinOdds1?: number;
  pinOdds2?: number;
  stakeUnits?: number;
  policyMode: string;
  signalProfile: string;
  settlementStatus: string;
  result: string;
  betOutcome: string;
  settledAt: string;
  settlementNote: string;
  refreshCount?: number;
};

type SignalCohortSummary = {
  signals: number;
  settled: number;
  unsettled: number;
  wins: number;
  losses: number;
  voids: number;
  stakedUnits: number;
  pnlUnits: number;
  roiPct?: number;
  avgValuePct?: number;
};

type LaneScoreRow = {
  policy: string;
  lane: string;
  marketType: string;
  usageNote?: string;
  settled: number;
  signals: number;
  open: number;
  wlv: string;
  roi?: number;
  flatStakePounds?: number;
  flatTotalStakedPounds?: number;
  unitTotalStakedPounds?: number;
  unitStakePounds?: number;
  winRate?: number;
  clv?: number;
  clvLabel?: string;
  statusBadge?: { tone: "muted" | "warn" | "ok"; label: string };
};

export const dynamic = "force-dynamic";
const CLEAN_EVAL_START = "2026-03-14";

const MODEL_MONITOR_PUBLIC =
  process.env.MODEL_MONITOR_PUBLIC === "1" ||
  process.env.NEXT_PUBLIC_ENABLE_MODEL_MONITOR === "1";
const MODEL_MONITOR_ENABLED =
  MODEL_MONITOR_PUBLIC || process.env.VERCEL_ENV === "preview";
const INTERNAL_RESEARCH_LANES = process.env.INTERNAL_RESEARCH_LANES === "1";

function parseCsvLine(line: string): string[] {
  const out: string[] = [];
  let cur = "";
  let inQuotes = false;
  for (let i = 0; i < line.length; i += 1) {
    const ch = line[i];
    if (ch === '"') {
      if (inQuotes && line[i + 1] === '"') {
        cur += '"';
        i += 1;
      } else {
        inQuotes = !inQuotes;
      }
      continue;
    }
    if (ch === "," && !inQuotes) {
      out.push(cur);
      cur = "";
      continue;
    }
    cur += ch;
  }
  out.push(cur);
  return out;
}

function parseCsv(text: string): CsvRow[] {
  const lines = text
    .split(/\r?\n/)
    .map((line) => line.trimEnd())
    .filter(Boolean);
  if (!lines.length) return [];
  const headers = parseCsvLine(lines[0]);
  return lines.slice(1).map((line) => {
    const values = parseCsvLine(line);
    const row: CsvRow = {};
    headers.forEach((header, idx) => {
      row[header] = values[idx] ?? "";
    });
    return row;
  });
}

async function readLocalFile(relPath: string): Promise<string | null> {
  try {
    const fullPath = tryGetKnownProjectFilePath(relPath);
    if (!fullPath) return null;
    return await fs.readFile(fullPath, "utf8");
  } catch {
    return null;
  }
}

async function readLocalMtime(relPath: string): Promise<string | null> {
  try {
    const fullPath = tryGetKnownProjectFilePath(relPath);
    if (!fullPath) return null;
    const stat = await fs.stat(fullPath);
    return stat.mtime.toISOString();
  } catch {
    return null;
  }
}

function parseJsonMaybe<T>(text: string | null): T | undefined {
  if (!text) return undefined;
  try {
    return JSON.parse(text) as T;
  } catch {
    return undefined;
  }
}

function lastMatching(rows: CsvRow[], predicate: (row: CsvRow) => boolean): CsvRow | undefined {
  for (let i = rows.length - 1; i >= 0; i -= 1) {
    if (predicate(rows[i])) return rows[i];
  }
  return undefined;
}

function parsePerf(rows: CsvRow[], policyMode: string): PerfSnapshot {
  const matchEval = (row: CsvRow, evalPeriod: string) => {
    const value = row.eval_period ?? "";
    if (!value) return evalPeriod === "overall";
    return value === evalPeriod;
  };
  const matchLeagueScope = (row: CsvRow) => {
    const value = (row.league_scope ?? "").trim();
    return value === "" || value === "combined";
  };
  const preferEval = (scope: string, betType: string, evalPeriod: string) =>
    lastMatching(
      rows,
      (row) =>
        row.scope === scope &&
        matchLeagueScope(row) &&
        row.policy_mode === policyMode &&
        (betType ? row.bet_type === betType : !row.bet_type) &&
        matchEval(row, evalPeriod)
    );
  return {
    combinedAll: preferEval("all_time", "", "clean") ?? preferEval("all_time", "", "overall"),
    combinedWindow: preferEval("window", "", "clean") ?? preferEval("window", "", "overall"),
    mlAll: preferEval("all_time", "ml", "clean") ?? preferEval("all_time", "ml", "overall"),
    handicapAll: preferEval("all_time", "handicap", "clean") ?? preferEval("all_time", "handicap", "overall"),
    mlWindow: preferEval("window", "ml", "clean") ?? preferEval("window", "ml", "overall"),
    handicapWindow: preferEval("window", "handicap", "clean") ?? preferEval("window", "handicap", "overall"),
  };
}

function parseFloatMaybe(value?: string): number | undefined {
  if (!value) return undefined;
  const n = Number.parseFloat(value);
  return Number.isFinite(n) ? n : undefined;
}

function parseIntMaybe(value?: string): number | undefined {
  if (!value) return undefined;
  const n = Number.parseInt(value, 10);
  return Number.isFinite(n) ? n : undefined;
}

function formatPct(value?: number, digits = 2, showSign = true): string {
  if (value == null || Number.isNaN(value)) return "n/a";
  const prefix = value < 0 ? "-" : showSign && value > 0 ? "+" : "";
  return `${prefix}${Math.abs(value).toFixed(digits)}%`;
}

function formatUnits(value?: number, digits = 2): string {
  if (value == null || Number.isNaN(value)) return "n/a";
  return `${value >= 0 ? "+" : ""}${value.toFixed(digits)}u`;
}

function challengerSkipReasonLabel(reason?: string): string {
  if (reason === "coverage_thin") return "Coverage thin";
  if (reason === "confidence_low") return "Confidence low";
  if (reason === "edge_below_floor") return "Edge below floor";
  if (reason === "edge_above_cap") return "Edge above cap";
  if (reason === "model_market_gap") return "Model/market gap";
  if (reason === "model_ml_excluded") return "Model ML excluded";
  if (reason === "pin_ml_excluded") return "Pinnacle excluded";
  if (reason === "surface_blocked") return "Surface blocked";
  return reason ? reason.replace(/_/g, " ") : "Unknown";
}

function formatPounds(value?: number, digits = 0, showSign = true): string {
  if (value == null || Number.isNaN(value)) return "n/a";
  const abs = Math.abs(value);
  const prefix = value < 0 ? "-" : showSign && value > 0 ? "+" : "";
  return `${prefix}GBP ${abs.toLocaleString("en-GB", {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  })}`;
}

function metricTone(value?: number): string {
  if (value == null || Number.isNaN(value)) return "text-slate-300";
  if (value > 0) return "text-emerald-300";
  if (value < 0) return "text-rose-300";
  return "text-slate-300";
}

function statusBadgeClass(tone: NonNullable<LaneScoreRow["statusBadge"]>["tone"]): string {
  if (tone === "ok") return "border-emerald-500/40 bg-emerald-500/10 text-emerald-200";
  if (tone === "warn") return "border-amber-500/40 bg-amber-500/10 text-amber-200";
  return "border-slate-700/70 bg-slate-900/80 text-slate-300";
}

function parseClvAudit(text: string | null): ClvSummary {
  if (!text) return {};
  const warningBlock = text.match(/Coverage warning\s+([\s\S]+?)(?:\n\n|$)/);
  const settledAudited =
    parseIntMaybe(text.match(/Settled ML rows audited:\s+(\d+)/)?.[1]) ??
    parseIntMaybe(text.match(/Settled spread rows audited:\s+(\d+)/)?.[1]);
  const matchedCount =
    parseIntMaybe(text.match(/Matched ML rows:\s+(\d+)\s+\/\s+\d+/)?.[1]) ??
    parseIntMaybe(text.match(/Matched spread rows:\s+(\d+)\s+\/\s+\d+/)?.[1]);
  const matchedTotal =
    parseIntMaybe(text.match(/Matched ML rows:\s+\d+\s+\/\s+(\d+)/)?.[1]) ??
    parseIntMaybe(text.match(/Matched spread rows:\s+\d+\s+\/\s+(\d+)/)?.[1]);
  return {
    rawRows: parseIntMaybe(text.match(/Raw strict rows:\s+(\d+)/)?.[1]),
    settledMlAudited: settledAudited,
    matchedMl: matchedCount,
    matchedMlTotal: matchedTotal,
    historyRows: parseIntMaybe(text.match(/History rows loaded:\s+(\d+)/)?.[1]),
    avgClvPct: parseFloatMaybe(text.match(/Avg CLV implied delta:\s+([+-]?[\d.]+)%/)?.[1]),
    medianClvPct: parseFloatMaybe(text.match(/Median CLV implied delta:\s+([+-]?[\d.]+)%/)?.[1]),
    positiveClvCount: parseIntMaybe(text.match(/Positive CLV share:\s+(\d+)\/\d+/)?.[1]),
    positiveClvTotal: parseIntMaybe(text.match(/Positive CLV share:\s+\d+\/(\d+)/)?.[1]),
    positiveClvSharePct: parseFloatMaybe(text.match(/Positive CLV share:\s+\d+\/\d+\s+\(([+-]?[\d.]+)%\)/)?.[1]),
    avgOddsMovePct: parseFloatMaybe(text.match(/Avg odds move pct:\s+([+-]?[\d.]+)%/)?.[1]),
    signalDateRange: text.match(/Signal date range:\s+(.+)/)?.[1]?.trim(),
    matchDateRange: text.match(/Settled match-date range:\s+(.+)/)?.[1]?.trim(),
    closingDateRange: text.match(/Closing date range:\s+(.+)/)?.[1]?.trim(),
    warning: warningBlock?.[1]?.trim().replace(/\s+/g, " "),
  };
}

function parseClayMlAnalysis(text: string | null): ClayMlAnalysis {
  if (!text) return {};
  return {
    generatedAt: text.match(/Generated UTC:\s+(.+)/)?.[1]?.trim(),
    holdoutEce: parseFloatMaybe(text.match(/Holdout 2025 ECE:\s+([+-]?[\d.]+)/)?.[1]),
    logLossDelta: parseFloatMaybe(text.match(/Holdout 2025 log-loss delta vs Pinnacle:\s+([+-]?[\d.]+)/)?.[1]),
    verdict: text.match(/Verdict:\s+(.+)/)?.[1]?.trim(),
  };
}

function parsePolicyProfiles(text: string | null): ProfileSummary[] {
  if (!text) return [];
  const blocks = [...text.matchAll(/\[([^\]]+)\]\n([\s\S]*?)(?=\n\[[^\]]+\]|\s*$)/g)];
  return blocks.map((match) => {
    const name = match[1];
    const body = match[2];
    const headline = body.match(/Bets=(\d+)\s+Avg\/Year=([\d.]+)\s+W-L=\d+-\d+\s+WR=([\d.]+)%\s+AvgValue=([\d.]+)%/);
    const flat = body.match(/Flat stake:\s+P\/L=[+-]?[\d.]+u\s+ROI=([+-]?[\d.]+)%/);
    const tier = body.match(/Value-tiered:\s+Staked=([\d.]+)u\s+P\/L=([+-]?[\d.]+)u\s+ROI=([+-]?[\d.]+)%/);
    const yearMatches = [...body.matchAll(/^\s+(\d{4}): bets=(\d+).*?tierROI=([+-]?[\d.]+)%/gm)];
    return {
      name,
      bets: parseIntMaybe(headline?.[1]),
      avgPerYear: parseFloatMaybe(headline?.[2]),
      winRatePct: parseFloatMaybe(headline?.[3]),
      avgValuePct: parseFloatMaybe(headline?.[4]),
      flatRoiPct: parseFloatMaybe(flat?.[1]),
      tierStaked: parseFloatMaybe(tier?.[1]),
      tierPnL: parseFloatMaybe(tier?.[2]),
      tierRoiPct: parseFloatMaybe(tier?.[3]),
      years: yearMatches.map((yearMatch) => ({
        year: yearMatch[1],
        bets: parseIntMaybe(yearMatch[2]),
        tierRoiPct: parseFloatMaybe(yearMatch[3]),
      })),
    };
  });
}

function perfValue(row: CsvRow | undefined, key: string, parser: (value?: string) => number | undefined) {
  return parser(row?.[key]);
}

function perfVoidCount(row: CsvRow | undefined): number {
  const settled = perfValue(row, "settled", parseIntMaybe) ?? 0;
  const wins = perfValue(row, "wins", parseIntMaybe) ?? 0;
  const losses = perfValue(row, "losses", parseIntMaybe) ?? 0;
  const voids = settled - wins - losses;
  return voids > 0 ? voids : 0;
}

function perfWlv(row: CsvRow | undefined): string {
  const wins = perfValue(row, "wins", parseIntMaybe) ?? 0;
  const losses = perfValue(row, "losses", parseIntMaybe) ?? 0;
  const voids = perfVoidCount(row);
  return `${wins}/${losses}/${voids}`;
}

function MonitorCard({
  title,
  subtitle,
  children,
}: {
  title: string;
  subtitle?: string;
  children: React.ReactNode;
}) {
  return (
    <section className="rounded-2xl border border-slate-800 bg-[linear-gradient(180deg,rgba(20,25,34,0.96),rgba(11,15,21,0.96))] p-5 shadow-[0_20px_60px_rgba(0,0,0,0.28)]">
      <div className="mb-4 flex items-start justify-between gap-4">
        <div>
          <h2 className="text-lg font-semibold text-slate-100">{title}</h2>
          {subtitle ? <p className="mt-1 text-sm text-slate-400">{subtitle}</p> : null}
        </div>
      </div>
      {children}
    </section>
  );
}

function Stat({
  label,
  value,
  tone = "text-slate-100",
  compact = false,
}: {
  label: string;
  value: string;
  tone?: string;
  compact?: boolean;
}) {
  return (
    <div className="rounded-xl border border-slate-800/80 bg-slate-950/35 px-3 py-3">
      <div className="text-[11px] uppercase tracking-[0.18em] text-slate-500">{label}</div>
      <div className={`mt-1 font-semibold ${compact ? "text-base leading-5" : "text-lg"} ${tone}`}>{value}</div>
    </div>
  );
}

function SplitBucket({
  title,
  roi,
  roiTone,
  wlv,
}: {
  title: string;
  roi: string;
  roiTone?: string;
  wlv: string;
}) {
  return (
    <div className="rounded-xl border border-slate-800/80 bg-slate-950/35 p-3">
      <div className="mb-2 text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-500">{title}</div>
      <div className="grid gap-2">
        <Stat label="ROI" value={roi} tone={roiTone} compact />
        <Stat label="W/L/V" value={wlv} tone="text-slate-100" compact />
      </div>
    </div>
  );
}

function SpreadOrientationCard({
  title,
  summary,
  tone,
  note,
}: {
  title: string;
  summary?: SpreadOrientationSummary;
  tone: string;
  note: string;
}) {
  return (
    <div className={`rounded-2xl border bg-slate-950/35 p-4 ${tone}`}>
      <div className="flex items-start justify-between gap-3">
        <div>
          <div className="text-sm font-semibold text-slate-100">{title}</div>
          <div className="mt-1 text-xs leading-5 text-slate-500">{note}</div>
        </div>
        <div className="rounded-full border border-slate-700/80 bg-slate-900/80 px-2 py-1 text-xs font-semibold text-slate-300">
          n={summary?.settled ?? 0}
        </div>
      </div>
      <div className="mt-4 grid gap-2 sm:grid-cols-2">
        <Stat label="W-L" value={orientationWl(summary)} compact />
        <Stat label="ROI" value={formatPct(summary?.roi_pct)} tone={metricTone(summary?.roi_pct)} compact />
        <Stat label="Avg CLV" value={formatPct(summary?.avg_clv_pct, 3)} tone={metricTone(summary?.avg_clv_pct)} compact />
        <Stat label="CLV Match" value={formatPct(summary?.clv_match_rate_pct, 1, false)} compact />
        <Stat label="Rolling 20" value={formatPct(summary?.rolling_20_roi_pct)} tone={metricTone(summary?.rolling_20_roi_pct)} compact />
        <Stat label="P/L" value={formatUnits(summary?.pnl_units)} tone={metricTone(summary?.pnl_units)} compact />
      </div>
    </div>
  );
}

function FileStamp({ label, value }: { label: string; value: string | null }) {
  return (
    <div className="rounded-full border border-slate-700/80 bg-slate-900/80 px-3 py-1.5 text-xs text-slate-300">
      <span className="text-slate-500">{label}</span> {value ?? "missing"}
    </div>
  );
}

function parseSignalRows(text: string | null): MonitorSignalRow[] {
  if (!text) return [];
  return parseCsv(text).map((row) => ({
    date: row.date ?? "",
    timeUtc: row.time_utc ?? "",
    matchDate: row.match_date ?? "",
    player1: row.player1 ?? "",
    player2: row.player2 ?? "",
    surface: row.surface ?? "",
    league: row.league ?? "",
    series: row.series ?? "",
    confidence: row.confidence ?? "",
    side: row.side ?? "",
    valuePct: parseFloatMaybe(row.value_pct),
    claySpeedTier: row.clay_speed_tier ?? "",
    tournamentSpeedSignal: parseFloatMaybe(row.tournament_speed_signal),
    betType: row.bet_type ?? "",
    spreadLine: parseFloatMaybe(row.spread_line),
    spreadOdds: parseFloatMaybe(row.spread_odds),
    pinOdds1: parseFloatMaybe(row.pin_odds1),
    pinOdds2: parseFloatMaybe(row.pin_odds2),
    stakeUnits: parseFloatMaybe(row.stake_units),
    policyMode: row.policy_mode ?? "",
    signalProfile: row.signal_profile ?? "",
    settlementStatus: row.settlement_status ?? "",
    result: row.result ?? "",
    betOutcome: row.bet_outcome ?? "",
    settledAt: row.settled_at ?? "",
    settlementNote: row.settlement_note ?? "",
  }));
}

function isSettledSignal(row: MonitorSignalRow): boolean {
  return (row.settlementStatus || "").trim().toLowerCase() === "settled";
}

function mergeSettlementFields(base: MonitorSignalRow, update: MonitorSignalRow): MonitorSignalRow {
  return {
    ...base,
    settlementStatus: update.settlementStatus || base.settlementStatus,
    result: update.result || base.result,
    betOutcome: update.betOutcome || base.betOutcome,
    settledAt: update.settledAt || base.settledAt,
    settlementNote: update.settlementNote || base.settlementNote,
    matchDate: update.matchDate || base.matchDate,
  };
}

function logicalSignalKey(row: MonitorSignalRow): string {
  const eventDate = row.matchDate || row.date;
  return [
    eventDate,
    row.player1.trim().toLowerCase(),
    row.player2.trim().toLowerCase(),
    row.betType || "match",
    row.side,
    row.policyMode || "base",
    row.signalProfile,
  ].join("|");
}

function dedupeLogicalSignalRows(rows: MonitorSignalRow[]): MonitorSignalRow[] {
  const byKey = new Map<string, MonitorSignalRow>();
  const ordered = [...rows].sort((left, right) => signalTimestamp(left) - signalTimestamp(right));
  for (const row of ordered) {
    const key = logicalSignalKey(row);
    const prev = byKey.get(key);
    if (!prev) {
      byKey.set(key, { ...row, refreshCount: 1 });
      continue;
    }
    const merged = isSettledSignal(row) ? mergeSettlementFields(prev, row) : prev;
    byKey.set(key, { ...merged, refreshCount: (prev.refreshCount ?? 1) + 1 });
  }
  return [...byKey.values()];
}

function normalizeLeague(league?: string): "ATP" | "Challenger" {
  return league === "Challenger" ? "Challenger" : "ATP";
}

function summarizeSignalCohort(
  rows: MonitorSignalRow[],
  league?: "ATP" | "Challenger",
  stakeMode: "recorded" | "flat" = "recorded",
  betType?: "match" | "spread",
): SignalCohortSummary {
  const filtered = rows.filter((row) => {
    if (league && normalizeLeague(row.league) !== league) return false;
    if (betType && row.betType !== betType) return false;
    return true;
  });
  let settled = 0;
  let wins = 0;
  let losses = 0;
  let stakedUnits = 0;
  let pnlUnits = 0;
  const values: number[] = [];

  for (const row of filtered) {
    if (row.valuePct != null) values.push(row.valuePct);
    if (!isSettledSignal(row)) continue;
    settled += 1;

    const outcome = (row.betOutcome || "").trim().toLowerCase();
    const side = (row.side || "").trim().toLowerCase();
    const stakeUnitsRow =
      stakeMode === "flat" ? 1.0 : row.stakeUnits && row.stakeUnits > 0 ? row.stakeUnits : 1.0;
    let odds: number | undefined;
    if (row.betType === "spread") {
      odds = row.spreadOdds;
    } else if (side === "p1") {
      odds = row.pinOdds1;
    } else if (side === "p2") {
      odds = row.pinOdds2;
    }
    if (outcome === "win" && odds != null && odds > 1) {
      wins += 1;
      stakedUnits += stakeUnitsRow;
      pnlUnits += stakeUnitsRow * (odds - 1);
    } else if (outcome === "loss") {
      losses += 1;
      stakedUnits += stakeUnitsRow;
      pnlUnits -= stakeUnitsRow;
    }
  }

  const voids = settled - wins - losses;
  return {
    signals: filtered.length,
    settled,
    unsettled: filtered.length - settled,
    wins,
    losses,
    voids: voids > 0 ? voids : 0,
    stakedUnits,
    pnlUnits,
    roiPct: stakedUnits > 0 ? (pnlUnits / stakedUnits) * 100 : undefined,
    avgValuePct: values.length ? values.reduce((sum, value) => sum + value, 0) / values.length : undefined,
  };
}

function filterCleanSignalRows(rows: MonitorSignalRow[]): MonitorSignalRow[] {
  return rows.filter((row) => (row.date || "") >= CLEAN_EVAL_START);
}

function cohortWlv(summary: SignalCohortSummary): string {
  return `${summary.wins}/${summary.losses}/${summary.voids}`;
}

function orientationWl(summary?: SpreadOrientationSummary): string {
  if (!summary) return "n/a";
  return `${summary.wins ?? 0}-${summary.losses ?? 0}`;
}

function formatClvCell(value?: number, label = "n/a"): string {
  if (value == null || Number.isNaN(value)) return label;
  return formatPct(value, 3, false);
}

function signalTimestamp(row: MonitorSignalRow): number {
  const stamp = Date.parse(`${row.date}T${row.timeUtc || "00:00:00"}Z`);
  return Number.isFinite(stamp) ? stamp : 0;
}

function getUnsettledSignalRows(rows: MonitorSignalRow[]): MonitorSignalRow[] {
  return rows
    .filter((row) => (row.settlementStatus || "").trim().toLowerCase() !== "settled")
    .sort((left, right) => signalTimestamp(right) - signalTimestamp(left));
}

function getActiveQueueRows(rows: MonitorSignalRow[]): MonitorSignalRow[] {
  return getUnsettledSignalRows(rows).filter((row) => (row.settlementStatus || "").trim().toLowerCase() !== "no_match");
}

function getNoMatchRows(rows: MonitorSignalRow[]): MonitorSignalRow[] {
  return rows
    .filter((row) => (row.settlementStatus || "").trim().toLowerCase() === "no_match")
    .sort((left, right) => signalTimestamp(right) - signalTimestamp(left));
}

function getSettledSignalRows(rows: MonitorSignalRow[]): MonitorSignalRow[] {
  return rows
    .filter(isSettledSignal)
    .sort((left, right) => {
      const leftStamp = Date.parse(left.settledAt || "") || signalTimestamp(left);
      const rightStamp = Date.parse(right.settledAt || "") || signalTimestamp(right);
      return rightStamp - leftStamp;
    });
}

function getSelectedOdds(row: MonitorSignalRow): number | undefined {
  if (row.betType === "spread") return row.spreadOdds;
  return row.side === "P2" ? row.pinOdds2 : row.pinOdds1;
}

function signalSelectionLabel(row: MonitorSignalRow): string {
  if (row.betType === "spread") return `${row.side} ${formatSignedLine(row.spreadLine)} HC`;
  return `${row.side} ML`;
}

function signalPnlUnits(row: MonitorSignalRow): number | undefined {
  if (!isSettledSignal(row)) return undefined;
  const outcome = (row.betOutcome || "").trim().toLowerCase();
  const stake = row.stakeUnits && row.stakeUnits > 0 ? row.stakeUnits : 1;
  const odds = getSelectedOdds(row);
  if (outcome === "win" && odds != null && odds > 1) return stake * (odds - 1);
  if (outcome === "loss") return -stake;
  return 0;
}

function signalStatusClass(row: MonitorSignalRow): string {
  const status = (row.settlementStatus || "").trim().toLowerCase();
  const outcome = (row.betOutcome || "").trim().toLowerCase();
  if (outcome === "win") return "border-emerald-500/25 bg-emerald-500/10 text-emerald-300";
  if (outcome === "loss") return "border-rose-500/25 bg-rose-500/10 text-rose-300";
  if (status === "no_match") return "border-amber-500/25 bg-amber-500/10 text-amber-300";
  return "border-slate-700/80 bg-slate-900/80 text-slate-300";
}

function signalStatusLabel(row: MonitorSignalRow): string {
  if (row.betOutcome) return row.betOutcome;
  if (row.settlementStatus) return row.settlementStatus;
  return "pending";
}

function sortSignalRowsForBrowser(rows: MonitorSignalRow[]): MonitorSignalRow[] {
  return [...rows].sort((left, right) => {
    const leftStamp = Date.parse(left.settledAt || "") || signalTimestamp(left);
    const rightStamp = Date.parse(right.settledAt || "") || signalTimestamp(right);
    return rightStamp - leftStamp;
  });
}

function sortSignalRowsByCapture(rows: MonitorSignalRow[]): MonitorSignalRow[] {
  return [...rows].sort((left, right) => signalTimestamp(right) - signalTimestamp(left));
}

function getSettlementDate(row: MonitorSignalRow): string {
  return row.settledAt ? row.settledAt.slice(0, 10) : row.matchDate || row.date;
}

function shiftIsoDate(isoDate: string, days: number): string {
  const stamp = Date.parse(`${isoDate}T00:00:00Z`);
  if (!Number.isFinite(stamp)) return isoDate;
  return new Date(stamp + days * 86400000).toISOString().slice(0, 10);
}

function latestIsoDate(...values: Array<string | undefined>): string | null {
  const valid = values.filter((value): value is string => Boolean(value && /^\d{4}-\d{2}-\d{2}$/.test(value)));
  if (valid.length === 0) return null;
  return [...valid].sort().at(-1) ?? null;
}

function formatSignedLine(value?: number): string {
  if (value == null || Number.isNaN(value)) return "n/a";
  return `${value > 0 ? "+" : ""}${value.toFixed(value % 1 === 0 ? 0 : 1)}`;
}

export default async function ModelMonitorPage() {
  if (process.env.NODE_ENV === "production" && !MODEL_MONITOR_ENABLED) {
    notFound();
  }

  const [
    strictPerfCsv,
    volumePerfCsv,
    spreadV1PerfCsv,
    spreadShadowPerfCsv,
    strictSignalsArchiveCsv,
    strictSignalsLiveCsv,
    clvAuditTxt,
    clvAuditVolumeTxt,
    clvAuditSpreadV1Txt,
    profileTxt,
    grandSlamEvalJson,
    shadowComparisonTxt,
    modelVariantsCsv,
    volumeSignalsArchiveCsv,
    volumeSignalsLiveCsv,
    spreadV1SignalsArchiveCsv,
    spreadV1SignalsLiveCsv,
    spreadShadowSignalsArchiveCsv,
    spreadShadowSignalsLiveCsv,
    challengerSignalsArchiveCsv,
    challengerSignalsLiveCsv,
    challengerNearmissCsv,
    challengerPerfCsv,
    clvAuditChallengerTxt,
    clayFavSignalsArchiveCsv,
    clayFavSignalsLiveCsv,
    clayFavPerfCsv,
    clvAuditClayFavTxt,
    spreadV1StatusJson,
    clayMlAnalysisTxt,
    claySpreadCalibrationJson,
    strictPerfMtime,
    volumePerfMtime,
    spreadV1PerfMtime,
    spreadShadowPerfMtime,
    clvAuditMtime,
    clvAuditVolumeMtime,
    clvAuditSpreadV1Mtime,
    profileMtime,
    grandSlamEvalMtime,
    modelVariantsMtime,
    strictSignalsLiveMtime,
    volumeSignalsMtime,
    spreadV1SignalsMtime,
    spreadShadowSignalsMtime,
    spreadV1StatusMtime,
    clayMlAnalysisMtime,
    claySpreadCalibrationMtime,
  ] = await Promise.all([
    readLocalFile("data/backtest/strict-policy-performance-weekly.csv"),
    readLocalFile("data/backtest/strict-policy-performance-volume200-weekly.csv"),
    readLocalFile("data/backtest/strict-policy-performance-spreadv1-weekly.csv"),
    readLocalFile("data/backtest/strict-policy-performance-spreadshadow-weekly.csv"),
    readLocalFile("data/backtest/strict-signals-archive.csv"),
    readLocalFile("data/backtest/strict-signals-live.csv"),
    readLocalFile("data/backtest/strict-clv-audit-2026.txt"),
    readLocalFile("data/backtest/strict-clv-audit-volume200-2026.txt"),
    readLocalFile("data/backtest/strict-clv-audit-spreadv1-2026.txt"),
    readLocalFile("data/backtest/policy-profile-backtest-2022-2025.txt"),
    readLocalFile("data/backtest/grand-slam-eval-2022-2025.json"),
    readLocalFile("data/backtest/shadow-profile-comparison.txt"),
    readLocalFile("data/backtest/model-variants-shadow.csv"),
    readLocalFile("data/backtest/strict-signals-volume200-archive.csv"),
    readLocalFile("data/backtest/strict-signals-volume200-live.csv"),
    readLocalFile("data/backtest/strict-signals-spreadv1-archive.csv"),
    readLocalFile("data/backtest/strict-signals-spreadv1-live.csv"),
    readLocalFile("data/backtest/strict-signals-spreadshadow-archive.csv"),
    readLocalFile("data/backtest/strict-signals-spreadshadow-live.csv"),
    INTERNAL_RESEARCH_LANES ? readLocalFile("data/backtest/strict-signals-challenger-ml-v2-archive.csv") : null,
    INTERNAL_RESEARCH_LANES ? readLocalFile("data/backtest/strict-signals-challenger-ml-v2-live.csv") : null,
    INTERNAL_RESEARCH_LANES ? readLocalFile("data/backtest/challenger-ml-v2-nearmiss.csv") : null,
    INTERNAL_RESEARCH_LANES ? readLocalFile("data/backtest/strict-policy-performance-challenger-ml-v2-weekly.csv") : null,
    INTERNAL_RESEARCH_LANES ? readLocalFile("data/backtest/strict-clv-audit-challenger-ml-v2-2026.txt") : null,
    INTERNAL_RESEARCH_LANES ? readLocalFile("data/backtest/strict-signals-clay-fav-archive.csv") : null,
    INTERNAL_RESEARCH_LANES ? readLocalFile("data/backtest/strict-signals-clay-fav-live.csv") : null,
    INTERNAL_RESEARCH_LANES ? readLocalFile("data/backtest/strict-policy-performance-clay-fav-weekly.csv") : null,
    INTERNAL_RESEARCH_LANES ? readLocalFile("data/backtest/strict-clv-audit-clay-fav-2026.txt") : null,
    readLocalFile("data/backtest/spread-v1-shadow-status.json"),
    readLocalFile("data/backtest/clay-ml-calibration-analysis.txt"),
    readLocalFile("data/backtest/spread-v1-clay-calibration-params.json"),
    readLocalMtime("data/backtest/strict-policy-performance-weekly.csv"),
    readLocalMtime("data/backtest/strict-policy-performance-volume200-weekly.csv"),
    readLocalMtime("data/backtest/strict-policy-performance-spreadv1-weekly.csv"),
    readLocalMtime("data/backtest/strict-policy-performance-spreadshadow-weekly.csv"),
    readLocalMtime("data/backtest/strict-clv-audit-2026.txt"),
    readLocalMtime("data/backtest/strict-clv-audit-volume200-2026.txt"),
    readLocalMtime("data/backtest/strict-clv-audit-spreadv1-2026.txt"),
    readLocalMtime("data/backtest/policy-profile-backtest-2022-2025.txt"),
    readLocalMtime("data/backtest/grand-slam-eval-2022-2025.json"),
    readLocalMtime("data/backtest/model-variants-shadow.csv"),
    readLocalMtime("data/backtest/strict-signals-live.csv"),
    readLocalMtime("data/backtest/strict-signals-volume200-live.csv"),
    readLocalMtime("data/backtest/strict-signals-spreadv1-live.csv"),
    readLocalMtime("data/backtest/strict-signals-spreadshadow-live.csv"),
    readLocalMtime("data/backtest/spread-v1-shadow-status.json"),
    readLocalMtime("data/backtest/clay-ml-calibration-analysis.txt"),
    readLocalMtime("data/backtest/spread-v1-clay-calibration-params.json"),
  ]);

  const strictRows = strictPerfCsv ? parseCsv(strictPerfCsv) : [];
  const volumeRows = volumePerfCsv ? parseCsv(volumePerfCsv) : [];
  const spreadV1Rows = spreadV1PerfCsv ? parseCsv(spreadV1PerfCsv) : [];
  const spreadShadowRows = spreadShadowPerfCsv ? parseCsv(spreadShadowPerfCsv) : [];
  const strictBase = parsePerf(strictRows, "base");
  const strictOverlay = parsePerf(strictRows, "overlay");
  const volumeBase = parsePerf(volumeRows, "base");
  const spreadV1Base = parsePerf(spreadV1Rows, "base");
  const spreadShadowBase = parsePerf(spreadShadowRows, "base");
  const clv = parseClvAudit(clvAuditTxt);
  const clvVolume = parseClvAudit(clvAuditVolumeTxt);
  const clvSpreadV1 = parseClvAudit(clvAuditSpreadV1Txt);
  const profiles = parsePolicyProfiles(profileTxt);
  const grandSlamEval = parseJsonMaybe<GrandSlamEvalReport>(grandSlamEvalJson);
  const grandSlamRows = grandSlamEval?.rows ?? [];
  const modelVariantRows = modelVariantsCsv ? parseCsv(modelVariantsCsv) : [];
  const profileMap = new Map(profiles.map((profile) => [profile.name, profile]));
  const strictSignalsArchiveRaw = parseSignalRows(strictSignalsArchiveCsv);
  const strictSignalsArchive = dedupeLogicalSignalRows(strictSignalsArchiveRaw);
  const strictSignalsLive = dedupeLogicalSignalRows(parseSignalRows(strictSignalsLiveCsv));
  const strictSignalsClean = filterCleanSignalRows(strictSignalsArchive);
  const strictSettledRows = getSettledSignalRows(strictSignalsArchive);
  const strictQueue = getActiveQueueRows(strictSignalsLive);
  const volumeSignalsArchiveRaw = parseSignalRows(volumeSignalsArchiveCsv);
  const volumeSignalsArchive = dedupeLogicalSignalRows(volumeSignalsArchiveRaw);
  const volumeSignalsLive = dedupeLogicalSignalRows(parseSignalRows(volumeSignalsLiveCsv));
  const volumeSignalsClean = filterCleanSignalRows(volumeSignalsArchive);
  const volumeQueue = getActiveQueueRows(volumeSignalsLive);
  const volumeNoMatchRows = getNoMatchRows(volumeSignalsArchive);
  const volumeVisibleNoMatchRows = getNoMatchRows(volumeSignalsLive);
  const volumeSettledRows = getSettledSignalRows(volumeSignalsArchive);
  const spreadV1SignalsArchiveRaw = parseSignalRows(spreadV1SignalsArchiveCsv);
  const spreadV1SignalsArchive = dedupeLogicalSignalRows(spreadV1SignalsArchiveRaw);
  const spreadV1SignalsLive = dedupeLogicalSignalRows(parseSignalRows(spreadV1SignalsLiveCsv));
  const spreadV1SignalsClean = filterCleanSignalRows(spreadV1SignalsArchive);
  const spreadV1Queue = getActiveQueueRows(spreadV1SignalsLive);
  const spreadV1NoMatchRows = getNoMatchRows(spreadV1SignalsArchive);
  const spreadV1VisibleNoMatchRows = getNoMatchRows(spreadV1SignalsLive);
  const spreadV1SettledRows = getSettledSignalRows(spreadV1SignalsArchive);
  const spreadShadowSignalsArchiveRaw = parseSignalRows(spreadShadowSignalsArchiveCsv);
  const spreadShadowSignalsArchive = dedupeLogicalSignalRows(spreadShadowSignalsArchiveRaw);
  const spreadShadowSignalsLive = dedupeLogicalSignalRows(parseSignalRows(spreadShadowSignalsLiveCsv));
  const spreadShadowSignalsClean = filterCleanSignalRows(spreadShadowSignalsArchive);
  const spreadShadowQueue = getActiveQueueRows(spreadShadowSignalsLive);
  const challengerSignalsArchive = dedupeLogicalSignalRows(parseSignalRows(challengerSignalsArchiveCsv));
  const challengerSignalsLive = dedupeLogicalSignalRows(parseSignalRows(challengerSignalsLiveCsv));
  const challengerSignalsClean = filterCleanSignalRows(challengerSignalsArchive);
  const challengerQueue = getActiveQueueRows(challengerSignalsLive);
  const challengerNearmissRows = challengerNearmissCsv ? parseCsv(challengerNearmissCsv) : [];
  const challengerNearmissReasonCounts = Array.from(
    challengerNearmissRows.reduce((acc, row) => {
      const reason = row.skip_reason || "unknown";
      acc.set(reason, (acc.get(reason) ?? 0) + 1);
      return acc;
    }, new Map<string, number>()),
  ).sort((a, b) => b[1] - a[1]);
  const latestChallengerNearmissRows = [...challengerNearmissRows]
    .sort((a, b) => `${b.date ?? ""} ${b.time_utc ?? ""}`.localeCompare(`${a.date ?? ""} ${a.time_utc ?? ""}`))
    .slice(0, 8);
  const challengerSignalByNearmissKey = new Map(
    challengerSignalsArchive.map((row) => [
      `${row.date}|${row.player1.trim().toLowerCase()}|${row.player2.trim().toLowerCase()}|${row.side}`,
      row,
    ]),
  );
  const challengerRows = challengerPerfCsv ? parseCsv(challengerPerfCsv) : [];
  const challengerBase = parsePerf(challengerRows, "base");
  const clvChallenger = parseClvAudit(clvAuditChallengerTxt);
  const clayFavSignalsArchive = dedupeLogicalSignalRows(parseSignalRows(clayFavSignalsArchiveCsv));
  const clayFavSignalsLive = dedupeLogicalSignalRows(parseSignalRows(clayFavSignalsLiveCsv));
  const clayFavSignalsClean = filterCleanSignalRows(clayFavSignalsArchive);
  const clayFavQueue = getActiveQueueRows(clayFavSignalsLive);
  const clayFavRows = clayFavPerfCsv ? parseCsv(clayFavPerfCsv) : [];
  const clayFavBase = parsePerf(clayFavRows, "base");
  const clvClayFav = parseClvAudit(clvAuditClayFavTxt);
  const strictMlRecordedCohort = summarizeSignalCohort(strictSignalsClean, undefined, "recorded", "match");
  const strictSpreadRecordedCohort = summarizeSignalCohort(strictSignalsClean, undefined, "recorded", "spread");
  const strictMlFlatCohort = summarizeSignalCohort(strictSignalsClean, undefined, "flat", "match");
  const strictSpreadFlatCohort = summarizeSignalCohort(strictSignalsClean, undefined, "flat", "spread");
  const volumeMlRecordedCohort = summarizeSignalCohort(volumeSignalsClean, undefined, "recorded", "match");
  const volumeMlFlatCohort = summarizeSignalCohort(volumeSignalsClean, undefined, "flat", "match");
  const spreadV1SpreadRecordedCohort = summarizeSignalCohort(spreadV1SignalsClean, undefined, "recorded", "spread");
  const spreadV1SpreadFlatCohort = summarizeSignalCohort(spreadV1SignalsClean, undefined, "flat", "spread");
  const spreadShadowSpreadRecordedCohort = summarizeSignalCohort(spreadShadowSignalsClean, undefined, "recorded", "spread");
  const spreadShadowSpreadFlatCohort = summarizeSignalCohort(spreadShadowSignalsClean, undefined, "flat", "spread");
  const challengerMlRecordedCohort = summarizeSignalCohort(challengerSignalsClean, undefined, "recorded", "match");
  const clayFavSpreadRecordedCohort = summarizeSignalCohort(clayFavSignalsClean, undefined, "recorded", "spread");
  const clayFavSpreadFlatCohort = summarizeSignalCohort(clayFavSignalsClean, undefined, "flat", "spread");
  const spreadV1Status = parseJsonMaybe<SpreadV1Status>(spreadV1StatusJson);
  const clayMlAnalysis = parseClayMlAnalysis(clayMlAnalysisTxt);
  const claySpreadCalibration = parseJsonMaybe<SpreadCalibrationParams>(claySpreadCalibrationJson);
  const claySpreadCalibrationReady = claySpreadCalibration?.calibration_valid === true;
  const claySpreadOrientation = spreadV1Status?.surfaces?.clay?.orientation_breakout ?? {};
  const clayFavHandicap = claySpreadOrientation.favorite_handicap;
  const clayDogHandicap = claySpreadOrientation.dog_handicap;
  const clayScratchHandicap = claySpreadOrientation.scratch;
  const clayThresholds = spreadV1Status?.surfaces?.clay?.threshold_results ?? [];
  const clayFavCandidateStatus = claySpreadCalibrationReady ? "tracking shadow candidate" : "blocked until clay-only calibration is valid";
  const variantRow = (variant: string, profile: string) =>
    modelVariantRows.find((row) => row.variant === variant && row.profile === profile);
  const variantNumber = (row: CsvRow | undefined, key: string) => parseFloatMaybe(row?.[key]);
  const variantGenerated = modelVariantRows[0]?.generated_utc;
  const baselineVariantStrict = variantRow("baseline_current", "strict");
  const baselineVariantVolume = variantRow("baseline_current", "volume_200_hard");
  const baselineVariantHardAll = variantRow("baseline_current", "hard_edge10_all");
  const baselineVariantClayAll = variantRow("baseline_current", "clay_edge10_all");
  const modelVariantCards = [
    {
      key: "hardcal-strict",
      title: "Hard Cal Strict",
      row: variantRow("hardcal_strict_live", "strict"),
      baseline: baselineVariantStrict,
      badge: "de-promoted",
      tone: "rose",
      note: "Identity-clean regeneration makes the raw baseline better calibrated and slightly more profitable. Hard calibration is disabled pending a fresh fit.",
    },
    {
      key: "hardcal-volume",
      title: "Hard Cal Volume",
      row: variantRow("hardcal_strict_live", "volume_200_hard"),
      baseline: baselineVariantVolume,
      badge: "rejected",
      tone: "rose",
      note: "The stale calibration roughly halves identity-clean volume ROI and worsens ECE. It is not eligible for routing.",
    },
    {
      key: "h2h-strict",
      title: "H2H n>=2",
      row: variantRow("h2h_n2_shrunk", "strict"),
      baseline: baselineVariantStrict,
      badge: "shadow",
      tone: "amber",
      note: "Cleaner probability metrics, but lower strict ROI than baseline. Useful as an audit feature, not a live promotion yet.",
    },
    {
      key: "fatigue-volume",
      title: "Fatigue x1.5",
      row: variantRow("fatigue_x1.5", "volume_200_hard"),
      baseline: baselineVariantVolume,
      badge: "rejected",
      tone: "rose",
      note: "The heavier fatigue multiplier hurts volume ROI. Keep the existing conservative fatigue/rust sizing.",
    },
    {
      key: "clay-cal",
      title: "Clay Calibration",
      row: variantRow("claycal_lanes", "clay_edge10_all"),
      baseline: baselineVariantClayAll,
      badge: "blocked",
      tone: "rose",
      note: "Clay overlay is still a no-go: calibration improves shape but destroys ROI. Do not route clay ML through it.",
    },
    {
      key: "atp250-hard",
      title: "Hard ATP250 20%+",
      row: variantRow("atp250_hard_20", "atp250_hard_20"),
      baseline: baselineVariantHardAll,
      badge: "watch",
      tone: "amber",
      note: "Historically interesting but 2026 is tiny and ugly. Track only; no product claim.",
    },
  ];

  const strictAllRoi = perfValue(strictBase.combinedAll, "roi_pct", parseFloatMaybe);
  const volumeAllRoi = perfValue(volumeBase.combinedAll, "roi_pct", parseFloatMaybe);
  const spreadV1AllRoi = spreadV1SpreadRecordedCohort.roiPct;
  const spreadShadowAllRoi = perfValue(spreadShadowBase.combinedAll, "roi_pct", parseFloatMaybe);
  const strictWindowRoi = perfValue(strictBase.combinedWindow, "roi_pct", parseFloatMaybe);
  const overlayAllRoi = perfValue(strictOverlay.combinedAll, "roi_pct", parseFloatMaybe);
  const matchedMl = clv.matchedMl ?? 0;
  const auditedMl = clv.matchedMlTotal ?? clv.settledMlAudited ?? 0;
  const matchedMlVolume = clvVolume.matchedMl ?? 0;
  const auditedMlVolume = clvVolume.matchedMlTotal ?? clvVolume.settledMlAudited ?? 0;
  const matchedSpreadV1 = clvSpreadV1.matchedMl ?? 0;
  const auditedSpreadV1 = clvSpreadV1.matchedMlTotal ?? clvSpreadV1.settledMlAudited ?? 0;
  const strictAsOf = strictBase.combinedAll?.as_of_date;
  const volumeAsOf = volumeBase.combinedAll?.as_of_date;
  const spreadV1AsOf = spreadV1Base.combinedAll?.as_of_date;
  const spreadShadowAsOf = spreadShadowBase.combinedAll?.as_of_date;
  const shadowProfile = profileMap.get("volume_200");
  const legacyShadowProfile = profileMap.get("volume_275");
  const missingReports = [
    !strictPerfCsv ? "strict weekly performance" : null,
    !volumePerfCsv ? "volume_200 weekly performance" : null,
    !spreadV1PerfCsv ? "spread_v1 weekly performance" : null,
    !spreadShadowPerfCsv ? "spread shadow weekly performance" : null,
    !clvAuditTxt ? "strict CLV audit" : null,
    !clvAuditVolumeTxt ? "volume_200 CLV audit" : null,
    !clvAuditSpreadV1Txt ? "spread_v1 CLV audit" : null,
    !profileTxt ? "policy profile backtest" : null,
  ].filter(Boolean) as string[];
  const strictDiagnosis =
    strictAllRoi == null
      ? "Strict live has no settled ROI yet."
      : strictAllRoi < 0
        ? `Strict live control is negative at ${formatPct(strictAllRoi)} as of ${strictAsOf ?? "n/a"}.`
        : `Strict live control is positive at ${formatPct(strictAllRoi)} as of ${strictAsOf ?? "n/a"}.`;
  const shadowDiagnosis =
    volumeSignalsLive.length === 0
      ? "ATP ML research file is empty right now."
      : volumeQueue.length === 0 && volumeVisibleNoMatchRows.length > 0
      ? `ATP ML research has ${volumeVisibleNoMatchRows.length} live rows parked as no_match settlement mismatches, but no true live queue at the moment.`
      : perfValue(volumeBase.combinedAll, "settled", parseIntMaybe) === 0
      ? "ATP ML research has no settled sample yet."
      : `ATP ML research has settled enough to start comparing against strict on live results.`;
  const spreadShadowDiagnosis =
    `Old Spread Shadow is archived reference only (${spreadShadowSignalsArchive.length} logical rows). It is excluded from active scoreboard and latest-settled cards.`;
  const spreadV1Diagnosis =
    !spreadV1SignalsLiveCsv
      ? "Spread v1 shadow has no live CSV on disk yet."
      : spreadV1Queue.length === 0 && spreadV1VisibleNoMatchRows.length > 0
        ? `Spread v1 shadow has ${spreadV1VisibleNoMatchRows.length} live rows parked as no_match, but no true live queue right now.`
        : spreadV1SignalsLive.length === 0
          ? "Spread v1 shadow is wired in, but scheduled runs are hard-only right now and have not logged a qualifying row."
          : spreadV1SettledRows.length === 0
            ? `Spread v1 shadow has ${spreadV1SignalsArchive.length} tracked rows, but no settled spread sample yet.`
            : `Spread v1 shadow has ${spreadV1SettledRows.length} settled spreads with CLV coverage ${matchedSpreadV1}/${auditedSpreadV1 || 0}.`;
  const volumeQueueMlCount = volumeQueue.filter((row) => row.betType !== "spread").length;
  const volumeSettledMlCount =
    perfValue(volumeBase.mlAll, "settled", parseIntMaybe) ??
    volumeSignalsArchive.filter((row) => row.betType !== "spread" && (row.settlementStatus || "").trim().toLowerCase() === "settled").length;
  const volumeTrackedCount = perfValue(volumeBase.combinedAll, "signals", parseIntMaybe) ?? volumeSignalsArchive.length;
  const volumeOpenCount = volumeQueue.length;
  const volumeNoMatchCount = volumeNoMatchRows.length;
  const volumeSettledCount =
    perfValue(volumeBase.combinedAll, "settled", parseIntMaybe) ??
    volumeSignalsArchive.filter((row) => (row.settlementStatus || "").trim().toLowerCase() === "settled").length;
  const spreadV1TrackedCount = spreadV1SignalsArchive.length;
  const spreadV1SettledCount = spreadV1SettledRows.length;
  const challengerTrackedCount = challengerSignalsArchive.length;
  const challengerSettledCount = getSettledSignalRows(challengerSignalsArchive).length;
  const challengerRoiEligibleCount = challengerSignalsArchive.filter((row) => {
    if (!isSettledSignal(row) || (row.betType || "match") === "spread") return false;
    const side = (row.side || "").trim().toLowerCase();
    const odds = side === "p1" ? row.pinOdds1 : side === "p2" ? row.pinOdds2 : undefined;
    return odds != null && odds > 1;
  }).length;
  const challengerInvalidOddsCount = Math.max(0, challengerSettledCount - challengerRoiEligibleCount);
  const challengerPerfRow = challengerBase.mlAll ?? challengerBase.combinedAll;
  const clayFavTrackedCount = clayFavSignalsArchive.length;
  const clayFavSettledCount = getSettledSignalRows(clayFavSignalsArchive).length;
  const spreadShadowTrackedCount = perfValue(spreadShadowBase.combinedAll, "signals", parseIntMaybe) ?? spreadShadowSignalsArchive.length;
  const spreadShadowSettledCount = perfValue(spreadShadowBase.combinedAll, "settled", parseIntMaybe) ?? 0;
  const strictMlOpenCount = strictQueue.filter((row) => row.betType !== "spread").length;
  const strictSpreadOpenCount = strictQueue.filter((row) => row.betType === "spread").length;
  const volumeMlOpenCount = volumeQueueMlCount;
  const spreadV1OpenCount = spreadV1Queue.length;
  const challengerOpenCount = challengerQueue.length;
  const clayFavOpenCount = clayFavQueue.length;
  const spreadShadowOpenCount = spreadShadowQueue.length;
  const resultsAsOfDate =
    latestIsoDate(spreadShadowAsOf, volumeAsOf, strictAsOf) ??
    new Date().toISOString().slice(0, 10);
  const priorResultsDate = shiftIsoDate(resultsAsOfDate, -1);
  const latestSettledRows = [
    ...strictSettledRows.map((row) => ({ source: "Strict", lane: row.betType === "spread" ? "Strict Spread" : "Strict ML", accent: "rose" as const, row })),
    ...volumeSettledRows.filter((row) => row.betType !== "spread").map((row) => ({ source: "Volume 200", lane: "Volume 200 ML", accent: "amber" as const, row })),
    ...spreadV1SettledRows.map((row) => ({ source: "Spread v1", lane: "Spread v1 HC", accent: "sky" as const, row })),
  ].sort((left, right) => {
    const leftStamp = Date.parse(left.row.settledAt || "") || signalTimestamp(left.row);
    const rightStamp = Date.parse(right.row.settledAt || "") || signalTimestamp(right.row);
    return rightStamp - leftStamp;
  });
  const settledTodayRows = latestSettledRows.filter((entry) => getSettlementDate(entry.row) === resultsAsOfDate).slice(0, 10);
  const settledYesterdayRows = latestSettledRows.filter((entry) => getSettlementDate(entry.row) === priorResultsDate).slice(0, 10);
  const laneScoreRows: LaneScoreRow[] = [
    {
      policy: "Strict",
      lane: "ML",
      marketType: "Match winner",
      usageNote: "Hard Masters 1000 high-confidence strict lane.",
      settled: perfValue(strictBase.mlAll, "settled", parseIntMaybe) ?? strictMlRecordedCohort.settled,
      signals: perfValue(strictBase.mlAll, "signals", parseIntMaybe) ?? strictMlRecordedCohort.signals,
      open: perfValue(strictBase.mlAll, "unsettled", parseIntMaybe) ?? strictMlOpenCount,
      wlv: perfWlv(strictBase.mlAll),
      roi: perfValue(strictBase.mlAll, "roi_pct", parseFloatMaybe),
      flatStakePounds: strictMlFlatCohort.pnlUnits * 100,
      flatTotalStakedPounds: strictMlFlatCohort.stakedUnits * 100,
      unitTotalStakedPounds: strictMlRecordedCohort.stakedUnits * 100,
      unitStakePounds: strictMlRecordedCohort.pnlUnits * 100,
      winRate: perfValue(strictBase.mlAll, "win_rate_pct", parseFloatMaybe),
      clv: clv.avgClvPct,
      statusBadge: { tone: "ok", label: "active - hard m1000" },
    },
    {
      policy: "Strict",
      lane: "Spread",
      marketType: "Handicap",
      usageNote: "Hard Masters 1000 high-confidence handicap lane.",
      settled: perfValue(strictBase.handicapAll, "settled", parseIntMaybe) ?? strictSpreadRecordedCohort.settled,
      signals: perfValue(strictBase.handicapAll, "signals", parseIntMaybe) ?? strictSpreadRecordedCohort.signals,
      open: perfValue(strictBase.handicapAll, "unsettled", parseIntMaybe) ?? strictSpreadOpenCount,
      wlv: perfWlv(strictBase.handicapAll),
      roi: perfValue(strictBase.handicapAll, "roi_pct", parseFloatMaybe),
      flatStakePounds: strictSpreadFlatCohort.pnlUnits * 100,
      flatTotalStakedPounds: strictSpreadFlatCohort.stakedUnits * 100,
      unitTotalStakedPounds: strictSpreadRecordedCohort.stakedUnits * 100,
      unitStakePounds: strictSpreadRecordedCohort.pnlUnits * 100,
      winRate: perfValue(strictBase.handicapAll, "win_rate_pct", parseFloatMaybe),
      clvLabel: "n/a",
      statusBadge: { tone: "ok", label: "active - hard m1000" },
    },
    {
      policy: "Volume 200",
      lane: "ML",
      marketType: "Match winner",
      usageNote: "ATP main-tour ML expansion: Hard M1000, Hard ATP500, Hard Grand Slam, Clay ATP500, Grass ATP500. No Clay/Grass Slam. No handicap output.",
      settled: perfValue(volumeBase.mlAll, "settled", parseIntMaybe) ?? volumeMlRecordedCohort.settled,
      signals: perfValue(volumeBase.mlAll, "signals", parseIntMaybe) ?? volumeMlRecordedCohort.signals,
      open: perfValue(volumeBase.mlAll, "unsettled", parseIntMaybe) ?? volumeMlOpenCount,
      wlv: perfWlv(volumeBase.mlAll),
      roi: perfValue(volumeBase.mlAll, "roi_pct", parseFloatMaybe),
      flatStakePounds: volumeMlFlatCohort.pnlUnits * 100,
      flatTotalStakedPounds: volumeMlFlatCohort.stakedUnits * 100,
      unitTotalStakedPounds: volumeMlRecordedCohort.stakedUnits * 100,
      unitStakePounds: volumeMlRecordedCohort.pnlUnits * 100,
      winRate: perfValue(volumeBase.mlAll, "win_rate_pct", parseFloatMaybe),
      clv: clvVolume.avgClvPct,
      statusBadge: { tone: "ok", label: "active - atp ml" },
    },
    {
      policy: "Spread v1",
      lane: "HC",
      marketType: "Handicap",
      usageNote: "Handicap research. Scheduled hard-only right now; clay-fav slice is manual/dormant.",
      settled: spreadV1SettledCount,
      signals: spreadV1TrackedCount,
      open: spreadV1OpenCount,
      wlv: cohortWlv(spreadV1SpreadRecordedCohort),
      roi: spreadV1SpreadRecordedCohort.roiPct,
      flatStakePounds: spreadV1SpreadFlatCohort.pnlUnits * 100,
      flatTotalStakedPounds: spreadV1SpreadFlatCohort.stakedUnits * 100,
      unitTotalStakedPounds: spreadV1SpreadRecordedCohort.stakedUnits * 100,
      unitStakePounds: spreadV1SpreadRecordedCohort.pnlUnits * 100,
      winRate:
        spreadV1SpreadRecordedCohort.settled > 0
          ? (spreadV1SpreadRecordedCohort.wins / spreadV1SpreadRecordedCohort.settled) * 100
          : undefined,
      clv: clvSpreadV1.avgClvPct,
      statusBadge: { tone: "warn", label: "research - hard hc" },
    },
    ...(INTERNAL_RESEARCH_LANES
      ? [
          {
            policy: "Challenger ML v2 tracker",
            lane: "EVID",
            marketType: challengerNearmissRows.length
              ? `Outcome calibration - ${challengerNearmissRows.length} retained candidates`
              : "Outcome calibration",
            usageNote: "Zero-stake prospective evidence. Entry odds and verified-close CLV are collected; this is not a betting lane.",
            settled: perfValue(challengerPerfRow, "settled", parseIntMaybe) ?? challengerSettledCount,
            signals: perfValue(challengerPerfRow, "signals", parseIntMaybe) ?? challengerTrackedCount,
            open: perfValue(challengerPerfRow, "unsettled", parseIntMaybe) ?? challengerOpenCount,
            wlv: perfWlv(challengerPerfRow) || cohortWlv(challengerMlRecordedCohort),
            roi: undefined,
            flatStakePounds: undefined,
            flatTotalStakedPounds: undefined,
            unitTotalStakedPounds: undefined,
            unitStakePounds: undefined,
            winRate: perfValue(challengerBase.mlAll ?? challengerBase.combinedAll, "win_rate_pct", parseFloatMaybe),
            clv: clvChallenger.avgClvPct,
            clvLabel: clvChallenger.matchedMl ? `CLV n=${clvChallenger.matchedMl}` : "awaiting CLV",
            statusBadge: { tone: "muted" as const, label: "zero stake - evidence" },
          },
          {
            policy: "Clay-Fav HC (internal)",
            lane: "HC",
            marketType: "Handicap",
            settled: perfValue(clayFavBase.handicapAll ?? clayFavBase.combinedAll, "settled", parseIntMaybe) ?? clayFavSettledCount,
            signals: perfValue(clayFavBase.handicapAll ?? clayFavBase.combinedAll, "signals", parseIntMaybe) ?? clayFavTrackedCount,
            open: perfValue(clayFavBase.handicapAll ?? clayFavBase.combinedAll, "unsettled", parseIntMaybe) ?? clayFavOpenCount,
            wlv: perfWlv(clayFavBase.handicapAll ?? clayFavBase.combinedAll) || cohortWlv(clayFavSpreadRecordedCohort),
            roi: perfValue(clayFavBase.handicapAll ?? clayFavBase.combinedAll, "roi_pct", parseFloatMaybe) ?? clayFavSpreadRecordedCohort.roiPct,
            flatStakePounds: clayFavSpreadFlatCohort.pnlUnits * 100,
            flatTotalStakedPounds: clayFavSpreadFlatCohort.stakedUnits * 100,
            unitTotalStakedPounds: clayFavSpreadRecordedCohort.stakedUnits * 100,
            unitStakePounds: clayFavSpreadRecordedCohort.pnlUnits * 100,
            winRate: perfValue(clayFavBase.handicapAll ?? clayFavBase.combinedAll, "win_rate_pct", parseFloatMaybe),
            clv: clvClayFav.avgClvPct,
          },
        ]
      : []),
    {
      policy: "Spread Shadow",
      lane: "HC",
      marketType: "Handicap",
      settled: spreadShadowSettledCount,
      signals: spreadShadowTrackedCount,
      open: perfValue(spreadShadowBase.combinedAll, "unsettled", parseIntMaybe) ?? spreadShadowOpenCount,
      wlv: perfWlv(spreadShadowBase.handicapAll ?? spreadShadowBase.combinedAll),
      roi: perfValue(spreadShadowBase.handicapAll ?? spreadShadowBase.combinedAll, "roi_pct", parseFloatMaybe),
      flatStakePounds: spreadShadowSpreadFlatCohort.pnlUnits * 100,
      flatTotalStakedPounds: spreadShadowSpreadFlatCohort.stakedUnits * 100,
      unitTotalStakedPounds: spreadShadowSpreadRecordedCohort.stakedUnits * 100,
      unitStakePounds: spreadShadowSpreadRecordedCohort.pnlUnits * 100,
      winRate: perfValue(spreadShadowBase.handicapAll ?? spreadShadowBase.combinedAll, "win_rate_pct", parseFloatMaybe),
      clvLabel: "n/a",
    },
  ];
  const activeLaneScoreRows = laneScoreRows.filter(
    (row) => row.policy !== "Spread Shadow" && row.policy !== "Challenger ML v2 tracker" && !row.policy.includes("(internal)"),
  );
  const laneDetailRows = new Map<string, MonitorSignalRow[]>([
    ["Strict|ML", sortSignalRowsByCapture(strictSignalsArchive.filter((row) => row.betType !== "spread"))],
    ["Strict|Spread", sortSignalRowsByCapture(strictSignalsArchive.filter((row) => row.betType === "spread"))],
    ["Volume 200|ML", sortSignalRowsByCapture(volumeSignalsLive.filter((row) => row.betType !== "spread"))],
    ["Spread v1|HC", sortSignalRowsByCapture(spreadV1SignalsLive)],
    ["Challenger ML v2 tracker|EVID", sortSignalRowsByCapture(challengerSignalsArchive)],
    ["Clay-Fav HC (internal)|HC", sortSignalRowsByCapture(clayFavSignalsLive)],
  ]);
  const signalBrowserGroups = [
    {
      key: "volume-200-ml",
      title: "Volume 200 ML live file",
      subtitle: "Current live rows only. Historical archive rows stay in the CSV/downloads and are not rendered here.",
      accent: "amber",
      statusBadge: { tone: "ok" as const, label: "live file - current only" },
      rows: sortSignalRowsForBrowser(volumeSignalsLive.filter((row) => row.betType !== "spread")),
    },
    {
      key: "spread-v1",
      title: "Spread v1 HC live file",
      subtitle: "Current live rows only. Historical archive rows stay in the CSV/downloads and are not rendered here.",
      accent: "sky",
      statusBadge: { tone: "ok" as const, label: "live file - current only" },
      rows: sortSignalRowsForBrowser(spreadV1SignalsLive),
    },
    {
      key: "spread-shadow",
      title: "Spread Shadow Legacy",
      subtitle: "Legacy 20%+ spread shadow. Kept in files for audit history, not rendered inline to avoid stale signal confusion.",
      accent: "slate",
      statusBadge: { tone: "muted" as const, label: "dormant - audit" },
      rows: [],
    },
    ...(INTERNAL_RESEARCH_LANES
      ? [
          {
            key: "challenger-ml",
            title: "Challenger ML v2 Prospective Tracker",
            subtitle: "Zero-stake model evidence with real entry odds and verified-close CLV. Not a betting lane.",
            accent: "cyan",
            statusBadge: { tone: "muted" as const, label: "zero stake - evidence" },
            rows: sortSignalRowsForBrowser(challengerSignalsArchive),
          },
          {
            key: "clay-fav-hc",
            title: "Clay-Fav HC Internal",
            subtitle: "Manual Clay-Fav HC ledger derived from spread_v1 archive. Kept in files only; no live queue.",
            accent: "emerald",
            statusBadge: { tone: "muted" as const, label: "manual - internal" },
            rows: [],
          },
        ]
      : []),
  ];

  return (
    <div className="min-h-screen bg-[radial-gradient(circle_at_top_left,_rgba(16,185,129,0.12),_transparent_28%),radial-gradient(circle_at_top_right,_rgba(244,63,94,0.10),_transparent_22%),#0b0f14] text-slate-100">
      <div className="mx-auto max-w-7xl px-4 py-8 sm:px-6 lg:px-8">
        <div className="mb-8 flex flex-wrap items-center gap-3">
          <Link href="/fair-odds" className="inline-flex items-center rounded-full border border-slate-700/80 bg-slate-900/80 px-3 py-1.5 text-sm text-slate-300 transition-colors hover:border-emerald-500/40 hover:text-emerald-300">
            Fair Odds
          </Link>
          <Link href="/model-monitor/tennis-props" className="inline-flex items-center rounded-full border border-emerald-500/25 bg-emerald-500/10 px-3 py-1.5 text-sm text-emerald-200 transition-colors hover:border-emerald-400/40 hover:text-emerald-100">
            Aces / DFs
          </Link>
          <Link href="/model-monitor/tennis" className="inline-flex items-center rounded-full border border-teal-500/25 bg-teal-500/10 px-3 py-1.5 text-sm text-teal-200 transition-colors hover:border-teal-400/40 hover:text-teal-100">
            Tennis ML Lanes
          </Link>
          <Link href="/api/model-monitor/betting-archive" className="inline-flex items-center rounded-full border border-cyan-500/25 bg-cyan-500/10 px-3 py-1.5 text-sm text-cyan-200 transition-colors hover:border-cyan-400/40 hover:text-cyan-100">
            Download Bet Archive
          </Link>
          <Link href="/model-monitor/goalscorer" className="inline-flex items-center rounded-full border border-slate-700/80 bg-slate-900/80 px-3 py-1.5 text-sm text-slate-300 transition-colors hover:border-emerald-500/40 hover:text-emerald-300">
            Goalscorer Preview
          </Link>
          <Link href="/model-monitor/team-shots" className="inline-flex items-center rounded-full border border-slate-700/80 bg-slate-900/80 px-3 py-1.5 text-sm text-slate-300 transition-colors hover:border-emerald-500/40 hover:text-emerald-300">
            Shots / Fouls
          </Link>
          <Link href="/model-monitor/corners" className="inline-flex items-center rounded-full border border-slate-700/80 bg-slate-900/80 px-3 py-1.5 text-sm text-slate-300 transition-colors hover:border-emerald-500/40 hover:text-emerald-300">
            Corners / O-U
          </Link>
          <Link href="/model-monitor/reddit-intel" className="inline-flex items-center rounded-full border border-slate-700/80 bg-slate-900/80 px-3 py-1.5 text-sm text-slate-300 transition-colors hover:border-emerald-500/40 hover:text-emerald-300">
            Reddit Intel
          </Link>
          <Link href="/" className="inline-flex items-center rounded-full border border-slate-700/80 bg-slate-900/80 px-3 py-1.5 text-sm text-slate-300 transition-colors hover:border-emerald-500/40 hover:text-emerald-300">
            Home
          </Link>
        </div>

        <section className="mb-8 overflow-hidden rounded-3xl border border-slate-800 bg-[linear-gradient(135deg,rgba(16,185,129,0.12),rgba(15,23,42,0.92)_40%,rgba(244,63,94,0.08))] p-6 sm:p-8">
          <div className="flex flex-col gap-5 lg:flex-row lg:items-center lg:justify-between">
            <div className="max-w-3xl">
              <div className="mb-3 inline-flex items-center rounded-full border border-emerald-500/25 bg-emerald-500/10 px-3 py-1 text-xs font-semibold uppercase tracking-[0.24em] text-emerald-300">
                Model Monitor
              </div>
              <h1 className="text-3xl font-semibold tracking-tight text-white sm:text-4xl">Live control, shadow policy, CLV coverage, and historical edge in one place.</h1>
              <p className="mt-3 max-w-2xl text-sm leading-6 text-slate-300 sm:text-base">
                This page reads the generated report files directly. On localhost it reflects your latest local pipeline runs. On Vercel it only updates when those files are deployed.
              </p>
            </div>
            <div className="grid gap-2 sm:grid-cols-2">
              <FileStamp label="Strict perf" value={strictPerfMtime} />
              <FileStamp label="Shadow perf" value={volumePerfMtime} />
              <FileStamp label="Spread v1 perf" value={spreadV1PerfMtime} />
              <FileStamp label="Spread shadow perf" value={spreadShadowPerfMtime} />
              <FileStamp label="Strict CLV" value={clvAuditMtime} />
              <FileStamp label="Vol200 CLV" value={clvAuditVolumeMtime} />
              <FileStamp label="Spread v1 CLV" value={clvAuditSpreadV1Mtime} />
              <FileStamp label="Profile backtest" value={profileMtime} />
              <FileStamp label="GS eval" value={grandSlamEvalMtime} />
              <FileStamp label="Model variants" value={modelVariantsMtime} />
              <FileStamp label="Strict signals" value={strictSignalsLiveMtime} />
              <FileStamp label="Vol200 signals" value={volumeSignalsMtime} />
              <FileStamp label="Spread v1 signals" value={spreadV1SignalsMtime} />
              <FileStamp label="Spread shadow signals" value={spreadShadowSignalsMtime} />
              <FileStamp label="Spread v1 status" value={spreadV1StatusMtime} />
              <FileStamp label="Clay ML analysis" value={clayMlAnalysisMtime} />
              <FileStamp label="Clay spread calib" value={claySpreadCalibrationMtime} />
            </div>
          </div>
        </section>

        {missingReports.length > 0 ? (
          <section className="mb-8 rounded-2xl border border-amber-500/25 bg-amber-500/10 p-4 text-sm text-amber-100">
            Reports not found for: <span className="font-semibold">{missingReports.join(", ")}</span>. Run the daily/weekly pipeline locally or deploy fresh report files.
          </section>
        ) : null}

        <section className="mb-8">
          <div className="mb-3">
            <h2 className="text-xl font-semibold text-slate-100">Monitor Pages</h2>
            <p className="mt-1 text-sm text-slate-400">Direct entry points for the live model monitors and diagnostics pages.</p>
          </div>
          <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
            <Link
              href="/model-monitor/tennis"
              className="rounded-2xl border border-slate-800 bg-[linear-gradient(180deg,rgba(15,20,33,0.97),rgba(10,13,22,0.97))] p-5 transition-colors hover:border-teal-500/30"
            >
              <div className="mb-2 text-xs font-semibold uppercase tracking-[0.22em] text-teal-300">Tennis ML</div>
              <div className="text-lg font-semibold text-white">Surface Lanes</div>
              <p className="mt-2 text-sm leading-6 text-slate-400">
                Hard, clay, grass, Challenger, and indoor research-lane status with the active surface policy notes.
              </p>
            </Link>
            <Link
              href="/model-monitor/tennis#tennis-proof"
              className="rounded-2xl border border-emerald-500/25 bg-[radial-gradient(circle_at_top_left,rgba(16,185,129,0.17),transparent_38%),linear-gradient(180deg,rgba(15,20,33,0.97),rgba(10,13,22,0.97))] p-5 transition-colors hover:border-emerald-400/45"
            >
              <div className="mb-2 text-xs font-semibold uppercase tracking-[0.22em] text-emerald-300">Tennis Proof</div>
              <div className="text-lg font-semibold text-white">Lane Proof Board</div>
              <p className="mt-2 text-sm leading-6 text-slate-400">
                One-click view of which tennis lanes are live-grade, collecting, caution-only, or missing CLV proof.
              </p>
            </Link>
            <Link
              href="/model-monitor/tennis-props"
              className="rounded-2xl border border-slate-800 bg-[linear-gradient(180deg,rgba(15,20,33,0.97),rgba(10,13,22,0.97))] p-5 transition-colors hover:border-emerald-500/30"
            >
              <div className="mb-2 text-xs font-semibold uppercase tracking-[0.22em] text-emerald-300">Tennis Props</div>
              <div className="text-lg font-semibold text-white">Aces / DFs / Breaks</div>
              <p className="mt-2 text-sm leading-6 text-slate-400">
                Daily Slam player-prop projections, per-round aces/DF/break logs, Bet365 line comparison, and shadow settlement.
              </p>
            </Link>
            <Link
              href="/model-monitor/goalscorer"
              className="rounded-2xl border border-slate-800 bg-[linear-gradient(180deg,rgba(15,20,33,0.97),rgba(10,13,22,0.97))] p-5 transition-colors hover:border-emerald-500/30"
            >
              <div className="mb-2 text-xs font-semibold uppercase tracking-[0.22em] text-emerald-300">Goalscorer</div>
              <div className="text-lg font-semibold text-white">Goalscorer Monitor</div>
              <p className="mt-2 text-sm leading-6 text-slate-400">
                Snapshot-backed live bets, fixture health, penalty watchlist, and lineup diagnostics.
              </p>
            </Link>
            <Link
              href="/model-monitor/assist-value"
              className="rounded-2xl border border-slate-800 bg-[linear-gradient(180deg,rgba(15,20,33,0.97),rgba(10,13,22,0.97))] p-5 transition-colors hover:border-sky-500/30"
            >
              <div className="mb-2 flex items-center gap-2 text-xs font-semibold uppercase tracking-[0.22em] text-slate-400">
                Assist Value
                <span className="rounded-full border border-rose-500/25 bg-rose-500/10 px-2 py-0.5 text-[9px] tracking-[0.16em] text-rose-300">Paused</span>
              </div>
              <div className="text-lg font-semibold text-white">Assist Research Archive</div>
              <p className="mt-2 text-sm leading-6 text-slate-400">
                Frozen, unbacktested research lane. Scripts and source evidence are preserved for a future rebuild.
              </p>
            </Link>
            <Link
              href="/model-monitor/goalscorer/lineups"
              className="rounded-2xl border border-slate-800 bg-[linear-gradient(180deg,rgba(15,20,33,0.97),rgba(10,13,22,0.97))] p-5 transition-colors hover:border-cyan-500/30"
            >
              <div className="mb-2 text-xs font-semibold uppercase tracking-[0.22em] text-cyan-300">Lineups</div>
              <div className="text-lg font-semibold text-white">Goalscorer Lineups</div>
              <p className="mt-2 text-sm leading-6 text-slate-400">
                Fixture-by-fixture lineup states, taker context, and squad availability for goalscorer markets.
              </p>
            </Link>
            <Link
              href="/model-monitor/team-shots"
              className="rounded-2xl border border-slate-800 bg-[linear-gradient(180deg,rgba(15,20,33,0.97),rgba(10,13,22,0.97))] p-5 transition-colors hover:border-amber-500/30"
            >
              <div className="mb-2 text-xs font-semibold uppercase tracking-[0.22em] text-amber-300">Team Shots</div>
              <div className="text-lg font-semibold text-white">Team Shots Monitor</div>
              <p className="mt-2 text-sm leading-6 text-slate-400">
                Base, venue, and recent lambdas with shadow bets, settled ledger, and comparison diagnostics.
              </p>
            </Link>
            <Link
              href="/model-monitor/team-fouls"
              className="rounded-2xl border border-emerald-500/20 bg-[linear-gradient(180deg,rgba(6,78,59,0.18),rgba(10,13,22,0.97))] p-5 transition-colors hover:border-emerald-400/40"
            >
              <div className="mb-2 text-xs font-semibold uppercase tracking-[0.22em] text-emerald-300">Team Fouls F2</div>
              <div className="text-lg font-semibold text-white">Team Fouls Research Gate</div>
              <p className="mt-2 text-sm leading-6 text-slate-400">
                F1/F2 holdout accuracy, FotMob source agreement, live Bet365 market probe, and the explicit signal block.
              </p>
            </Link>
            <Link
              href="/model-monitor/gk-saves"
              className="rounded-2xl border border-sky-500/20 bg-[linear-gradient(180deg,rgba(14,116,144,0.16),rgba(10,13,22,0.97))] p-5 transition-colors hover:border-sky-400/40"
            >
              <div className="mb-2 text-xs font-semibold uppercase tracking-[0.22em] text-sky-300">Goalkeeper Saves v1</div>
              <div className="text-lg font-semibold text-white">Saves O/U Evidence</div>
              <p className="mt-2 text-sm leading-6 text-slate-400">
                Bet365 O/U lines, confirmed-starter gating, named-player settlement, ROI, true-close CLV, and promotion progress.
              </p>
            </Link>
            <Link
              href="/model-monitor/corners"
              className="rounded-2xl border border-slate-800 bg-[linear-gradient(180deg,rgba(15,20,33,0.97),rgba(10,13,22,0.97))] p-5 transition-colors hover:border-fuchsia-500/30"
            >
              <div className="mb-2 text-xs font-semibold uppercase tracking-[0.22em] text-fuchsia-300">Corners / O-U</div>
              <div className="text-lg font-semibold text-white">Corners Monitor</div>
              <p className="mt-2 text-sm leading-6 text-slate-400">
                Match corners model, settled history, Pinnacle line checks, and shortlist health in one place.
              </p>
            </Link>
          </div>
        </section>

        <div className="mb-8">
          <MonitorCard
            title="Tennis Model Variants Shadow"
            subtitle={
              variantGenerated
                ? `Generated ${variantGenerated}. Historical ATP 2022-2026 comparison only; this does not change live routing by itself.`
                : "Run scripts/tennis-model-variants-shadow.py to refresh the model-variant comparison."
            }
          >
            {modelVariantRows.length === 0 ? (
              <p className="rounded-xl border border-slate-800/80 bg-slate-950/35 p-4 text-sm text-slate-400">
                No model-variant report found. Run <span className="font-mono text-slate-200">python scripts/tennis-model-variants-shadow.py</span>.
              </p>
            ) : (
              <>
                <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
                  {modelVariantCards.map((card) => {
                    const roi = variantNumber(card.row, "tier_roi_pct");
                    const baselineRoi = variantNumber(card.baseline, "tier_roi_pct");
                    const delta = roi != null && baselineRoi != null ? roi - baselineRoi : undefined;
                    const bets = parseIntMaybe(card.row?.bets);
                    const ece = variantNumber(card.row, "ece");
                    const status = card.row?.status ?? "missing";
                    const staleSince = card.row?.stale_since;
                    const statusLabel = status === "stale_ok" && staleSince ? `stale since ${staleSince}` : status;
                    const badgeClass =
                      status === "stale_ok"
                        ? "border-amber-500/35 bg-amber-500/10 text-amber-200"
                        : card.tone === "emerald"
                        ? "border-emerald-500/35 bg-emerald-500/10 text-emerald-200"
                        : card.tone === "rose"
                          ? "border-rose-500/35 bg-rose-500/10 text-rose-200"
                          : "border-amber-500/35 bg-amber-500/10 text-amber-200";
                    return (
                      <div key={card.key} className="rounded-2xl border border-slate-800 bg-slate-950/45 p-4">
                        <div className="mb-3 flex items-start justify-between gap-3">
                          <div>
                            <h3 className="text-base font-semibold text-white">{card.title}</h3>
                            <p className={`mt-1 text-xs uppercase tracking-[0.16em] ${status === "stale_ok" ? "text-amber-300" : "text-slate-500"}`}>{statusLabel}</p>
                          </div>
                          <span className={`rounded-full border px-2 py-0.5 text-[10px] font-semibold uppercase tracking-[0.14em] ${badgeClass}`}>
                            {card.badge}
                          </span>
                        </div>
                        <div className="grid grid-cols-2 gap-2 text-sm">
                          <Stat label="Tier ROI" value={formatPct(roi)} tone={metricTone(roi)} compact />
                          <Stat label="vs Baseline" value={formatPct(delta)} tone={metricTone(delta)} compact />
                          <Stat label="Bets" value={bets != null ? `${bets}` : "n/a"} compact />
                          <Stat label="ECE" value={ece != null ? ece.toFixed(5) : "n/a"} tone={ece != null && ece <= 0.04 ? "text-emerald-300" : "text-slate-300"} compact />
                        </div>
                        <p className="mt-3 text-sm leading-6 text-slate-400">{card.note}</p>
                        {card.row?.by_year ? (
                          <div className="mt-3 rounded-xl border border-slate-800/80 bg-slate-900/55 p-3 font-mono text-[11px] leading-5 text-slate-400">
                            {card.row.by_year}
                          </div>
                        ) : null}
                      </div>
                    );
                  })}
                </div>
                <div className="mt-4 rounded-xl border border-amber-500/20 bg-amber-500/10 p-4 text-sm leading-6 text-amber-50">
                  Current interpretation: <span className="font-semibold text-white">identity-clean raw baseline is the control</span>. Hard calibration is de-promoted;
                  H2H, fatigue and tournament-cap rows are stale until regenerated through the repaired identity/history loader.
                </div>
              </>
            )}
          </MonitorCard>
        </div>

        <div className="mb-3 flex items-center justify-between gap-4">
          <div>
            <h2 className="text-xl font-semibold text-slate-100">Operations Board</h2>
            <p className="mt-1 text-sm text-slate-400">Lane-by-lane scoreboard first, latest settled results second, deeper diagnostics below.</p>
          </div>
        </div>

        <div className="mb-8">
          <MonitorCard title="Active Lane Scoreboard" subtitle="Logical picks only: repeat refreshes of the same fixture/side/lane are collapsed. Old Spread Shadow is archived below, not mixed into the active board.">
            <div className="overflow-x-auto">
              <table className="min-w-full text-sm">
                <thead>
                  <tr className="border-b border-slate-800 text-left text-[11px] uppercase tracking-[0.18em] text-slate-500">
                    <th className="px-3 py-3 font-semibold">Policy</th>
                    <th className="px-3 py-3 font-semibold">Lane</th>
                    <th className="px-3 py-3 font-semibold">Market</th>
                    <th className="px-3 py-3 font-semibold">Total Bets</th>
                    <th className="px-3 py-3 font-semibold">Signals</th>
                    <th className="px-3 py-3 font-semibold">Open</th>
                    <th className="px-3 py-3 font-semibold">W/L/V</th>
                    <th className="px-3 py-3 font-semibold">ROI</th>
                    <th className="px-3 py-3 font-semibold">Recorded P/L (GBP100/u)</th>
                    <th className="px-3 py-3 font-semibold">Win Rate</th>
                    <th className="px-3 py-3 font-semibold">CLV</th>
                  </tr>
                </thead>
                <tbody>
                  {activeLaneScoreRows.map((row) => (
                    <tr key={`${row.policy}-${row.lane}`} className="border-b border-slate-900/80 text-slate-200">
                      <td className="px-3 py-3 font-semibold text-white">
                        <div>{row.policy}</div>
                        {row.statusBadge ? (
                          <div className={`mt-1 inline-flex rounded-full border px-2 py-0.5 text-[10px] uppercase tracking-[0.14em] ${statusBadgeClass(row.statusBadge.tone)}`}>
                            {row.statusBadge.label}
                          </div>
                        ) : null}
                      </td>
                      <td className="px-3 py-3 font-mono tabular-nums text-slate-100">{row.lane}</td>
                      <td className="px-3 py-3 text-slate-300">
                        <div>{row.marketType}</div>
                        {row.usageNote ? <div className="mt-1 max-w-[18rem] text-xs leading-5 text-slate-500">{row.usageNote}</div> : null}
                      </td>
                      <td className="px-3 py-3 font-mono tabular-nums">{row.settled}</td>
                      <td className="px-3 py-3 font-mono tabular-nums text-slate-300">{row.signals}</td>
                      <td className="px-3 py-3 font-mono tabular-nums text-slate-300">{row.open}</td>
                      <td className="px-3 py-3 font-mono tabular-nums text-slate-100">{row.wlv}</td>
                      <td className={`px-3 py-3 font-mono tabular-nums ${metricTone(row.roi)}`}>{formatPct(row.roi, 2, false)}</td>
                      <td className={`px-3 py-3 font-mono tabular-nums ${metricTone(row.unitStakePounds)}`}>{formatPounds(row.unitStakePounds, 0, true)}</td>
                      <td className={`px-3 py-3 font-mono tabular-nums ${metricTone((row.winRate ?? 0) - 50)}`}>{formatPct(row.winRate, 2, false)}</td>
                      <td className={`px-3 py-3 font-mono tabular-nums ${row.clv != null ? metricTone(row.clv) : "text-slate-500"}`}>
                        {formatClvCell(row.clv, row.clvLabel ?? "n/a")}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <details className="mt-4 rounded-xl border border-slate-800/80 bg-slate-950/35 p-3">
              <summary className="cursor-pointer text-sm font-medium text-slate-200">
                Latest captured picks by lane
              </summary>
              <div className="mt-3 grid gap-3">
                {activeLaneScoreRows.map((row) => {
                  const detailRows = laneDetailRows.get(`${row.policy}|${row.lane}`) ?? [];
                  const latestRows = detailRows.slice(0, 8);
                  return (
                    <details key={`latest-lane-${row.policy}-${row.lane}`} className="rounded-xl border border-slate-800/80 bg-slate-900/55 p-3">
                      <summary className="cursor-pointer text-xs font-semibold uppercase tracking-[0.16em] text-slate-400">
                        {row.policy} {row.lane} - latest {latestRows.length || 0}
                      </summary>
                      {latestRows.length === 0 ? (
                        <p className="mt-3 text-sm text-slate-500">No captured rows are present in this lane archive.</p>
                      ) : (
                        <div className="mt-3 grid gap-2 xl:grid-cols-5">
                          {latestRows.map((pick, idx) => {
                            const pnl = signalPnlUnits(pick);
                            return (
                              <div
                                key={`${row.policy}-${row.lane}-latest-${pick.date}-${pick.timeUtc}-${pick.player1}-${pick.player2}-${pick.side}-${idx}`}
                                className="rounded-xl border border-slate-800 bg-slate-950/60 p-3"
                              >
                                <div className="mb-2 flex items-start justify-between gap-2">
                                  <div className="min-w-0">
                                    <div className="font-semibold leading-snug text-slate-100">{pick.player1} vs {pick.player2}</div>
                                    <div className="mt-1 font-mono text-[11px] text-slate-500">{pick.date} {pick.timeUtc || "00:00:00"} UTC</div>
                                  </div>
                                  <span className={`shrink-0 rounded-full border px-2 py-0.5 text-[10px] font-semibold uppercase tracking-[0.12em] ${signalStatusClass(pick)}`}>
                                    {signalStatusLabel(pick)}
                                  </span>
                                </div>
                                <div className="grid grid-cols-2 gap-2 text-xs">
                                  <div>
                                    <div className="uppercase tracking-[0.16em] text-slate-600">Pick</div>
                                    <div className="mt-0.5 font-mono text-slate-200">{signalSelectionLabel(pick)}</div>
                                  </div>
                                  <div>
                                    <div className="uppercase tracking-[0.16em] text-slate-600">Odds</div>
                                    <div className="mt-0.5 font-mono text-slate-200">{getSelectedOdds(pick)?.toFixed(3) ?? "n/a"}</div>
                                  </div>
                                  <div>
                                    <div className="uppercase tracking-[0.16em] text-slate-600">Edge</div>
                                    <div className="mt-0.5 font-mono text-amber-200">{formatPct(pick.valuePct)}</div>
                                  </div>
                                  <div>
                                    <div className="uppercase tracking-[0.16em] text-slate-600">P/L</div>
                                    <div className={`mt-0.5 font-mono ${metricTone(pnl)}`}>{pnl == null ? "pending" : formatUnits(pnl, 2)}</div>
                                  </div>
                                </div>
                              </div>
                            );
                          })}
                        </div>
                      )}
                    </details>
                  );
                })}
              </div>
            </details>
            <p className="mt-3 text-xs leading-6 text-slate-500">
              Default board uses one money column only: <span className="font-semibold text-slate-300">Recorded P/L (GBP100/u)</span>. That is the actual settled P/L from stored unit sizes with 1u = GBP100. CLV is audited on strict ML, ATP ML research, spread_v1 shadow and the zero-stake Challenger v2 cohort. Research lanes are not mixed into active counts.
            </p>
            <div className="mt-4 grid gap-3 lg:grid-cols-3">
              <div className="rounded-xl border border-slate-800/80 bg-slate-950/35 p-3 text-sm text-slate-300">
                <div className="text-[11px] uppercase tracking-[0.18em] text-slate-500">Dormant / Manual Lanes</div>
                <div className="mt-2">Spread Shadow, Challenger ML v2, Clay-Fav HC internal, and Clay Calibrated are audit/research only.</div>
                <div className="mt-1 text-slate-500">They stay browsable below, but do not pretend to be active scheduled models.</div>
              </div>
              <div className="rounded-xl border border-slate-800/80 bg-slate-950/35 p-3 text-sm text-slate-300">
                <div className="text-[11px] uppercase tracking-[0.18em] text-slate-500">Volume 200 Open</div>
                <div className="mt-2">ML {volumeMlOpenCount}</div>
                <div className="mt-1 text-slate-500">No-match rows parked: {volumeNoMatchCount}. Handicap work belongs to Spread v1 / HC research, not Volume 200.</div>
              </div>
              <div className="rounded-xl border border-slate-800/80 bg-slate-950/35 p-3 text-sm text-slate-300">
                <div className="text-[11px] uppercase tracking-[0.18em] text-slate-500">Grand Slam Coverage</div>
                <div className="mt-2">Hard Slam ML is already inside Volume 200: 229 bets, +9.97% tier ROI in the 2022-2025 profile audit.</div>
                <div className="mt-1 text-slate-500">RG / Wimbledon are not approved by current data: Clay GS -7.54%, Grass GS -13.75% in the same quick segment read.</div>
              </div>
            </div>
            <details className="mt-4 rounded-xl border border-slate-800/80 bg-slate-950/35 p-3">
              <summary className="cursor-pointer text-sm font-medium text-slate-200">Stake basis detail</summary>
              <p className="mt-2 text-xs leading-6 text-slate-500">
                Flat view assumes every settled bet risked £100. Recorded view converts the stored unit stakes into pounds at 1u = £100. When a lane uses mixed 1u and 2u staking, recorded P/L will diverge from flat P/L.
              </p>
              <div className="mt-3 grid gap-3 lg:grid-cols-2">
                {activeLaneScoreRows.map((row) => (
                  <div key={`stake-basis-${row.policy}-${row.lane}`} className="rounded-xl border border-slate-800/80 bg-slate-900/70 p-3 text-sm text-slate-300">
                    <div className="font-semibold text-slate-100">{row.policy} {row.lane}</div>
                    <div className="mt-2 grid gap-2 sm:grid-cols-2">
                      <div>
                        <div className="text-[11px] uppercase tracking-[0.18em] text-slate-500">Flat P/L (GBP100)</div>
                        <div className={`mt-1 font-mono tabular-nums ${metricTone(row.flatStakePounds)}`}>{formatPounds(row.flatStakePounds, 0, true)}</div>
                      </div>
                      <div>
                        <div className="text-[11px] uppercase tracking-[0.18em] text-slate-500">Flat Stake (GBP100)</div>
                        <div className="mt-1 font-mono tabular-nums text-slate-200">{formatPounds(row.flatTotalStakedPounds, 0, false)}</div>
                      </div>
                      <div>
                        <div className="text-[11px] uppercase tracking-[0.18em] text-slate-500">Recorded P/L (GBP100/u)</div>
                        <div className={`mt-1 font-mono tabular-nums ${metricTone(row.unitStakePounds)}`}>{formatPounds(row.unitStakePounds, 0, true)}</div>
                      </div>
                      <div>
                        <div className="text-[11px] uppercase tracking-[0.18em] text-slate-500">Recorded Stake (GBP100/u)</div>
                        <div className="mt-1 font-mono tabular-nums text-slate-200">{formatPounds(row.unitTotalStakedPounds, 0, false)}</div>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </details>
          </MonitorCard>
        </div>

        <div className="mb-8">
          <MonitorCard
            title="Grand Slam Evidence"
            subtitle={`Research-only ML split by event. ${grandSlamEval?.generated_at_utc ? `Generated ${grandSlamEval.generated_at_utc}` : "Run scripts/run-grand-slam-eval.py to refresh."}`}
          >
            {grandSlamRows.length === 0 ? (
              <p className="rounded-xl border border-slate-800/80 bg-slate-950/35 p-4 text-sm text-slate-400">
                No Grand Slam evidence file found. Run <span className="font-mono text-slate-200">python scripts/run-grand-slam-eval.py --years 2022 2023 2024 2025</span>.
              </p>
            ) : (
              <div className="grid gap-3 xl:grid-cols-5">
                {grandSlamRows.map((row) => {
                  const status = (row.status ?? "MISSING").toUpperCase();
                  const statusClass =
                    status === "PASS"
                      ? "border-emerald-500/40 bg-emerald-500/10 text-emerald-200"
                      : status === "WATCH"
                        ? "border-amber-500/40 bg-amber-500/10 text-amber-200"
                        : "border-rose-500/40 bg-rose-500/10 text-rose-200";
                  const latestYear = row.yearly?.[row.yearly.length - 1];
                  const high = row.confidence_breakdown?.high;
                  const medium = row.confidence_breakdown?.medium;
                  return (
                    <div key={row.key ?? row.label} className="rounded-2xl border border-slate-800 bg-slate-950/45 p-4">
                      <div className="mb-3 flex items-start justify-between gap-3">
                        <div>
                          <h3 className="text-base font-semibold text-white">{row.label}</h3>
                          <p className="mt-1 text-xs uppercase tracking-[0.16em] text-slate-500">{row.surface} ML</p>
                        </div>
                        <span className={`rounded-full border px-2 py-0.5 text-[10px] font-semibold uppercase tracking-[0.14em] ${statusClass}`}>
                          {status}
                        </span>
                      </div>
                      <div className="grid grid-cols-2 gap-2 text-sm">
                        <Stat label="Bets" value={`${row.bets ?? 0}`} compact />
                        <Stat label="W-L" value={`${row.wins ?? 0}-${row.losses ?? 0}`} compact />
                        <Stat label="Tier ROI" value={formatPct(row.tier_roi_pct)} tone={metricTone(row.tier_roi_pct)} compact />
                        <Stat label="Tier P/L" value={`${formatUnits(row.tier_pnl_units)} / ${(row.tier_staked_units ?? 0).toFixed(1)}u`} tone={metricTone(row.tier_pnl_units)} compact />
                      </div>
                      <div className="mt-3 rounded-xl border border-slate-800/80 bg-slate-900/50 p-3 text-xs leading-5 text-slate-400">
                        <div>Latest year: {latestYear?.year ?? "n/a"} {formatPct(latestYear?.tier_roi_pct)}</div>
                        <div>High: {high?.bets ?? 0} bets, {formatPct(high?.tier_roi_pct)} | Medium: {medium?.bets ?? 0} bets, {formatPct(medium?.tier_roi_pct)}</div>
                      </div>
                      <p className="mt-3 text-xs leading-5 text-slate-500">
                        {(row.status_reasons ?? []).join("; ") || "Meets current research evidence gate."}
                      </p>
                    </div>
                  );
                })}
              </div>
            )}
            <div className="mt-4 rounded-xl border border-slate-800/80 bg-slate-950/35 p-3 text-xs leading-5 text-slate-400">
              Gate: bets &gt;= {grandSlamEval?.criteria?.min_bets ?? 150}, tier ROI &gt;= +{grandSlamEval?.criteria?.min_tier_roi_pct ?? 5}%, positive years &gt;= {grandSlamEval?.criteria?.min_positive_years ?? 3}, latest year non-negative. This card is evidence only; it does not authorise new public signals.
            </div>
          </MonitorCard>
        </div>

        <div className="mb-8">
          <MonitorCard title="Signal Browser" subtitle="Actual captured rows by lane. This is where you inspect the matches behind each aggregate, including internal research lanes.">
            <div className="grid gap-4">
              {signalBrowserGroups.map((group) => {
                const displayedRows = group.rows.slice(0, 80);
                const accentClass =
                  group.accent === "emerald"
                    ? "border-emerald-500/25 bg-emerald-500/8 text-emerald-200"
                    : group.accent === "cyan"
                      ? "border-cyan-500/25 bg-cyan-500/8 text-cyan-200"
                      : group.accent === "sky"
                        ? "border-sky-500/25 bg-sky-500/8 text-sky-200"
                        : group.accent === "slate"
                          ? "border-slate-700/70 bg-slate-900/80 text-slate-300"
                          : "border-amber-500/25 bg-amber-500/8 text-amber-200";
                return (
                  <details
                    key={group.key}
                    open={group.rows.length > 0}
                    className="rounded-2xl border border-slate-800 bg-slate-950/35 p-4"
                  >
                    <summary className="cursor-pointer list-none">
                      <div className="flex flex-wrap items-center justify-between gap-3">
                        <div>
                          <div className="flex flex-wrap items-center gap-2">
                            <span className={`rounded-full border px-2 py-0.5 text-[10px] font-semibold uppercase tracking-[0.14em] ${accentClass}`}>
                              {group.rows.length} rows
                            </span>
                            {group.statusBadge ? (
                              <span className={`rounded-full border px-2 py-0.5 text-[10px] font-semibold uppercase tracking-[0.14em] ${statusBadgeClass(group.statusBadge.tone)}`}>
                                {group.statusBadge.label}
                              </span>
                            ) : null}
                            <h3 className="text-base font-semibold text-slate-100">{group.title}</h3>
                          </div>
                          <p className="mt-1 text-sm leading-6 text-slate-400">{group.subtitle}</p>
                        </div>
                        <div className="text-xs text-slate-500">latest {displayedRows.length} shown</div>
                      </div>
                    </summary>
                    {displayedRows.length === 0 ? (
                      <p className="mt-4 rounded-xl border border-slate-800/80 bg-slate-900/70 p-3 text-sm text-slate-400">
                        No captured rows for this lane in the current archive file.
                      </p>
                    ) : (
                      <div className="mt-4 overflow-x-auto">
                        <table className="min-w-[1100px] w-full text-sm">
                          <thead>
                            <tr className="border-b border-slate-800 text-left text-[11px] uppercase tracking-[0.18em] text-slate-500">
                              <th className="px-3 py-3 font-semibold">Signal</th>
                              <th className="px-3 py-3 font-semibold">Match</th>
                              <th className="px-3 py-3 font-semibold">Pick</th>
                              <th className="px-3 py-3 font-semibold">Odds</th>
                              <th className="px-3 py-3 font-semibold">Edge</th>
                              <th className="px-3 py-3 font-semibold">Stake</th>
                              <th className="px-3 py-3 font-semibold">Status</th>
                              <th className="px-3 py-3 font-semibold">P/L</th>
                              <th className="px-3 py-3 font-semibold">Context</th>
                            </tr>
                          </thead>
                          <tbody>
                            {displayedRows.map((row, idx) => {
                              const pnl = signalPnlUnits(row);
                              return (
                                <tr
                                  key={`${group.key}-${row.date}-${row.timeUtc}-${row.player1}-${row.player2}-${row.side}-${row.spreadLine ?? "ml"}-${idx}`}
                                  className="border-b border-slate-900/80 text-slate-200"
                                >
                                  <td className="px-3 py-3 font-mono text-xs tabular-nums text-slate-400">
                                    <div>{row.date}</div>
                                    <div>{row.timeUtc || "00:00:00"} UTC</div>
                                    {(row.refreshCount ?? 1) > 1 ? <div className="mt-1 text-amber-300">{row.refreshCount} refreshes</div> : null}
                                  </td>
                                  <td className="px-3 py-3">
                                    <div className="font-semibold text-slate-100">{row.player1} vs {row.player2}</div>
                                    <div className="mt-1 text-xs text-slate-500">Match date {row.matchDate || row.date}</div>
                                  </td>
                                  <td className="px-3 py-3 font-mono tabular-nums text-slate-100">{signalSelectionLabel(row)}</td>
                                  <td className="px-3 py-3 font-mono tabular-nums text-slate-200">{getSelectedOdds(row)?.toFixed(3) ?? "n/a"}</td>
                                  <td className="px-3 py-3 font-mono tabular-nums text-amber-200">{formatPct(row.valuePct)}</td>
                                  <td className="px-3 py-3 font-mono tabular-nums text-slate-300">{(row.stakeUnits ?? 1).toFixed(2)}u</td>
                                  <td className="px-3 py-3">
                                    <span className={`rounded-full border px-2 py-0.5 text-[10px] font-semibold uppercase tracking-[0.14em] ${signalStatusClass(row)}`}>
                                      {signalStatusLabel(row)}
                                    </span>
                                  </td>
                                  <td className={`px-3 py-3 font-mono tabular-nums ${metricTone(pnl)}`}>{pnl == null ? "pending" : formatUnits(pnl, 2)}</td>
                                  <td className="px-3 py-3 text-xs leading-5 text-slate-500">
                                    <div>{row.surface || "surface n/a"} | {row.league || "ATP"} | {row.series || "series n/a"}</div>
                                    <div>{row.confidence || "confidence n/a"} | {row.signalProfile || "profile n/a"}</div>
                                    {row.settlementNote ? <div className="mt-1 text-amber-200">{row.settlementNote}</div> : null}
                                  </td>
                                </tr>
                              );
                            })}
                          </tbody>
                        </table>
                      </div>
                    )}
                  </details>
                );
              })}
            </div>
          </MonitorCard>
        </div>

        <div className="mb-8">
          <MonitorCard title="Latest Settled Results" subtitle="Active lanes only. Repeat refreshes are collapsed into one logical pick so the same market is not shown as multiple bets.">
            <div className="grid gap-4 xl:grid-cols-2">
              {[
                { label: `Settled Today (${resultsAsOfDate})`, rows: settledTodayRows },
                { label: `Settled Yesterday (${priorResultsDate})`, rows: settledYesterdayRows },
              ].map((group) => (
                <div key={group.label} className="rounded-2xl border border-slate-800 bg-slate-950/35 p-4">
                  <div className="mb-3 flex items-center justify-between gap-3">
                    <div className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">{group.label}</div>
                    <div className="text-xs text-slate-500">{group.rows.length} logical picks</div>
                  </div>
                  {group.rows.length === 0 ? (
                    <p className="text-sm leading-6 text-slate-400">No settled rows logged for this date.</p>
                  ) : (
                    <div className="space-y-3">
                      {group.rows.map(({ source, lane, accent, row }, idx) => {
                        const selectedOdds = getSelectedOdds(row);
                        const accentClasses =
                          accent === "rose"
                            ? "border-rose-500/20 bg-rose-500/5 text-rose-200"
                            : accent === "amber"
                              ? "border-amber-500/20 bg-amber-500/5 text-amber-200"
                              : accent === "sky"
                                ? "border-sky-500/20 bg-sky-500/5 text-sky-200"
                                : "border-orange-500/20 bg-orange-500/5 text-orange-200";
                        const outcomeClasses =
                          row.betOutcome === "WIN"
                            ? "border-emerald-500/20 bg-emerald-500/10 text-emerald-300"
                            : row.betOutcome === "LOSS"
                              ? "border-rose-500/20 bg-rose-500/10 text-rose-300"
                              : "border-slate-700/80 bg-slate-900/80 text-slate-300";
                        return (
                          <div
                            key={`${group.label}-${source}-${row.date}-${row.timeUtc}-${row.settledAt}-${row.player1}-${row.player2}-${row.side}-${row.spreadLine ?? "ml"}-${idx}`}
                            className="rounded-xl border border-slate-800/80 bg-slate-900/70 p-3"
                          >
                            <div className="flex flex-wrap items-start justify-between gap-3">
                              <div>
                                <div className="flex flex-wrap items-center gap-2">
                                  <span className={`rounded-full border px-2 py-0.5 text-[10px] font-semibold uppercase tracking-[0.14em] ${accentClasses}`}>
                                    {lane}
                                  </span>
                                  <span className={`rounded-full border px-2 py-0.5 text-[10px] font-semibold uppercase tracking-[0.14em] ${outcomeClasses}`}>
                                    {row.betOutcome || "settled"}
                                  </span>
                                </div>
                                <div className="mt-2 font-semibold text-slate-100">
                                  {row.player1} vs {row.player2}
                                </div>
                                <div className="mt-1 text-xs text-slate-500">
                                  {row.surface} | {row.league || "ATP"} | {row.series} | {source}
                                  {row.claySpeedTier ? ` | ${row.claySpeedTier}` : ""}
                                  {row.settledAt ? ` | settled ${row.settledAt.replace("T", " ").slice(0, 16)} UTC` : ""}
                                  {(row.refreshCount ?? 1) > 1 ? ` | ${row.refreshCount} refreshes collapsed` : ""}
                                </div>
                              </div>
                              <div className="text-right text-sm">
                                <div className="font-semibold text-slate-100">
                                  {row.betType === "spread" ? `${row.side} ${formatSignedLine(row.spreadLine)}` : `${row.side} ML`}
                                </div>
                                <div className="mt-1 text-xs text-slate-500">
                                  @ {selectedOdds?.toFixed(3) ?? "n/a"} | edge {formatPct(row.valuePct)}
                                </div>
                              </div>
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  )}
                </div>
              ))}
            </div>
          </MonitorCard>
        </div>

        <div className="mb-8 grid gap-4 md:grid-cols-2 xl:grid-cols-3 2xl:grid-cols-6">
          <MonitorCard title="Strict Live Control" subtitle={`Clean sample first: Hard | Masters 1000 | high | public >=10%${strictAsOf ? ` | as of ${strictAsOf}` : ""}`}>
            <div className="grid gap-3">
              <Stat label="Clean ROI" value={formatPct(strictAllRoi)} tone={metricTone(strictAllRoi)} />
              <Stat label="Clean 7d ROI" value={formatPct(strictWindowRoi)} tone={metricTone(strictWindowRoi)} />
              <Stat label="Settled" value={`${perfValue(strictBase.combinedAll, "settled", parseIntMaybe) ?? 0}`} />
              <Stat label="Open" value={`${perfValue(strictBase.combinedAll, "unsettled", parseIntMaybe) ?? 0}`} />
            </div>
          </MonitorCard>

          <MonitorCard title="Volume 200 Shadow" subtitle={`Clean sample first, ATP ML expansion including Hard Grand Slam ML; no handicap lane${volumeAsOf ? ` | as of ${volumeAsOf}` : ""}`}>
            <div className="grid gap-3">
              <Stat label="Clean ROI" value={formatPct(volumeAllRoi)} tone={metricTone(volumeAllRoi)} />
              <Stat label="Tracked Rows" value={`${volumeTrackedCount}`} />
              <Stat label="Open Queue" value={`${volumeOpenCount}`} />
              <Stat label="Avg Value" value={formatPct(perfValue(volumeBase.combinedAll, "avg_value_pct", parseFloatMaybe))} tone="text-amber-300" />
            </div>
          </MonitorCard>

          <MonitorCard title="Spread v1 Shadow" subtitle={`Strict-first ATP bo3 handicap research; scheduled hard-only right now${spreadV1AsOf ? ` | as of ${spreadV1AsOf}` : ""}`}>
            <div className="grid gap-3">
              <Stat label="Clean ROI" value={formatPct(spreadV1AllRoi)} tone={metricTone(spreadV1AllRoi)} />
              <Stat label="Signals" value={`${spreadV1TrackedCount}`} />
              <Stat label="Settled" value={`${spreadV1SettledCount}`} />
              <Stat label="Unsettled" value={`${spreadV1OpenCount}`} />
              <Stat label="Hard Status" value={spreadV1Status?.surfaces?.hard?.promotion_status ?? "off"} tone="text-sky-300" />
              <Stat label="Clay Status" value={spreadV1Status?.surfaces?.clay?.promotion_status ?? "off"} tone="text-sky-300" />
            </div>
          </MonitorCard>

          <MonitorCard title="Strict CLV" subtitle="Strict ML rows only. History first, Tennis-Data fallback second.">
            <div className="grid gap-3">
              <Stat label="Matched ML" value={`${matchedMl}/${auditedMl || 0}`} tone={matchedMl > 0 ? "text-emerald-300" : "text-amber-300"} />
              <Stat label="Avg CLV" value={formatPct(clv.avgClvPct, 3)} tone={metricTone(clv.avgClvPct)} />
              <Stat label="History Rows" value={`${clv.historyRows ?? 0}`} />
              <Stat
                label="Positive Share"
                value={
                  clv.positiveClvCount != null && clv.positiveClvTotal != null
                    ? `${clv.positiveClvCount}/${clv.positiveClvTotal}`
                    : "n/a"
                }
                tone={metricTone((clv.positiveClvSharePct ?? 0) - 50)}
              />
            </div>
          </MonitorCard>

          <MonitorCard title="ATP ML CLV" subtitle="ATP-only ML research rows. Same audit path, separate shadow read.">
            <div className="grid gap-3">
              <Stat label="Matched ML" value={`${matchedMlVolume}/${auditedMlVolume || 0}`} tone={matchedMlVolume > 0 ? "text-emerald-300" : "text-amber-300"} />
              <Stat label="Avg CLV" value={formatPct(clvVolume.avgClvPct, 3)} tone={metricTone(clvVolume.avgClvPct)} />
              <Stat label="History Rows" value={`${clvVolume.historyRows ?? 0}`} />
              <Stat
                label="Positive Share"
                value={
                  clvVolume.positiveClvCount != null && clvVolume.positiveClvTotal != null
                    ? `${clvVolume.positiveClvCount}/${clvVolume.positiveClvTotal}`
                    : "n/a"
                }
                tone={metricTone((clvVolume.positiveClvSharePct ?? 0) - 50)}
              />
            </div>
          </MonitorCard>

          <MonitorCard title="Historical Summary" subtitle="Exact policy-profile backtest from current CSV outputs">
            <div className="grid gap-3">
              <Stat label="Strict Tier ROI" value={formatPct(profileMap.get("strict")?.tierRoiPct)} tone={metricTone(profileMap.get("strict")?.tierRoiPct)} />
              <Stat label="Vol200 Tier ROI" value={formatPct(profileMap.get("volume_200")?.tierRoiPct)} tone={metricTone(profileMap.get("volume_200")?.tierRoiPct)} />
              <Stat label="Vol200 Bets/Yr" value={`${profileMap.get("volume_200")?.avgPerYear?.toFixed(1) ?? "n/a"}`} />
              <Stat label="Vol275 Bets/Yr" value={`${profileMap.get("volume_275")?.avgPerYear?.toFixed(1) ?? "n/a"}`} />
            </div>
          </MonitorCard>
        </div>

        <div className="mb-8">
          <MonitorCard title="Live Performance Detail" subtitle="Current weekly settlement reports with ML vs spread split">
            <div className="grid gap-6 2xl:grid-cols-2">
              <div className="rounded-2xl border border-rose-500/20 bg-rose-500/5 p-4">
                <div className="mb-4 flex items-center justify-between">
                  <h3 className="text-base font-semibold text-white">Strict Base</h3>
                  <span className={`rounded-full px-2 py-1 text-xs font-semibold ${strictAllRoi != null && strictAllRoi < 0 ? "bg-rose-500/15 text-rose-300" : "bg-emerald-500/15 text-emerald-300"}`}>
                    control
                  </span>
                </div>
                <div className="grid gap-3 sm:grid-cols-2">
                  <Stat label="Clean ROI" value={formatPct(strictAllRoi)} tone={metricTone(strictAllRoi)} compact />
                  <Stat label="Clean 7d ROI" value={formatPct(strictWindowRoi)} tone={metricTone(strictWindowRoi)} compact />
                  <Stat label="Clean P/L" value={formatUnits(perfValue(strictBase.combinedAll, "pnl_units", parseFloatMaybe))} tone={metricTone(perfValue(strictBase.combinedAll, "pnl_units", parseFloatMaybe))} compact />
                  <Stat label="Overall W/L/V" value={perfWlv(strictBase.combinedAll)} tone="text-slate-100" compact />
                </div>
                <div className="mt-3 space-y-3">
                  <SplitBucket
                    title="ML"
                    roi={formatPct(perfValue(strictBase.mlAll, "roi_pct", parseFloatMaybe))}
                    roiTone={metricTone(perfValue(strictBase.mlAll, "roi_pct", parseFloatMaybe))}
                    wlv={perfWlv(strictBase.mlAll)}
                  />
                  <SplitBucket
                    title="Spread"
                    roi={formatPct(perfValue(strictBase.handicapAll, "roi_pct", parseFloatMaybe))}
                    roiTone={metricTone(perfValue(strictBase.handicapAll, "roi_pct", parseFloatMaybe))}
                    wlv={perfWlv(strictBase.handicapAll)}
                  />
                </div>
              </div>

              <div className="rounded-2xl border border-amber-500/20 bg-amber-500/5 p-4">
                <div className="mb-4 flex items-center justify-between">
                  <h3 className="text-base font-semibold text-white">ATP ML Research</h3>
                  <span className="rounded-full bg-amber-500/15 px-2 py-1 text-xs font-semibold text-amber-300">active candidate</span>
                </div>
                <div className="grid gap-3 sm:grid-cols-2">
                  <Stat label="Clean ROI" value={formatPct(volumeAllRoi)} tone={metricTone(volumeAllRoi)} compact />
                  <Stat label="Tracked Rows" value={`${volumeTrackedCount}`} compact />
                  <Stat label="Settled" value={`${volumeSettledCount}`} compact />
                  <Stat label="Open Queue" value={`${volumeOpenCount}`} compact />
                </div>
                <div className="mt-3 space-y-3">
                  <SplitBucket
                    title="ML"
                    roi={formatPct(perfValue(volumeBase.mlAll, "roi_pct", parseFloatMaybe))}
                    roiTone={metricTone(perfValue(volumeBase.mlAll, "roi_pct", parseFloatMaybe))}
                    wlv={perfWlv(volumeBase.mlAll)}
                  />
                </div>
                <div className="mt-3 rounded-xl border border-slate-800/80 bg-slate-950/35 p-3 text-xs text-slate-400">
                  Open queue: ML {volumeQueueMlCount}. Settled so far: ML {volumeSettledMlCount}. No-match settlement rows: {volumeNoMatchCount}. This profile is ATP-only ML expansion; handicap needs its own HC model rather than a disabled Volume 200 spread row.
                </div>
              </div>

              <div className="rounded-2xl border border-sky-500/20 bg-sky-500/5 p-4">
                <div className="mb-4 flex items-center justify-between">
                  <h3 className="text-base font-semibold text-white">Spread v1 Shadow</h3>
                  <span className="rounded-full bg-sky-500/15 px-2 py-1 text-xs font-semibold text-sky-300">active spread research</span>
                </div>
                <div className="grid gap-3 sm:grid-cols-2">
                  <Stat label="Clean ROI" value={formatPct(spreadV1AllRoi)} tone={metricTone(spreadV1AllRoi)} compact />
                  <Stat label="Signals" value={`${spreadV1TrackedCount}`} compact />
                  <Stat label="Settled" value={`${spreadV1SettledCount}`} compact />
                  <Stat label="Unsettled" value={`${spreadV1OpenCount}`} compact />
                  <Stat label="Avg Value" value={formatPct(spreadV1SpreadRecordedCohort.avgValuePct)} tone="text-sky-200" compact />
                  <Stat label="Avg CLV" value={formatPct(clvSpreadV1.avgClvPct, 3)} tone={metricTone(clvSpreadV1.avgClvPct)} compact />
                </div>
                <div className="mt-3 space-y-3">
                  <SplitBucket
                    title="Spread"
                    roi={formatPct(spreadV1SpreadRecordedCohort.roiPct)}
                    roiTone={metricTone(spreadV1SpreadRecordedCohort.roiPct)}
                    wlv={cohortWlv(spreadV1SpreadRecordedCohort)}
                  />
                  <div className="rounded-xl border border-slate-800/80 bg-slate-950/35 p-3 text-xs text-slate-400">
                    Calibration: {spreadV1Status?.calibration?.valid ? "ready" : "off"} | source {spreadV1Status?.calibration?.line_source_used || "n/a"} | hard {spreadV1Status?.surfaces?.hard?.promotion_status ?? "off"} | clay {spreadV1Status?.surfaces?.clay?.promotion_status ?? "off"} | capture {spreadV1Status?.last_spread_capture_at || "n/a"}
                  </div>
                </div>
              </div>

            </div>

            <div className="mt-6 grid gap-4 md:grid-cols-3">
              <div className="rounded-2xl border border-slate-800 bg-slate-950/35 p-4">
                <div className="mb-2 text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">Overlay reference</div>
                <div className={`text-2xl font-semibold ${metricTone(overlayAllRoi)}`}>{formatPct(overlayAllRoi)}</div>
                <p className="mt-2 text-sm text-slate-400">
                  {overlayAllRoi == null
                    ? "Overlay comparison has no settled ROI yet."
                    : `Overlay all-time ROI is ${formatPct(overlayAllRoi)} as of ${strictOverlay.combinedAll?.as_of_date ?? "n/a"}. Keep it as context, not as production proof.`}
                </p>
              </div>
              <div className="rounded-2xl border border-slate-800 bg-slate-950/35 p-4">
                <div className="mb-2 text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">Current diagnosis</div>
                <ul className="space-y-2 text-sm leading-6 text-slate-300">
                  <li>{strictDiagnosis}</li>
                  <li>{shadowDiagnosis}</li>
                  <li>{spreadV1Diagnosis}</li>
                  <li>{spreadShadowDiagnosis}</li>
                  <li>
                    The active shadow slots are now <span className="font-semibold text-amber-300">ATP-only ML research</span> and <span className="font-semibold text-sky-300">spread_v1_shadow</span>. Legacy spread_shadow stays archived for reference only.
                  </li>
                </ul>
              </div>

              <div className="rounded-2xl border border-slate-800 bg-slate-950/35 p-4">
                <div className="mb-2 text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">ATP ML Research Queue</div>
                {volumeQueue.length === 0 ? (
                  <p className="text-sm leading-6 text-slate-400">
                    {volumeVisibleNoMatchRows.length > 0
                      ? `No true open ATP ML research bets right now. ${volumeVisibleNoMatchRows.length} live rows are parked as no_match settlement mismatches instead.`
                      : "No open ATP ML research rows right now. When the active ATP-only ML candidate logs live bets, they will appear here."}
                  </p>
                ) : (
                  <div className="space-y-3">
                    {volumeQueue.slice(0, 8).map((row) => (
                      <div key={`${row.date}-${row.player1}-${row.player2}-${row.side}-${row.spreadLine}`} className="rounded-xl border border-slate-800/80 bg-slate-900/70 p-3">
                        <div className="flex items-start justify-between gap-3">
                          <div>
                            <div className="font-semibold text-slate-100">{row.player1} vs {row.player2}</div>
                            <div className="mt-1 text-xs text-slate-500">
                              {row.surface} | {row.league || "ATP"} | {row.series} | {row.confidence}
                              {row.claySpeedTier ? ` | ${row.claySpeedTier}${row.tournamentSpeedSignal != null ? ` ${row.tournamentSpeedSignal > 0 ? "+" : ""}${row.tournamentSpeedSignal.toFixed(3)}` : ""}` : ""}
                              {" | "}{row.date} {row.timeUtc}
                            </div>
                          </div>
                          <div className="text-right">
                            {row.betType === "spread" ? (
                              <>
                                <div className="text-sm font-semibold text-cyan-300">{row.side} {formatSignedLine(row.spreadLine)}</div>
                                <div className="mt-1 text-xs text-slate-500">@ {row.spreadOdds?.toFixed(3) ?? "n/a"}</div>
                              </>
                            ) : (
                              <>
                                <div className="text-sm font-semibold text-amber-300">{row.side}</div>
                                <div className="mt-1 text-xs text-slate-500">match lane</div>
                              </>
                            )}
                          </div>
                        </div>
                        <div className="mt-2 text-xs text-slate-400">
                          {row.betType === "spread" ? "spread" : "match"} | edge {formatPct(row.valuePct)} | status {(row.settlementStatus || "pending").replace(/_/g, " ")}
                        </div>
                        {row.settlementNote ? (
                          <div className="mt-1 text-[11px] text-slate-500">{row.settlementNote}</div>
                        ) : null}
                      </div>
                    ))}
                  </div>
                )}
                {volumeVisibleNoMatchRows.length > 0 ? (
                  <div className="mt-4 rounded-xl border border-rose-500/20 bg-rose-500/5 p-3">
                    <div className="text-xs font-semibold uppercase tracking-[0.18em] text-rose-300">Settlement Mismatch</div>
                    <p className="mt-2 text-sm leading-6 text-slate-300">
                      {volumeVisibleNoMatchRows.length} live volume_200 rows are tagged <span className="font-semibold text-rose-200">no_match</span>. They were generated by the model, but the settlement step did not find a matching OnCourt row yet.
                    </p>
                    <div className="mt-3 space-y-2">
                      {volumeVisibleNoMatchRows.slice(0, 5).map((row) => (
                        <div key={`nomatch-${row.date}-${row.player1}-${row.player2}-${row.side}-${row.spreadLine}`} className="rounded-lg border border-slate-800/80 bg-slate-900/70 px-3 py-2 text-sm text-slate-300">
                          <div className="font-medium text-slate-100">{row.player1} vs {row.player2}</div>
                          <div className="mt-1 text-xs text-slate-500">
                            {row.date} {row.timeUtc} | {row.surface} | {row.league || "ATP"} | {row.series} | {row.side} | {row.betType === "spread" ? `spread ${formatSignedLine(row.spreadLine)}` : "match"}
                          </div>
                          {row.settlementNote ? <div className="mt-1 text-[11px] text-rose-200/80">{row.settlementNote}</div> : null}
                        </div>
                      ))}
                    </div>
                  </div>
                ) : null}
              </div>

              <div className="rounded-2xl border border-slate-800 bg-slate-950/35 p-4">
                <div className="mb-2 text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">Spread v1 Queue</div>
                {spreadV1Queue.length === 0 ? (
                  <p className="text-sm leading-6 text-slate-400">
                    {spreadV1SignalsLiveCsv
                      ? "No open spread_v1_shadow bets right now. When a strict-first ATP bo3 hard handicap qualifies, it will appear here."
                      : "No spread_v1 shadow CSV on disk right now. That usually means the lane has not written a qualifying row yet."}
                  </p>
                ) : (
                  <div className="space-y-3">
                    {spreadV1Queue.slice(0, 6).map((row) => (
                      <div key={`${row.date}-${row.player1}-${row.player2}-${row.side}-${row.spreadLine}`} className="rounded-xl border border-slate-800/80 bg-slate-900/70 p-3">
                        <div className="flex items-start justify-between gap-3">
                          <div>
                            <div className="font-semibold text-slate-100">{row.player1} vs {row.player2}</div>
                            <div className="mt-1 text-xs text-slate-500">
                              {row.surface} | {row.league || "ATP"} | {row.series} | {row.confidence}
                              {row.claySpeedTier ? ` | ${row.claySpeedTier}${row.tournamentSpeedSignal != null ? ` ${row.tournamentSpeedSignal > 0 ? "+" : ""}${row.tournamentSpeedSignal.toFixed(3)}` : ""}` : ""}
                              {" | "}{row.date} {row.timeUtc}
                            </div>
                          </div>
                          <div className="text-right">
                            <div className="text-sm font-semibold text-sky-300">{row.side} {formatSignedLine(row.spreadLine)}</div>
                            <div className="mt-1 text-xs text-slate-500">@ {row.spreadOdds?.toFixed(3) ?? "n/a"}</div>
                          </div>
                        </div>
                        <div className="mt-2 text-xs text-slate-400">
                          edge {formatPct(row.valuePct)} | status {(row.settlementStatus || "pending").replace(/_/g, " ")}
                        </div>
                      </div>
                    ))}
                  </div>
                )}
                <div className="mt-4 rounded-xl border border-slate-800/80 bg-slate-950/35 p-3 text-xs text-slate-400">
                  Hard: {spreadV1Status?.surfaces?.hard?.promotion_status ?? "off"} | Clay: {spreadV1Status?.surfaces?.clay?.promotion_status ?? "off"} | Hard thr {spreadV1Status?.surfaces?.hard?.recommended_threshold_pct ?? "n/a"} | Clay thr {spreadV1Status?.surfaces?.clay?.recommended_threshold_pct ?? "n/a"}
                </div>
              </div>
            </div>
          </MonitorCard>
        </div>

        {INTERNAL_RESEARCH_LANES ? (
          <div className="mb-8">
            <MonitorCard title="Challenger ML v2 Prospective Tracker" subtitle="Fresh zero-stake evidence with immutable entry prices, nightly settlement and verified-close CLV.">
              <div className="grid gap-4 xl:grid-cols-[0.85fr_1.15fr]">
                <div className="rounded-2xl border border-fuchsia-400/25 bg-fuchsia-400/5 p-4">
                  <div className="mb-4 flex items-start justify-between gap-3">
                    <div>
                      <h3 className="text-base font-semibold text-white">Current Challenger v2 cohort</h3>
                      <p className="mt-1 text-sm leading-6 text-slate-400">
                        Tracks the current production hybrid prospectively at zero stake. The failed legacy batch is frozen outside this cohort.
                      </p>
                    </div>
                    <span className="rounded-full border border-fuchsia-400/30 bg-fuchsia-400/10 px-2 py-1 text-xs font-semibold uppercase tracking-[0.14em] text-fuchsia-200">
                      internal
                    </span>
                  </div>
                  <div className="grid gap-3 sm:grid-cols-2">
                    <Stat label="Tracked signals" value={`${challengerTrackedCount}`} compact />
                    <Stat label="Open signals" value={`${challengerOpenCount}`} tone={challengerOpenCount > 0 ? "text-fuchsia-200" : "text-slate-300"} compact />
                    <Stat label="Settled signals" value={`${challengerSettledCount}`} compact />
                    <Stat label="Near-miss shadow rows" value={`${challengerNearmissRows.length}`} tone={challengerNearmissRows.length > 0 ? "text-amber-300" : "text-slate-300"} compact />
                    <Stat label="Odds-matched rows" value={`${challengerRoiEligibleCount}/${challengerSettledCount}`} tone={challengerInvalidOddsCount > 0 ? "text-amber-300" : "text-slate-300"} compact />
                    <Stat label="ROI claim" value="not authorised" tone="text-amber-300" compact />
                    <Stat label="CLV proof" value={clvChallenger.matchedMl ? `${formatSignedLine(clvChallenger.avgClvPct)}% (n=${clvChallenger.matchedMl})` : "awaiting sample"} tone="text-amber-300" compact />
                  </div>
                  <div className="mt-4 rounded-xl border border-slate-800/80 bg-slate-950/45 p-3 text-xs leading-5 text-slate-400">
                    Locked cohort: Challenger singles, HIGH coverage, high confidence, value 10-15%, 0u. Promotion requires at least 300 CLV-eligible forecasts, mean CLV +1% or better, at least 52% beating close, ECE at most 0.03 and log loss no worse than Pinnacle.
                  </div>
                </div>

                <div className="rounded-2xl border border-slate-800 bg-slate-950/35 p-4">
                  <div className="mb-4 flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
                    <div>
                      <h3 className="text-base font-semibold text-white">Near-miss reasons</h3>
                      <p className="mt-1 text-sm leading-6 text-slate-400">
                        These are candidates that hit the Challenger universe but failed one gate. They are retained so the gate can be judged with actual outcomes, not to imply a current betting edge.
                      </p>
                    </div>
                    <div className="flex flex-wrap gap-2">
                      {challengerNearmissReasonCounts.length ? (
                        challengerNearmissReasonCounts.map(([reason, count]) => (
                          <span key={reason} className="rounded-full border border-slate-700/80 bg-slate-900/80 px-2 py-1 text-xs text-slate-300">
                            {challengerSkipReasonLabel(reason)} <span className="text-slate-500">{count}</span>
                          </span>
                        ))
                      ) : (
                        <span className="rounded-full border border-slate-700/80 bg-slate-900/80 px-2 py-1 text-xs text-slate-400">
                          no near-misses
                        </span>
                      )}
                    </div>
                  </div>
                  {latestChallengerNearmissRows.length ? (
                    <div className="overflow-hidden rounded-xl border border-slate-800/80">
                      <table className="w-full text-left text-xs">
                        <thead className="border-b border-slate-800 bg-slate-900/80 text-slate-500">
                          <tr>
                            <th className="px-3 py-2 font-semibold uppercase tracking-[0.16em]">Match</th>
                            <th className="px-3 py-2 font-semibold uppercase tracking-[0.16em]">Tag</th>
                            <th className="px-3 py-2 font-semibold uppercase tracking-[0.16em]">Edge</th>
                            <th className="px-3 py-2 font-semibold uppercase tracking-[0.16em]">Coverage</th>
                            <th className="px-3 py-2 font-semibold uppercase tracking-[0.16em]">Reason</th>
                            <th className="px-3 py-2 font-semibold uppercase tracking-[0.16em]">Result</th>
                            <th className="px-3 py-2 font-semibold uppercase tracking-[0.16em]">Odds</th>
                          </tr>
                        </thead>
                        <tbody className="divide-y divide-slate-800/80">
                          {latestChallengerNearmissRows.map((row) => {
                            const settledRow = challengerSignalByNearmissKey.get(
                              `${row.date}|${(row.player1 || "").trim().toLowerCase()}|${(row.player2 || "").trim().toLowerCase()}|${row.side}`,
                            );
                            const side = (row.side || "").toLowerCase();
                            const odds = side === "p1" ? settledRow?.pinOdds1 : side === "p2" ? settledRow?.pinOdds2 : undefined;
                            return (
                              <tr key={`${row.date}-${row.player1}-${row.player2}-${row.skip_reason}`} className="text-slate-300">
                                <td className="px-3 py-2">
                                  <div className="font-medium text-slate-100">{row.player1} vs {row.player2}</div>
                                  <div className="mt-0.5 text-[11px] text-slate-500">{row.surface || "surface?"} | {row.series || row.tour_name || "tournament?"}</div>
                                </td>
                                <td className="px-3 py-2 font-mono">{row.data_coverage_tag || "n/a"}</td>
                                <td className={`px-3 py-2 font-mono ${metricTone(parseFloatMaybe(row.value_pct))}`}>{formatPct(parseFloatMaybe(row.value_pct))}</td>
                                <td className="px-3 py-2 font-mono text-[11px] text-slate-400">
                                  s {row.match_count_12m_p1 || "?"}/{row.match_count_12m_p2 || "?"} | total {row.matches_total_p1 || "?"}/{row.matches_total_p2 || "?"} | days {row.last_match_days_p1 || "?"}/{row.last_match_days_p2 || "?"}
                                </td>
                                <td className="px-3 py-2">
                                  <span className="rounded border border-amber-500/25 bg-amber-500/10 px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-[0.12em] text-amber-200">
                                    {challengerSkipReasonLabel(row.skip_reason)}
                                  </span>
                                </td>
                                <td className="px-3 py-2 font-mono text-[11px]">
                                  {settledRow?.settlementStatus === "settled" ? (
                                    <span className={settledRow.betOutcome === "WIN" ? "text-emerald-300" : "text-rose-300"}>
                                      {settledRow.betOutcome || "settled"}
                                    </span>
                                  ) : (
                                    <span className="text-slate-500">{settledRow?.settlementStatus || "pending"}</span>
                                  )}
                                </td>
                                <td className="px-3 py-2 font-mono text-[11px] text-slate-300">
                                  {odds != null && odds > 1 ? odds.toFixed(3) : <span className="text-amber-300">missing</span>}
                                </td>
                              </tr>
                            );
                          })}
                        </tbody>
                      </table>
                    </div>
                  ) : (
                    <div className="rounded-xl border border-slate-800/80 bg-slate-950/45 p-4 text-sm text-slate-400">
                      No Challenger near-miss file yet. Once the daily runner executes with CHALLENGER_ML_ENABLE=1, this panel should populate even if no live signal passes.
                    </div>
                  )}
                </div>
              </div>
            </MonitorCard>
          </div>
        ) : null}

        <div className="mb-8">
          <MonitorCard title="Clay Tennis Research Watch" subtitle="Clay ML is paused; clay favourite handicap is tracked as a gated research candidate only.">
            <div className="grid gap-4 xl:grid-cols-[0.85fr_1.15fr]">
              <div className="rounded-2xl border border-orange-500/25 bg-orange-500/5 p-4">
                <div className="mb-4 flex items-start justify-between gap-3">
                  <div>
                    <h3 className="text-base font-semibold text-white">Clay ML calibrated lane</h3>
                    <p className="mt-1 text-sm leading-6 text-slate-400">
                      Held off by default. The latest calibration diagnostic says the 2025 holdout is not good enough to restart this lane.
                    </p>
                  </div>
                  <span className="rounded-full border border-orange-400/30 bg-orange-400/10 px-2 py-1 text-xs font-semibold uppercase tracking-[0.14em] text-orange-200">
                    paused
                  </span>
                </div>
                <div className="grid gap-3 sm:grid-cols-2">
                  <Stat label="Holdout ECE" value={clayMlAnalysis.holdoutEce != null ? clayMlAnalysis.holdoutEce.toFixed(4) : "n/a"} tone={clayMlAnalysis.holdoutEce != null && clayMlAnalysis.holdoutEce > 0.05 ? "text-rose-300" : "text-emerald-300"} compact />
                  <Stat label="Log-loss vs Pin" value={clayMlAnalysis.logLossDelta != null ? `${clayMlAnalysis.logLossDelta >= 0 ? "+" : ""}${clayMlAnalysis.logLossDelta.toFixed(4)}` : "n/a"} tone={metricTone((clayMlAnalysis.logLossDelta ?? 0) * -1)} compact />
                  <Stat label="Generated" value={clayMlAnalysis.generatedAt ? clayMlAnalysis.generatedAt.slice(0, 10) : "n/a"} compact />
                  <Stat label="Default" value="off" tone="text-orange-200" compact />
                </div>
                <div className="mt-4 rounded-xl border border-slate-800/80 bg-slate-950/45 p-3 text-sm leading-6 text-slate-300">
                  {clayMlAnalysis.verdict ?? "No clay ML diagnostic verdict found. Keep this lane off until the analysis file is generated."}
                </div>
              </div>

              <div className="rounded-2xl border border-emerald-500/20 bg-emerald-500/5 p-4">
                <div className="mb-4 flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
                  <div>
                    <h3 className="text-base font-semibold text-white">Clay favourite-handicap candidate</h3>
                    <p className="mt-1 text-sm leading-6 text-slate-400">
                      The monitor tracks the exact split Claude asked for: favourite handicap versus dog and scratch. Fav HC is the only positive clay spread cluster so far.
                    </p>
                  </div>
                  <span className={`rounded-full border px-2 py-1 text-xs font-semibold uppercase tracking-[0.14em] ${claySpreadCalibrationReady ? "border-emerald-400/30 bg-emerald-400/10 text-emerald-200" : "border-amber-400/30 bg-amber-400/10 text-amber-200"}`}>
                    {clayFavCandidateStatus}
                  </span>
                </div>
                <div className="grid gap-3 lg:grid-cols-3">
                  <SpreadOrientationCard
                    title="Favourite handicap"
                    summary={clayFavHandicap}
                    tone="border-emerald-500/25"
                    note="Candidate lane: fav HC, high confidence, 2.0-3.5 games, 8-18% edge."
                  />
                  <SpreadOrientationCard
                    title="Dog handicap"
                    summary={clayDogHandicap}
                    tone="border-rose-500/25"
                    note="Blocked from clay candidate scope unless future calibration proves otherwise."
                  />
                  <SpreadOrientationCard
                    title="Scratch / near-zero"
                    summary={clayScratchHandicap}
                    tone="border-slate-700/80"
                    note="Blocked; this bucket is too noisy for clay handicap promotion."
                  />
                </div>
                <div className="mt-4 grid gap-3 lg:grid-cols-[0.8fr_1.2fr]">
                  <div className="rounded-xl border border-slate-800/80 bg-slate-950/45 p-3 text-sm leading-6 text-slate-300">
                    <div className="text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-500">Calibration gate</div>
                    <div className="mt-2">
                      Clay-only spread calibration: <span className={claySpreadCalibrationReady ? "font-semibold text-emerald-300" : "font-semibold text-amber-300"}>{claySpreadCalibrationReady ? "valid" : "missing / invalid"}</span>
                    </div>
                    <div className="mt-1 text-slate-500">
                      File: spread-v1-clay-calibration-params.json. Source {claySpreadCalibration?.line_source_used ?? "n/a"}, reason {claySpreadCalibration?.calibration_reason ?? "n/a"}.
                    </div>
                    <div className="mt-3 text-xs text-slate-500">
                      No public output. This is monitor-only research until sample, CLV, and calibration gates pass.
                    </div>
                  </div>
                  <div className="overflow-hidden rounded-xl border border-slate-800/80 bg-slate-950/45">
                    <table className="w-full text-left text-xs">
                      <thead className="border-b border-slate-800 bg-slate-900/80 text-slate-500">
                        <tr>
                          <th className="px-3 py-2 font-semibold uppercase tracking-[0.16em]">Clay edge gate</th>
                          <th className="px-3 py-2 font-semibold uppercase tracking-[0.16em]">n</th>
                          <th className="px-3 py-2 font-semibold uppercase tracking-[0.16em]">ROI</th>
                          <th className="px-3 py-2 font-semibold uppercase tracking-[0.16em]">Roll20</th>
                          <th className="px-3 py-2 font-semibold uppercase tracking-[0.16em]">CLV</th>
                          <th className="px-3 py-2 font-semibold uppercase tracking-[0.16em]">Ready</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-slate-800/80">
                        {clayThresholds.slice(0, 6).map((row) => (
                          <tr key={`clay-threshold-${row.threshold_pct}`} className="text-slate-300">
                            <td className="px-3 py-2 font-mono">{row.threshold_pct != null ? `${row.threshold_pct.toFixed(0)}%+` : "n/a"}</td>
                            <td className="px-3 py-2 font-mono">{row.settled ?? 0}</td>
                            <td className={`px-3 py-2 font-mono ${metricTone(row.roi_pct)}`}>{formatPct(row.roi_pct)}</td>
                            <td className={`px-3 py-2 font-mono ${metricTone(row.rolling_20_roi_pct)}`}>{formatPct(row.rolling_20_roi_pct)}</td>
                            <td className={`px-3 py-2 font-mono ${metricTone(row.avg_clv_pct)}`}>{formatPct(row.avg_clv_pct, 3)}</td>
                            <td className="px-3 py-2">{row.live_ready ? <span className="text-emerald-300">yes</span> : <span className="text-slate-500">no</span>}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              </div>
            </div>
          </MonitorCard>
        </div>

        <div className="mb-8 grid gap-6 2xl:grid-cols-2">
          <MonitorCard title="Strict CLV Coverage" subtitle="This decides whether strict live-vs-backtest drift can be diagnosed cleanly">
            <div className="rounded-2xl border border-slate-800 bg-slate-950/35 p-4">
              <div className="grid gap-3 sm:grid-cols-2">
                <Stat label="Strict Rows" value={`${clv.rawRows ?? 0}`} compact />
                <Stat label="Settled ML Audited" value={`${clv.settledMlAudited ?? 0}`} compact />
                <Stat label="Matched ML" value={`${matchedMl}/${auditedMl || 0}`} tone={matchedMl > 0 ? "text-emerald-300" : "text-amber-300"} compact />
                <Stat label="History Captures" value={`${clv.historyRows ?? 0}`} compact />
                <Stat label="Avg CLV" value={formatPct(clv.avgClvPct, 3)} tone={metricTone(clv.avgClvPct)} compact />
                <Stat label="Median CLV" value={formatPct(clv.medianClvPct, 3)} tone={metricTone(clv.medianClvPct)} compact />
                <Stat
                  label="Positive Share"
                  value={
                    clv.positiveClvCount != null && clv.positiveClvTotal != null
                      ? `${clv.positiveClvCount}/${clv.positiveClvTotal} (${formatPct(clv.positiveClvSharePct, 2)})`
                      : "n/a"
                  }
                  tone={metricTone((clv.positiveClvSharePct ?? 0) - 50)}
                  compact
                />
                <Stat label="Avg Odds Move" value={formatPct(clv.avgOddsMovePct, 3)} tone={metricTone(clv.avgOddsMovePct)} compact />
              </div>
              <div className="mt-4 grid gap-3 md:grid-cols-3">
                <div className="rounded-xl border border-slate-800/80 bg-slate-900/70 p-3 text-sm text-slate-300">
                  <div className="text-[11px] uppercase tracking-[0.18em] text-slate-500">Signals</div>
                  <div className="mt-1">{clv.signalDateRange ?? "n/a"}</div>
                </div>
                <div className="rounded-xl border border-slate-800/80 bg-slate-900/70 p-3 text-sm text-slate-300">
                  <div className="text-[11px] uppercase tracking-[0.18em] text-slate-500">Settled Matches</div>
                  <div className="mt-1">{clv.matchDateRange ?? "n/a"}</div>
                </div>
                <div className="rounded-xl border border-slate-800/80 bg-slate-900/70 p-3 text-sm text-slate-300">
                  <div className="text-[11px] uppercase tracking-[0.18em] text-slate-500">Tennis-Data Close Range</div>
                  <div className="mt-1">{clv.closingDateRange ?? "n/a"}</div>
                </div>
              </div>
              <div className="mt-4 rounded-2xl border border-amber-500/20 bg-amber-500/8 p-4 text-sm leading-6 text-amber-100">
                {clv.warning ?? "No CLV coverage warning present."}
              </div>
            </div>
          </MonitorCard>

          <MonitorCard title="Volume 200 CLV Coverage" subtitle="Same CLV read, but for the shadow profile rather than strict">
            <div className="rounded-2xl border border-slate-800 bg-slate-950/35 p-4">
              <div className="grid gap-3 sm:grid-cols-2">
                <Stat label="Shadow Rows" value={`${clvVolume.rawRows ?? 0}`} compact />
                <Stat label="Settled ML Audited" value={`${clvVolume.settledMlAudited ?? 0}`} compact />
                <Stat label="Matched ML" value={`${matchedMlVolume}/${auditedMlVolume || 0}`} tone={matchedMlVolume > 0 ? "text-emerald-300" : "text-amber-300"} compact />
                <Stat label="History Captures" value={`${clvVolume.historyRows ?? 0}`} compact />
                <Stat label="Avg CLV" value={formatPct(clvVolume.avgClvPct, 3)} tone={metricTone(clvVolume.avgClvPct)} compact />
                <Stat label="Median CLV" value={formatPct(clvVolume.medianClvPct, 3)} tone={metricTone(clvVolume.medianClvPct)} compact />
                <Stat
                  label="Positive Share"
                  value={
                    clvVolume.positiveClvCount != null && clvVolume.positiveClvTotal != null
                      ? `${clvVolume.positiveClvCount}/${clvVolume.positiveClvTotal} (${formatPct(clvVolume.positiveClvSharePct, 2)})`
                      : "n/a"
                  }
                  tone={metricTone((clvVolume.positiveClvSharePct ?? 0) - 50)}
                  compact
                />
                <Stat label="Avg Odds Move" value={formatPct(clvVolume.avgOddsMovePct, 3)} tone={metricTone(clvVolume.avgOddsMovePct)} compact />
              </div>
              <div className="mt-4 grid gap-3 md:grid-cols-3">
                <div className="rounded-xl border border-slate-800/80 bg-slate-900/70 p-3 text-sm text-slate-300">
                  <div className="text-[11px] uppercase tracking-[0.18em] text-slate-500">Signals</div>
                  <div className="mt-1">{clvVolume.signalDateRange ?? "n/a"}</div>
                </div>
                <div className="rounded-xl border border-slate-800/80 bg-slate-900/70 p-3 text-sm text-slate-300">
                  <div className="text-[11px] uppercase tracking-[0.18em] text-slate-500">Settled Matches</div>
                  <div className="mt-1">{clvVolume.matchDateRange ?? "n/a"}</div>
                </div>
                <div className="rounded-xl border border-slate-800/80 bg-slate-900/70 p-3 text-sm text-slate-300">
                  <div className="text-[11px] uppercase tracking-[0.18em] text-slate-500">Tennis-Data Close Range</div>
                  <div className="mt-1">{clvVolume.closingDateRange ?? "n/a"}</div>
                </div>
              </div>
              <div className="mt-4 rounded-2xl border border-amber-500/20 bg-amber-500/8 p-4 text-sm leading-6 text-amber-100">
                {clvVolume.warning ?? "No CLV coverage warning present."}
              </div>
            </div>
          </MonitorCard>

          <MonitorCard title="Spread v1 CLV Coverage" subtitle="Captured Pinnacle spread history only. No synthetic close fallback.">
            <div className="rounded-2xl border border-slate-800 bg-slate-950/35 p-4">
              <div className="grid gap-3 sm:grid-cols-2">
                <Stat label="Spread Rows" value={`${clvSpreadV1.rawRows ?? 0}`} compact />
                <Stat label="Settled Spread Audited" value={`${clvSpreadV1.settledMlAudited ?? 0}`} compact />
                <Stat label="Matched Spread" value={`${matchedSpreadV1}/${auditedSpreadV1 || 0}`} tone={matchedSpreadV1 > 0 ? "text-emerald-300" : "text-amber-300"} compact />
                <Stat label="History Captures" value={`${clvSpreadV1.historyRows ?? 0}`} compact />
                <Stat label="Avg CLV" value={formatPct(clvSpreadV1.avgClvPct, 3)} tone={metricTone(clvSpreadV1.avgClvPct)} compact />
                <Stat label="Median CLV" value={formatPct(clvSpreadV1.medianClvPct, 3)} tone={metricTone(clvSpreadV1.medianClvPct)} compact />
                <Stat
                  label="Positive Share"
                  value={
                    clvSpreadV1.positiveClvCount != null && clvSpreadV1.positiveClvTotal != null
                      ? `${clvSpreadV1.positiveClvCount}/${clvSpreadV1.positiveClvTotal} (${formatPct(clvSpreadV1.positiveClvSharePct, 2)})`
                      : "n/a"
                  }
                  tone={metricTone((clvSpreadV1.positiveClvSharePct ?? 0) - 50)}
                  compact
                />
                <Stat label="Avg Odds Move" value={formatPct(clvSpreadV1.avgOddsMovePct, 3)} tone={metricTone(clvSpreadV1.avgOddsMovePct)} compact />
              </div>
              <div className="mt-4 grid gap-3 md:grid-cols-3">
                <div className="rounded-xl border border-slate-800/80 bg-slate-900/70 p-3 text-sm text-slate-300">
                  <div className="text-[11px] uppercase tracking-[0.18em] text-slate-500">Signals</div>
                  <div className="mt-1">{clvSpreadV1.signalDateRange ?? "n/a"}</div>
                </div>
                <div className="rounded-xl border border-slate-800/80 bg-slate-900/70 p-3 text-sm text-slate-300">
                  <div className="text-[11px] uppercase tracking-[0.18em] text-slate-500">Settled Matches</div>
                  <div className="mt-1">{clvSpreadV1.matchDateRange ?? "n/a"}</div>
                </div>
                <div className="rounded-xl border border-slate-800/80 bg-slate-900/70 p-3 text-sm text-slate-300">
                  <div className="text-[11px] uppercase tracking-[0.18em] text-slate-500">Capture / Close Range</div>
                  <div className="mt-1">{clvSpreadV1.closingDateRange ?? spreadV1Status?.last_spread_capture_at ?? "n/a"}</div>
                </div>
              </div>
              <div className="mt-4 rounded-2xl border border-sky-500/20 bg-sky-500/8 p-4 text-sm leading-6 text-sky-100">
                {clvSpreadV1.warning ?? "Spread v1 CLV uses captured Pinnacle spread history and exact line matching in signal orientation."}
              </div>
            </div>
          </MonitorCard>
        </div>

        <MonitorCard title="Historical Policy Profiles Detail" subtitle="Exact 2022-2025 ATP ML-only backtest from generated backtest CSVs">
          <div className="grid gap-4 lg:grid-cols-3">
            {profiles.map((profile) => (
              <div key={profile.name} className="rounded-2xl border border-slate-800 bg-slate-950/35 p-4">
                <div className="mb-4 flex items-center justify-between">
                  <h3 className="text-base font-semibold text-white">{profile.name}</h3>
                  <span className={`rounded-full px-2 py-1 text-xs font-semibold ${profile.name === "volume_200" ? "bg-amber-500/15 text-amber-300" : "bg-slate-800 text-slate-300"}`}>
                    {profile.name === "volume_200" ? "active shadow" : "reference"}
                  </span>
                </div>
                <div className="grid gap-3 sm:grid-cols-2">
                  <Stat label="Tier ROI" value={formatPct(profile.tierRoiPct)} tone={metricTone(profile.tierRoiPct)} />
                  <Stat label="Flat ROI" value={formatPct(profile.flatRoiPct)} tone={metricTone(profile.flatRoiPct)} />
                  <Stat label="Bets" value={`${profile.bets ?? 0}`} />
                  <Stat label="Avg / Year" value={profile.avgPerYear?.toFixed(1) ?? "n/a"} />
                  <Stat label="Tier P/L" value={formatUnits(profile.tierPnL)} tone={metricTone(profile.tierPnL)} />
                  <Stat label="Tier Staked" value={profile.tierStaked != null ? `${profile.tierStaked.toFixed(2)}u` : "n/a"} />
                </div>
                <div className="mt-4 rounded-xl border border-slate-800/80 bg-slate-900/70 p-3">
                  <div className="mb-2 text-[11px] uppercase tracking-[0.18em] text-slate-500">By year</div>
                  <div className="space-y-2 text-sm">
                    {profile.years.map((year) => (
                      <div key={year.year} className="flex items-center justify-between gap-4">
                        <span className="text-slate-300">{year.year}</span>
                        <span className="text-slate-500">{year.bets ?? 0} bets</span>
                        <span className={metricTone(year.tierRoiPct)}>{formatPct(year.tierRoiPct)}</span>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            ))}
          </div>
        </MonitorCard>

        <div className="mt-8 grid gap-6 xl:grid-cols-2">
          <MonitorCard title="Shadow Decision Summary" subtitle="Compact read, with raw comparison available on demand">
            <div className="space-y-4 text-sm leading-6 text-slate-300">
              <ul className="space-y-2">
                <li>
                  Active shadow candidate: <span className="font-semibold text-amber-300">ATP-only ML research</span>
                  {shadowProfile?.tierRoiPct != null && shadowProfile?.avgPerYear != null
                    ? ` (${formatPct(shadowProfile.tierRoiPct)} tier ROI, ${shadowProfile.avgPerYear.toFixed(1)} bets/year on the current ATP-only ML rule backtest).`
                    : "."}
                </li>
                <li>
                  Legacy comparison: <span className="font-semibold text-slate-100">volume_275</span>
                  {legacyShadowProfile?.tierRoiPct != null && legacyShadowProfile?.avgPerYear != null
                    ? ` (${formatPct(legacyShadowProfile.tierRoiPct)} tier ROI, ${legacyShadowProfile.avgPerYear.toFixed(1)} bets/year historical).`
                    : "."}
                </li>
                <li>
                  Live ATP ML research tracking: {volumeTrackedCount} rows, {volumeSettledCount} settled, {volumeOpenCount} currently open, {volumeNoMatchCount} parked as no_match, {formatPct(volumeAllRoi)} clean ROI.
                </li>
                <li>
                  Archived old Spread Shadow: {spreadShadowTrackedCount} signals, {spreadShadowSettledCount} settled, {formatPct(spreadShadowAllRoi)} ROI. Not active.
                </li>
              </ul>
              <details className="rounded-xl border border-slate-800 bg-slate-950/35 p-3">
                <summary className="cursor-pointer text-sm font-semibold text-slate-200">Show raw comparison report</summary>
                <pre className="mt-3 overflow-x-auto whitespace-pre-wrap text-xs leading-6 text-slate-400">{shadowComparisonTxt ?? "Missing shadow comparison report."}</pre>
              </details>
            </div>
          </MonitorCard>
          <MonitorCard title="Practical Use" subtitle="What this page means operationally">
            <div className="space-y-4 text-sm leading-6 text-slate-300">
              <p>
                <span className="font-semibold text-slate-100">Localhost:</span> this page reflects the report files produced by your daily and weekly jobs.
              </p>
              <p>
                <span className="font-semibold text-slate-100">Vercel:</span> this page only updates when the report files in the repo are deployed. It is not yet a true live monitor in production.
              </p>
              <p>
                <span className="font-semibold text-slate-100">Next clean upgrade:</span> move the monitor metrics into Supabase so this page can be real-time without redeploys.
              </p>
              <p>
                <span className="font-semibold text-slate-100">Current interpretation:</span> Spread v1 is still shadow/research. Logical-pick dedupe is active, so repeated refreshes of the same fixture do not count as extra bets.
              </p>
              <p>
                <span className="font-semibold text-slate-100">Archived lanes:</span> old Spread Shadow is audit history only. It is intentionally excluded from active scoreboard and latest-settled cards.
              </p>
            </div>
          </MonitorCard>
        </div>
      </div>
    </div>
  );
}
