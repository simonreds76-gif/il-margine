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
};

type ChartPoint = ProgressionPoint;

type ChartModel = {
  width: number;
  height: number;
  points: ChartPoint[];
  archivePath: string;
  livePath: string;
  liveAreaPath: string;
  zeroY: number;
};

function formatUnits(value: number, decimals = 2): string {
  return `${value >= 0 ? "+" : ""}${value.toFixed(decimals)}u`;
}

function roundUnits(value: number): number {
  return Math.round((value + Number.EPSILON) * 100) / 100;
}

function formatShortDate(value: string | null, isArchive?: boolean, isOrigin?: boolean): string {
  if (isArchive) return "Archive";
  if (isOrigin) return "Start";
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

function buildArchiveRamp(stats: BaselineMarketStats, anchorCount = 7): Omit<ProgressionPoint, "x" | "y">[] {
  const target = Number(stats.total_profit) || 0;
  return Array.from({ length: anchorCount + 1 }, (_, index) => {
    const t = index / anchorCount;
    const eased = t * t * (3 - 2 * t);
    return {
      id: -1000 - index,
      date: null,
      category: "archive",
      event: "Archive summary",
      player: "",
      selection: "Pre-tracking aggregate record",
      status: "settled",
      stake: 0,
      profit_loss: 0,
      index,
      cumulative: roundUnits(target * eased),
      isArchiveReconstruction: true,
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

function ProgressionStat({ label, value, tone = "neutral" }: { label: string; value: string; tone?: "positive" | "negative" | "neutral" }) {
  const toneClass = tone === "positive" ? "text-emerald-400" : tone === "negative" ? "text-rose-400" : "text-slate-100";
  return (
    <div className="rounded-xl border border-slate-800 bg-slate-950/45 px-3 py-2.5">
      <div className="font-mono text-[10px] font-bold uppercase tracking-[0.16em] text-slate-500">{label}</div>
      <div className={`mt-1 font-mono text-sm font-black tabular-nums ${toneClass}`}>{value}</div>
    </div>
  );
}

function archiveSummaryText(stats?: BaselineMarketStats | null) {
  if (!shouldShowArchive(stats)) return "No archive baseline for this tab.";
  const roi = calculateROI(stats.total_profit, stats.total_stake || stats.total_bets || 1);
  const winRate = calculateWinRate(stats.wins, stats.losses);
  return `${stats.total_bets} bets · ${roi >= 0 ? "+" : ""}${roi.toFixed(1)}% ROI · ${winRate.toFixed(1)}% win rate`;
}

function buildChart(pointsRaw: Omit<ProgressionPoint, "x" | "y">[]): ChartModel {
  const width = 720;
  const height = 220;
  const paddingX = 18;
  const paddingY = 18;
  if (pointsRaw.length === 0) {
    return { width, height, points: [], archivePath: "", livePath: "", liveAreaPath: "", zeroY: height / 2 };
  }

  const cumulativeValues = pointsRaw.map((point) => point.cumulative);
  const minValue = Math.min(0, ...cumulativeValues);
  const maxValue = Math.max(0, ...cumulativeValues);
  const span = Math.max(1, maxValue - minValue);
  const plotWidth = width - paddingX * 2;
  const plotHeight = height - paddingY * 2;

  const points = pointsRaw.map((point, index) => {
    const x = pointsRaw.length === 1 ? width / 2 : paddingX + (index / (pointsRaw.length - 1)) * plotWidth;
    const y = paddingY + ((maxValue - point.cumulative) / span) * plotHeight;
    return { ...point, x, y };
  });

  const archivePoints = points.filter((point) => point.isArchiveReconstruction);
  const livePoints = points.filter((point) => !point.isArchiveReconstruction && !point.isOriginPoint);
  const bridgePoint = archivePoints[archivePoints.length - 1] ?? points.find((point) => point.isOriginPoint);
  const livePathPoints = livePoints.length > 0 && bridgePoint ? [bridgePoint, ...livePoints] : livePoints;
  const zeroY = paddingY + ((maxValue - 0) / span) * plotHeight;
  const livePath = buildPath(livePathPoints);
  const liveAreaPath = livePathPoints.length
    ? `${livePath} L ${livePathPoints[livePathPoints.length - 1].x.toFixed(1)} ${zeroY.toFixed(1)} L ${livePathPoints[0].x.toFixed(1)} ${zeroY.toFixed(1)} Z`
    : "";

  return {
    width,
    height,
    points,
    archivePath: buildPath(archivePoints),
    livePath,
    liveAreaPath,
    zeroY,
  };
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
    let peak = 0;
    let maxDrawdown = 0;
    for (const point of rawPoints) {
      peak = Math.max(peak, point.cumulative);
      maxDrawdown = Math.max(maxDrawdown, peak - point.cumulative);
    }
    const last10 = livePoints.slice(-10).reduce((sum, point) => sum + point.profit_loss, 0);
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

  return (
    <div className="mt-4 overflow-hidden rounded-2xl border border-emerald-500/20 bg-[radial-gradient(circle_at_18%_0%,rgba(16,185,129,0.10),transparent_34%),linear-gradient(135deg,rgba(15,23,42,0.78),rgba(2,6,23,0.88))]">
      <div className="grid gap-0 lg:grid-cols-[1.1fr,0.9fr]">
        <div className="border-b border-slate-800/80 p-5 lg:border-b-0 lg:border-r">
          <div className="mb-4 flex flex-wrap items-start justify-between gap-3">
            <div>
              <div className="font-mono text-[10px] font-black uppercase tracking-[0.22em] text-emerald-400/90">
                P/L progression
              </div>
              <h3 className="mt-1 text-lg font-semibold text-slate-100">{activeName} equity curve</h3>
              <p className="mt-1 text-xs leading-relaxed text-slate-500">
                Cumulative P/L from zero. Solid = verified public ledger. Dashed = pre-tracking record shown as an aggregate.
              </p>
            </div>
            <div className={`rounded-full border px-3 py-1.5 font-mono text-xs font-black tabular-nums ${
              metrics.cumulative >= 0
                ? "border-emerald-500/25 bg-emerald-500/10 text-emerald-300"
                : "border-rose-500/25 bg-rose-500/10 text-rose-300"
            }`}>
              {formatUnits(metrics.cumulative)}
            </div>
          </div>

          <div className="relative h-[220px] rounded-xl border border-slate-800 bg-slate-950/55 p-2">
            {chart.points.length > 0 ? (
              <svg
                viewBox={`0 0 ${chart.width} ${chart.height}`}
                className="h-full w-full"
                role="img"
                aria-label={`${activeName} profit and loss progression`}
                onMouseLeave={() => setActivePointId(null)}
              >
                <line x1="0" x2={chart.width} y1={chart.zeroY} y2={chart.zeroY} stroke="rgba(148,163,184,0.22)" strokeDasharray="6 7" />
                {chart.liveAreaPath ? <path d={chart.liveAreaPath} fill={liveFill} /> : null}
                {chart.archivePath ? (
                  <path
                    d={chart.archivePath}
                    fill="none"
                    stroke="rgba(148,163,184,0.62)"
                    strokeDasharray="8 8"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth="3"
                  />
                ) : null}
                {chart.livePath ? (
                  <path d={chart.livePath} fill="none" stroke={liveStroke} strokeLinecap="round" strokeLinejoin="round" strokeWidth="4" />
                ) : null}
                {chart.points.map((point, index) => {
                  const isActive = activePoint?.id === point.id;
                  const isArchive = point.isArchiveReconstruction;
                  const isOrigin = point.isOriginPoint;
                  const showPoint =
                    isActive ||
                    index === chart.points.length - 1 ||
                    isArchive ||
                    index % Math.ceil(chart.points.length / 18) === 0;
                  return (
                    <circle
                      key={`${point.id}-${index}`}
                      cx={point.x}
                      cy={point.y}
                      r={isActive ? 7 : isArchive ? 3.5 : showPoint ? 4 : 8}
                      fill={isArchive || isOrigin ? "#020617" : isActive ? "#fbbf24" : showPoint ? liveStroke : "transparent"}
                      stroke={isActive ? "rgba(251,191,36,0.5)" : isArchive || isOrigin ? "rgba(148,163,184,0.7)" : `${liveStroke}66`}
                      strokeWidth={isActive ? 8 : isArchive || isOrigin ? 2 : showPoint ? 3 : 0}
                      className={isArchive || isOrigin ? "cursor-default transition-opacity" : "cursor-pointer transition-opacity"}
                      onMouseEnter={() => setActivePointId(point.id)}
                      onClick={() => setActivePointId(point.id)}
                    />
                  );
                })}
              </svg>
            ) : (
              <div className="flex h-full items-center justify-center text-center">
                <div>
                  <div className="text-sm font-semibold text-slate-300">No settled rows yet</div>
                  <div className="mt-1 max-w-xs text-xs text-slate-500">The progression line appears once this tab has won/lost settlements.</div>
                </div>
              </div>
            )}
          </div>

          <div className="mt-3 flex flex-wrap gap-x-4 gap-y-2 text-[11px] text-slate-500">
            <span><span className="mr-1 inline-block h-0.5 w-6 align-middle" style={{ backgroundColor: liveStroke }} />Public ledger</span>
            <span><span className="mr-1 inline-block h-0.5 w-6 border-t border-dashed border-slate-400 align-middle" />Archive summary</span>
            <span>Max DD = largest peak-to-trough drawdown</span>
            <span>Last 10 = last 10 settled public picks</span>
          </div>
        </div>

        <div className="p-5">
          <div className="grid grid-cols-2 gap-3">
            <ProgressionStat label="Current" value={formatUnits(metrics.cumulative)} tone={metrics.cumulative >= 0 ? "positive" : "negative"} />
            <ProgressionStat label="Peak" value={formatUnits(metrics.peak)} tone={metrics.peak >= 0 ? "positive" : "neutral"} />
            <ProgressionStat label="Max DD" value={`${metrics.maxDrawdown.toFixed(2)}u`} tone={metrics.maxDrawdown > 0 ? "negative" : "neutral"} />
            <ProgressionStat label="Last 10" value={formatUnits(metrics.last10)} tone={metrics.last10 >= 0 ? "positive" : "negative"} />
          </div>

          <div className="mt-4 rounded-xl border border-slate-800 bg-slate-950/45 p-4">
            <div className="font-mono text-[10px] font-bold uppercase tracking-[0.16em] text-slate-500">
              Selected point
            </div>
            {activeRawPoint ? (
              <div className="mt-3">
                <div className="flex items-center justify-between gap-3">
                  <span className="text-sm font-semibold text-slate-100">
                    {formatShortDate(activeRawPoint.date, activeRawPoint.isArchiveReconstruction, activeRawPoint.isOriginPoint)}
                  </span>
                  <span className={`font-mono text-sm font-black ${activeRawPoint.cumulative >= 0 ? "text-emerald-400" : "text-rose-400"}`}>
                    {formatUnits(activeRawPoint.isArchiveReconstruction || activeRawPoint.isOriginPoint ? activeRawPoint.cumulative : activeRawPoint.profit_loss)}
                  </span>
                </div>
                {activeRawPoint.isArchiveReconstruction ? (
                  <>
                    <div className="mt-2 text-sm leading-snug text-slate-300">Archive summary · pre-tracking record</div>
                    <div className="mt-1 text-sm font-semibold leading-relaxed text-slate-100">{archiveSummaryText(archiveStats)}</div>
                  </>
                ) : activeRawPoint.isOriginPoint ? (
                  <>
                    <div className="mt-2 text-sm leading-snug text-slate-300">Public ledger start</div>
                    <div className="mt-1 text-sm font-semibold leading-relaxed text-slate-100">Tracked record starts from 0.</div>
                  </>
                ) : (
                  <>
                    <div className="mt-2 text-sm leading-snug text-slate-300">{activeRawPoint.event}</div>
                    <div className="mt-1 text-sm font-semibold leading-relaxed text-slate-100">
                      {activeRawPoint.player ? `${activeRawPoint.player} - ${activeRawPoint.selection}` : activeRawPoint.selection}
                    </div>
                  </>
                )}
                <div className="mt-3 flex flex-wrap gap-2 font-mono text-[11px]">
                  {!activeRawPoint.isArchiveReconstruction && !activeRawPoint.isOriginPoint ? (
                    <span className="rounded-full border border-slate-700 bg-slate-900/80 px-2.5 py-1 text-slate-400">
                      Stake {activeRawPoint.stake.toFixed(2)}u
                    </span>
                  ) : null}
                  <span className="rounded-full border border-emerald-500/20 bg-emerald-500/10 px-2.5 py-1 text-emerald-300">
                    Balance {formatUnits(activeRawPoint.cumulative)}
                  </span>
                  {activeRawPoint.isArchiveReconstruction ? (
                    <span className="rounded-full border border-slate-700 bg-slate-900/80 px-2.5 py-1 text-slate-400">
                      Aggregate only
                    </span>
                  ) : null}
                </div>
              </div>
            ) : (
              <p className="mt-3 text-sm text-slate-500">No settled pick selected.</p>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
