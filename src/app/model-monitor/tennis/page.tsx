import { readFile } from "node:fs/promises";
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
  process.env.NODE_ENV !== "production" && process.env.INTERNAL_RESEARCH_LANES === "1";

type LaneView = {
  id: TennisResearchLaneId;
  title: string;
  state: "LIVE ALIAS" | "SHADOW LIVE" | "SHADOW PLANNED" | "DEFERRED" | "DISABLED";
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

type CpiSummary = {
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
    title: "Challenger ML tracker",
    state: "DEFERRED",
    badgeTone: badgeTones.deferred,
    market: "Outcome calibration",
    summary: "Outcome-calibration tracker only. No ROI/CLV claim until Pinnacle Challenger odds capture is complete."
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
    state: "SHADOW LIVE",
    badgeTone: badgeTones.shadow,
    market: "ML by court speed",
    summary:
      "ATP-only ML shadow lane using lagged CPI z-score gates. It admits only cells that passed the 2024 train and 2025 holdout gate; no live staking or public routing.",
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
    const fullPath = tryGetKnownProjectFilePath(candidate);
    if (!fullPath) continue;
    try {
      return await readFile(fullPath, "utf8");
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
  const [csv, overlayCsv, overlayReport, regimeCsv, regimeReport, gateCsv, factorCsv, gateReport] = await Promise.all([
    readKnownFile("data/backtest/cpi-all-surfaces-cells.csv"),
    readKnownFile("data/backtest/cpi-shadow-overlay-cells.csv"),
    readKnownFile("data/backtest/cpi-shadow-overlay-report.txt"),
    readKnownFile("data/backtest/cpi-regime-surface-cells.csv"),
    readKnownFile("data/backtest/cpi-regime-surface-report.txt"),
    readKnownFile("data/backtest/cpi-regime-shadow-gates.csv"),
    readKnownFile("data/backtest/cpi-regime-shadow-value-factors.csv"),
    readKnownFile("data/backtest/cpi-regime-shadow-report.txt"),
  ]);
  if (!csv) {
    return {
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
  const regimeGateRows = regimeGateRowsRaw
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
              CLV n={stats.clvRowCount} Ã‚Â· avg {formatNumber(stats.avgClvPct, "%", 2)} Ã‚Â· positive {formatNumber(stats.positiveClvPct, "%")}
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
  const cpiSummary = await loadCpiSummary();

  return (
    <main className="min-h-screen bg-slate-950 text-slate-100">
      <div className="mx-auto max-w-7xl px-4 py-8 sm:px-6 lg:px-8">
        <div className="rounded-3xl border border-slate-800 bg-[radial-gradient(circle_at_top_left,rgba(16,185,129,0.13),transparent_34%),linear-gradient(135deg,rgba(15,23,42,0.96),rgba(2,6,23,0.98))] p-6 md:p-8">
          <p className="text-xs font-semibold uppercase tracking-[0.22em] text-emerald-300">Internal research</p>
          <div className="mt-3 flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
            <div>
              <h1 className="text-3xl font-semibold tracking-tight text-slate-50 md:text-4xl">
                Tennis Research Lanes
              </h1>
              <p className="mt-3 max-w-3xl text-sm leading-6 text-slate-400">
                Internal-only tennis lane board. Clay bo3 and Grass bo3 are active shadow lanes; deferred tabs stay
                scaffolded until their own research phases are built.
              </p>
            </div>
            <StatusPill label="LOCALHOST ONLY" tone="border-slate-600 bg-slate-900 text-slate-300" />
          </div>
        </div>

        <nav className="mt-6 flex flex-wrap gap-2" aria-label="Tennis research lanes">
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

        <div className="mt-6 space-y-5">
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
