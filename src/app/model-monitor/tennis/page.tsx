import { readFile, stat } from "node:fs/promises";
import path from "node:path";
import Link from "next/link";
import { notFound } from "next/navigation";
import {
  TENNIS_LEGACY_DISABLED_LANES,
  TENNIS_MONITOR_FILES,
  TENNIS_RESEARCH_LANES,
  type TennisMonitorFilePath,
  type TennisResearchLaneId,
} from "@/lib/tennis-monitor-files";
import { tryGetKnownProjectFilePath } from "@/lib/project-file-paths";
import { StatusPill, cn } from "../shared";

export const dynamic = "force-dynamic";

const TENNIS_MONITOR_ENABLED =
  process.env.NODE_ENV !== "production" ||
  process.env.INTERNAL_RESEARCH_LANES === "1" ||
  process.env.MODEL_MONITOR_PUBLIC === "1" ||
  process.env.NEXT_PUBLIC_ENABLE_MODEL_MONITOR === "1";

type LaneView = {
  id: TennisResearchLaneId;
  title: string;
  state: "LIVE ALIAS" | "SHADOW LIVE" | "SHADOW PLANNED" | "DEFERRED" | "DISABLED" | "PAUSED - IDENTITY STALE";
  badgeTone: string;
  market: string;
  summary: string;
  disabledReason?: string;
};

type CsvRow = Record<string, string>;

type LaneStats = {
  liveCount: number;
  archiveCount: number;
  nearMissCount: number;
  pendingCount: number;
  settledCount: number;
  wins: number;
  losses: number;
  pnlUnits: number;
  roiPct: number | null;
  avgClvPct: number | null;
  clvRowCount: number;
  positiveClvPct: number | null;
  topNearMissReasons: string[];
  latestSignals: CsvRow[];
};

type SideFlipCohortSummary = {
  rows: CsvRow[];
  pending: number;
  settled: number;
  wins: number;
  losses: number;
  pnlUnits: number;
  roiPct: number | null;
  clvRows: number;
  avgClvPct: number | null;
  positiveClvPct: number | null;
};

const SIDE_FLIP_RETROSPECTIVE = {
  sample: 129,
  wins: 74,
  losses: 55,
  pnlUnits: 40.48,
  roiPct: 31.38,
  bootstrapLowPct: 11.31,
  bootstrapHighPct: 50.89,
  yearlyRoiPct: [
    ["2022", 44.79],
    ["2023", 20.23],
    ["2024", 22.72],
    ["2025", 39.97],
  ] as const,
};

type VNextResearchSummary = {
  verdict: string;
  residualVerdict: string;
  residualRows?: number;
  residualDelta?: number;
  residualCiHigh?: number;
  residualWorstFold?: number;
  countsIdentityVerdict: string;
  pairedRows?: number;
  coveragePct?: number;
  logLossDelta?: number;
  rawEce?: number;
  changedIdentityPct?: number;
  cleanLogLoss?: number;
  cleanEce?: number;
  cleanStrictBets?: number;
  cleanStrictRoi?: number;
};

function reportNumber(text: string | null, pattern: RegExp): number | undefined {
  const match = text?.match(pattern)?.[1];
  if (match == null) return undefined;
  const parsed = Number(match);
  return Number.isFinite(parsed) ? parsed : undefined;
}

function parseVNextResearchSummary(
  vnext: string | null,
  identity: string | null,
  residual: string | null,
  countsIdentity: string | null,
): VNextResearchSummary {
  return {
    verdict: vnext?.match(/VERDICT:\s*([^\r\n]+)/)?.[1]?.trim() || "NOT RUN",
    residualVerdict: residual?.match(/VERDICT:\s*([^\r\n]+)/)?.[1]?.trim() || "NOT RUN",
    residualRows: reportNumber(residual, /OOF rows:\s*(\d+)/i),
    residualDelta: reportNumber(residual, /Delta log-loss:\s*([+-]?[\d.]+)/i),
    residualCiHigh: reportNumber(residual, /bootstrap 95% CI:\s*\[[^,]+,\s*([+-]?[\d.]+)\]/i),
    residualWorstFold: reportNumber(residual, /Worst fold delta:\s*([+-]?[\d.]+)/i),
    countsIdentityVerdict: countsIdentity?.match(/VERDICT:\s*([^\r\n]+)/)?.[1]?.trim() || "NOT RUN",
    pairedRows: reportNumber(vnext, /paired count\/model rows:\s*(\d+)/i),
    coveragePct: reportNumber(vnext, /paired count\/model rows:[^\r\n]*\(([+-]?[\d.]+)% coverage\)/i),
    logLossDelta: reportNumber(vnext, /paired log-loss delta:\s*([+-]?[\d.]+)/i),
    rawEce: reportNumber(vnext, /vNext raw ECE:\s*([\d.]+)/i),
    changedIdentityPct: reportNumber(identity, /changed player IDs:[^\r\n]*\(([\d.]+)%\)/i),
    cleanLogLoss: reportNumber(identity, /identity-clean log-loss:\s*([\d.]+)/i),
    cleanEce: reportNumber(identity, /identity-clean ECE:\s*([\d.]+)/i),
    cleanStrictBets: reportNumber(identity, /strict identity-clean:\s*n=(\d+)/i),
    cleanStrictRoi: reportNumber(identity, /strict identity-clean:[^\r\n]*tier ROI\s*([+-]?[\d.]+)%/i),
  };
}

function VNextResearchCard({ summary }: { summary: VNextResearchSummary }) {
  const failed = summary.verdict.includes("FAIL");
  const residualFailed = summary.residualVerdict.includes("FAIL");
  return (
    <section className="rounded-2xl border border-amber-500/25 bg-[linear-gradient(135deg,rgba(120,53,15,0.16),rgba(2,6,23,0.82)_42%,rgba(15,23,42,0.9))] p-5 shadow-[0_18px_60px_rgba(2,6,23,0.28)]">
      <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.22em] text-amber-300">Architecture decision</p>
          <h2 className="mt-2 text-xl font-semibold text-slate-100">vNext registered decisions and identity audit</h2>
          <p className="mt-2 max-w-4xl text-sm leading-6 text-slate-400">
            Two locked ATP-hard experiments have now tested point information against the identity-clean incumbent. Both
            are research evidence only and neither can route signals.
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <StatusPill label={summary.verdict.replaceAll("_", " ")} tone={failed ? badgeTones.disabled : badgeTones.live} />
          <StatusPill label={summary.residualVerdict.replaceAll("_", " ")} tone={residualFailed ? badgeTones.disabled : badgeTones.live} />
          <StatusPill label={`COUNTS ID ${summary.countsIdentityVerdict}`} tone={summary.countsIdentityVerdict === "PASS" ? badgeTones.live : badgeTones.disabled} />
        </div>
      </div>
      <div className="mt-5 grid gap-3 sm:grid-cols-2 lg:grid-cols-4 xl:grid-cols-8">
        <EmptyMetric label="Paired rows" value={summary.pairedRows == null ? "-" : String(summary.pairedRows)} />
        <EmptyMetric label="Coverage" value={formatNumber(summary.coveragePct ?? null, "%")} />
        <EmptyMetric label="vNext LL delta" value={formatNumber(summary.logLossDelta ?? null, "", 4)} />
        <EmptyMetric label="vNext raw ECE" value={formatNumber(summary.rawEce ?? null, "", 4)} />
        <EmptyMetric label="IDs changed" value={formatNumber(summary.changedIdentityPct ?? null, "%")} />
        <EmptyMetric label="Clean log-loss" value={formatNumber(summary.cleanLogLoss ?? null, "", 4)} />
        <EmptyMetric label="Clean ECE" value={formatNumber(summary.cleanEce ?? null, "", 4)} />
        <EmptyMetric label="Clean strict" value={summary.cleanStrictBets == null ? "-" : `${summary.cleanStrictBets} / ${formatNumber(summary.cleanStrictRoi ?? null, "%")}`} />
      </div>
      <div className="mt-3 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <EmptyMetric label="v0.2 OOF rows" value={summary.residualRows == null ? "-" : String(summary.residualRows)} />
        <EmptyMetric label="v0.2 LL delta" value={formatNumber(summary.residualDelta ?? null, "", 6)} />
        <EmptyMetric label="v0.2 CI high" value={formatNumber(summary.residualCiHigh ?? null, "", 6)} />
        <EmptyMetric label="Worst fold" value={formatNumber(summary.residualWorstFold ?? null, "", 6)} />
      </div>
      <div className="mt-4 grid gap-3 md:grid-cols-2">
        <p className="rounded-xl border border-rose-500/20 bg-rose-500/8 px-4 py-3 text-sm leading-6 text-rose-100">
          v0.1 replacement and v0.2 anchored residual both failed their registered improvement gates. Further ML feature
          rungs are shelved; do not add CPI, event, fatigue or H2H terms to rescue the result.
        </p>
        <p className="rounded-xl border border-amber-500/20 bg-amber-500/8 px-4 py-3 text-sm leading-6 text-amber-100">
          Identity-clean strict remains the control. Point-level work now moves to derivatives and aces/DFs, where serve
          levels may improve count and line pricing without changing ML routing.
        </p>
      </div>
    </section>
  );
}


type ProofRow = {
  lane: string;
  label: string;
  signals: number;
  liveRows: number;
  pending: number;
  settled: number;
  wins: number;
  losses: number;
  voids: number;
  pnlUnits: number | null;
  roiPct: number | null;
  clvRows: number;
  avgClvPct: number | null;
  positiveClvPct: number | null;
  verdict: string;
  source: string;
  note: string;
};
type ProofReportLoad = {
  rows: ProofRow[];
  updatedAt: Date | null;
  ageLabel: string | null;
  stale: boolean;
};

type CpiSummary = {
  identityPaused: boolean;
  identityStatus: string | null;
  headlineRows: CsvRow[];
  candidateRows: CsvRow[];
  overlayRows: CsvRow[];
  overlayVerdict: string | null;
  overlayAvailable: boolean;
  regimeRows: CsvRow[];
  regimeVerdict: string | null;
  regimeAvailable: boolean;
  regimeGateRows: CsvRow[];
  regimeFactorRows: CsvRow[];
  regimeGateVerdict: string | null;
  regimeGatesAvailable: boolean;
  reportAvailable: boolean;
};

type ExtremeGapMetric = {
  signals: number;
  pending: number;
  settled: number;
  wins: number;
  losses: number;
  voids: number;
  pnl_units: number;
  roi_pct: number | null;
  clv_rows: number;
  avg_clv_pct: number | null;
  positive_clv_pct: number | null;
};

type ExtremeGapReport = {
  generated_at: string;
  status: string;
  anomalies: number;
  ml: ExtremeGapMetric;
  spread: ExtremeGapMetric;
  paired_settled: number;
  paired_outcomes: Record<string, number>;
  spread_rescues?: number;
  spread_rescue_rate_pct?: number | null;
  windows?: {
    last_7_days: { spread: ExtremeGapMetric };
    last_30_days: { spread: ExtremeGapMetric };
  };
  long_ev_100_plus?: {
    ml: ExtremeGapMetric;
    spread: ExtremeGapMetric;
  };
  weekly_review?: {
    verdict: string;
    reason: string;
    handicap_trustworthy_live: boolean;
    automatic_promotion: boolean;
  };
  spread_promotion_gate: {
    passes: boolean;
    rule: string;
  };
  ml_guard_replacement?: {
    registered_at: string;
    status: string;
    automatic_promotion: boolean;
    rule: string;
    experiments: Record<string, {
      description: string;
      captured: number;
      quality_eligible: number;
      excluded_low_quality: number;
      performance: ExtremeGapMetric;
      passes: boolean;
      verdict: string;
      historical?: {
        passes_retrospective_screen?: boolean;
        performance?: HistoricalGapPerformance;
        positive_material_years?: number;
        material_years?: number;
      };
    }>;
    side_flip_by_surface: Record<string, ExtremeGapMetric>;
  };
};

type ExtremeGapLoad = {
  report: ExtremeGapReport | null;
  historical: HistoricalGapReport | null;
  liveRows: CsvRow[];
};

type HistoricalGapPerformance = {
  settled: number;
  wins: number;
  losses: number;
  pushes: number;
  pnl_units: number;
  roi_pct: number | null;
  roi_95ci_pct: [number, number] | null;
};

type GapThresholdPartition = {
  threshold_pp: number;
  candidates: number;
  allowed: HistoricalGapPerformance;
  blocked: HistoricalGapPerformance;
  gap_blocked: HistoricalGapPerformance;
  side_flip_blocked: HistoricalGapPerformance;
  blocked_side_flips: number;
};

type GapThresholdProfile = {
  description: string;
  candidates: number;
  cutoffs: Record<string, GapThresholdPartition>;
};

type HistoricalGapReport = {
  status: string;
  screening_verdict: string;
  anomalies: number;
  ml: HistoricalGapPerformance;
  paired_real_spread_matches: number;
  spread: HistoricalGapPerformance;
  spread_rescues: number;
  ml_losses_with_spread: number;
  long_ev_100_plus: {
    anomalies: number;
    paired_spread_anomalies: number;
    ml: HistoricalGapPerformance;
    spread: HistoricalGapPerformance;
  };
  threshold_audit?: {
    status: string;
    locked_guard_pp: number;
    thresholds_pp: number[];
    decision: string;
    warning: string;
    profiles: Record<string, GapThresholdProfile>;
    locked_10pp_by_surface: Record<string, GapThresholdPartition>;
    locked_10pp_by_year: Record<string, GapThresholdPartition>;
    registered_replacement_experiments?: {
      registered_at: string;
      status: string;
      automatic_promotion: boolean;
      forward_gate: string;
      experiments: Record<string, {
        description: string;
        performance: HistoricalGapPerformance;
        positive_material_years: number;
        material_years: number;
        passes_retrospective_screen: boolean;
      }>;
      side_flip_surface_diagnostics: Record<string, {
        performance: HistoricalGapPerformance;
        passes_retrospective_screen: boolean;
      }>;
    };
  };
};

type GuardPerformance = {
  bets: number;
  wins: number;
  losses: number;
  pnl_units: number;
  roi_pct: number | null;
  win_rate_pct: number | null;
  avg_odds: number | null;
};

