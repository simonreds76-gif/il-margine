"use client";

import { useMemo, useState } from "react";
import { BaselineMarketStats, calculateROI, calculateWinRate } from "@/lib/baseline";

export type CategoryProgressionRow = {
  id: number;
  date: string | null;
  category: string;
  event: string;
  player: string;
  selection: string;
  status: string;
  stake: number;
  profit_loss: number;
};

type ProgressionPoint = CategoryProgressionRow & {
  index: number;
  cumulative: number;
  x: number;
  y: number;
  isArchiveReconstruction?: boolean;
  isOriginPoint?: boolean;
  archiveStep?: number;
  archiveSteps?: number;
};

type ChartPoint = ProgressionPoint;

type ChartModel = {
  width: number;
  height: number;
  points: ChartPoint[];
  archivePath: string;
  archiveAreaPath: string;
  livePath: string;
  liveAreaPath: string;
  bridgeX: number | null;
  zeroY: number;
};

// Fixed anchor count keeps the archive line crisp regardless of how many
// historical bets the baseline summarises. The archive is an aggregate, not
// per-bet data, so it never needs hundreds of points.
const ARCHIVE_ANCHORS = 56;
// Share of the plot width reserved for the archive ramp when a live ledger
// also exists. The archive represents roughly 20+ months of old record, so it
// needs visual time to breathe; otherwise large PL/Serie A records look like a
// sudden jump. Keep a live-ledger floor so verified picks remain inspectable.
const ARCHIVE_MAX_WIDTH_FRACTION = 0.72;
const ARCHIVE_MIN_WIDTH_FRACTION = 0.6;
const UNIT_GBP = 100;

function formatUnits(value: number, decimals = 2): string {
  return `${value >= 0 ? "+" : ""}${value.toFixed(decimals)}u`;
}

function formatGbpFromUnits(value: number, unitValue = UNIT_GBP): string {
  const amount = Math.round(Math.abs(value * unitValue));
  const formatted = new Intl.NumberFormat("en-GB", {
    style: "currency",
    currency: "GBP",
    maximumFractionDigits: 0,
  }).format(amount);
  return `${value >= 0 ? "+" : "-"}${formatted}`;
}

function roundUnits(value: number): number {
  return Math.round((value + Number.EPSILON) * 100) / 100;
}

function formatShortDate(value: string | null, isArchive?: boolean, isOrigin?: boolean): string {
  if (isArchive) return "Archive record";
  if (isOrigin) return "Tracking start";
  if (!value) return "Unknown date";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value.slice(0, 10);
  return date.toLocaleDateString("en-GB", { day: "2-digit", month: "short" });
}

function buildPath(points: ChartPoint[]): string {
  if (points.length === 0) return "";
  return points.map((point, index) => `${index === 0 ? "M" : "L"} ${point.x.toFixed(1)} ${point.y.toFixed(1)}`).join(" ");
}

function shouldShowArchive(stats?: BaselineMarketStats | null): stats is BaselineMarketStats {
  return Boolean(stats && (stats.total_bets > 0 || Math.abs(stats.total_profit) > 0.0001));
}

function getArchiveMonthCount(stats: BaselineMarketStats): number {
  const bets = Math.max(0, Math.round(stats.total_bets || 0));
  return Math.max(20, Math.min(30, Math.round(bets / 30)));
}

