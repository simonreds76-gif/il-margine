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
  signalProfile: string;
  settlementStatus: string;
  result: string;
  betOutcome: string;
  settledAt: string;
  settlementNote: string;
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
};

export const dynamic = "force-dynamic";
const CLEAN_EVAL_START = "2026-03-14";

const MODEL_MONITOR_PUBLIC =
  process.env.MODEL_MONITOR_PUBLIC === "1" ||
  process.env.NEXT_PUBLIC_ENABLE_MODEL_MONITOR === "1";
const MODEL_MONITOR_ENABLED =
  MODEL_MONITOR_PUBLIC || process.env.VERCEL_ENV === "preview";

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

function formatPct(value?: number, digits = 2): string {
  if (value == null || Number.isNaN(value)) return "n/a";
  return `${value >= 0 ? "+" : ""}${value.toFixed(digits)}%`;
}

function formatUnits(value?: number, digits = 2): string {
  if (value == null || Number.isNaN(value)) return "n/a";
  return `${value >= 0 ? "+" : ""}${value.toFixed(digits)}u`;
}

function formatPounds(value?: number, digits = 0): string {
  if (value == null || Number.isNaN(value)) return "n/a";
  const abs = Math.abs(value);
  return `${value >= 0 ? "+" : "-"}£${abs.toLocaleString("en-GB", {
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

function parseClvAudit(text: string | null): ClvSummary {
  if (!text) return {};
  const warningBlock = text.match(/Coverage warning\s+([\s\S]+?)(?:\n\n|$)/);
  return {
    rawRows: parseIntMaybe(text.match(/Raw strict rows:\s+(\d+)/)?.[1]),
    settledMlAudited: parseIntMaybe(text.match(/Settled ML rows audited:\s+(\d+)/)?.[1]),
    matchedMl: parseIntMaybe(text.match(/Matched ML rows:\s+(\d+)\s+\/\s+\d+/)?.[1]),
    matchedMlTotal: parseIntMaybe(text.match(/Matched ML rows:\s+\d+\s+\/\s+(\d+)/)?.[1]),
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
    signalProfile: row.signal_profile ?? "",
    settlementStatus: row.settlement_status ?? "",
    result: row.result ?? "",
    betOutcome: row.bet_outcome ?? "",
    settledAt: row.settled_at ?? "",
    settlementNote: row.settlement_note ?? "",
  }));
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
    if ((row.settlementStatus || "").trim().toLowerCase() !== "settled") continue;
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

function formatClvCell(value?: number, label = "n/a"): string {
  if (value == null || Number.isNaN(value)) return label;
  return formatPct(value, 3);
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
    .filter((row) => (row.settlementStatus || "").trim().toLowerCase() === "settled")
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

function getSettlementDate(row: MonitorSignalRow): string {
  return row.settledAt ? row.settledAt.slice(0, 10) : row.matchDate || row.date;
}

function shiftIsoDate(isoDate: string, days: number): string {
  const stamp = Date.parse(`${isoDate}T00:00:00Z`);
  if (!Number.isFinite(stamp)) return isoDate;
  return new Date(stamp + days * 86400000).toISOString().slice(0, 10);
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
    spreadShadowPerfCsv,
    clay2026PerfCsv,
    strictSignalsCsv,
    clvAuditTxt,
    clvAuditVolumeTxt,
    profileTxt,
    shadowComparisonTxt,
    volumeSignalsCsv,
    spreadShadowSignalsCsv,
    clay2026SignalsCsv,
    strictPerfMtime,
    volumePerfMtime,
    spreadShadowPerfMtime,
    clay2026PerfMtime,
    clvAuditMtime,
    clvAuditVolumeMtime,
    profileMtime,
    volumeSignalsMtime,
    spreadShadowSignalsMtime,
    clay2026SignalsMtime,
  ] = await Promise.all([
    readLocalFile("data/backtest/strict-policy-performance-weekly.csv"),
    readLocalFile("data/backtest/strict-policy-performance-volume200-weekly.csv"),
    readLocalFile("data/backtest/strict-policy-performance-spreadshadow-weekly.csv"),
    readLocalFile("data/backtest/strict-policy-performance-clay2026-weekly.csv"),
    readLocalFile("data/backtest/strict-signals.csv"),
    readLocalFile("data/backtest/strict-clv-audit-2026.txt"),
    readLocalFile("data/backtest/strict-clv-audit-volume200-2026.txt"),
    readLocalFile("data/backtest/policy-profile-backtest-2022-2025.txt"),
    readLocalFile("data/backtest/shadow-profile-comparison.txt"),
    readLocalFile("data/backtest/strict-signals-volume200.csv"),
    readLocalFile("data/backtest/strict-signals-spreadshadow.csv"),
    readLocalFile("data/backtest/strict-signals-claycal.csv"),
    readLocalMtime("data/backtest/strict-policy-performance-weekly.csv"),
    readLocalMtime("data/backtest/strict-policy-performance-volume200-weekly.csv"),
    readLocalMtime("data/backtest/strict-policy-performance-spreadshadow-weekly.csv"),
    readLocalMtime("data/backtest/strict-policy-performance-clay2026-weekly.csv"),
    readLocalMtime("data/backtest/strict-clv-audit-2026.txt"),
    readLocalMtime("data/backtest/strict-clv-audit-volume200-2026.txt"),
    readLocalMtime("data/backtest/policy-profile-backtest-2022-2025.txt"),
    readLocalMtime("data/backtest/strict-signals-volume200.csv"),
    readLocalMtime("data/backtest/strict-signals-spreadshadow.csv"),
    readLocalMtime("data/backtest/strict-signals-claycal.csv"),
  ]);

  const strictRows = strictPerfCsv ? parseCsv(strictPerfCsv) : [];
  const volumeRows = volumePerfCsv ? parseCsv(volumePerfCsv) : [];
  const spreadShadowRows = spreadShadowPerfCsv ? parseCsv(spreadShadowPerfCsv) : [];
  const clay2026Rows = clay2026PerfCsv ? parseCsv(clay2026PerfCsv) : [];
  const strictBase = parsePerf(strictRows, "base");
  const strictOverlay = parsePerf(strictRows, "overlay");
  const volumeBase = parsePerf(volumeRows, "base");
  const spreadShadowBase = parsePerf(spreadShadowRows, "base");
  const clay2026Base = parsePerf(clay2026Rows, "base");
  const clv = parseClvAudit(clvAuditTxt);
  const clvVolume = parseClvAudit(clvAuditVolumeTxt);
  const profiles = parsePolicyProfiles(profileTxt);
  const profileMap = new Map(profiles.map((profile) => [profile.name, profile]));
  const strictSignals = parseSignalRows(strictSignalsCsv);
  const strictSignalsClean = filterCleanSignalRows(strictSignals);
  const strictSettledRows = getSettledSignalRows(strictSignals);
  const volumeSignals = parseSignalRows(volumeSignalsCsv);
  const volumeSignalsClean = filterCleanSignalRows(volumeSignals);
  const volumeQueue = getActiveQueueRows(volumeSignals);
  const volumeNoMatchRows = getNoMatchRows(volumeSignals);
  const volumeSettledRows = getSettledSignalRows(volumeSignals);
  const spreadShadowSignals = parseSignalRows(spreadShadowSignalsCsv);
  const spreadShadowSignalsClean = filterCleanSignalRows(spreadShadowSignals);
  const spreadShadowQueue = getActiveQueueRows(spreadShadowSignals);
  const spreadShadowNoMatchRows = getNoMatchRows(spreadShadowSignals);
  const spreadShadowSettledRows = getSettledSignalRows(spreadShadowSignals);
  const clay2026Signals = parseSignalRows(clay2026SignalsCsv);
  const clay2026SignalsClean = filterCleanSignalRows(clay2026Signals);
  const clay2026Queue = getActiveQueueRows(clay2026Signals);
  const clay2026NoMatchRows = getNoMatchRows(clay2026Signals);
  const clay2026SettledRows = getSettledSignalRows(clay2026Signals);
  const clay2026AllCohort = summarizeSignalCohort(clay2026Signals);
  const clay2026AtpCohort = summarizeSignalCohort(clay2026Signals, "ATP");
  const clay2026ChallengerCohort = summarizeSignalCohort(clay2026Signals, "Challenger");
  const strictMlRecordedCohort = summarizeSignalCohort(strictSignalsClean, undefined, "recorded", "match");
  const strictSpreadRecordedCohort = summarizeSignalCohort(strictSignalsClean, undefined, "recorded", "spread");
  const strictMlFlatCohort = summarizeSignalCohort(strictSignalsClean, undefined, "flat", "match");
  const strictSpreadFlatCohort = summarizeSignalCohort(strictSignalsClean, undefined, "flat", "spread");
  const volumeMlRecordedCohort = summarizeSignalCohort(volumeSignalsClean, undefined, "recorded", "match");
  const volumeSpreadRecordedCohort = summarizeSignalCohort(volumeSignalsClean, undefined, "recorded", "spread");
  const volumeMlFlatCohort = summarizeSignalCohort(volumeSignalsClean, undefined, "flat", "match");
  const volumeSpreadFlatCohort = summarizeSignalCohort(volumeSignalsClean, undefined, "flat", "spread");
  const spreadShadowSpreadRecordedCohort = summarizeSignalCohort(spreadShadowSignalsClean, undefined, "recorded", "spread");
  const spreadShadowSpreadFlatCohort = summarizeSignalCohort(spreadShadowSignalsClean, undefined, "flat", "spread");
  const clay2026MlRecordedCohort = summarizeSignalCohort(clay2026SignalsClean, undefined, "recorded", "match");
  const clay2026MlFlatCohort = summarizeSignalCohort(clay2026SignalsClean, undefined, "flat", "match");

  const strictAllRoi = perfValue(strictBase.combinedAll, "roi_pct", parseFloatMaybe);
  const volumeAllRoi = perfValue(volumeBase.combinedAll, "roi_pct", parseFloatMaybe);
  const spreadShadowAllRoi = perfValue(spreadShadowBase.combinedAll, "roi_pct", parseFloatMaybe);
  const clay2026AllRoi = perfValue(clay2026Base.combinedAll, "roi_pct", parseFloatMaybe);
  const strictWindowRoi = perfValue(strictBase.combinedWindow, "roi_pct", parseFloatMaybe);
  const overlayAllRoi = perfValue(strictOverlay.combinedAll, "roi_pct", parseFloatMaybe);
  const matchedMl = clv.matchedMl ?? 0;
  const auditedMl = clv.matchedMlTotal ?? clv.settledMlAudited ?? 0;
  const matchedMlVolume = clvVolume.matchedMl ?? 0;
  const auditedMlVolume = clvVolume.matchedMlTotal ?? clvVolume.settledMlAudited ?? 0;
  const strictAsOf = strictBase.combinedAll?.as_of_date;
  const volumeAsOf = volumeBase.combinedAll?.as_of_date;
  const spreadShadowAsOf = spreadShadowBase.combinedAll?.as_of_date;
  const clay2026AsOf = clay2026Base.combinedAll?.as_of_date;
  const shadowProfile = profileMap.get("volume_200");
  const legacyShadowProfile = profileMap.get("volume_275");
  const missingReports = [
    !strictPerfCsv ? "strict weekly performance" : null,
    !volumePerfCsv ? "volume_200 weekly performance" : null,
    !spreadShadowPerfCsv ? "spread shadow weekly performance" : null,
    !clay2026PerfCsv ? "Clay 2026 weekly performance" : null,
    !clvAuditTxt ? "strict CLV audit" : null,
    !clvAuditVolumeTxt ? "volume_200 CLV audit" : null,
    !profileTxt ? "policy profile backtest" : null,
  ].filter(Boolean) as string[];
  const strictDiagnosis =
    strictAllRoi == null
      ? "Strict live has no settled ROI yet."
      : strictAllRoi < 0
        ? `Strict live control is negative at ${formatPct(strictAllRoi)} as of ${strictAsOf ?? "n/a"}.`
        : `Strict live control is positive at ${formatPct(strictAllRoi)} as of ${strictAsOf ?? "n/a"}.`;
  const shadowDiagnosis =
    volumeSignals.length === 0
      ? "Volume 200 shadow file is empty right now."
      : volumeQueue.length === 0 && volumeNoMatchRows.length > 0
      ? `Volume 200 has ${volumeNoMatchRows.length} unresolved settlement rows marked no_match, but no true live queue at the moment.`
      : perfValue(volumeBase.combinedAll, "settled", parseIntMaybe) === 0
      ? "Volume 200 shadow has no settled sample yet."
      : `Volume 200 shadow has settled enough to start comparing against strict on live results.`;
  const spreadShadowDiagnosis =
    !spreadShadowSignalsCsv
      ? "Spread shadow has no live CSV on disk right now, which usually means no qualifying clay/non-policy handicap row has been written yet."
      : spreadShadowQueue.length === 0 && spreadShadowNoMatchRows.length > 0
      ? `Spread shadow has ${spreadShadowNoMatchRows.length} unresolved no_match rows, but no true live queue right now.`
      : spreadShadowSignals.length === 0
      ? "Spread shadow is wired in, but it has not logged a qualifying 20%+ clay/non-policy handicap row yet."
      : perfValue(spreadShadowBase.combinedAll, "settled", parseIntMaybe) === 0
        ? `Spread shadow has ${spreadShadowSignals.length} tracked rows, but no settled sample yet.`
        : `Spread shadow is tracking ${perfValue(spreadShadowBase.combinedAll, "signals", parseIntMaybe) ?? 0} rows with ${perfValue(spreadShadowBase.combinedAll, "settled", parseIntMaybe) ?? 0} settled so far.`;
  const clay2026Diagnosis =
    !clay2026SignalsCsv
      ? "Clay 2026 has no live CSV on disk right now, which usually means the calibrated lane has not written a qualifying row yet."
      : clay2026Queue.length === 0 && clay2026NoMatchRows.length > 0
      ? `Clay 2026 has ${clay2026NoMatchRows.length} unresolved no_match rows, but no true live queue right now.`
      : clay2026Signals.length === 0
      ? "Clay 2026 is wired in, but it has not logged a qualifying calibrated-favorite row yet."
      : clay2026AllCohort.settled === 0
        ? `Clay 2026 has ${clay2026Signals.length} tracked rows (ATP ${clay2026AtpCohort.signals}, Challenger ${clay2026ChallengerCohort.signals}), but no settled sample yet. Challenger remains observational only.`
        : `Clay 2026 is tracking ${clay2026AllCohort.signals} rows with ${clay2026AllCohort.settled} settled so far. ATP and Challenger are shown separately; Challenger remains observational only.`;
  const volumeQueueMlCount = volumeQueue.filter((row) => row.betType !== "spread").length;
  const volumeQueueSpreadCount = volumeQueue.filter((row) => row.betType === "spread").length;
  const volumeSettledMlCount =
    perfValue(volumeBase.mlAll, "settled", parseIntMaybe) ??
    volumeSignals.filter((row) => row.betType !== "spread" && (row.settlementStatus || "").trim().toLowerCase() === "settled").length;
  const volumeSettledSpreadCount =
    perfValue(volumeBase.handicapAll, "settled", parseIntMaybe) ??
    volumeSignals.filter((row) => row.betType === "spread" && (row.settlementStatus || "").trim().toLowerCase() === "settled").length;
  const volumeTrackedCount = perfValue(volumeBase.combinedAll, "signals", parseIntMaybe) ?? volumeSignals.length;
  const volumeOpenCount = perfValue(volumeBase.combinedAll, "unsettled", parseIntMaybe) ?? volumeQueue.length;
  const volumeNoMatchCount = volumeNoMatchRows.length;
  const volumeSettledCount =
    perfValue(volumeBase.combinedAll, "settled", parseIntMaybe) ??
    volumeSignals.filter((row) => (row.settlementStatus || "").trim().toLowerCase() === "settled").length;
  const spreadShadowTrackedCount = perfValue(spreadShadowBase.combinedAll, "signals", parseIntMaybe) ?? spreadShadowSignals.length;
  const spreadShadowSettledCount = perfValue(spreadShadowBase.combinedAll, "settled", parseIntMaybe) ?? 0;
  const clay2026TrackedCount = perfValue(clay2026Base.combinedAll, "signals", parseIntMaybe) ?? clay2026Signals.length;
  const clay2026SettledCount = perfValue(clay2026Base.combinedAll, "settled", parseIntMaybe) ?? 0;
  const strictMlOpenCount = strictSignals.filter((row) => row.betType !== "spread" && (row.settlementStatus || "").trim().toLowerCase() !== "settled" && (row.settlementStatus || "").trim().toLowerCase() !== "no_match").length;
  const strictSpreadOpenCount = strictSignals.filter((row) => row.betType === "spread" && (row.settlementStatus || "").trim().toLowerCase() !== "settled" && (row.settlementStatus || "").trim().toLowerCase() !== "no_match").length;
  const volumeMlOpenCount = volumeQueueMlCount;
  const volumeSpreadOpenCount = volumeQueueSpreadCount;
  const spreadShadowOpenCount = spreadShadowQueue.length;
  const clay2026OpenCount = clay2026Queue.length;
  const resultsAsOfDate = clay2026AsOf ?? spreadShadowAsOf ?? volumeAsOf ?? strictAsOf ?? new Date().toISOString().slice(0, 10);
  const priorResultsDate = shiftIsoDate(resultsAsOfDate, -1);
  const latestSettledRows = [
    ...strictSettledRows.map((row) => ({ source: "Strict", lane: row.betType === "spread" ? "Strict Spread" : "Strict ML", accent: "rose" as const, row })),
    ...volumeSettledRows.map((row) => ({ source: "Volume 200", lane: row.betType === "spread" ? "Volume 200 Spread" : "Volume 200 ML", accent: "amber" as const, row })),
    ...spreadShadowSettledRows.map((row) => ({ source: "Spread Shadow", lane: "Spread Shadow HC", accent: "cyan" as const, row })),
    ...clay2026SettledRows.map((row) => ({ source: "Clay 2026", lane: "Clay 2026 ML", accent: "orange" as const, row })),
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
    },
    {
      policy: "Strict",
      lane: "Spread",
      marketType: "Handicap",
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
    },
    {
      policy: "Volume 200",
      lane: "ML",
      marketType: "Match winner",
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
    },
    {
      policy: "Volume 200",
      lane: "Spread",
      marketType: "Handicap",
      settled: perfValue(volumeBase.handicapAll, "settled", parseIntMaybe) ?? volumeSpreadRecordedCohort.settled,
      signals: perfValue(volumeBase.handicapAll, "signals", parseIntMaybe) ?? volumeSpreadRecordedCohort.signals,
      open: perfValue(volumeBase.handicapAll, "unsettled", parseIntMaybe) ?? volumeSpreadOpenCount,
      wlv: perfWlv(volumeBase.handicapAll),
      roi: perfValue(volumeBase.handicapAll, "roi_pct", parseFloatMaybe),
      flatStakePounds: volumeSpreadFlatCohort.pnlUnits * 100,
      flatTotalStakedPounds: volumeSpreadFlatCohort.stakedUnits * 100,
      unitTotalStakedPounds: volumeSpreadRecordedCohort.stakedUnits * 100,
      unitStakePounds: volumeSpreadRecordedCohort.pnlUnits * 100,
      winRate: perfValue(volumeBase.handicapAll, "win_rate_pct", parseFloatMaybe),
      clvLabel: "n/a",
    },
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
    {
      policy: "Clay 2026",
      lane: "ML",
      marketType: "Match winner",
      settled: clay2026SettledCount,
      signals: clay2026TrackedCount,
      open: perfValue(clay2026Base.combinedAll, "unsettled", parseIntMaybe) ?? clay2026OpenCount,
      wlv: perfWlv(clay2026Base.mlAll ?? clay2026Base.combinedAll),
      roi: clay2026AllRoi,
      flatStakePounds: clay2026MlFlatCohort.pnlUnits * 100,
      flatTotalStakedPounds: clay2026MlFlatCohort.stakedUnits * 100,
      unitTotalStakedPounds: clay2026MlRecordedCohort.stakedUnits * 100,
      unitStakePounds: clay2026MlRecordedCohort.pnlUnits * 100,
      winRate: perfValue(clay2026Base.mlAll ?? clay2026Base.combinedAll, "win_rate_pct", parseFloatMaybe),
      clvLabel: "n/a",
    },
  ];

  return (
    <div className="min-h-screen bg-[radial-gradient(circle_at_top_left,_rgba(16,185,129,0.12),_transparent_28%),radial-gradient(circle_at_top_right,_rgba(244,63,94,0.10),_transparent_22%),#0b0f14] text-slate-100">
      <div className="mx-auto max-w-7xl px-4 py-8 sm:px-6 lg:px-8">
        <div className="mb-8 flex flex-wrap items-center gap-3">
          <Link href="/fair-odds" className="inline-flex items-center rounded-full border border-slate-700/80 bg-slate-900/80 px-3 py-1.5 text-sm text-slate-300 transition-colors hover:border-emerald-500/40 hover:text-emerald-300">
            Fair Odds
          </Link>
          <Link href="/api/model-monitor/betting-archive" className="inline-flex items-center rounded-full border border-cyan-500/25 bg-cyan-500/10 px-3 py-1.5 text-sm text-cyan-200 transition-colors hover:border-cyan-400/40 hover:text-cyan-100">
            Download Bet Archive
          </Link>
          <Link href="/model-monitor/goalscorer" className="inline-flex items-center rounded-full border border-slate-700/80 bg-slate-900/80 px-3 py-1.5 text-sm text-slate-300 transition-colors hover:border-emerald-500/40 hover:text-emerald-300">
            Goalscorer Preview
          </Link>
          <Link href="/model-monitor/reddit-intel" className="inline-flex items-center rounded-full border border-slate-700/80 bg-slate-900/80 px-3 py-1.5 text-sm text-slate-300 transition-colors hover:border-emerald-500/40 hover:text-emerald-300">
            Reddit Intel
          </Link>
          <Link href="/" className="inline-flex items-center rounded-full border border-slate-700/80 bg-slate-900/80 px-3 py-1.5 text-sm text-slate-300 transition-colors hover:border-emerald-500/40 hover:text-emerald-300">
            Home
          </Link>
        </div>

        <section className="mb-8 overflow-hidden rounded-3xl border border-slate-800 bg-[linear-gradient(135deg,rgba(16,185,129,0.12),rgba(15,23,42,0.92)_40%,rgba(244,63,94,0.08))] p-6 sm:p-8">
          <div className="flex flex-col gap-5 lg:flex-row lg:items-end lg:justify-between">
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
              <FileStamp label="Spread shadow perf" value={spreadShadowPerfMtime} />
              <FileStamp label="Clay 2026 perf" value={clay2026PerfMtime} />
              <FileStamp label="Strict CLV" value={clvAuditMtime} />
              <FileStamp label="Vol200 CLV" value={clvAuditVolumeMtime} />
              <FileStamp label="Profile backtest" value={profileMtime} />
              <FileStamp label="Vol200 signals" value={volumeSignalsMtime} />
              <FileStamp label="Spread shadow signals" value={spreadShadowSignalsMtime} />
              <FileStamp label="Clay 2026 signals" value={clay2026SignalsMtime} />
            </div>
          </div>
        </section>

        {missingReports.length > 0 ? (
          <section className="mb-8 rounded-2xl border border-amber-500/25 bg-amber-500/10 p-4 text-sm text-amber-100">
            Reports not found for: <span className="font-semibold">{missingReports.join(", ")}</span>. Run the daily/weekly pipeline locally or deploy fresh report files.
          </section>
        ) : null}

        <div className="mb-3 flex items-center justify-between gap-4">
          <div>
            <h2 className="text-xl font-semibold text-slate-100">Operations Board</h2>
            <p className="mt-1 text-sm text-slate-400">Lane-by-lane scoreboard first, latest settled results second, deeper diagnostics below.</p>
          </div>
        </div>

        <div className="mb-8">
          <MonitorCard title="Lane Scoreboard" subtitle="Every lane on its own row so ML and spread can be judged separately. Total Bets = settled bets.">
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
                    <th className="px-3 py-3 font-semibold">GBP100 / Bet</th>
                    <th className="px-3 py-3 font-semibold">Staked / Bet</th>
                    <th className="px-3 py-3 font-semibold">Staked / Unit</th>
                    <th className="px-3 py-3 font-semibold">GBP100 / Unit</th>
                    <th className="px-3 py-3 font-semibold">Win Rate</th>
                    <th className="px-3 py-3 font-semibold">CLV</th>
                  </tr>
                </thead>
                <tbody>
                  {laneScoreRows.map((row) => (
                    <tr key={`${row.policy}-${row.lane}`} className="border-b border-slate-900/80 text-slate-200">
                      <td className="px-3 py-3 font-semibold text-white">{row.policy}</td>
                      <td className="px-3 py-3 font-mono tabular-nums text-slate-100">{row.lane}</td>
                      <td className="px-3 py-3 text-slate-300">{row.marketType}</td>
                      <td className="px-3 py-3 font-mono tabular-nums">{row.settled}</td>
                      <td className="px-3 py-3 font-mono tabular-nums text-slate-300">{row.signals}</td>
                      <td className="px-3 py-3 font-mono tabular-nums text-slate-300">{row.open}</td>
                      <td className="px-3 py-3 font-mono tabular-nums text-slate-100">{row.wlv}</td>
                      <td className={`px-3 py-3 font-mono tabular-nums ${metricTone(row.roi)}`}>{formatPct(row.roi)}</td>
                      <td className={`px-3 py-3 font-mono tabular-nums ${metricTone(row.flatStakePounds)}`}>{formatPounds(row.flatStakePounds)}</td>
                      <td className="px-3 py-3 font-mono tabular-nums text-slate-200">{formatPounds(row.flatTotalStakedPounds)}</td>
                      <td className="px-3 py-3 font-mono tabular-nums text-slate-200">{formatPounds(row.unitTotalStakedPounds)}</td>
                      <td className={`px-3 py-3 font-mono tabular-nums ${metricTone(row.unitStakePounds)}`}>{formatPounds(row.unitStakePounds)}</td>
                      <td className={`px-3 py-3 font-mono tabular-nums ${metricTone((row.winRate ?? 0) - 50)}`}>{formatPct(row.winRate)}</td>
                      <td className={`px-3 py-3 font-mono tabular-nums ${row.clv != null ? metricTone(row.clv) : "text-slate-500"}`}>
                        {formatClvCell(row.clv, row.clvLabel ?? "n/a")}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <p className="mt-3 text-xs leading-6 text-slate-500">
              GBP100 / Bet and Staked / Bet assume a flat GBP100 stake on each settled priced bet. Staked / Unit and GBP100 / Unit use recorded stake units with 1u = GBP100, so 2u spreads count as GBP200 risk. All four use the current clean settled sample.{" "}
              CLV is only audited on the ML lanes with dedicated history coverage right now. Spread Shadow and Clay 2026 show <span className="font-semibold text-slate-400">n/a</span> until that audit exists.
            </p>
            <div className="mt-4 grid gap-3 lg:grid-cols-3">
              <div className="rounded-xl border border-slate-800/80 bg-slate-950/35 p-3 text-sm text-slate-300">
                <div className="text-[11px] uppercase tracking-[0.18em] text-slate-500">Clay 2026 Split</div>
                <div className="mt-2">ATP only: {cohortWlv(clay2026AtpCohort)} | {formatPct(clay2026AtpCohort.roiPct)}</div>
                <div className="mt-1">Challenger: {cohortWlv(clay2026ChallengerCohort)} | {formatPct(clay2026ChallengerCohort.roiPct)}</div>
              </div>
              <div className="rounded-xl border border-slate-800/80 bg-slate-950/35 p-3 text-sm text-slate-300">
                <div className="text-[11px] uppercase tracking-[0.18em] text-slate-500">Volume 200 Open</div>
                <div className="mt-2">ML {volumeMlOpenCount} | Spread {volumeSpreadOpenCount}</div>
                <div className="mt-1 text-slate-500">No-match rows parked: {volumeNoMatchCount}</div>
              </div>
              <div className="rounded-xl border border-slate-800/80 bg-slate-950/35 p-3 text-sm text-slate-300">
                <div className="text-[11px] uppercase tracking-[0.18em] text-slate-500">Board Dates</div>
                <div className="mt-2">Settled today: {resultsAsOfDate}</div>
                <div className="mt-1">Settled yesterday: {priorResultsDate}</div>
              </div>
            </div>
          </MonitorCard>
        </div>

        <div className="mb-8">
          <MonitorCard title="Latest Settled Results" subtitle="Fastest way to answer questions like “did Clay 2026 win yesterday?” without digging through the raw CSVs.">
            <div className="grid gap-4 xl:grid-cols-2">
              {[
                { label: `Settled Today (${resultsAsOfDate})`, rows: settledTodayRows },
                { label: `Settled Yesterday (${priorResultsDate})`, rows: settledYesterdayRows },
              ].map((group) => (
                <div key={group.label} className="rounded-2xl border border-slate-800 bg-slate-950/35 p-4">
                  <div className="mb-3 flex items-center justify-between gap-3">
                    <div className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">{group.label}</div>
                    <div className="text-xs text-slate-500">{group.rows.length} rows</div>
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
                              : accent === "cyan"
                                ? "border-cyan-500/20 bg-cyan-500/5 text-cyan-200"
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

        <div className="mb-8 grid gap-4 md:grid-cols-2 xl:grid-cols-4 2xl:grid-cols-7">
          <MonitorCard title="Strict Live Control" subtitle={`Clean sample first: Hard | Masters 1000 | high | public >=10%${strictAsOf ? ` | as of ${strictAsOf}` : ""}`}>
            <div className="grid gap-3">
              <Stat label="Clean ROI" value={formatPct(strictAllRoi)} tone={metricTone(strictAllRoi)} />
              <Stat label="Clean 7d ROI" value={formatPct(strictWindowRoi)} tone={metricTone(strictWindowRoi)} />
              <Stat label="Settled" value={`${perfValue(strictBase.combinedAll, "settled", parseIntMaybe) ?? 0}`} />
              <Stat label="Open" value={`${perfValue(strictBase.combinedAll, "unsettled", parseIntMaybe) ?? 0}`} />
            </div>
          </MonitorCard>

          <MonitorCard title="Volume 200 Shadow" subtitle={`Clean sample first, ML + spread tracked together${volumeAsOf ? ` | as of ${volumeAsOf}` : ""}`}>
            <div className="grid gap-3">
              <Stat label="Clean ROI" value={formatPct(volumeAllRoi)} tone={metricTone(volumeAllRoi)} />
              <Stat label="Tracked Rows" value={`${volumeTrackedCount}`} />
              <Stat label="Open Queue" value={`${volumeOpenCount}`} />
              <Stat label="Avg Value" value={formatPct(perfValue(volumeBase.combinedAll, "avg_value_pct", parseFloatMaybe))} tone="text-amber-300" />
            </div>
          </MonitorCard>

          <MonitorCard title="Spread Shadow" subtitle={`Clean sample first, clay + non-policy handicap lane${spreadShadowAsOf ? ` | as of ${spreadShadowAsOf}` : ""}`}>
            <div className="grid gap-3">
              <Stat label="Clean ROI" value={formatPct(spreadShadowAllRoi)} tone={metricTone(spreadShadowAllRoi)} />
              <Stat label="Signals" value={`${spreadShadowTrackedCount}`} />
              <Stat label="Settled" value={`${spreadShadowSettledCount}`} />
              <Stat label="Unsettled" value={`${perfValue(spreadShadowBase.combinedAll, "unsettled", parseIntMaybe) ?? spreadShadowQueue.length}`} />
            </div>
          </MonitorCard>

          <MonitorCard title="Clay 2026" subtitle={`ATP validated lane, Challenger observational${clay2026AsOf ? ` | as of ${clay2026AsOf}` : ""}`}>
            <div className="grid gap-3">
              <Stat label="Clean ROI" value={formatPct(clay2026AllRoi)} tone={metricTone(clay2026AllRoi)} />
              <Stat label="Signals" value={`${clay2026TrackedCount}`} />
              <Stat label="Settled" value={`${clay2026SettledCount}`} />
              <Stat label="Unsettled" value={`${perfValue(clay2026Base.combinedAll, "unsettled", parseIntMaybe) ?? clay2026Queue.length}`} />
              <Stat label="ATP Signals" value={`${clay2026AtpCohort.signals}`} tone="text-emerald-300" />
              <Stat label="CH Signals" value={`${clay2026ChallengerCohort.signals}`} tone="text-amber-300" />
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

          <MonitorCard title="Vol200 CLV" subtitle="Volume 200 ML rows only. Same audit path, separate shadow read.">
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
                  <h3 className="text-base font-semibold text-white">Volume 200 Shadow</h3>
                  <span className="rounded-full bg-amber-500/15 px-2 py-1 text-xs font-semibold text-amber-300">shadow</span>
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
                  <SplitBucket
                    title="Spread"
                    roi={formatPct(perfValue(volumeBase.handicapAll, "roi_pct", parseFloatMaybe))}
                    roiTone={metricTone(perfValue(volumeBase.handicapAll, "roi_pct", parseFloatMaybe))}
                    wlv={perfWlv(volumeBase.handicapAll)}
                  />
                </div>
                <div className="mt-3 rounded-xl border border-slate-800/80 bg-slate-950/35 p-3 text-xs text-slate-400">
                  Open queue: ML {volumeQueueMlCount} | Spread {volumeQueueSpreadCount}. Settled so far: ML {volumeSettledMlCount} | Spread {volumeSettledSpreadCount}. No-match settlement rows: {volumeNoMatchCount}.
                </div>
              </div>

              <div className="rounded-2xl border border-cyan-500/20 bg-cyan-500/5 p-4">
                <div className="mb-4 flex items-center justify-between">
                  <h3 className="text-base font-semibold text-white">Spread Shadow</h3>
                  <span className="rounded-full bg-cyan-500/15 px-2 py-1 text-xs font-semibold text-cyan-300">clay / non-policy</span>
                </div>
                <div className="grid gap-3 sm:grid-cols-2">
                  <Stat label="Clean ROI" value={formatPct(spreadShadowAllRoi)} tone={metricTone(spreadShadowAllRoi)} compact />
                  <Stat label="Signals" value={`${spreadShadowTrackedCount}`} compact />
                  <Stat label="Settled" value={`${spreadShadowSettledCount}`} compact />
                  <Stat label="Unsettled" value={`${perfValue(spreadShadowBase.combinedAll, "unsettled", parseIntMaybe) ?? spreadShadowQueue.length}`} compact />
                  <Stat label="Avg Value" value={formatPct(perfValue(spreadShadowBase.combinedAll, "avg_value_pct", parseFloatMaybe))} tone="text-cyan-200" compact />
                </div>
                <div className="mt-3">
                  <SplitBucket
                    title="Spread"
                    roi={formatPct(perfValue(spreadShadowBase.handicapAll, "roi_pct", parseFloatMaybe))}
                    roiTone={metricTone(perfValue(spreadShadowBase.handicapAll, "roi_pct", parseFloatMaybe))}
                    wlv={perfWlv(spreadShadowBase.handicapAll)}
                  />
                </div>
              </div>

              <div className="rounded-2xl border border-orange-500/20 bg-orange-500/5 p-4">
                <div className="mb-4 flex items-center justify-between">
                  <h3 className="text-base font-semibold text-white">Clay 2026</h3>
                  <span className="rounded-full bg-orange-500/15 px-2 py-1 text-xs font-semibold text-orange-200">calibrated lane</span>
                </div>
                <p className="mb-3 text-sm leading-6 text-slate-400">
                  ATP is the historically validated cohort. Challenger stays in the shadow stream, but it is observational only and should not drive promotion decisions.
                </p>
                <div className="grid gap-3 sm:grid-cols-2">
                  <Stat label="Clean ROI" value={formatPct(clay2026AllRoi)} tone={metricTone(clay2026AllRoi)} compact />
                  <Stat label="Signals" value={`${clay2026TrackedCount}`} compact />
                  <Stat label="Settled" value={`${clay2026SettledCount}`} compact />
                  <Stat label="Unsettled" value={`${perfValue(clay2026Base.combinedAll, "unsettled", parseIntMaybe) ?? clay2026Queue.length}`} compact />
                  <Stat label="Avg Value" value={formatPct(perfValue(clay2026Base.combinedAll, "avg_value_pct", parseFloatMaybe))} tone="text-orange-200" compact />
                </div>
                <div className="mt-3">
                  <SplitBucket
                    title="ML"
                    roi={formatPct(perfValue(clay2026Base.mlAll, "roi_pct", parseFloatMaybe))}
                    roiTone={metricTone(perfValue(clay2026Base.mlAll, "roi_pct", parseFloatMaybe))}
                    wlv={perfWlv(clay2026Base.mlAll)}
                  />
                </div>
                <div className="mt-3 grid gap-3 sm:grid-cols-3">
                  <SplitBucket
                    title="ATP only"
                    roi={formatPct(clay2026AtpCohort.roiPct)}
                    roiTone={metricTone(clay2026AtpCohort.roiPct)}
                    wlv={cohortWlv(clay2026AtpCohort)}
                  />
                  <SplitBucket
                    title="Challenger only"
                    roi={formatPct(clay2026ChallengerCohort.roiPct)}
                    roiTone={metricTone(clay2026ChallengerCohort.roiPct)}
                    wlv={cohortWlv(clay2026ChallengerCohort)}
                  />
                  <SplitBucket
                    title="Combined signals"
                    roi={formatPct(clay2026AllCohort.roiPct)}
                    roiTone={metricTone(clay2026AllCohort.roiPct)}
                    wlv={cohortWlv(clay2026AllCohort)}
                  />
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
                  <li>{spreadShadowDiagnosis}</li>
                  <li>{clay2026Diagnosis}</li>
                  <li>
                    Historical exact profiles still favor <span className="font-semibold text-amber-300">volume_200</span>, but live promotion is not justified until shadow settles and CLV coverage overlaps the sample.
                  </li>
                </ul>
              </div>

              <div className="rounded-2xl border border-slate-800 bg-slate-950/35 p-4">
                <div className="mb-2 text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">Volume 200 Live Queue</div>
                {volumeQueue.length === 0 ? (
                  <p className="text-sm leading-6 text-slate-400">
                    {volumeNoMatchRows.length > 0
                      ? `No true open volume_200 bets right now. ${volumeNoMatchRows.length} rows are parked as no_match settlement mismatches instead.`
                      : "No open volume_200 rows right now. When the shadow lane logs live candidates, they will appear here with ML vs spread clearly split."}
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
                {volumeNoMatchRows.length > 0 ? (
                  <div className="mt-4 rounded-xl border border-rose-500/20 bg-rose-500/5 p-3">
                    <div className="text-xs font-semibold uppercase tracking-[0.18em] text-rose-300">Settlement Mismatch</div>
                    <p className="mt-2 text-sm leading-6 text-slate-300">
                      {volumeNoMatchRows.length} volume_200 rows are tagged <span className="font-semibold text-rose-200">no_match</span>. They were generated by the model, but the settlement step did not find a matching OnCourt row yet.
                    </p>
                    <div className="mt-3 space-y-2">
                      {volumeNoMatchRows.slice(0, 5).map((row) => (
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
                <div className="mb-2 text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">Spread Shadow Queue</div>
                {spreadShadowQueue.length === 0 ? (
                  <p className="text-sm leading-6 text-slate-400">
                    {spreadShadowSignalsCsv
                      ? "No open spread-shadow bets right now. When a 20%+ clay or non-policy handicap signal qualifies, it will appear here."
                      : "No spread-shadow CSV on disk right now. That usually means the lane has not written a qualifying row yet."}
                  </p>
                ) : (
                  <div className="space-y-3">
                    {spreadShadowQueue.slice(0, 6).map((row) => (
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
                            <div className="text-sm font-semibold text-cyan-300">{row.side} {formatSignedLine(row.spreadLine)}</div>
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
              </div>

              <div className="rounded-2xl border border-slate-800 bg-slate-950/35 p-4">
                <div className="mb-2 text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">Clay 2026 Queue</div>
                {clay2026Queue.length === 0 ? (
                  <p className="text-sm leading-6 text-slate-400">
                    {clay2026SignalsCsv
                      ? "No open Clay 2026 bets right now. When the calibrated clay lane finds a qualifying 55-65% favorite, it will appear here."
                      : "No Clay 2026 CSV on disk right now. That usually means the lane has not written a qualifying row yet."}
                  </p>
                ) : (
                  <div className="space-y-3">
                    {clay2026Queue.slice(0, 6).map((row) => (
                      <div key={`${row.date}-${row.player1}-${row.player2}-${row.side}-${row.spreadLine}`} className="rounded-xl border border-slate-800/80 bg-slate-900/70 p-3">
                        <div className="flex items-start justify-between gap-3">
                          <div>
                            <div className="flex items-center gap-2 flex-wrap">
                              <div className="font-semibold text-slate-100">{row.player1} vs {row.player2}</div>
                              {normalizeLeague(row.league) === "Challenger" ? (
                                <span className="rounded-full border border-amber-500/25 bg-amber-500/10 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-[0.14em] text-amber-200">
                                  Unvalidated CH
                                </span>
                              ) : (
                                <span className="rounded-full border border-emerald-500/25 bg-emerald-500/10 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-[0.14em] text-emerald-300">
                                  ATP validated
                                </span>
                              )}
                            </div>
                            <div className="mt-1 text-xs text-slate-500">
                              {row.surface} | {row.league || "ATP"} | {row.series} | {row.confidence}
                              {row.claySpeedTier ? ` | ${row.claySpeedTier}${row.tournamentSpeedSignal != null ? ` ${row.tournamentSpeedSignal > 0 ? "+" : ""}${row.tournamentSpeedSignal.toFixed(3)}` : ""}` : ""}
                              {" | "}{row.date} {row.timeUtc}
                            </div>
                          </div>
                          <div className="text-right">
                            <div className="text-sm font-semibold text-orange-200">{row.side}</div>
                            <div className="mt-1 text-xs text-slate-500">match lane</div>
                          </div>
                        </div>
                        <div className="mt-2 text-xs text-slate-400">
                          edge {formatPct(row.valuePct)} | status {(row.settlementStatus || "pending").replace(/_/g, " ")}
                        </div>
                        {row.settlementNote ? (
                          <div className="mt-1 text-[11px] text-slate-500">{row.settlementNote}</div>
                        ) : null}
                      </div>
                    ))}
                  </div>
                )}
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
                  Active shadow candidate: <span className="font-semibold text-amber-300">volume_200</span>
                  {shadowProfile?.tierRoiPct != null && shadowProfile?.avgPerYear != null
                    ? ` (${formatPct(shadowProfile.tierRoiPct)} tier ROI, ${shadowProfile.avgPerYear.toFixed(1)} bets/year historical).`
                    : "."}
                </li>
                <li>
                  Legacy comparison: <span className="font-semibold text-slate-100">volume_275</span>
                  {legacyShadowProfile?.tierRoiPct != null && legacyShadowProfile?.avgPerYear != null
                    ? ` (${formatPct(legacyShadowProfile.tierRoiPct)} tier ROI, ${legacyShadowProfile.avgPerYear.toFixed(1)} bets/year historical).`
                    : "."}
                </li>
                <li>
                  Live volume_200 tracking: {volumeTrackedCount} rows, {volumeSettledCount} settled, {volumeOpenCount} currently open, {volumeNoMatchCount} parked as no_match, {formatPct(volumeAllRoi)} clean ROI.
                </li>
                <li>
                  Spread shadow tracking: {spreadShadowTrackedCount} signals, {spreadShadowSettledCount} settled, {formatPct(spreadShadowAllRoi)} ROI.
                </li>
                <li>
                  Clay 2026 tracking: {clay2026TrackedCount} signals, {clay2026SettledCount} settled, {formatPct(clay2026AllRoi)} ROI. ATP {clay2026AtpCohort.signals} tracked / {clay2026AtpCohort.settled} settled; Challenger {clay2026ChallengerCohort.signals} tracked / {clay2026ChallengerCohort.settled} settled and remains observational.
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
                <span className="font-semibold text-slate-100">Current interpretation:</span> strict live control is negative, shadow is too young, and CLV diagnosis is blocked by missing overlap from historical close data. Your own Pinnacle history capture is now the right path to fix that.
              </p>
              <p>
                <span className="font-semibold text-slate-100">Spread shadow:</span> this is now a separate clay/non-policy handicap lane. If it has no open picks, that means the tracker found nothing above the 20% threshold, not that the lane is broken.
              </p>
            </div>
          </MonitorCard>
        </div>
      </div>
    </div>
  );
}