type GuardReplayEntry = {
  flagged: GuardPerformance;
  unique: GuardPerformance;
  marginal_removed: GuardPerformance;
  survivors_without_this_guard: GuardPerformance;
  first_hit_bets: number;
};

type GuardProfileAudit = {
  before_guards: GuardPerformance;
  after_all_replayable_guards: GuardPerformance;
  blocked_by_any: GuardPerformance;
  guards: Record<string, GuardReplayEntry>;
};

type GuardInventoryEntry = {
  id: string;
  decision: string;
  evidence: string;
  live_scope?: string;
};

type TennisGuardAudit = {
  generated_at: string;
  status: string;
  rows_loaded: number;
  profile_descriptions: Record<string, string>;
  profiles: Record<string, GuardProfileAudit>;
  inventory: Record<string, GuardInventoryEntry[]>;
};

const badgeTones = {
  live: "border-emerald-500/25 bg-emerald-500/10 text-emerald-300",
  shadow: "border-cyan-500/25 bg-cyan-500/10 text-cyan-300",
  deferred: "border-slate-600/50 bg-slate-800/70 text-slate-300",
  disabled: "border-amber-500/25 bg-amber-500/10 text-amber-300",
};

const laneViews: Record<TennisResearchLaneId, LaneView> = {
  hard_bo3: {
    id: "hard_bo3",
    title: "Hard bo3",
    state: "LIVE ALIAS",
    badgeTone: badgeTones.live,
    market: "ML anchor",
    summary: "Phase 0 aliases this lane to the existing strict profile. No probability math changes.",
  },
  clay_bo3: {
    id: "clay_bo3",
    title: "Clay bo3",
    state: "SHADOW LIVE",
    badgeTone: badgeTones.shadow,
    market: "ML, dog HC",
    summary: "Internal clay shadow lane using existing fair-odds output: ATP clay ML edges plus dog-handicap candidates.",
  },
  slam_bo5: {
    id: "slam_bo5",
    title: "Slam bo5",
    state: "SHADOW PLANNED",
    badgeTone: badgeTones.shadow,
    market: "Fav ML, dog HC, overs",
    summary: "Placeholder for the Grand Slam best-of-five lane. No bo5 model is active in Phase 0.",
  },
  challenger_ml: {
    id: "challenger_ml",
    title: "Challenger ML v2 tracker",
    state: "SHADOW LIVE",
    badgeTone: badgeTones.shadow,
    market: "ML evidence only",
    summary: "Fresh zero-stake cohort with immutable entry prices, nightly settlement and verified-close CLV. The rejected 23-row legacy batch is excluded."
  },
  indoor_bo3: {
    id: "indoor_bo3",
    title: "Indoor bo3",
    state: "DEFERRED",
    badgeTone: badgeTones.deferred,
    market: "ML, fav HC, unders",
    summary: "Scaffold only. Build starts during the indoor swing if the active lanes prove stable.",
  },
  grass_bo3: {
    id: "grass_bo3",
    title: "Grass bo3",
    state: "SHADOW LIVE",
    badgeTone: badgeTones.shadow,
    market: "ML only",
    summary: "Internal ATP grass warm-up ML lane: ATP250/ATP500, high+medium confidence, 10-30% value, model-market favourite agreement, and lagged CPI guard: slow grass (<1.05) and missing CPI blocked; neutral/fast allowed.",
  },
  cpi_speed_shadow: {
    id: "cpi_speed_shadow",
    title: "CPI speed shadow",
    state: "PAUSED - IDENTITY STALE",
    badgeTone: badgeTones.disabled,
    market: "ML by court speed",
    summary:
      "Historical CPI pass cells predate the identity repair. Signal attachment is fail-closed until every gate is regenerated with identity_basis=idclean_v1.",
  },
  challenger_hc: {
    id: "challenger_hc",
    title: "Challenger HC",
    state: "DISABLED",
    badgeTone: badgeTones.disabled,
    market: "No active market",
    summary: "Disabled until Challenger ML has enough proof and Pinnacle HC coverage is audited.",
    disabledReason: "awaiting Pinnacle HC coverage + challenger_ml proof",
  },
};

function laneAnchor(id: string) {
  return id.replaceAll("_", "-");
}

function parseCsvLine(line: string): string[] {
  const out: string[] = [];
  let current = "";
  let inQuotes = false;
  for (let i = 0; i < line.length; i += 1) {
    const char = line[i];
    if (char === '"') {
      if (inQuotes && line[i + 1] === '"') {
        current += '"';
        i += 1;
      } else {
        inQuotes = !inQuotes;
      }
    } else if (char === "," && !inQuotes) {
      out.push(current);
      current = "";
    } else {
      current += char;
    }
  }
  out.push(current);
  return out;
}

function parseCsv(text: string): CsvRow[] {
  const lines = text.split(/\r?\n/).filter((line) => line.trim().length > 0);
  if (lines.length === 0) return [];
  const headers = parseCsvLine(lines[0]).map((header) => header.trim());
  return lines.slice(1).map((line) => {
    const values = parseCsvLine(line);
    return Object.fromEntries(headers.map((header, index) => [header, values[index] ?? ""]));
  });
}

async function readKnownFile(relativePath?: TennisMonitorFilePath): Promise<string | null> {
  if (!relativePath) return null;
  const candidates = Array.isArray(relativePath) ? relativePath : [relativePath];
  for (const candidate of candidates) {
    const fullPath = tryGetKnownProjectFilePath(candidate) ?? path.join(process.cwd(), candidate);
    try {
      return await readFile(fullPath, "utf8");
    } catch {
      // Try the next fallback path.
    }
  }
  return null;
}

async function readKnownMtime(relativePath?: TennisMonitorFilePath): Promise<Date | null> {
  if (!relativePath) return null;
  const candidates = Array.isArray(relativePath) ? relativePath : [relativePath];
  for (const candidate of candidates) {
    const fullPath = tryGetKnownProjectFilePath(candidate) ?? path.join(process.cwd(), candidate);
    try {
      const info = await stat(fullPath);
      return info.mtime;
    } catch {
      // Try the next fallback path.
    }
  }
  return null;
}
function formatFileTarget(target?: TennisMonitorFilePath): string {
  if (!target) return "-";
  return Array.isArray(target) ? target.join(" | fallback: ") : target;
}

function toNumber(value: string | undefined): number | null {
  if (value === undefined || value === "") return null;
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : null;
}

function isWon(row: CsvRow): boolean {
  const raw = `${row.won_bet || row.bet_outcome || row.result || ""}`.toLowerCase();
  return raw === "true" || raw === "1" || raw.includes("won") || raw === "w";
}

function isLost(row: CsvRow): boolean {
  const raw = `${row.won_bet || row.bet_outcome || row.result || ""}`.toLowerCase();
  return raw === "false" || raw === "0" || raw.includes("lost") || raw === "l";
}

function isPendingRow(row: CsvRow): boolean {
  const status = (row.settlement_status || row.status || "").trim().toLowerCase();
  if (status === "settled" || status === "void" || status === "cancelled") return false;
  return !isWon(row) && !isLost(row);
}

function settledRows(rows: CsvRow[]): CsvRow[] {
  return rows.filter((row) => isWon(row) || isLost(row));
}

function rowPnlUnits(row: CsvRow): number | null {
  const stake = toNumber(row.stake_units) ?? 1;
  if (isLost(row)) return -stake;
  if (!isWon(row)) return null;
  const odds =
    row.bet_type === "spread"
      ? toNumber(row.spread_odds)
      : row.side === "P2"
        ? toNumber(row.pin_odds2)
        : toNumber(row.pin_odds1);
  if (!odds) return null;
  return (odds - 1) * stake;
}

function normalizedTwoWayProbabilities(odds1: number | null, odds2: number | null): [number, number] | null {
  if (odds1 == null || odds2 == null || odds1 <= 1 || odds2 <= 1) return null;
  const inverse1 = 1 / odds1;
  const inverse2 = 1 / odds2;
  const total = inverse1 + inverse2;
  if (!(total > 0)) return null;
  return [inverse1 / total, inverse2 / total];
}

function isAllowedStrictSideFlip(row: CsvRow): boolean {
  if ((row.bet_type || "match").trim().toLowerCase() !== "match") return false;
  if ((row.surface || "").trim().toLowerCase() !== "hard") return false;
  if ((row.series || "").trim().toLowerCase() !== "masters 1000") return false;
  if ((row.confidence || "").trim().toLowerCase() !== "high") return false;
  if (row.league && row.league.trim().toLowerCase() !== "atp") return false;

  const model = normalizedTwoWayProbabilities(toNumber(row.our_odds1), toNumber(row.our_odds2));
  const market = normalizedTwoWayProbabilities(toNumber(row.pin_odds1), toNumber(row.pin_odds2));
  if (!model || !market) return false;

  const modelSide = model[0] >= model[1] ? "P1" : "P2";
  const marketSide = market[0] >= market[1] ? "P1" : "P2";
  const modelFavoriteProb = Math.max(...model);
  const marketFavoriteProb = Math.max(...market);
  return (
    modelSide !== marketSide &&
    Math.abs(model[0] - 0.5) >= 0.03 &&
    Math.abs(market[0] - 0.5) >= 0.03 &&
    Math.abs(modelFavoriteProb - marketFavoriteProb) <= 0.1
  );
}

function signalClvKey(row: CsvRow): string {
  return [
    row.match_date || row.signal_date || row.date || "",
    (row.player1 || "").trim().toLowerCase(),
    (row.player2 || "").trim().toLowerCase(),
    (row.side || "").trim().toUpperCase(),
  ].join("|");
}

async function loadSideFlipCohort(): Promise<SideFlipCohortSummary> {
  const files = TENNIS_MONITOR_FILES.hard_bo3;
  const [liveCsv, archiveCsv, clvCsv] = await Promise.all([
    readKnownFile(files.live),
    readKnownFile(files.archive),
    readKnownFile(files.clvAuditCsv),
  ]);
  const allRows = latestCapturedRows(
    [...(archiveCsv ? parseCsv(archiveCsv) : []), ...(liveCsv ? parseCsv(liveCsv) : [])],
    Number.POSITIVE_INFINITY,
  ).filter(isAllowedStrictSideFlip);
  const clvByKey = new Map(
    (clvCsv ? parseCsv(clvCsv) : []).map((row) => [signalClvKey(row), row] as const),
  );
  const rows = allRows
    .map((row) => {
      const clv = clvByKey.get(signalClvKey(row));
      return clv ? { ...row, cohort_clv_pct: clv.clv_implied_delta_pct || clv.clv_pct || "" } : row;
    })
    .sort((left, right) => rowSignalTimestamp(right) - rowSignalTimestamp(left));
  const settled = settledRows(rows);
  const wins = settled.filter(isWon).length;
  const losses = settled.filter(isLost).length;
  const pnlUnits = settled.map(rowPnlUnits).filter((value): value is number => value !== null).reduce((sum, value) => sum + value, 0);
  const stakedUnits = settled.reduce((sum, row) => sum + (toNumber(row.stake_units) ?? 1), 0);
  const clvValues = rows.map((row) => toNumber(row.cohort_clv_pct)).filter((value): value is number => value !== null);
  return {
    rows,
    pending: rows.filter(isPendingRow).length,
    settled: settled.length,
    wins,
    losses,
    pnlUnits,
    roiPct: stakedUnits > 0 ? (pnlUnits / stakedUnits) * 100 : null,
    clvRows: clvValues.length,
    avgClvPct: avg(clvValues),
    positiveClvPct: clvValues.length ? (clvValues.filter((value) => value > 0).length / clvValues.length) * 100 : null,
  };
}

function avg(values: number[]): number | null {
  if (values.length === 0) return null;
  return values.reduce((sum, value) => sum + value, 0) / values.length;
}

function formatNumber(value: number | null, suffix = "", digits = 1): string {
  if (value === null || !Number.isFinite(value)) return "-";
  const sign = value > 0 ? "+" : "";
  return `${sign}${value.toFixed(digits)}${suffix}`;
}

function formatSignedPct(value: string | undefined): string {
  return formatNumber(toNumber(value), "%");
}


function proofReportAgeLabel(updatedAt: Date | null, nowMs: number): string | null {
  if (!updatedAt) return null;
  const hours = Math.max(0, (nowMs - updatedAt.getTime()) / 36e5);
  if (hours < 1) return "updated <1h ago";
  if (hours < 48) return `updated ${Math.round(hours)}h ago`;
  return `updated ${Math.round(hours / 24)}d ago`;
}
function numericMetric(value: string | undefined): number {
  return toNumber(value) ?? 0;
}

function nullableMetric(value: string | undefined): number | null {
  return toNumber(value);
}

function proofVerdictFromStats(stats: LaneStats): string {
  if (stats.settledCount === 0) return stats.pendingCount > 0 || stats.liveCount > 0 ? "COLLECTING" : "NO SAMPLE";
  if (stats.settledCount < 30) return "TOO EARLY";
  if (stats.clvRowCount === 0) return "ROI ONLY - CLV MISSING";
  if (
    stats.settledCount >= 100 &&
    stats.clvRowCount >= 50 &&
    (stats.roiPct ?? 0) >= 0 &&
    (stats.avgClvPct ?? 0) >= 0.5 &&
    (stats.positiveClvPct ?? 0) >= 52
  ) {
    return "PROMOTION WATCH";
  }
  if ((stats.roiPct ?? 0) < -5 || (stats.avgClvPct ?? 0) < -0.5) return "CAUTION";
  return "SHADOW HOLD";
}

function proofTone(verdict: string): string {
  const normalized = verdict.toUpperCase();
  if (normalized.includes("PROMOTION")) return badgeTones.live;
  if (normalized.includes("CAUTION")) return "border-rose-500/25 bg-rose-500/10 text-rose-300";
  if (normalized.includes("MISSING") || normalized.includes("COLLECTING") || normalized.includes("TOO EARLY")) {
    return badgeTones.disabled;
  }
  if (normalized.includes("NO SAMPLE")) return badgeTones.deferred;
  return badgeTones.shadow;
}