function buildArchiveRamp(stats: BaselineMarketStats): Omit<ProgressionPoint, "x" | "y">[] {
  const monthCount = getArchiveMonthCount(stats);
  const target = Number(stats.total_profit) || 0;
  const magnitude = Math.abs(target);
  let previous = 0;
  return Array.from({ length: ARCHIVE_ANCHORS + 1 }, (_, index) => {
    const t = index / ARCHIVE_ANCHORS;
    // Near-linear archive bridge with small controlled hills. This represents
    // an aggregate 20+ month record, so it should read as steady long-run P/L,
    // not as a dramatic drawdown/recovery or a fabricated pick-by-pick curve.
    const trend = target * t;
    const smallHill = Math.sin(t * Math.PI * 6) * magnitude * 0.006;
    const slowHill = Math.sin(t * Math.PI * 2) * magnitude * 0.004;
    let cumulative = index === 0 ? 0 : index === ARCHIVE_ANCHORS ? target : trend + smallHill + slowHill;
    if (target >= 0) {
      cumulative = Math.min(target, Math.max(previous, cumulative));
    } else {
      cumulative = Math.max(target, Math.min(previous, cumulative));
    }
    previous = cumulative;
    return {
      id: -1000 - index,
      date: null,
      category: "archive",
      event: "Archive record",
      player: "",
      selection: `Pre-tracking record | period ${Math.max(1, Math.ceil(t * monthCount))}/${monthCount}`,
      status: "settled",
      stake: 0,
      profit_loss: 0,
      index,
      cumulative: roundUnits(cumulative),
      isArchiveReconstruction: true,
      archiveStep: index,
      archiveSteps: ARCHIVE_ANCHORS,
    };
  });
}

function buildOriginPoint(): Omit<ProgressionPoint, "x" | "y"> {
  return {
    id: -1,
    date: null,
    category: "origin",
    event: "Public ledger start",
    player: "",
    selection: "Tracked record starts from 0",
    status: "settled",
    stake: 0,
    profit_loss: 0,
    index: 0,
    cumulative: 0,
    isOriginPoint: true,
  };
}

function buildProgressionPoints(rows: CategoryProgressionRow[], archiveStats?: BaselineMarketStats | null): Omit<ProgressionPoint, "x" | "y">[] {
  const sortedRows = rows
    .slice()
    .sort((a, b) => {
      const aDate = a.date || "";
      const bDate = b.date || "";
      const dateCompare = aDate.localeCompare(bDate);
      if (dateCompare !== 0) return dateCompare;
      return a.id - b.id;
    });

  const points: Omit<ProgressionPoint, "x" | "y">[] = shouldShowArchive(archiveStats) ? buildArchiveRamp(archiveStats) : [buildOriginPoint()];
  let cumulative = points[points.length - 1]?.cumulative ?? 0;

  sortedRows.forEach((row) => {
    cumulative += Number(row.profit_loss) || 0;
    points.push({
      ...row,
      index: points.length,
      cumulative: roundUnits(cumulative),
    });
  });

  return points;
}

function archiveSummary(stats?: BaselineMarketStats | null): { line: string } | null {
  if (!shouldShowArchive(stats)) return null;
  const roi = calculateROI(stats.total_profit, stats.total_stake || stats.total_bets || 1);
  const winRate = calculateWinRate(stats.wins, stats.losses);
  return {
    line: `${stats.total_bets} bets | ${roi >= 0 ? "+" : ""}${roi.toFixed(1)}% ROI | ${winRate.toFixed(1)}% win rate | ${formatUnits(stats.total_profit)}`,
  };
}

function getArchiveWidthFraction(hasArchive: boolean, liveCount: number): number {
  if (!hasArchive) return 0;
  if (liveCount <= 0) return 1;
  const livePressure = Math.min(1, liveCount / 120);
  return ARCHIVE_MAX_WIDTH_FRACTION - (ARCHIVE_MAX_WIDTH_FRACTION - ARCHIVE_MIN_WIDTH_FRACTION) * livePressure;
}

