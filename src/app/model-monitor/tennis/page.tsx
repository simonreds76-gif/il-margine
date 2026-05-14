import { readFile } from "node:fs/promises";
import { notFound } from "next/navigation";
import {
  TENNIS_LEGACY_DISABLED_LANES,
  TENNIS_MONITOR_FILES,
  TENNIS_RESEARCH_LANES,
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
  settledCount: number;
  roiPct: number | null;
  avgClvPct: number | null;
  topNearMissReasons: string[];
  latestSignals: CsvRow[];
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
    title: "Challenger ML",
    state: "SHADOW PLANNED",
    badgeTone: badgeTones.shadow,
    market: "ML only",
    summary: "Future registry name for the existing Challenger ML shadow work. The old profile remains untouched.",
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
    state: "DEFERRED",
    badgeTone: badgeTones.deferred,
    market: "Fav HC, overs",
    summary: "Scaffold only. Grass is sample-thin and will stay shadow-only until proven.",
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
  clay_calibrated: {
    id: "clay_calibrated",
    title: "Clay Calibrated (legacy)",
    state: "DISABLED",
    badgeTone: badgeTones.disabled,
    market: "Legacy ML",
    summary: "Legacy lane remains disabled. It is shown here so the status is explicit.",
    disabledReason: "diagnostics inconclusive 2025-04",
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

async function readKnownFile(relativePath?: string): Promise<string | null> {
  if (!relativePath) return null;
  const fullPath = tryGetKnownProjectFilePath(relativePath);
  if (!fullPath) return null;
  try {
    return await readFile(fullPath, "utf8");
  } catch {
    return null;
  }
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
  const settled = settledRows(archiveRows);
  const pnlValues = settled.map(rowPnlUnits).filter((value): value is number => value !== null);
  const stakeValues = settled.map((row) => toNumber(row.stake_units) ?? 1);
  const totalStake = stakeValues.reduce((sum, value) => sum + value, 0);
  const totalPnl = pnlValues.reduce((sum, value) => sum + value, 0);
  const clvRows = [...(clvCsv ? parseCsv(clvCsv) : []), ...(clvSpreadCsv ? parseCsv(clvSpreadCsv) : [])];
  const clvValues = clvRows
    .map((row) => toNumber(row.clv_pct) ?? toNumber(row.avg_clv_pct))
    .filter((value): value is number => value !== null);

  return {
    liveCount: liveRows.length,
    archiveCount: archiveRows.length,
    nearMissCount: nearMissRows.length,
    settledCount: settled.length,
    roiPct: totalStake > 0 ? (totalPnl / totalStake) * 100 : null,
    avgClvPct: avg(clvValues),
    topNearMissReasons: topReasons(nearMissRows),
    latestSignals: liveRows.slice(-5).reverse(),
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

function LaneCard({ lane, stats }: { lane: LaneView; stats: LaneStats }) {
  const files = TENNIS_MONITOR_FILES[lane.id];

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

      <div className="mt-5 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <EmptyMetric label="Live signals" value={String(stats.liveCount)} />
        <EmptyMetric label="Near misses" value={String(stats.nearMissCount)} />
        <EmptyMetric label="Settled" value={String(stats.settledCount || stats.archiveCount)} />
        <EmptyMetric label="ROI" value={formatNumber(stats.roiPct, "%")} />
      </div>

      <div className="mt-5 grid gap-3 lg:grid-cols-3">
        <div className="rounded-xl border border-slate-800/70 bg-slate-950/40 p-4 lg:col-span-2">
          <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            <p className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">Latest live rows</p>
            <p className="text-xs text-slate-500">Avg CLV: {formatNumber(stats.avgClvPct, "%")}</p>
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
                    <th className="py-2 pr-4 font-medium">Reason</th>
                  </tr>
                </thead>
                <tbody className="text-slate-300">
                  {stats.latestSignals.map((row, index) => (
                    <tr key={`${row.player1}-${row.player2}-${row.side}-${index}`} className="border-t border-slate-800/70">
                      <td className="py-2 pr-4">{row.player1 || "-"} vs {row.player2 || "-"}</td>
                      <td className="py-2 pr-4">{row.bet_type || "match"}</td>
                      <td className="py-2 pr-4">{row.side || "-"}</td>
                      <td className="py-2 pr-4">{row.value_pct || "-"}</td>
                      <td className="py-2 pr-4">{row.shadow_reason || "-"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <p className="mt-2 text-sm leading-6 text-slate-400">
              No live rows yet. Run the lane with `INTERNAL_RESEARCH_LANES=1` and `--signal-profile clay_bo3`.
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
              <dd className="break-all text-slate-300">{files.calibration || "-"}</dd>
            </div>
            <div>
              <dt className="text-slate-500">Live</dt>
              <dd className="break-all text-slate-300">{files.live || "-"}</dd>
            </div>
            <div>
              <dt className="text-slate-500">Near miss</dt>
              <dd className="break-all text-slate-300">{files.nearMiss || "-"}</dd>
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
                Internal-only tennis lane board. Clay bo3 is the first active shadow lane; later tabs stay scaffolded
                until their own research phases are built.
              </p>
            </div>
            <StatusPill label="LOCALHOST ONLY" tone="border-slate-600 bg-slate-900 text-slate-300" />
          </div>
        </div>

        <nav className="mt-6 flex flex-wrap gap-2" aria-label="Tennis research lanes">
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