function proofRowsFromStats(statsByLane: Record<TennisResearchLaneId, LaneStats>): ProofRow[] {
  return TENNIS_RESEARCH_LANES.map((id) => {
    const stats = statsByLane[id];
    const lane = laneViews[id];
    return {
      lane: id,
      label: lane.title,
      signals: stats.archiveCount,
      liveRows: stats.liveCount,
      pending: stats.pendingCount,
      settled: stats.settledCount,
      wins: stats.wins,
      losses: stats.losses,
      voids: 0,
      pnlUnits: stats.pnlUnits,
      roiPct: stats.roiPct,
      clvRows: stats.clvRowCount,
      avgClvPct: stats.avgClvPct,
      positiveClvPct: stats.positiveClvPct,
      verdict: proofVerdictFromStats(stats),
      source: "live page fallback",
      note: lane.summary,
    };
  });
}

function findProofRow(rows: ProofRow[], lane: string): ProofRow | null {
  return rows.find((row) => row.lane === lane) ?? null;
}

function formatRecord(row: ProofRow | null): string {
  if (!row) return "-";
  if (row.settled === 0) return "0 settled";
  return `${row.wins}W-${row.losses}L / ${formatNumber(row.pnlUnits, "u", 2)}`;
}

function metricTone(value: number | null | undefined): string {
  if (value === null || value === undefined || !Number.isFinite(value)) return "text-slate-300";
  if (value > 0) return "text-emerald-300";
  if (value < 0) return "text-rose-300";
  return "text-slate-300";
}

function DecisionCard({
  eyebrow,
  title,
  body,
  rows,
  tone,
  href,
  cta,
}: {
  eyebrow: string;
  title: string;
  body: string;
  rows: Array<ProofRow | null>;
  tone: string;
  href?: string;
  cta?: string;
}) {
  const content = (
    <div className={cn("group h-full rounded-2xl border p-5 transition-colors", tone)}>
      <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-400">{eyebrow}</p>
      <h2 className="mt-2 text-xl font-semibold text-slate-50">{title}</h2>
      <p className="mt-2 text-sm leading-6 text-slate-300">{body}</p>
      <div className="mt-4 space-y-2">
        {rows.map((row, index) => (
          <div key={row?.lane ?? index} className="rounded-xl border border-slate-800/75 bg-slate-950/55 p-3">
            <div className="flex items-start justify-between gap-3">
              <div>
                <p className="text-sm font-semibold text-slate-100">{row?.label ?? "No lane"}</p>
                <p className="mt-1 text-xs text-slate-500">{row ? formatRecord(row) : "No data file yet"}</p>
              </div>
              {row ? (
                <StatusPill
                  label={row.lane === "strict_ml" ? "LIVE CORE" : row.verdict}
                  tone={row.lane === "strict_ml" ? badgeTones.live : proofTone(row.verdict)}
                />
              ) : null}
            </div>
            {row ? (
              <div className="mt-3 grid grid-cols-3 gap-2 text-xs">
                <div>
                  <p className="text-slate-500">ROI</p>
                  <p className={cn("font-semibold tabular-nums", metricTone(row.roiPct))}>{formatNumber(row.roiPct, "%")}</p>
                </div>
                <div>
                  <p className="text-slate-500">CLV n</p>
                  <p className="font-semibold tabular-nums text-slate-100">{row.clvRows}</p>
                </div>
                <div>
                  <p className="text-slate-500">Avg CLV</p>
                  <p className={cn("font-semibold tabular-nums", metricTone(row.avgClvPct))}>{formatNumber(row.avgClvPct, "%", 2)}</p>
                </div>
              </div>
            ) : null}
          </div>
        ))}
      </div>
      {href && cta ? (
        <p className="mt-4 text-xs font-semibold uppercase tracking-[0.14em] text-emerald-200 group-hover:text-emerald-100">
          {cta} {"->"}
        </p>
      ) : null}
    </div>
  );
  return href ? <Link href={href}>{content}</Link> : content;
}

function TennisDecisionBoard({
  rows,
  fromReport,
  reportAge,
  reportStale,
}: {
  rows: ProofRow[];
  fromReport: boolean;
  reportAge: string | null;
  reportStale: boolean;
}) {
  const strict = findProofRow(rows, "strict_ml");
  const volume = findProofRow(rows, "volume_200");
  const spread = findProofRow(rows, "spread_v1");
  const grass = findProofRow(rows, "grass_bo3");
  const cpi = findProofRow(rows, "cpi_speed_shadow");
  const challenger = findProofRow(rows, "challenger_ml");
  const clay = findProofRow(rows, "clay_bo3");

  return (
    <section className="rounded-3xl border border-emerald-500/20 bg-[radial-gradient(circle_at_top_left,rgba(16,185,129,0.17),transparent_34%),linear-gradient(135deg,rgba(15,23,42,0.97),rgba(2,6,23,0.98))] p-5 shadow-[0_24px_80px_rgba(2,6,23,0.34)] md:p-6">
      <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
        <div>
          <div className="flex flex-wrap items-center gap-2">
            <p className="text-xs font-semibold uppercase tracking-[0.22em] text-emerald-300">Tennis control room</p>
            <StatusPill label={fromReport ? "PROOF REPORT LOADED" : "LIVE FALLBACK"} tone={fromReport ? badgeTones.live : badgeTones.disabled} />
            <StatusPill label={reportStale ? "STALE / MISSING" : "FRESH"} tone={reportStale ? badgeTones.disabled : badgeTones.live} />
          </div>
          <h1 className="mt-3 text-3xl font-semibold tracking-tight text-slate-50 md:text-4xl">
            What can I trust today?
          </h1>
          <p className="mt-3 max-w-4xl text-sm leading-6 text-slate-400">
            Read this page top to bottom: sellable core first, measured expansion second, then shadow experiments that need ROI/CLV proof before they become tips.
          </p>
        </div>
        <div className="rounded-2xl border border-slate-800 bg-slate-950/55 px-4 py-3 text-sm text-slate-300">
          <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-500">Refresh source</p>
          <p className="mt-1">{fromReport ? reportAge ?? "timestamp unavailable" : "generated from live CSVs"}</p>
        </div>
      </div>

      <div className="mt-6 grid gap-4 xl:grid-cols-3">
        <DecisionCard
          eyebrow="Use now, narrowly"
          title="Strict ML is still the core product"
          body="Only the strict hard/Masters/high-confidence cell is live-grade. Keep showing CLV coverage honestly; do not broaden it just to create volume."
          rows={[strict]}
          tone="border-emerald-500/25 bg-emerald-500/10 hover:border-emerald-400/50"
          href="#tennis-proof"
          cta="Open proof board"
        />
        <DecisionCard
          eyebrow="Watch / bundle"
          title="Volume 200 is not a standalone product"
          body="The record is positive, but the sample is small and CLV proof is missing. Treat it as a measured add-on inside tennis, not a separate sellable lane."
          rows={[volume]}
          tone="border-cyan-500/25 bg-cyan-500/10 hover:border-cyan-400/50"
          href="#tennis-proof"
          cta="Check sample"
        />
        <DecisionCard
          eyebrow="Do not bet yet"
          title="Shadow lanes need proof"
          body="Spread v1, grass, CPI speed, clay, and Challenger are visible so we can learn. They are not trusted tips until settled ROI and CLV gates pass."
          rows={[spread, grass, cpi, challenger, clay]}
          tone="border-amber-500/25 bg-amber-500/10 hover:border-amber-400/50"
          href="#shadow-lanes"
          cta="Review shadows"
        />
      </div>

      <div className="mt-4 grid gap-3 md:grid-cols-2">
        <Link
          href="/model-monitor/tennis-props"
          className="rounded-2xl border border-slate-800 bg-slate-950/55 p-4 transition-colors hover:border-emerald-500/40"
        >
          <p className="text-xs font-semibold uppercase tracking-[0.18em] text-emerald-300">Props board</p>
          <p className="mt-1 text-lg font-semibold text-slate-100">Aces / DFs / breaks / tiebreaks</p>
          <p className="mt-1 text-sm text-slate-400">Projection and Bet365 comparison board. Research-only unless matched prices and settlement prove it.</p>
        </Link>
        <Link
          href="/fair-odds"
          className="rounded-2xl border border-slate-800 bg-slate-950/55 p-4 transition-colors hover:border-teal-500/40"
        >
          <p className="text-xs font-semibold uppercase tracking-[0.18em] text-teal-300">Live board</p>
          <p className="mt-1 text-lg font-semibold text-slate-100">Fair odds page</p>
          <p className="mt-1 text-sm text-slate-400">Current match board. Signals must still pass the policy/guard layer before being treated as picks.</p>
        </Link>
      </div>
    </section>
  );
}

function gapMetricValue(value: number | null, suffix = "%") {
  return value == null ? "n/a" : `${value >= 0 ? "+" : ""}${value.toFixed(2)}${suffix}`;
}

function gapDiagnosisLabel(row: CsvRow) {
  const tags = String(row.diagnosis_tags || "")
    .split("|")
    .map((tag) => tag.trim())
    .filter(Boolean);
  const priority = [
    "component_disagreement",
    "serve_return_market_outlier",
    "elo_market_outlier",
    "point_shape_divergence",
    "large_calibration_shift",
    "low_12m_sample",
    "inactivity_45d",
    "partial_coverage",
  ];
  const selected = priority.filter((tag) => tags.includes(tag)).slice(0, 3);
  return (selected.length > 0 ? selected : [String(row.diagnosis_primary || "unexplained")])
    .map((tag) => tag.replaceAll("_", " "))
    .join(" · ");
}