function buildChart(pointsRaw: Omit<ProgressionPoint, "x" | "y">[]): ChartModel {
  const width = 720;
  const height = 240;
  const paddingX = 20;
  const paddingTop = 22;
  const paddingBottom = 24;

  const archive = pointsRaw.filter((point) => point.isArchiveReconstruction);
  const origin = pointsRaw.filter((point) => point.isOriginPoint);
  const live = pointsRaw.filter((point) => !point.isArchiveReconstruction && !point.isOriginPoint);
  const hasArchive = archive.length > 0;
  const hasLive = live.length > 0;

  if (!hasArchive && !hasLive) {
    return { width, height, points: [], archivePath: "", archiveAreaPath: "", livePath: "", liveAreaPath: "", bridgeX: null, zeroY: height / 2 };
  }

  const cumulativeValues = pointsRaw.map((point) => point.cumulative);
  const minValue = Math.min(0, ...cumulativeValues);
  const maxValue = Math.max(0, ...cumulativeValues);
  const span = Math.max(1, maxValue - minValue);
  const plotWidth = width - paddingX * 2;
  const plotHeight = height - paddingTop - paddingBottom;
  const yOf = (cumulative: number) => paddingTop + ((maxValue - cumulative) / span) * plotHeight;

  const archiveWidthFraction = getArchiveWidthFraction(hasArchive, live.length);
  const leadWidth = hasArchive ? archiveWidthFraction * plotWidth : 0;
  const liveStart = paddingX + leadWidth;
  const liveWidth = plotWidth - leadWidth;

  const archiveXY: ChartPoint[] = archive.map((point, index) => ({
    ...point,
    x: archive.length === 1 ? paddingX : paddingX + (index / (archive.length - 1)) * leadWidth,
    y: yOf(point.cumulative),
  }));
  const originXY: ChartPoint[] = origin.map((point) => ({ ...point, x: paddingX, y: yOf(point.cumulative) }));
  const liveXY: ChartPoint[] = live.map((point, index) => ({
    ...point,
    x: liveStart + ((index + 1) / live.length) * liveWidth,
    y: yOf(point.cumulative),
  }));

  const bridge = archiveXY[archiveXY.length - 1] ?? originXY[0] ?? null;
  const livePathPoints = bridge && liveXY.length > 0 ? [bridge, ...liveXY] : liveXY;
  const zeroY = yOf(0);

  const archivePath = buildPath(archiveXY);
  const archiveAreaPath =
    archiveXY.length > 1
      ? `${archivePath} L ${archiveXY[archiveXY.length - 1].x.toFixed(1)} ${zeroY.toFixed(1)} L ${archiveXY[0].x.toFixed(1)} ${zeroY.toFixed(1)} Z`
      : "";
  const livePath = buildPath(livePathPoints);
  const liveAreaPath = livePathPoints.length
    ? `${livePath} L ${livePathPoints[livePathPoints.length - 1].x.toFixed(1)} ${zeroY.toFixed(1)} L ${livePathPoints[0].x.toFixed(1)} ${zeroY.toFixed(1)} Z`
    : "";

  return {
    width,
    height,
    points: [...archiveXY, ...originXY, ...liveXY],
    archivePath,
    archiveAreaPath,
    livePath,
    liveAreaPath,
    bridgeX: bridge?.x ?? null,
    zeroY,
  };
}

function HeroMetric({ units, positive }: { units: number; positive: boolean }) {
  return (
    <div className={`rounded-2xl border p-4 ${positive ? "border-emerald-500/25 bg-emerald-500/[0.07]" : "border-rose-500/25 bg-rose-500/[0.07]"}`}>
      <div className="font-mono text-[10px] font-bold uppercase tracking-[0.18em] text-slate-400">Net profit</div>
      <div className={`mt-1 font-mono text-3xl font-black leading-none tabular-nums ${positive ? "text-emerald-300" : "text-rose-300"}`}>
        {formatUnits(units)}
      </div>
      <div className="mt-2 text-sm text-slate-300">
        At {"\u00a3"}100 per unit:{" "}
        <span className={`font-mono font-bold tabular-nums ${positive ? "text-emerald-300" : "text-rose-300"}`}>
          {formatGbpFromUnits(units)}
        </span>
      </div>
    </div>
  );
}