function ExtremeGapLab({ data }: { data: ExtremeGapLoad }) {
  const { report, historical, liveRows } = data;
  const ml = report?.ml;
  const spread = report?.spread;
  const spreadRescues = report?.paired_outcomes?.ml_loss__spread_win ?? 0;
  const reviewVerdict = report?.weekly_review?.verdict ?? "KEEP COLLECTING";
  const reviewReason = report?.weekly_review?.reason ?? "Waiting for enough settled prices and closing-line evidence.";
  const trailing30Spread = report?.windows?.last_30_days?.spread;
  const longEvSpread = report?.long_ev_100_plus?.spread;
  const thresholdProfiles = historical?.threshold_audit?.profiles ?? {};
  const guardReplacement = report?.ml_guard_replacement;
  const replacementExperiments = guardReplacement?.experiments ?? {};
  const historicalSideFlips = historical?.threshold_audit?.registered_replacement_experiments?.side_flip_surface_diagnostics ?? {};
  const currentMlRows = liveRows.filter((row) => row.bet_type !== "spread").slice(0, 8);
  const spreadByAnomaly = new Map(
    liveRows.filter((row) => row.bet_type === "spread").map((row) => [row.anomaly_id, row]),
  );
  return (
    <section id="extreme-gap-lab" className="rounded-3xl border border-rose-500/20 bg-[radial-gradient(circle_at_top_right,rgba(244,63,94,0.13),transparent_36%),linear-gradient(135deg,rgba(15,23,42,0.97),rgba(2,6,23,0.98))] p-5 md:p-6">
      <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
        <div>
          <div className="flex flex-wrap items-center gap-2">
            <p className="text-xs font-semibold uppercase tracking-[0.22em] text-rose-300">Extreme gap lab</p>
            <StatusPill label="RESEARCH ONLY" tone={badgeTones.disabled} />
            <StatusPill label={report?.spread_promotion_gate?.passes ? "REVIEW CANDIDATE" : reviewVerdict.replaceAll("_", " ")} tone={report?.spread_promotion_gate?.passes ? badgeTones.live : badgeTones.disabled} />
          </div>
          <h2 className="mt-3 text-2xl font-semibold tracking-tight text-slate-50">When the model and Pinnacle violently disagree</h2>
          <p className="mt-2 max-w-4xl text-sm leading-6 text-slate-400">
            Every large gap is frozen as two separate tests: the model&apos;s ML side and that same player on the available Pinnacle spread. A huge EV is treated as a fault signal first, not a tip.
          </p>
        </div>
        <div className="rounded-2xl border border-slate-800 bg-slate-950/55 px-4 py-3 text-sm text-slate-300">
          <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-500">Promotion review gate</p>
          <p className="mt-1 max-w-sm text-xs leading-5 text-slate-400">{report?.spread_promotion_gate?.rule ?? "n>=200 plus positive ROI and CLV proof"}</p>
          <p className="mt-2 text-[10px] font-semibold uppercase tracking-[0.14em] text-amber-300">Never auto-promoted</p>
        </div>
      </div>

      <div className="mt-5 grid gap-3 sm:grid-cols-2 xl:grid-cols-5">
        <div className="rounded-2xl border border-slate-800 bg-slate-950/55 p-4">
          <p className="text-[11px] uppercase tracking-[0.16em] text-slate-500">Today&apos;s anomalies</p>
          <p className="mt-2 text-2xl font-semibold tabular-nums text-white">{new Set(liveRows.map((row) => row.anomaly_id).filter(Boolean)).size}</p>
        </div>
        <div className="rounded-2xl border border-slate-800 bg-slate-950/55 p-4">
          <p className="text-[11px] uppercase tracking-[0.16em] text-slate-500">ML settled / ROI</p>
          <p className="mt-2 text-lg font-semibold tabular-nums text-slate-100">{ml?.settled ?? 0} / <span className={metricTone(ml?.roi_pct)}>{gapMetricValue(ml?.roi_pct ?? null)}</span></p>
        </div>
        <div className="rounded-2xl border border-slate-800 bg-slate-950/55 p-4">
          <p className="text-[11px] uppercase tracking-[0.16em] text-slate-500">Spread settled / ROI</p>
          <p className="mt-2 text-lg font-semibold tabular-nums text-slate-100">{spread?.settled ?? 0} / <span className={metricTone(spread?.roi_pct)}>{gapMetricValue(spread?.roi_pct ?? null)}</span></p>
        </div>
        <div className="rounded-2xl border border-slate-800 bg-slate-950/55 p-4">
          <p className="text-[11px] uppercase tracking-[0.16em] text-slate-500">Spread CLV</p>
          <p className="mt-2 text-lg font-semibold tabular-nums text-slate-100"><span className={metricTone(spread?.avg_clv_pct)}>{gapMetricValue(spread?.avg_clv_pct ?? null)}</span> <span className="text-xs text-slate-500">n={spread?.clv_rows ?? 0}</span></p>
        </div>
        <div className="rounded-2xl border border-slate-800 bg-slate-950/55 p-4">
          <p className="text-[11px] uppercase tracking-[0.16em] text-slate-500">Spread rescued ML loss</p>
          <p className="mt-2 text-2xl font-semibold tabular-nums text-cyan-200">{spreadRescues}</p>
        </div>
      </div>

      <div className="mt-4 grid gap-3 lg:grid-cols-3">
        <div className="rounded-2xl border border-amber-500/20 bg-amber-500/5 p-4">
          <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-amber-300">Weekly decision</p>
          <p className="mt-2 text-lg font-semibold text-slate-100">{reviewVerdict.replaceAll("_", " ")}</p>
          <p className="mt-2 text-xs leading-5 text-slate-400">{reviewReason}</p>
        </div>
        <div className="rounded-2xl border border-slate-800 bg-slate-950/55 p-4">
          <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-500">Last 30 days · spread</p>
          <p className="mt-2 text-lg font-semibold tabular-nums text-slate-100">
            {trailing30Spread?.settled ?? 0} settled · <span className={metricTone(trailing30Spread?.roi_pct)}>{gapMetricValue(trailing30Spread?.roi_pct ?? null)} ROI</span>
          </p>
          <p className="mt-2 text-xs text-slate-500">CLV {gapMetricValue(trailing30Spread?.avg_clv_pct ?? null)} · n={trailing30Spread?.clv_rows ?? 0}</p>
        </div>
        <div className="rounded-2xl border border-slate-800 bg-slate-950/55 p-4">
          <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-500">ML EV ≥100% · paired spread</p>
          <p className="mt-2 text-lg font-semibold tabular-nums text-slate-100">
            {longEvSpread?.settled ?? 0} settled · <span className={metricTone(longEvSpread?.roi_pct)}>{gapMetricValue(longEvSpread?.roi_pct ?? null)} ROI</span>
          </p>
          <p className="mt-2 text-xs text-slate-500">CLV {gapMetricValue(longEvSpread?.avg_clv_pct ?? null)} · n={longEvSpread?.clv_rows ?? 0}</p>
        </div>
      </div>

      <div className="mt-4 rounded-2xl border border-emerald-500/20 bg-emerald-500/[0.06] p-4 md:p-5">
        <div className="flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
          <div>
            <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-emerald-300">Registered ML guard replacement</p>
            <h3 className="mt-2 text-lg font-semibold text-slate-100">Test the blocked ML bets, not the losing handicap shortcut</h3>
            <p className="mt-2 max-w-4xl text-xs leading-5 text-slate-400">
              Strict tests same-side gaps from 10-20pp. Volume 200 tests 10-15pp. Low-quality or partial inputs are excluded from forward proof, and live routing remains unchanged.
            </p>
          </div>
          <div className="flex flex-wrap gap-2">
            <StatusPill label="SHADOW ONLY" tone={badgeTones.shadow} />
            <StatusPill label="NO AUTO PROMOTION" tone={badgeTones.disabled} />
          </div>
        </div>

        <div className="mt-4 grid gap-3 xl:grid-cols-2">
          {Object.entries(replacementExperiments).map(([experimentId, experiment]) => {
            const forward = experiment.performance;
            const backtest = experiment.historical?.performance;
            return (
              <div key={experimentId} className="rounded-2xl border border-slate-800 bg-slate-950/55 p-4">
                <div className="flex flex-wrap items-start justify-between gap-2">
                  <div>
                    <p className="text-sm font-semibold text-slate-100">{experimentId.startsWith("strict") ? "Strict ML gap replacement" : "Volume 200 gap replacement"}</p>
                    <p className="mt-1 text-[11px] text-slate-500">{experiment.description}</p>
                  </div>
                  <StatusPill label={experiment.verdict.replaceAll("_", " ")} tone={experiment.passes ? badgeTones.live : badgeTones.shadow} />
                </div>
                <div className="mt-4 grid grid-cols-2 gap-3 sm:grid-cols-4">
                  <div>
                    <p className="text-[10px] uppercase tracking-[0.13em] text-slate-600">Backtest</p>
                    <p className="mt-1 font-semibold tabular-nums text-slate-200">n={backtest?.settled ?? 0}</p>
                  </div>
                  <div>
                    <p className="text-[10px] uppercase tracking-[0.13em] text-slate-600">Historical ROI</p>
                    <p className={cn("mt-1 font-semibold tabular-nums", metricTone(backtest?.roi_pct))}>{gapMetricValue(backtest?.roi_pct ?? null)}</p>
                  </div>
                  <div>
                    <p className="text-[10px] uppercase tracking-[0.13em] text-slate-600">Forward settled</p>
                    <p className="mt-1 font-semibold tabular-nums text-slate-200">{forward.settled} / 150</p>
                  </div>
                  <div>
                    <p className="text-[10px] uppercase tracking-[0.13em] text-slate-600">Forward ROI / CLV</p>
                    <p className="mt-1 font-semibold tabular-nums text-slate-200">
                      <span className={metricTone(forward.roi_pct)}>{gapMetricValue(forward.roi_pct)}</span>
                      <span className="text-slate-600"> / </span>
                      <span className={metricTone(forward.avg_clv_pct)}>{gapMetricValue(forward.avg_clv_pct)}</span>
                    </p>
                  </div>
                </div>
                <p className="mt-3 border-t border-slate-800 pt-3 text-[10px] leading-4 text-slate-500">
                  Captured {experiment.captured} · quality eligible {experiment.quality_eligible} · excluded low-quality {experiment.excluded_low_quality}. Historical screen {experiment.historical?.passes_retrospective_screen ? "passed" : "not passed"}; forward ROI and CLV still decide promotion.
                </p>
              </div>
            );
          })}
          {Object.keys(replacementExperiments).length === 0 ? (
            <p className="rounded-xl border border-slate-800 bg-slate-950/55 p-4 text-sm text-slate-500">Run the nightly gap report to populate the registered replacement cohorts.</p>
          ) : null}
        </div>

        <details className="mt-4 border-t border-emerald-500/15 pt-4">
          <summary className="cursor-pointer text-xs font-semibold uppercase tracking-[0.14em] text-slate-300">Side-flip evidence by surface</summary>
          <div className="mt-3 grid gap-3 sm:grid-cols-3">
            {Object.entries(historicalSideFlips).map(([surface, evidence]) => (
              <div key={surface} className="rounded-xl border border-slate-800 bg-slate-950/45 p-3">
                <div className="flex items-center justify-between gap-2">
                  <p className="font-semibold text-slate-200">{surface}</p>
                  <StatusPill label={evidence.passes_retrospective_screen ? "SCREEN PASS" : "SCREEN FAIL"} tone={evidence.passes_retrospective_screen ? badgeTones.deferred : badgeTones.disabled} />
                </div>
                <p className="mt-2 text-xs tabular-nums text-slate-400">n={evidence.performance.settled} · <span className={metricTone(evidence.performance.roi_pct)}>{gapMetricValue(evidence.performance.roi_pct)} ROI</span></p>
              </div>
            ))}
          </div>
          <p className="mt-3 text-[10px] leading-4 text-amber-200/80">A historical surface pass is not a tip. Every side flip stays blocked and separately monitored until forward CLV and ROI establish an edge.</p>
        </details>
      </div>

      <div className="mt-4 rounded-2xl border border-cyan-500/20 bg-cyan-500/5 p-4 md:p-5">
        <div className="flex flex-col gap-2 md:flex-row md:items-start md:justify-between">
          <div>
            <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-cyan-300">Historical reality check</p>
            <p className="mt-2 text-sm leading-6 text-slate-300">
              Fixed live thresholds replayed against real recorded ML prices. Handicap results use only the smaller real 2026 spread-capture subset; no synthetic spread prices.
            </p>
          </div>
          <StatusPill label={(historical?.screening_verdict ?? "NOT RUN").replaceAll("_", " ")} tone={badgeTones.deferred} />
        </div>
        <div className="mt-4 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
          <div className="rounded-xl border border-slate-800 bg-slate-950/50 p-3">
            <p className="text-[10px] uppercase tracking-[0.14em] text-slate-500">Extreme ML replay</p>
            <p className="mt-2 font-semibold tabular-nums text-slate-100">{historical?.ml.settled ?? 0} bets · <span className={metricTone(historical?.ml.roi_pct)}>{gapMetricValue(historical?.ml.roi_pct ?? null)} ROI</span></p>
          </div>
          <div className="rounded-xl border border-slate-800 bg-slate-950/50 p-3">
            <p className="text-[10px] uppercase tracking-[0.14em] text-slate-500">Real paired spreads</p>
            <p className="mt-2 font-semibold tabular-nums text-slate-100">{historical?.spread.settled ?? 0} bets · <span className={metricTone(historical?.spread.roi_pct)}>{gapMetricValue(historical?.spread.roi_pct ?? null)} ROI</span></p>
          </div>
          <div className="rounded-xl border border-slate-800 bg-slate-950/50 p-3">
            <p className="text-[10px] uppercase tracking-[0.14em] text-slate-500">ML EV ≥100% spreads</p>
            <p className="mt-2 font-semibold tabular-nums text-slate-100">{historical?.long_ev_100_plus.spread.settled ?? 0} bets · <span className={metricTone(historical?.long_ev_100_plus.spread.roi_pct)}>{gapMetricValue(historical?.long_ev_100_plus.spread.roi_pct ?? null)} ROI</span></p>
          </div>
          <div className="rounded-xl border border-slate-800 bg-slate-950/50 p-3">
            <p className="text-[10px] uppercase tracking-[0.14em] text-slate-500">Spread rescued ML loss</p>
            <p className="mt-2 font-semibold tabular-nums text-slate-100">{historical?.spread_rescues ?? 0} / {historical?.ml_losses_with_spread ?? 0}</p>
          </div>
        </div>
        {Object.keys(thresholdProfiles).length > 0 ? (
          <div className="mt-4 border-t border-cyan-500/15 pt-4">
            <div className="flex flex-col gap-2 md:flex-row md:items-end md:justify-between">
              <div>
                <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-cyan-300">Is 10pp the right cutoff?</p>
                <p className="mt-1 text-xs leading-5 text-slate-400">
                  Same historical sample at 5, 10, 15 and 20pp. Favourite-side flips remain a separate hard guard, so they cannot distort the gap comparison.
                </p>
              </div>
              <StatusPill label="DESCRIPTIVE - LIVE RULE LOCKED" tone={badgeTones.deferred} />
            </div>
            <div className="mt-3 grid gap-3 xl:grid-cols-3">
              {Object.entries(thresholdProfiles).map(([profile, payload]) => (
                <div key={profile} className="overflow-hidden rounded-xl border border-slate-800 bg-slate-950/55">
                  <div className="border-b border-slate-800 px-3 py-3">
                    <p className="text-xs font-semibold uppercase tracking-[0.12em] text-slate-200">{profile.replaceAll("_", " ")}</p>
                    <p className="mt-1 text-[10px] leading-4 text-slate-500">{payload.description} n={payload.candidates}</p>
                  </div>
                  <div className="grid grid-cols-[44px_1fr_1fr] gap-2 border-b border-slate-800 px-3 py-2 text-[9px] font-semibold uppercase tracking-[0.12em] text-slate-600">
                    <span>Cut</span><span>Allowed</span><span>Gap blocked</span>
                  </div>
                  {Object.entries(payload.cutoffs).map(([cutoff, partition]) => (
                    <div key={cutoff} className={`grid grid-cols-[44px_1fr_1fr] gap-2 border-b border-slate-900 px-3 py-2.5 text-[11px] last:border-0 ${Number(cutoff) === historical?.threshold_audit?.locked_guard_pp ? "bg-cyan-500/[0.07]" : ""}`}>
                      <span className={Number(cutoff) === historical?.threshold_audit?.locked_guard_pp ? "font-semibold text-cyan-200" : "text-slate-500"}>{cutoff}pp</span>
                      <span className="tabular-nums text-slate-300">n={partition.allowed.settled} <b className={metricTone(partition.allowed.roi_pct)}>{gapMetricValue(partition.allowed.roi_pct)}</b></span>
                      <span className="tabular-nums text-slate-300">n={partition.gap_blocked.settled} <b className={metricTone(partition.gap_blocked.roi_pct)}>{gapMetricValue(partition.gap_blocked.roi_pct)}</b></span>
                    </div>
                  ))}
                </div>
              ))}
            </div>
            <p className="mt-3 text-[10px] leading-4 text-amber-200/80">
              ROI here is retrospective diagnosis, not a promotion result. A cutoff cannot be selected from the same sample used to compare it; forward ROI and CLV remain mandatory.
            </p>
          </div>
        ) : null}
      </div>

      <div className="mt-5 overflow-hidden rounded-2xl border border-slate-800 bg-slate-950/45">
        <div className="grid grid-cols-[minmax(0,1fr)_64px_64px] gap-3 border-b border-slate-800 px-4 py-3 text-[10px] font-semibold uppercase tracking-[0.14em] text-slate-500 sm:grid-cols-[minmax(0,1.5fr)_80px_82px_minmax(0,1fr)]">
          <span>Current match / paired test</span><span>Gap</span><span>ML EV</span><span className="hidden sm:block">Likely cause</span>
        </div>
        {currentMlRows.map((row) => {
          const pairedSpread = spreadByAnomaly.get(row.anomaly_id);
          const cause = gapDiagnosisLabel(row);
          return (
            <div key={`${row.anomaly_id}-${row.signal_profile}`} className="grid grid-cols-[minmax(0,1fr)_64px_64px] gap-3 border-b border-slate-900 px-4 py-3 text-xs last:border-0 sm:grid-cols-[minmax(0,1.5fr)_80px_82px_minmax(0,1fr)]">
              <div className="min-w-0">
                <p className="truncate font-semibold text-slate-200">{row.player1} vs {row.player2}</p>
                <p className="mt-1 truncate text-slate-500">
                  {row.selected_player}{pairedSpread ? ` | ${pairedSpread.side} ${pairedSpread.spread_line} @ ${pairedSpread.spread_odds}` : " | no spread captured"}
                </p>
                <p className="mt-1 truncate text-[10px] text-slate-600 sm:hidden">{cause}</p>
              </div>
              <span className="font-semibold tabular-nums text-rose-200">{nullableMetric(row.model_market_gap_pp)?.toFixed(1) ?? "-"}pp</span>
              <span className="font-semibold tabular-nums text-amber-200">{nullableMetric(row.value_pct)?.toFixed(1) ?? "-"}%</span>
              <span className="hidden break-words text-slate-400 sm:block">{cause}</span>
            </div>
          );
        })}
        {liveRows.length === 0 ? <p className="px-4 py-6 text-sm text-slate-500">No current anomaly snapshot yet. The morning and nightly fair-odds runs now create it automatically.</p> : null}
      </div>
    </section>
  );
}