function ProgressionStat({ label, value, hint, tone = "neutral" }: { label: string; value: string; hint?: string; tone?: "positive" | "negative" | "neutral" }) {
  const toneClass = tone === "positive" ? "text-emerald-400" : tone === "negative" ? "text-rose-400" : "text-slate-100";
  return (
    <div className="rounded-xl border border-slate-800 bg-slate-950/45 px-3 py-2.5">
      <div className="font-mono text-[10px] font-bold uppercase tracking-[0.14em] text-slate-500">{label}</div>
      <div className={`mt-1 font-mono text-base font-black tabular-nums ${toneClass}`}>{value}</div>
      {hint ? <div className="mt-0.5 text-[10px] leading-tight text-slate-600">{hint}</div> : null}
    </div>
  );
}

export default function ProfitProgressionPanel({
  rows,
  activeName,
  archiveStats,
}: {
  rows: CategoryProgressionRow[];
  activeName: string;
  archiveStats?: BaselineMarketStats | null;
}) {
  const [activePointId, setActivePointId] = useState<number | null>(null);
  const rawPoints = useMemo(() => buildProgressionPoints(rows, archiveStats), [archiveStats, rows]);
  const livePoints = useMemo(() => rawPoints.filter((point) => !point.isArchiveReconstruction && !point.isOriginPoint), [rawPoints]);
  const latestPoint = livePoints[livePoints.length - 1] ?? rawPoints[rawPoints.length - 1] ?? null;
  const activeRawPoint = activePointId === null ? latestPoint : rawPoints.find((point) => point.id === activePointId) ?? latestPoint;

  const metrics = useMemo(() => {
    const bridgeCumulative = (() => {
      const archive = rawPoints.filter((point) => point.isArchiveReconstruction);
      return archive.length > 0 ? archive[archive.length - 1].cumulative : 0;
    })();
    const peak = rawPoints.reduce((max, point) => Math.max(max, point.cumulative), 0);
    // Drawdown is measured on the verified live ledger only - the archive is an
    // aggregate reconstruction and must not manufacture peaks or troughs.
    let runningPeak = bridgeCumulative;
    let maxDrawdown = 0;
    for (const point of livePoints) {
      runningPeak = Math.max(runningPeak, point.cumulative);
      maxDrawdown = Math.max(maxDrawdown, runningPeak - point.cumulative);
    }
    const last10 = livePoints.slice(-10).reduce((sum, point) => sum + (Number(point.profit_loss) || 0), 0);
    return {
      cumulative: latestPoint?.cumulative ?? 0,
      peak,
      maxDrawdown,
      last10,
    };
  }, [latestPoint?.cumulative, livePoints, rawPoints]);

  const chart = useMemo(() => buildChart(rawPoints), [rawPoints]);
  const activePoint = activeRawPoint ? chart.points.find((point) => point.id === activeRawPoint.id) ?? null : null;
  const positiveChart = metrics.cumulative >= 0;
  const liveStroke = positiveChart ? "#34d399" : "#fb7185";
  const liveFill = positiveChart ? "rgba(16,185,129,0.16)" : "rgba(251,113,133,0.14)";
  const summary = archiveSummary(archiveStats);

  const liveCount = livePoints.length;
  const liveNodeEvery = Math.max(1, Math.ceil(liveCount / 14));
  const archiveNodeEvery = Math.max(1, Math.ceil(ARCHIVE_ANCHORS / 4));
  const hasChart = chart.points.length > 0;

  return (
    <div className="mt-4 overflow-hidden rounded-2xl border border-emerald-500/20 bg-[radial-gradient(circle_at_18%_0%,rgba(16,185,129,0.10),transparent_34%),linear-gradient(135deg,rgba(15,23,42,0.78),rgba(2,6,23,0.88))]">
      <div className="grid gap-0 lg:grid-cols-[1.15fr,0.85fr]">
        <div className="border-b border-slate-800/80 p-5 lg:border-b-0 lg:border-r">
          <div className="mb-4">
            <div className="font-mono text-[10px] font-black uppercase tracking-[0.22em] text-emerald-400/90">Profit curve</div>
            <h3 className="mt-1 text-lg font-semibold text-slate-100">{activeName} profit curve</h3>
            <p className="mt-1 text-xs leading-relaxed text-slate-500">
              Dashed line is our archive record before public tracking; the solid line is the verified public ledger.
            </p>
          </div>

          <div className="relative h-[240px] rounded-xl border border-slate-800 bg-slate-950/55 p-2">
            {hasChart ? (
              <svg
                viewBox={`0 0 ${chart.width} ${chart.height}`}
                className="h-full w-full"
                role="img"
                aria-label={`${activeName} profit and loss progression`}
                onMouseLeave={() => setActivePointId(null)}
              >
                <line x1="0" x2={chart.width} y1={chart.zeroY} y2={chart.zeroY} stroke="rgba(148,163,184,0.20)" strokeDasharray="2 6" />
                {chart.bridgeX !== null && chart.archivePath ? (
                  <line x1={chart.bridgeX} x2={chart.bridgeX} y1="14" y2={chart.height - 16} stroke="rgba(148,163,184,0.16)" strokeDasharray="3 5" />
                ) : null}
                {chart.archiveAreaPath ? <path d={chart.archiveAreaPath} fill="rgba(148,163,184,0.06)" /> : null}
                {chart.liveAreaPath ? <path d={chart.liveAreaPath} fill={liveFill} /> : null}
                {chart.archivePath ? (
                  <path
                    d={chart.archivePath}
                    fill="none"
                    stroke="rgba(148,163,184,0.85)"
                    strokeDasharray="6 5"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth="2.25"
                  />
                ) : null}
                {chart.livePath ? (
                  <path d={chart.livePath} fill="none" stroke={liveStroke} strokeLinecap="round" strokeLinejoin="round" strokeWidth="3.25" />
                ) : null}
                {chart.points.map((point, index) => {
                  const isActive = activePoint?.id === point.id;
                  const isArchive = Boolean(point.isArchiveReconstruction);
                  const isOrigin = Boolean(point.isOriginPoint);
                  const isLive = !isArchive && !isOrigin;
                  const showArchiveNode =
                    isArchive && (point.archiveStep === 0 || point.archiveStep === point.archiveSteps || (point.archiveStep ?? 0) % archiveNodeEvery === 0);
                  const isLastLive = isLive && index === chart.points.length - 1;
                  const showLiveNode = isLive && (isLastLive || livePoints.indexOf(point) % liveNodeEvery === 0);
                  const visible = isActive || showArchiveNode || showLiveNode || isOrigin;
                  return (
                    <g key={`${point.id}-${index}`}>
                      {visible ? (
                        <circle
                          cx={point.x}
                          cy={point.y}
                          r={isActive ? 6 : isLive ? 3.5 : 3}
                          fill={isActive ? "#fbbf24" : isLive ? liveStroke : "#0b1220"}
                          stroke={isActive ? "rgba(251,191,36,0.45)" : isLive ? `${liveStroke}88` : "rgba(148,163,184,0.85)"}
                          strokeWidth={isActive ? 6 : 1.5}
                          className="transition-all"
                        />
                      ) : null}
                      <circle
                        cx={point.x}
                        cy={point.y}
                        r={10}
                        fill="transparent"
                        className={isLive ? "cursor-pointer" : "cursor-help"}
                        onMouseEnter={() => setActivePointId(point.id)}
                        onClick={() => setActivePointId(point.id)}
                      />
                    </g>
                  );
                })}
              </svg>
            ) : (
              <div className="flex h-full items-center justify-center text-center">
                <div>
                  <div className="text-sm font-semibold text-slate-300">No settled rows yet</div>
                  <div className="mt-1 max-w-xs text-xs text-slate-500">The profit curve appears once this tab has settled picks.</div>
                </div>
              </div>
            )}
          </div>

          <div className="mt-3 flex flex-wrap items-center gap-x-5 gap-y-2 text-[11px] text-slate-400">
            <span className="inline-flex items-center gap-2">
              <span className="inline-block h-[3px] w-7 rounded-full" style={{ backgroundColor: liveStroke }} />
              Public ledger
            </span>
            <span className="inline-flex items-center gap-2">
              <span className="inline-block h-0 w-7 border-t-2 border-dashed border-slate-400/80" />
              Archive record
            </span>
          </div>
        </div>

        <div className="p-5">
          <HeroMetric units={metrics.cumulative} positive={positiveChart} />

          <div className="mt-3 grid grid-cols-2 gap-3">
            <ProgressionStat label="Peak" value={formatUnits(metrics.peak)} tone={metrics.peak >= 0 ? "positive" : "neutral"} />
            <ProgressionStat
              label="Max drawdown"
              value={`-${metrics.maxDrawdown.toFixed(2)}u`}
              hint="Largest dip from a high"
              tone={metrics.maxDrawdown > 0 ? "negative" : "neutral"}
            />
            <ProgressionStat label="Last 10 picks" value={formatUnits(metrics.last10)} tone={metrics.last10 >= 0 ? "positive" : "negative"} />
            <ProgressionStat label="Public picks" value={`${liveCount}`} tone="neutral" />
          </div>

          <div className="mt-4 rounded-xl border border-slate-800 bg-slate-950/45 p-4">
            <div className="font-mono text-[10px] font-bold uppercase tracking-[0.16em] text-slate-500">Selected point</div>
            {activeRawPoint ? (
              <div className="mt-3">
                <div className="flex items-center justify-between gap-3">
                  <span className="text-sm font-semibold text-slate-100">
                    {formatShortDate(activeRawPoint.date, activeRawPoint.isArchiveReconstruction, activeRawPoint.isOriginPoint)}
                  </span>
                  <span className={`font-mono text-sm font-black tabular-nums ${activeRawPoint.cumulative >= 0 ? "text-emerald-400" : "text-rose-400"}`}>
                    {formatUnits(
                      activeRawPoint.isArchiveReconstruction || activeRawPoint.isOriginPoint ? activeRawPoint.cumulative : Number(activeRawPoint.profit_loss) || 0,
                    )}
                  </span>
                </div>

                {activeRawPoint.isArchiveReconstruction ? (
                  <>
                    <div className="mt-2 text-sm font-semibold text-slate-200">Archive record summary</div>
                    <div className="mt-1 text-sm leading-relaxed text-slate-300">{summary?.line ?? "Pre-tracking aggregate record."}</div>
                    <div className="mt-3 inline-flex rounded-full border border-slate-700 bg-slate-900/80 px-2.5 py-1 font-mono text-[11px] text-slate-400">
                      Aggregate - not individual bets
                    </div>
                  </>
                ) : activeRawPoint.isOriginPoint ? (
                  <>
                    <div className="mt-2 text-sm font-semibold text-slate-200">Public ledger start</div>
                    <div className="mt-1 text-sm leading-relaxed text-slate-300">Verified tracking starts from 0 for this tab.</div>
                  </>
                ) : (
                  <>
                    <div className="mt-2 text-sm leading-snug text-slate-300">{activeRawPoint.event}</div>
                    <div className="mt-1 text-sm font-semibold leading-relaxed text-slate-100">
                      {activeRawPoint.player ? `${activeRawPoint.player} - ${activeRawPoint.selection}` : activeRawPoint.selection}
                    </div>
                    <div className="mt-3 flex flex-wrap gap-2 font-mono text-[11px]">
                      <span className="rounded-full border border-slate-700 bg-slate-900/80 px-2.5 py-1 text-slate-400">
                        Stake {activeRawPoint.stake.toFixed(2)}u
                      </span>
                      <span className="rounded-full border border-emerald-500/20 bg-emerald-500/10 px-2.5 py-1 text-emerald-300">
                        Running {formatUnits(activeRawPoint.cumulative)}
                      </span>
                    </div>
                  </>
                )}
              </div>
            ) : (
              <p className="mt-3 text-sm text-slate-500">Hover the curve to inspect a point.</p>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