const guardLabels: Record<string, string> = {
  model_favourite_below_1_25: "Model favourite <1.25",
  market_favourite_below_1_25: "Pinnacle favourite <1.25",
  model_market_side_flip: "Model / market side flip",
  model_market_gap_above_10pp: "Model / market gap >10pp",
  atp500_hard_short_favourite: "ATP500 Hard favourite <1.80",
  masters_hard_heavy_favourite_dog: "Masters Hard heavy-favourite dog",
};

function guardDecisionTone(decision: string): string {
  if (decision.startsWith("KEEP")) return badgeTones.live;
  if (decision.includes("SHADOW") || decision.includes("PROSPECTIVE") || decision.includes("TRACK")) return badgeTones.shadow;
  if (decision === "STRATEGY_DEFINITION" || decision === "PRODUCT_STATUS" || decision === "OFF") return badgeTones.deferred;
  return badgeTones.disabled;
}

function guardRoi(metric: GuardPerformance | undefined): string {
  if (!metric || metric.roi_pct == null) return "n/a";
  return `${metric.roi_pct >= 0 ? "+" : ""}${metric.roi_pct.toFixed(2)}%`;
}

function TennisGuardAuditCard({ audit }: { audit: TennisGuardAudit | null }) {
  if (!audit) {
    return (
      <section id="guard-audit" className="rounded-2xl border border-amber-500/20 bg-amber-500/5 p-5">
        <div className="flex flex-wrap items-center gap-2">
          <h2 className="text-xl font-semibold text-slate-100">Tennis Guard Audit</h2>
          <StatusPill label="NOT RUN" tone={badgeTones.disabled} />
        </div>
        <p className="mt-2 text-sm text-slate-400">
          Run `python scripts/tennis-guard-audit.py` to replay every reconstructable ML guard and expose the remaining
          prospective-only protections.
        </p>
      </section>
    );
  }

  const replayable = audit.inventory.replayable_ml_guards ?? [];
  const strict = audit.profiles.strict;
  const replayEntries = replayable.map((item) => ({ item, replay: strict?.guards[item.id] }));
  const strictBlockedBetter =
    strict?.blocked_by_any.roi_pct != null &&
    strict.after_all_replayable_guards.roi_pct != null &&
    strict.blocked_by_any.roi_pct > strict.after_all_replayable_guards.roi_pct;

  return (
    <section id="guard-audit" className="rounded-3xl border border-amber-500/20 bg-[radial-gradient(circle_at_top_right,rgba(245,158,11,0.12),transparent_34%),linear-gradient(135deg,rgba(15,23,42,0.97),rgba(2,6,23,0.98))] p-5 md:p-6">
      <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
        <div>
          <div className="flex flex-wrap items-center gap-2">
            <p className="text-xs font-semibold uppercase tracking-[0.22em] text-amber-300">Guard control</p>
            <StatusPill label="AUDIT ONLY" tone={badgeTones.disabled} />
          </div>
          <h2 className="mt-3 text-2xl font-semibold text-slate-50">Every filter, its evidence and what it removed</h2>
          <p className="mt-2 max-w-4xl text-sm leading-6 text-slate-400">
            Historical blocked ROI is diagnostic, not permission to invert a rule. Unique rows show each guard&apos;s
            contribution after overlap; spread conflicts and probability modifiers stay separate until their own
            prospective or ablation tests exist.
          </p>
        </div>
        <div className="rounded-xl border border-slate-800 bg-slate-950/55 px-4 py-3 text-xs text-slate-400">
          <p><span className="font-semibold text-slate-200">{audit.rows_loaded.toLocaleString()}</span> ATP matches</p>
          <p className="mt-1">2022-2025 identity-clean replay</p>
        </div>
      </div>

      <div className="mt-5 grid gap-3 lg:grid-cols-3">
        {Object.entries(audit.profiles).map(([profileName, profile]) => (
          <div key={profileName} className="rounded-2xl border border-slate-800 bg-slate-950/55 p-4">
            <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-500">
              {profileName.replaceAll("_", " ")}
            </p>
            <p className="mt-2 text-xs leading-5 text-slate-400">{audit.profile_descriptions[profileName]}</p>
            <div className="mt-4 grid grid-cols-3 gap-2 text-xs">
              <div>
                <p className="text-slate-600">Before</p>
                <p className="mt-1 font-semibold tabular-nums text-slate-200">{profile.before_guards.bets}</p>
                <p className={cn("mt-0.5 tabular-nums", metricTone(profile.before_guards.roi_pct))}>{guardRoi(profile.before_guards)}</p>
              </div>
              <div>
                <p className="text-slate-600">Allowed</p>
                <p className="mt-1 font-semibold tabular-nums text-slate-200">{profile.after_all_replayable_guards.bets}</p>
                <p className={cn("mt-0.5 tabular-nums", metricTone(profile.after_all_replayable_guards.roi_pct))}>{guardRoi(profile.after_all_replayable_guards)}</p>
              </div>
              <div>
                <p className="text-slate-600">Blocked</p>
                <p className="mt-1 font-semibold tabular-nums text-slate-200">{profile.blocked_by_any.bets}</p>
                <p className={cn("mt-0.5 tabular-nums", metricTone(profile.blocked_by_any.roi_pct))}>{guardRoi(profile.blocked_by_any)}</p>
              </div>
            </div>
          </div>
        ))}
      </div>

      <div className="mt-5 overflow-x-auto rounded-2xl border border-slate-800 bg-slate-950/45">
        <table className="min-w-full text-left text-xs">
          <thead className="border-b border-slate-800 text-[10px] uppercase tracking-[0.14em] text-slate-500">
            <tr>
              <th className="px-4 py-3 font-semibold">Strict ML guard</th>
              <th className="px-3 py-3 font-semibold">Decision</th>
              <th className="px-3 py-3 font-semibold">Flagged</th>
              <th className="px-3 py-3 font-semibold">Blocked ROI</th>
              <th className="px-3 py-3 font-semibold">Unique</th>
              <th className="px-4 py-3 font-semibold">Evidence status</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-900 text-slate-300">
            {replayEntries.map(({ item, replay }) => (
              <tr key={item.id}>
                <td className="px-4 py-3 font-semibold text-slate-100">{guardLabels[item.id] ?? item.id.replaceAll("_", " ")}</td>
                <td className="px-3 py-3"><StatusPill label={item.decision.replaceAll("_", " ")} tone={guardDecisionTone(item.decision)} /></td>
                <td className="px-3 py-3 tabular-nums">{replay?.flagged.bets ?? 0}</td>
                <td className={cn("px-3 py-3 font-semibold tabular-nums", metricTone(replay?.flagged.roi_pct))}>{guardRoi(replay?.flagged)}</td>
                <td className="px-3 py-3 tabular-nums">{replay?.unique.bets ?? 0} / {guardRoi(replay?.unique)}</td>
                <td className="max-w-md px-4 py-3 leading-5 text-slate-400">{item.evidence}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <details className="mt-4 rounded-2xl border border-slate-800 bg-slate-950/40 p-4">
        <summary className="cursor-pointer text-sm font-semibold text-slate-200">Show spread guards, model modifiers and operational filters</summary>
        <div className="mt-4 grid gap-3 lg:grid-cols-3">
          {Object.entries(audit.inventory)
            .filter(([category]) => category !== "replayable_ml_guards")
            .map(([category, entries]) => (
              <div key={category} className="rounded-xl border border-slate-800/80 bg-slate-950/55 p-4">
                <p className="text-[10px] font-semibold uppercase tracking-[0.15em] text-slate-500">{category.replaceAll("_", " ")}</p>
                <div className="mt-3 space-y-3">
                  {entries.map((entry) => (
                    <div key={entry.id}>
                      <div className="flex flex-wrap items-center gap-2">
                        <p className="text-xs font-semibold text-slate-200">{entry.id.replaceAll("_", " ")}</p>
                        <StatusPill label={entry.decision.replaceAll("_", " ")} tone={guardDecisionTone(entry.decision)} />
                      </div>
                      <p className="mt-1 text-[11px] leading-5 text-slate-500">{entry.evidence}</p>
                    </div>
                  ))}
                </div>
              </div>
            ))}
        </div>
      </details>

      {strictBlockedBetter ? (
        <p className="mt-4 rounded-xl border border-rose-500/20 bg-rose-500/5 px-4 py-3 text-xs leading-5 text-rose-100">
          Critical finding: strict bets blocked by the current combined replay returned better historically than the
          allowed set. The model-favourite &lt;1.25 guard remains supported, but the blanket 10pp and side-flip vetoes are
          under review and must be measured separately going forward.
        </p>
      ) : (
        <p className="mt-4 rounded-xl border border-emerald-500/20 bg-emerald-500/5 px-4 py-3 text-xs leading-5 text-emerald-100">
          Combined strict filtering improved historical ROI in the current replay. Individual guards still require
          overlap-aware attribution before any threshold changes.
        </p>
      )}
    </section>
  );
}

async function loadExtremeGapLab(): Promise<ExtremeGapLoad> {
  const [reportText, historicalText, liveText] = await Promise.all([
    readKnownFile("data/backtest/tennis-model-market-gap-report.json"),
    readKnownFile("data/backtest/tennis-model-market-gap-historical-report.json"),
    readKnownFile("data/backtest/tennis-model-market-gap-live.csv"),
  ]);
  let report: ExtremeGapReport | null = null;
  let historical: HistoricalGapReport | null = null;
  if (reportText) {
    try {
      report = JSON.parse(reportText) as ExtremeGapReport;
    } catch {
      report = null;
    }
  }
  if (historicalText) {
    try {
      historical = JSON.parse(historicalText) as HistoricalGapReport;
    } catch {
      historical = null;
    }
  }
  return { report, historical, liveRows: liveText ? parseCsv(liveText) : [] };
}

async function loadTennisGuardAudit(): Promise<TennisGuardAudit | null> {
  const text = await readKnownFile("data/backtest/tennis-guard-audit.json");
  if (!text) return null;
  try {
    return JSON.parse(text) as TennisGuardAudit;
  } catch {
    return null;
  }
}

async function loadProofReport(): Promise<ProofReportLoad | null> {
  const reportPath = "data/backtest/tennis-shadow-proof-report.csv";
  const [csv, updatedAt] = await Promise.all([readKnownFile(reportPath), readKnownMtime(reportPath)]);
  if (!csv) return null;
  const rows = parseCsv(csv);
  if (rows.length === 0) return null;
  const nowMs = Date.now();
  return {
    updatedAt,
    ageLabel: proofReportAgeLabel(updatedAt, nowMs),
    stale: !updatedAt || nowMs - updatedAt.getTime() > 36 * 60 * 60 * 1000,
    rows: rows.map((row) => ({
      lane: row.lane || row.label || "unknown",
      label: row.label || row.lane || "Unknown lane",
      signals: numericMetric(row.signals),
      liveRows: numericMetric(row.live_rows),
      pending: numericMetric(row.pending),
      settled: numericMetric(row.settled),
      wins: numericMetric(row.wins),
      losses: numericMetric(row.losses),
      voids: numericMetric(row.voids),
      pnlUnits: nullableMetric(row.pnl_units),
      roiPct: nullableMetric(row.roi_pct),
      clvRows: numericMetric(row.clv_rows),
      avgClvPct: nullableMetric(row.avg_clv_pct),
      positiveClvPct: nullableMetric(row.positive_clv_pct),
      verdict: row.verdict || "UNKNOWN",
      source: row.archive_source || "missing",
      note: row.note || "",
    })),
  };
}
function topReasons(rows: CsvRow[]): string[] {
  const counts = new Map<string, number>();
  rows.forEach((row) => {
    const reason = row.skip_reason || "unknown";
    counts.set(reason, (counts.get(reason) ?? 0) + 1);
  });
  return [...counts.entries()]
    .sort((a, b) => b[1] - a[1])
    .slice(0, 3)
    .map(([reason, count]) => `${reason} (${count})`);
}

function rowSignalTimestamp(row: CsvRow): number {
  const stamp = Date.parse(`${row.date || ""}T${row.time_utc || "00:00:00"}Z`);
  return Number.isFinite(stamp) ? stamp : 0;
}

function logicalCsvSignalKey(row: CsvRow): string {
  return [
    row.match_date || row.date || "",
    (row.player1 || "").trim().toLowerCase(),
    (row.player2 || "").trim().toLowerCase(),
    row.bet_type || "match",
    row.side || "",
    row.policy_mode || "base",
    row.signal_profile || "",
  ].join("|");
}

function latestCapturedRows(rows: CsvRow[], limit = 5): CsvRow[] {
  const byKey = new Map<string, CsvRow>();
  [...rows]
    .sort((left, right) => rowSignalTimestamp(left) - rowSignalTimestamp(right))
    .forEach((row) => {
      const key = logicalCsvSignalKey(row);
      const previous = byKey.get(key);
      if (!previous) {
        byKey.set(key, row);
        return;
      }
      const rowSettled = (row.settlement_status || "").trim().toLowerCase() === "settled";
      const previousSettled = (previous.settlement_status || "").trim().toLowerCase() === "settled";
      byKey.set(key, rowSettled && !previousSettled ? { ...previous, ...row } : previous);
    });
  return [...byKey.values()].sort((left, right) => rowSignalTimestamp(right) - rowSignalTimestamp(left)).slice(0, limit);
}

async function loadLaneStats(id: TennisResearchLaneId): Promise<LaneStats> {
  const files = TENNIS_MONITOR_FILES[id];
  const [liveCsv, archiveCsv, nearMissCsv, clvCsv, clvSpreadCsv] = await Promise.all([
    readKnownFile(files.live),
    readKnownFile(files.archive),
    readKnownFile(files.nearMiss),
    readKnownFile(files.clvAuditCsv),
    readKnownFile(files.clvAuditSpreadCsv),
  ]);
  const liveRows = liveCsv ? parseCsv(liveCsv) : [];
  const archiveRows = archiveCsv ? parseCsv(archiveCsv) : [];
  const nearMissRows = nearMissCsv ? parseCsv(nearMissCsv) : [];
  const allSignalRows = latestCapturedRows([...archiveRows, ...liveRows], Number.POSITIVE_INFINITY);
  const pendingCount = allSignalRows.filter(isPendingRow).length;
  const settled = settledRows(archiveRows);
  const wins = settled.filter(isWon).length;
  const losses = settled.filter(isLost).length;
  const pnlValues = settled.map(rowPnlUnits).filter((value): value is number => value !== null);
  const stakeValues = settled.map((row) => toNumber(row.stake_units) ?? 1);
  const totalStake = stakeValues.reduce((sum, value) => sum + value, 0);
  const totalPnl = pnlValues.reduce((sum, value) => sum + value, 0);
  const clvRows = [...(clvCsv ? parseCsv(clvCsv) : []), ...(clvSpreadCsv ? parseCsv(clvSpreadCsv) : [])];
  const clvValues = clvRows
    .map((row) => toNumber(row.clv_implied_delta_pct) ?? toNumber(row.clv_pct) ?? toNumber(row.avg_clv_pct))
    .filter((value): value is number => value !== null);

  return {
    liveCount: liveRows.length,
    archiveCount: archiveRows.length,
    nearMissCount: nearMissRows.length,
    pendingCount,
    settledCount: settled.length,
    wins,
    losses,
    pnlUnits: totalPnl,
    roiPct: totalStake > 0 ? (totalPnl / totalStake) * 100 : null,
    avgClvPct: avg(clvValues),
    clvRowCount: clvValues.length,
    positiveClvPct:
      clvValues.length > 0 ? (clvValues.filter((value) => value > 0).length / clvValues.length) * 100 : null,
    topNearMissReasons: topReasons(nearMissRows),
    latestSignals: allSignalRows.slice(0, 5),
  };
}

async function loadCpiSummary(): Promise<CpiSummary> {
  const [csv, overlayCsv, overlayReport, regimeCsv, regimeReport, gateCsv, factorCsv, gateReport, identityStatus] = await Promise.all([
    readKnownFile("data/backtest/cpi-all-surfaces-cells.csv"),
    readKnownFile("data/backtest/cpi-shadow-overlay-cells.csv"),
    readKnownFile("data/backtest/cpi-shadow-overlay-report.txt"),
    readKnownFile("data/backtest/cpi-regime-surface-cells.csv"),
    readKnownFile("data/backtest/cpi-regime-surface-report.txt"),
    readKnownFile("data/backtest/cpi-regime-shadow-gates.csv"),
    readKnownFile("data/backtest/cpi-regime-shadow-value-factors.csv"),
    readKnownFile("data/backtest/cpi-regime-shadow-report.txt"),
    readKnownFile("data/backtest/cpi-regime-shadow-identity-status.txt"),
  ]);
  const identityPaused = !identityStatus?.includes("VERDICT: IDCLEAN_VALID");
  if (!csv) {
    return {
      identityPaused,
      identityStatus,
      headlineRows: [],
      candidateRows: [],
      overlayRows: [],
      overlayVerdict: null,
      overlayAvailable: false,
      regimeRows: [],
      regimeVerdict: null,
      regimeAvailable: false,
      regimeGateRows: [],
      regimeFactorRows: [],
      regimeGateVerdict: null,
      regimeGatesAvailable: false,
      reportAvailable: false,
    };
  }
  const rows = parseCsv(csv);
  const overlayRowsRaw = overlayCsv ? parseCsv(overlayCsv) : [];
  const regimeRowsRaw = regimeCsv ? parseCsv(regimeCsv) : [];
  const regimeGateRowsRaw = gateCsv ? parseCsv(gateCsv) : [];
  const regimeFactorRows = factorCsv ? parseCsv(factorCsv) : [];
  const laggedResearchRows = rows.filter((row) => row.mode === "lagged" && row.scope === "research_all");
  const surfaceOrder = new Map(["Hard", "Clay", "Grass"].map((surface, index) => [surface, index]));
  const bucketOrder = new Map(["all", "slow", "neutral", "fast"].map((bucket, index) => [bucket, index]));
  const overlayOrder = new Map(["all", "Hard", "Clay", "Grass"].map((value, index) => [value, index]));
  const regimeOrder = new Map(["all", "SpeedSlow", "SpeedNeutral", "SpeedFast"].map((value, index) => [value, index]));
  const headlineRows = laggedResearchRows
    .filter((row) => row.cell === "value_10_plus")
    .sort((left, right) => {
      const surfaceDiff = (surfaceOrder.get(left.surface) ?? 99) - (surfaceOrder.get(right.surface) ?? 99);
      if (surfaceDiff !== 0) return surfaceDiff;
      return (bucketOrder.get(left.bucket) ?? 99) - (bucketOrder.get(right.bucket) ?? 99);
    });
  const candidateRows = laggedResearchRows
    .filter((row) => {
      const n = toNumber(row.n) ?? 0;
      const roi = toNumber(row.roi_pct) ?? 0;
      return n >= 60 && roi > 0;
    })
    .sort((left, right) => {
      const roiDiff = (toNumber(right.roi_pct) ?? 0) - (toNumber(left.roi_pct) ?? 0);
      if (Math.abs(roiDiff) > 1e-9) return roiDiff;
      return (toNumber(right.n) ?? 0) - (toNumber(left.n) ?? 0);
    })
    .slice(0, 10);
  const overlayRows = overlayRowsRaw
    .filter((row) => row.threshold === "10.0" && (row.segment === "all" || row.segment === "surface"))
    .sort((left, right) => (overlayOrder.get(left.value) ?? 99) - (overlayOrder.get(right.value) ?? 99));
  const regimeRows = regimeRowsRaw
    .filter(
      (row) =>
        row.threshold === "10.0" &&
        ((row.segment === "all" && row.value === "all") ||
          (row.segment === "model_surface" && row.value.startsWith("Speed"))),
    )
    .sort((left, right) => (regimeOrder.get(left.value) ?? 99) - (regimeOrder.get(right.value) ?? 99));
  const gateOrder = new Map(["PASS_SHADOW", "WATCH"].map((status, index) => [status, index]));
  const regimeGateRows = (identityPaused ? [] : regimeGateRowsRaw)
    .filter((row) => row.status === "PASS_SHADOW" || row.status === "WATCH")
    .sort((left, right) => {
      const statusDiff = (gateOrder.get(left.status) ?? 99) - (gateOrder.get(right.status) ?? 99);
      if (statusDiff !== 0) return statusDiff;
      return (toNumber(right.combined_overlay_roi_pct) ?? 0) - (toNumber(left.combined_overlay_roi_pct) ?? 0);
    })
    .slice(0, 14);
  const overlayVerdict = overlayReport?.match(/Verdict:\s*([^\r\n]+)/)?.[1]?.trim() ?? null;
  const regimeVerdict = regimeReport?.match(/Verdict:\s*([^\r\n]+)/)?.[1]?.trim() ?? null;
  const regimeGateVerdict = gateReport?.match(/Verdict:\s*([^\r\n]+)/)?.[1]?.trim() ?? null;
  return {
    identityPaused,
    identityStatus,
    headlineRows,
    candidateRows,
    overlayRows,
    overlayVerdict,
    overlayAvailable: overlayRows.length > 0,
    regimeRows,
    regimeVerdict,
    regimeAvailable: regimeRows.length > 0,
    regimeGateRows,
    regimeFactorRows,
    regimeGateVerdict,
    regimeGatesAvailable: regimeGateRows.length > 0 || regimeFactorRows.length > 0,
    reportAvailable: true,
  };
}

function EmptyMetric({ label, value = "-" }: { label: string; value?: string }) {
  return (
    <div className="rounded-xl border border-slate-800/70 bg-slate-950/50 p-4">
      <p className="text-[10px] font-semibold uppercase tracking-[0.18em] text-slate-500">{label}</p>
      <p className="mt-2 text-2xl font-semibold tabular-nums text-slate-200">{value}</p>
    </div>
  );
}

function CpiSurfaceSpeedCard({ summary }: { summary: CpiSummary }) {
  return (
    <section
      id="cpi-surface-speed"
      className="rounded-2xl border border-emerald-500/20 bg-[radial-gradient(circle_at_top_left,rgba(16,185,129,0.15),transparent_38%),rgba(2,6,23,0.72)] p-5 shadow-[0_18px_60px_rgba(2,6,23,0.32)]"
    >
      <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
        <div>
          <div className="flex flex-wrap items-center gap-2">
            <h2 className="text-xl font-semibold text-slate-100">CPI Surface Speed Research</h2>
            <StatusPill label="SHADOW DIAGNOSTIC" tone={badgeTones.shadow} />
          </div>
          <p className="mt-2 max-w-4xl text-sm leading-6 text-slate-400">
            Lagged Tennis Abstract court-speed buckets across Hard, Clay and Grass. This is a research map for future
            gates and overlays; it does not change live staking by itself.
          </p>
          {summary.identityPaused ? (
            <div className="mt-4 rounded-xl border border-amber-500/30 bg-amber-500/10 px-4 py-3 text-sm leading-6 text-amber-100">
              <span className="font-semibold">CPI signals paused:</span> the visible historical cells were fitted before
              the identity repair. They remain diagnostic only; current signal attachment is blocked until an
              identity-clean gate file is registered.
            </div>
          ) : null}
        </div>
        <div className="rounded-full border border-emerald-500/20 bg-emerald-500/10 px-3 py-1 text-xs font-medium text-emerald-200">
          prior editions only
        </div>
      </div>

      {!summary.reportAvailable ? (
        <div className="mt-4 rounded-xl border border-amber-500/20 bg-amber-500/10 px-4 py-3 text-sm text-amber-200">
          CPI report not found. Run `python scripts\backtest-cpi-all-surfaces.py` locally.
        </div>
      ) : (
        <>
          {summary.overlayAvailable ? (
            <div className="mt-5 rounded-xl border border-cyan-500/20 bg-cyan-500/10 p-4">
              <div className="flex flex-col gap-2 lg:flex-row lg:items-center lg:justify-between">
                <div>
                  <p className="text-xs font-semibold uppercase tracking-[0.16em] text-cyan-300">
                    CPI overlay A/B verdict
                  </p>
                  <p className="mt-1 text-sm text-slate-300">
                    {summary.overlayVerdict || "Report generated"}: the current CPI overlay is research-only and is not
                    promoted into live staking.
                  </p>
                </div>
                <StatusPill label="NOT LIVE" tone={badgeTones.disabled} />
              </div>
              <div className="mt-4 overflow-x-auto">
                <table className="min-w-full text-left text-xs">
                  <thead className="text-slate-500">
                    <tr>
                      <th className="py-2 pr-4 font-medium">Scope</th>
                      <th className="py-2 pr-4 font-medium">Base bets</th>
                      <th className="py-2 pr-4 font-medium">Base ROI</th>
                      <th className="py-2 pr-4 font-medium">CPI bets</th>
                      <th className="py-2 pr-4 font-medium">CPI ROI</th>
                      <th className="py-2 pr-4 font-medium">P/L delta</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-cyan-500/10 text-slate-300">
                    {summary.overlayRows.map((row) => (
                      <tr key={`${row.segment}-${row.value}`}>
                        <td className="py-2 pr-4 font-semibold text-slate-100">{row.value}</td>
                        <td className="py-2 pr-4 tabular-nums">{row.base_bets}</td>
                        <td className="py-2 pr-4 tabular-nums">{formatSignedPct(row.base_roi_pct)}</td>
                        <td className="py-2 pr-4 tabular-nums">{row.overlay_bets}</td>
                        <td className="py-2 pr-4 tabular-nums">{formatSignedPct(row.overlay_roi_pct)}</td>
                        <td
                          className={cn(
                            "py-2 pr-4 font-semibold tabular-nums",
                            (toNumber(row.delta_pnl) ?? 0) >= 0 ? "text-emerald-300" : "text-rose-300",
                          )}
                        >
                          {formatNumber(toNumber(row.delta_pnl), "u", 2)}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          ) : null}

          {summary.regimeAvailable ? (
            <div className="mt-5 rounded-xl border border-emerald-500/25 bg-[linear-gradient(135deg,rgba(16,185,129,0.13),rgba(15,23,42,0.45))] p-4">
              <div className="flex flex-col gap-2 lg:flex-row lg:items-center lg:justify-between">
                <div>
                  <p className="text-xs font-semibold uppercase tracking-[0.16em] text-emerald-300">
                    CPI speed-regime model
                  </p>
                  <p className="mt-1 text-sm text-slate-300">
                    {summary.regimeVerdict || "Report generated"}: this tests treating venue speed as the model surface
                    itself. It is shadow-only until calibration and live CLV are proven.
                  </p>
                </div>
                <StatusPill label="SHADOW ONLY" tone={badgeTones.shadow} />
              </div>
              <div className="mt-4 overflow-x-auto">
                <table className="min-w-full text-left text-xs">
                  <thead className="text-slate-500">
                    <tr>
                      <th className="py-2 pr-4 font-medium">Model surface</th>
                      <th className="py-2 pr-4 font-medium">Base bets</th>
                      <th className="py-2 pr-4 font-medium">Base ROI</th>
                      <th className="py-2 pr-4 font-medium">Regime bets</th>
                      <th className="py-2 pr-4 font-medium">Regime ROI</th>
                      <th className="py-2 pr-4 font-medium">P/L delta</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-emerald-500/10 text-slate-300">
                    {summary.regimeRows.map((row) => (
                      <tr key={`${row.segment}-${row.value}`}>
                        <td className="py-2 pr-4 font-semibold text-slate-100">{row.value}</td>
                        <td className="py-2 pr-4 tabular-nums">{row.base_bets}</td>
                        <td className="py-2 pr-4 tabular-nums">{formatSignedPct(row.base_roi_pct)}</td>
                        <td className="py-2 pr-4 tabular-nums">{row.overlay_bets}</td>
                        <td className="py-2 pr-4 font-semibold tabular-nums text-emerald-300">
                          {formatSignedPct(row.overlay_roi_pct)}
                        </td>
                        <td
                          className={cn(
                            "py-2 pr-4 font-semibold tabular-nums",
                            (toNumber(row.delta_pnl) ?? 0) >= 0 ? "text-emerald-300" : "text-rose-300",
                          )}
                        >
                          {formatNumber(toNumber(row.delta_pnl), "u", 2)}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          ) : null}

          {summary.regimeGatesAvailable ? (
            <div className="mt-5 rounded-xl border border-lime-500/25 bg-[radial-gradient(circle_at_top_right,rgba(132,204,22,0.16),transparent_35%),rgba(15,23,42,0.55)] p-4">
              <div className="flex flex-col gap-2 lg:flex-row lg:items-center lg:justify-between">
                <div>
                  <p className="text-xs font-semibold uppercase tracking-[0.16em] text-lime-300">
                    CPI gated shadow cells
                  </p>
                  <p className="mt-1 text-sm text-slate-300">
                    {summary.regimeGateVerdict || "Shadow-only gate report"}: broad speed regimes are not trusted
                    directly. Only cells that passed 2024 train and 2025 holdout are listed here.
                  </p>
                </div>
                <StatusPill label="NOT ROUTED LIVE" tone={badgeTones.disabled} />
              </div>

              {summary.regimeFactorRows.length > 0 ? (
                <div className="mt-4 grid gap-3 md:grid-cols-3">
                  {summary.regimeFactorRows.map((row) => (
                    <div
                      key={row.model_surface}
                      className="rounded-xl border border-slate-800/80 bg-slate-950/55 p-3"
                    >
                      <div className="flex items-center justify-between gap-3">
                        <p className="text-sm font-semibold text-slate-100">{row.model_surface}</p>
                        <StatusPill
                          label={row.verdict || "unknown"}
                          tone={
                            row.verdict === "usable"
                              ? badgeTones.live
                              : "border-rose-500/25 bg-rose-500/10 text-rose-300"
                          }
                        />
                      </div>
                      <dl className="mt-3 grid grid-cols-3 gap-2 text-xs">
                        <div>
                          <dt className="text-slate-500">2024 bets</dt>
                          <dd className="font-semibold tabular-nums text-slate-200">{row.bets || "-"}</dd>
                        </div>
                        <div>
                          <dt className="text-slate-500">ROI</dt>
                          <dd className="font-semibold tabular-nums text-slate-200">
                            {formatSignedPct(row.roi_pct)}
                          </dd>
                        </div>
                        <div>
                          <dt className="text-slate-500">Factor</dt>
                          <dd className="font-semibold tabular-nums text-slate-200">
                            {row.realisation_factor || "-"}
                          </dd>
                        </div>
                      </dl>
                    </div>
                  ))}
                </div>
              ) : null}

              {summary.regimeGateRows.length > 0 ? (
                <div className="mt-4 overflow-x-auto rounded-xl border border-slate-800/80">
                  <table className="min-w-full text-left text-xs">
                    <thead className="bg-slate-950/80 text-slate-500">
                      <tr>
                        <th className="px-3 py-2 font-medium">Status</th>
                        <th className="px-3 py-2 font-medium">Gate</th>
                        <th className="px-3 py-2 font-medium">2024</th>
                        <th className="px-3 py-2 font-medium">2025 holdout</th>
                        <th className="px-3 py-2 font-medium">Combined</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-800/70 text-slate-300">
                      {summary.regimeGateRows.map((row) => (
                        <tr key={`${row.status}-${row.segment}-${row.value}`}>
                          <td className="px-3 py-2">
                            <StatusPill
                              label={row.status === "PASS_SHADOW" ? "PASS" : "WATCH"}
                              tone={row.status === "PASS_SHADOW" ? badgeTones.shadow : badgeTones.disabled}
                            />
                          </td>
                          <td className="px-3 py-2">
                            <p className="font-semibold text-slate-100">{row.value}</p>
                            <p className="mt-0.5 text-[11px] uppercase tracking-[0.12em] text-slate-500">
                              {row.segment}
                            </p>
                          </td>
                          <td className="px-3 py-2 tabular-nums">
                            {row.train_overlay_bets} bets / {formatSignedPct(row.train_overlay_roi_pct)}
                          </td>
                          <td className="px-3 py-2 tabular-nums">
                            {row.holdout_overlay_bets} bets / {formatSignedPct(row.holdout_overlay_roi_pct)}
                          </td>
                          <td className="px-3 py-2 font-semibold tabular-nums text-lime-200">
                            {row.combined_overlay_bets} bets / {formatSignedPct(row.combined_overlay_roi_pct)}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              ) : (
                <div className="mt-4 rounded-xl border border-amber-500/20 bg-amber-500/10 px-4 py-3 text-sm text-amber-200">
                  No CPI-specific cell passed the shadow gate yet.
                </div>
              )}
            </div>
          ) : null}

          <div className="mt-5 overflow-x-auto rounded-xl border border-slate-800/80">
            <table className="min-w-full text-left text-xs">
              <thead className="bg-slate-950/80 text-slate-500">
                <tr>
                  <th className="px-3 py-2 font-medium">Surface</th>
                  <th className="px-3 py-2 font-medium">CPI bucket</th>
                  <th className="px-3 py-2 font-medium">Bets</th>
                  <th className="px-3 py-2 font-medium">ROI</th>
                  <th className="px-3 py-2 font-medium">Years</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800/70 text-slate-300">
                {summary.headlineRows.map((row) => (
                  <tr key={`${row.surface}-${row.bucket}`}>
                    <td className="px-3 py-2 font-semibold text-slate-100">{row.surface}</td>
                    <td className="px-3 py-2 uppercase tracking-[0.12em] text-slate-400">{row.bucket}</td>
                    <td className="px-3 py-2 tabular-nums">{row.n}</td>
                    <td
                      className={cn(
                        "px-3 py-2 font-semibold tabular-nums",
                        (toNumber(row.roi_pct) ?? 0) >= 0 ? "text-emerald-300" : "text-rose-300",
                      )}
                    >
                      {formatSignedPct(row.roi_pct)}
                    </td>
                    <td className="min-w-[320px] px-3 py-2 text-slate-500">{row.years || "-"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <div className="mt-5 rounded-xl border border-slate-800/80 bg-slate-950/45 p-4">
            <p className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">
              Strongest lagged research cells
            </p>
            <div className="mt-3 grid gap-3 lg:grid-cols-2">
              {summary.candidateRows.map((row) => (
                <div key={`${row.surface}-${row.cell}-${row.bucket}`} className="rounded-xl border border-slate-800/70 bg-slate-950/55 p-3">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <p className="text-sm font-semibold text-slate-100">
                      {row.surface} / {row.cell.replaceAll("_", " ")} / {row.bucket}
                    </p>
                    <p className="text-sm font-bold tabular-nums text-emerald-300">{formatSignedPct(row.roi_pct)}</p>
                  </div>
                  <p className="mt-2 text-xs text-slate-500">
                    n={row.n} / WR {formatNumber(toNumber(row.wr_pct), "%")} / P(ROI le 0) {formatNumber(toNumber(row.p_roi_le_0), "", 2)}
                  </p>
                  <p className="mt-1 text-xs text-slate-600">{row.years || "No yearly split"}</p>
                </div>
              ))}
            </div>
          </div>
        </>
      )}
    </section>
  );
}


function ProofDashboard({
  rows,
  fromReport,
  reportAge,
  reportStale,
}: {
  rows: ProofRow[];
  fromReport: boolean;
  reportAge: string | null;
  reportStale: boolean;
}) {
  return (
    <section
      id="tennis-proof"
      className="rounded-2xl border border-emerald-500/20 bg-[radial-gradient(circle_at_top_left,rgba(16,185,129,0.16),transparent_34%),rgba(2,6,23,0.76)] p-5 shadow-[0_18px_60px_rgba(2,6,23,0.28)]"
    >
      <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
        <div>
          <div className="flex flex-wrap items-center gap-2">
            <h2 className="text-xl font-semibold text-slate-100">Tennis Lane Proof Board</h2>
            <StatusPill label={fromReport ? "LOCAL NIGHTLY REPORT" : "LIVE FALLBACK"} tone={fromReport ? badgeTones.live : badgeTones.disabled} />
            <StatusPill
              label={reportStale ? "STALE / MISSING" : "FRESH"}
              tone={reportStale ? badgeTones.disabled : badgeTones.live}
            />
          </div>
          <p className="mt-2 max-w-4xl text-sm leading-6 text-slate-400">
            First-read decision layer: what has proof, what is still collecting, and what is currently caution-only.
            This is local/internal and does not change staking or public picks.
          </p>
          <p className={cn("mt-2 text-xs", reportStale ? "text-amber-300" : "text-emerald-300")}>
            {fromReport
              ? `${reportAge ?? "report timestamp unavailable"}. Nightly settlement refreshes this after the fair-odds run.`
              : "Proof report not found. Showing live fallback until the local nightly settlement writes the report."}
          </p>
        </div>
        <a
          href="#cpi-surface-speed"
          className="rounded-full border border-emerald-500/30 bg-emerald-500/10 px-3 py-1.5 text-xs font-semibold uppercase tracking-[0.12em] text-emerald-200 hover:border-emerald-400/60"
        >
          CPI map
        </a>
      </div>

      <div className="mt-5 grid gap-3 md:grid-cols-2 xl:grid-cols-4">
        {rows.map((row) => (
          <div key={row.lane} className="rounded-xl border border-slate-800/80 bg-slate-950/58 p-4">
            <div className="flex flex-wrap items-start justify-between gap-2">
              <div>
                <p className="text-sm font-semibold text-slate-100">{row.label}</p>
                <p className="mt-1 text-[11px] uppercase tracking-[0.12em] text-slate-500">{row.source || "missing"}</p>
              </div>
              <StatusPill label={row.verdict} tone={proofTone(row.verdict)} />
            </div>
            <div className="mt-4 grid grid-cols-2 gap-2 text-xs">
              <div className="rounded-lg border border-slate-800/70 bg-slate-900/55 p-2">
                <p className="text-slate-500">Pending</p>
                <p className="mt-1 font-semibold tabular-nums text-slate-100">{row.pending}</p>
              </div>
              <div className="rounded-lg border border-slate-800/70 bg-slate-900/55 p-2">
                <p className="text-slate-500">Settled</p>
                <p className="mt-1 font-semibold tabular-nums text-slate-100">{row.settled} ({row.wins}W-{row.losses}L)</p>
              </div>
              <div className="rounded-lg border border-slate-800/70 bg-slate-900/55 p-2">
                <p className="text-slate-500">P/L</p>
                <p className={cn("mt-1 font-semibold tabular-nums", (row.pnlUnits ?? 0) >= 0 ? "text-emerald-300" : "text-rose-300")}>{formatNumber(row.pnlUnits, "u", 2)}</p>
              </div>
              <div className="rounded-lg border border-slate-800/70 bg-slate-900/55 p-2">
                <p className="text-slate-500">ROI</p>
                <p className={cn("mt-1 font-semibold tabular-nums", (row.roiPct ?? 0) >= 0 ? "text-emerald-300" : "text-rose-300")}>{formatNumber(row.roiPct, "%")}</p>
              </div>
            </div>
            <p className="mt-3 text-xs text-slate-500">
              CLV n={row.clvRows} / avg {formatNumber(row.avgClvPct, "%", 2)} / positive {formatNumber(row.positiveClvPct, "%")}
            </p>
            {row.note ? <p className="mt-2 line-clamp-2 text-xs leading-5 text-slate-500">{row.note}</p> : null}
          </div>
        ))}
      </div>
    </section>
  );
}

function SideFlipCohortPanel({ summary }: { summary: SideFlipCohortSummary }) {
  const liveVerdict = summary.settled === 0 ? "AWAITING RESULTS" : summary.settled < 30 ? "TOO EARLY" : "REVIEW FORWARD EVIDENCE";
  return (
    <section
      id="strict-side-flip-cohort"
      className="rounded-2xl border border-cyan-500/25 bg-[radial-gradient(circle_at_top_left,rgba(6,182,212,0.14),transparent_36%),rgba(2,6,23,0.78)] p-5 shadow-[0_18px_60px_rgba(2,6,23,0.28)]"
    >
      <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.22em] text-cyan-300">Strict ML expansion audit</p>
          <h2 className="mt-2 text-xl font-semibold text-slate-100">Hard Masters side-flip cohort</h2>
          <p className="mt-2 max-w-4xl text-sm leading-6 text-slate-400">
            Only ATP Hard / Masters 1000 / HIGH rows where model and market choose opposite favourites and their
            favourite-probability magnitudes differ by no more than 10pp. This is not a blanket permission for every
            model/market disagreement.
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <StatusPill label="LIVE INSIDE STRICT" tone={badgeTones.live} />
          <StatusPill label={liveVerdict} tone={proofTone(liveVerdict)} />
        </div>
      </div>

      <div className="mt-5 grid gap-3 sm:grid-cols-2 xl:grid-cols-6">
        <EmptyMetric label="Backtest" value={`${SIDE_FLIP_RETROSPECTIVE.sample} bets`} />
        <EmptyMetric label="Backtest W-L" value={`${SIDE_FLIP_RETROSPECTIVE.wins}W-${SIDE_FLIP_RETROSPECTIVE.losses}L`} />
        <EmptyMetric label="Backtest P/L" value={formatNumber(SIDE_FLIP_RETROSPECTIVE.pnlUnits, "u", 2)} />
        <EmptyMetric label="Backtest ROI" value={formatNumber(SIDE_FLIP_RETROSPECTIVE.roiPct, "%", 2)} />
        <EmptyMetric label="Forward settled" value={`${summary.settled} (${summary.wins}W-${summary.losses}L)`} />
        <EmptyMetric label="Forward ROI" value={formatNumber(summary.roiPct, "%", 2)} />
      </div>

      <div className="mt-3 grid gap-3 lg:grid-cols-2">
        <div className="rounded-xl border border-cyan-500/20 bg-cyan-500/8 p-4 text-sm leading-6 text-cyan-50">
          <p className="font-semibold">Retrospective evidence is strong, not certain.</p>
          <p className="mt-1 text-cyan-100/75">
            Positive in all four years: {SIDE_FLIP_RETROSPECTIVE.yearlyRoiPct.map(([year, roi]) => `${year} ${roi.toFixed(1)}%`).join(" / ")}.
            Bootstrap ROI interval: {SIDE_FLIP_RETROSPECTIVE.bootstrapLowPct.toFixed(1)}% to {SIDE_FLIP_RETROSPECTIVE.bootstrapHighPct.toFixed(1)}%.
          </p>
        </div>
        <div className="rounded-xl border border-amber-500/20 bg-amber-500/8 p-4 text-sm leading-6 text-amber-50">
          <p className="font-semibold">Forward proof is the decision-maker.</p>
          <p className="mt-1 text-amber-100/75">
            Pending {summary.pending}; settled {summary.settled}; CLV {summary.clvRows} rows, avg {formatNumber(summary.avgClvPct, "%", 2)}, positive {formatNumber(summary.positiveClvPct, "%")}.
            The cohort was selected after retrospective review, so it cannot be called guaranteed or fully validated yet.
          </p>
        </div>
      </div>

      <div className="mt-4 overflow-x-auto rounded-xl border border-slate-800/80 bg-slate-950/50">
        <div className="border-b border-slate-800 px-4 py-3 text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-500">
          Forward settlement ledger
        </div>
        {summary.rows.length ? (
          <table className="min-w-full text-left text-xs">
            <thead className="text-slate-500">
              <tr>
                <th className="px-4 py-3 font-medium">Date</th>
                <th className="px-4 py-3 font-medium">Match</th>
                <th className="px-4 py-3 font-medium">Pick</th>
                <th className="px-4 py-3 font-medium">Edge</th>
                <th className="px-4 py-3 font-medium">Result</th>
                <th className="px-4 py-3 font-medium">P/L</th>
                <th className="px-4 py-3 font-medium">CLV</th>
              </tr>
            </thead>
            <tbody className="text-slate-300">
              {summary.rows.slice(0, 12).map((row, index) => {
                const odds = row.side === "P2" ? toNumber(row.pin_odds2) : toNumber(row.pin_odds1);
                const pnl = rowPnlUnits(row);
                const status = isWon(row) ? "WIN" : isLost(row) ? "LOSS" : "PENDING";
                return (
                  <tr key={`${logicalCsvSignalKey(row)}-${index}`} className="border-t border-slate-800/70">
                    <td className="whitespace-nowrap px-4 py-3 text-slate-500">{row.match_date || row.date || "-"}</td>
                    <td className="px-4 py-3">{row.player1 || "-"} vs {row.player2 || "-"}</td>
                    <td className="whitespace-nowrap px-4 py-3 font-semibold text-slate-100">{row.side || "-"} @ {odds?.toFixed(2) ?? "-"}</td>
                    <td className="whitespace-nowrap px-4 py-3 text-cyan-300">{formatSignedPct(row.value_pct)}</td>
                    <td className={cn("whitespace-nowrap px-4 py-3 font-semibold", status === "WIN" ? "text-emerald-300" : status === "LOSS" ? "text-rose-300" : "text-amber-300")}>{status}</td>
                    <td className={cn("whitespace-nowrap px-4 py-3 font-semibold tabular-nums", metricTone(pnl))}>{formatNumber(pnl, "u", 2)}</td>
                    <td className={cn("whitespace-nowrap px-4 py-3 font-semibold tabular-nums", metricTone(toNumber(row.cohort_clv_pct)))}>{formatNumber(toNumber(row.cohort_clv_pct), "%", 2)}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        ) : (
          <p className="px-4 py-5 text-sm text-slate-500">No qualifying 2026 side-flip rows have been recorded yet.</p>
        )}
      </div>
    </section>
  );
}
function LaneCard({ lane, stats }: { lane: LaneView; stats: LaneStats }) {
  const files = TENNIS_MONITOR_FILES[lane.id];
  const proofLabel =
    stats.settledCount > 0 && stats.clvRowCount > 0
      ? "ROI + CLV tracked"
      : stats.settledCount > 0
        ? "ROI tracked, CLV pending"
        : stats.pendingCount > 0 || stats.liveCount > 0
          ? "pending settlement"
          : "no active sample";
  const proofTone =
    stats.settledCount > 0 && stats.clvRowCount > 0
      ? badgeTones.live
      : stats.settledCount > 0 || stats.pendingCount > 0 || stats.liveCount > 0
        ? badgeTones.shadow
        : badgeTones.deferred;

  return (
    <section
      id={laneAnchor(lane.id)}
      className="rounded-2xl border border-slate-800/80 bg-slate-950/55 p-5 shadow-[0_18px_60px_rgba(2,6,23,0.28)]"
    >
      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <div className="flex flex-wrap items-center gap-2">
            <h2 className="text-xl font-semibold text-slate-100">{lane.title}</h2>
            <StatusPill label={lane.state} tone={lane.badgeTone} />
            <StatusPill label={proofLabel} tone={proofTone} />
          </div>
          <p className="mt-2 max-w-3xl text-sm leading-6 text-slate-400">{lane.summary}</p>
        </div>
        <div className="rounded-full border border-slate-800 bg-slate-900/70 px-3 py-1 text-xs font-medium text-slate-300">
          {lane.market}
        </div>
      </div>

      {lane.disabledReason ? (
        <div className="mt-4 rounded-xl border border-amber-500/20 bg-amber-500/10 px-4 py-3 text-sm text-amber-200">
          Disabled reason: {lane.disabledReason}
        </div>
      ) : null}

      <div className="mt-5 grid gap-3 sm:grid-cols-2 lg:grid-cols-6">
        <EmptyMetric label="Live now" value={String(stats.liveCount)} />
        <EmptyMetric label="Pending" value={String(stats.pendingCount)} />
        <EmptyMetric label="Settled W-L" value={stats.settledCount > 0 ? `${stats.wins}W-${stats.losses}L` : "-"} />
        <EmptyMetric label="P/L" value={formatNumber(stats.pnlUnits, "u", 2)} />
        <EmptyMetric label="ROI" value={formatNumber(stats.roiPct, "%")} />
        <EmptyMetric label="Avg CLV" value={formatNumber(stats.avgClvPct, "%", 2)} />
      </div>

      <div className="mt-5 grid gap-3 lg:grid-cols-3">
        <div className="rounded-xl border border-slate-800/70 bg-slate-950/40 p-4 lg:col-span-2">
          <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            <p className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">Latest signal rows</p>
            <p className="text-xs text-slate-500">
              CLV n={stats.clvRowCount} / avg {formatNumber(stats.avgClvPct, "%", 2)} / positive {formatNumber(stats.positiveClvPct, "%")}
            </p>
          </div>
          {stats.latestSignals.length > 0 ? (
            <div className="mt-3 overflow-x-auto">
              <table className="min-w-full text-left text-xs">
                <thead className="text-slate-500">
                  <tr>
                    <th className="py-2 pr-4 font-medium">Match</th>
                    <th className="py-2 pr-4 font-medium">Type</th>
                    <th className="py-2 pr-4 font-medium">Side</th>
                    <th className="py-2 pr-4 font-medium">Edge</th>
                    <th className="py-2 pr-4 font-medium">Status</th>
                    <th className="py-2 pr-4 font-medium">Reason</th>
                  </tr>
                </thead>
                <tbody className="text-slate-300">
                  {stats.latestSignals.map((row, index) => {
                    const status = row.settlement_status || (isWon(row) ? "won" : isLost(row) ? "lost" : "pending");
                    return (
                      <tr key={`${row.player1}-${row.player2}-${row.side}-${index}`} className="border-t border-slate-800/70">
                        <td className="py-2 pr-4">{row.player1 || "-"} vs {row.player2 || "-"}</td>
                        <td className="py-2 pr-4">{row.bet_type || "match"}</td>
                        <td className="py-2 pr-4">{row.side || "-"}</td>
                        <td className="py-2 pr-4">{row.value_pct || "-"}</td>
                        <td className="py-2 pr-4 uppercase tracking-[0.12em] text-slate-500">{status}</td>
                        <td className="py-2 pr-4">{row.shadow_reason || row.blocked_reason || "-"}</td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          ) : (
            <p className="mt-2 text-sm leading-6 text-slate-400">
              No rows yet for this lane. If it is an active shadow lane, run the daily fair-odds pipeline locally.
            </p>
          )}
          {stats.topNearMissReasons.length > 0 ? (
            <p className="mt-4 text-xs text-slate-500">Near-miss reasons: {stats.topNearMissReasons.join(", ")}</p>
          ) : null}
        </div>
        <div className="rounded-xl border border-slate-800/70 bg-slate-950/40 p-4">
          <p className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">Primary file targets</p>
          <dl className="mt-3 space-y-2 text-xs text-slate-400">
            <div>
              <dt className="text-slate-500">Calibration</dt>
              <dd className="break-all text-slate-300">{formatFileTarget(files.calibration)}</dd>
            </div>
            <div>
              <dt className="text-slate-500">Live</dt>
              <dd className="break-all text-slate-300">{formatFileTarget(files.live)}</dd>
            </div>
            <div>
              <dt className="text-slate-500">Near miss</dt>
              <dd className="break-all text-slate-300">{formatFileTarget(files.nearMiss)}</dd>
            </div>
            <div>
              <dt className="text-slate-500">Weekly performance</dt>
              <dd className="break-all text-slate-300">{formatFileTarget(files.performance)}</dd>
            </div>
          </dl>
        </div>
      </div>
    </section>
  );
}

export default async function TennisMonitorPage() {
  if (!TENNIS_MONITOR_ENABLED) {
    notFound();
  }

  const activeLanes = TENNIS_RESEARCH_LANES.map((id) => laneViews[id]);
  const legacyLanes = TENNIS_LEGACY_DISABLED_LANES.map((id) => laneViews[id]);
  const statsEntries = await Promise.all(
    [...TENNIS_RESEARCH_LANES, ...TENNIS_LEGACY_DISABLED_LANES].map(async (id) => [id, await loadLaneStats(id)] as const),
  );
  const statsByLane = Object.fromEntries(statsEntries) as Record<TennisResearchLaneId, LaneStats>;
  const proofReportRows = await loadProofReport();
  const proofRows = proofReportRows?.rows ?? proofRowsFromStats(statsByLane);
  const cpiSummary = await loadCpiSummary();
  const sideFlipSummary = await loadSideFlipCohort();
  const [vnextReport, identityReport, residualReport, countsIdentityReport] = await Promise.all([
    readKnownFile("data/backtest/vnext-mve-report.txt"),
    readKnownFile("data/backtest/tennis-identity-audit.txt"),
    readKnownFile("data/backtest/vnext-v02-folds-report.txt"),
    readKnownFile("data/backtest/vnext-counts-identity-check.txt"),
  ]);
  const vnextSummary = parseVNextResearchSummary(vnextReport, identityReport, residualReport, countsIdentityReport);
  const [extremeGapLab, guardAudit] = await Promise.all([loadExtremeGapLab(), loadTennisGuardAudit()]);

  return (
    <main className="min-h-screen overflow-x-hidden bg-slate-950 text-slate-100">
      <div className="mx-auto max-w-7xl px-4 py-8 sm:px-6 lg:px-8">
        <TennisDecisionBoard
          rows={proofRows}
          fromReport={proofReportRows !== null}
          reportAge={proofReportRows?.ageLabel ?? null}
          reportStale={proofReportRows?.stale ?? true}
        />

        <div className="mt-6">
          <VNextResearchCard summary={vnextSummary} />
        </div>

        <div className="mt-6">
          <ExtremeGapLab data={extremeGapLab} />
        </div>

        <div className="mt-6">
          <TennisGuardAuditCard audit={guardAudit} />
        </div>

        <div className="mt-6">
          <ProofDashboard rows={proofRows} fromReport={proofReportRows !== null} reportAge={proofReportRows?.ageLabel ?? null} reportStale={proofReportRows?.stale ?? true} />
        </div>

        <div className="mt-6">
          <SideFlipCohortPanel summary={sideFlipSummary} />
        </div>

        <nav className="mt-6 flex flex-wrap gap-2" aria-label="Tennis research lanes">
          <a
            href="#extreme-gap-lab"
            className={cn(
              "rounded-full border px-3 py-1.5 text-xs font-semibold uppercase tracking-[0.12em] transition-colors",
              "border-rose-500/30 bg-rose-500/10 text-rose-200 hover:border-rose-400/60",
            )}
          >
            Extreme gap lab
          </a>
          <a
            href="#tennis-proof"
            className={cn(
              "rounded-full border px-3 py-1.5 text-xs font-semibold uppercase tracking-[0.12em] transition-colors",
              "border-emerald-500/30 bg-emerald-500/10 text-emerald-200 hover:border-emerald-400/60",
            )}
          >
            Proof board
          </a>
          <a
            href="#strict-side-flip-cohort"
            className={cn(
              "rounded-full border px-3 py-1.5 text-xs font-semibold uppercase tracking-[0.12em] transition-colors",
              "border-cyan-500/30 bg-cyan-500/10 text-cyan-200 hover:border-cyan-400/60",
            )}
          >
            Side-flip ledger
          </a>
          <a
            href="#guard-audit"
            className={cn(
              "rounded-full border px-3 py-1.5 text-xs font-semibold uppercase tracking-[0.12em] transition-colors",
              "border-amber-500/30 bg-amber-500/10 text-amber-200 hover:border-amber-400/60",
            )}
          >
            Guard audit
          </a>
          <a
            href="#cpi-surface-speed"
            className={cn(
              "rounded-full border px-3 py-1.5 text-xs font-semibold uppercase tracking-[0.12em] transition-colors",
              "border-emerald-500/30 bg-emerald-500/10 text-emerald-200 hover:border-emerald-400/60",
            )}
          >
            CPI speed map
          </a>
          {[...activeLanes, ...legacyLanes].map((lane) => (
            <a
              key={lane.id}
              href={`#${laneAnchor(lane.id)}`}
              className={cn(
                "rounded-full border px-3 py-1.5 text-xs font-semibold uppercase tracking-[0.12em] transition-colors",
                "border-slate-800 bg-slate-900/70 text-slate-300 hover:border-emerald-500/40 hover:text-emerald-200",
              )}
            >
              {lane.title}
            </a>
          ))}
        </nav>

        <div id="shadow-lanes" className="mt-6 space-y-5">
          <CpiSurfaceSpeedCard summary={cpiSummary} />
          {activeLanes.map((lane) => (
            <LaneCard key={lane.id} lane={lane} stats={statsByLane[lane.id]} />
          ))}
          {legacyLanes.map((lane) => (
            <LaneCard key={lane.id} lane={lane} stats={statsByLane[lane.id]} />
          ))}
        </div>
      </div>
    </main>
  );
}
