"use client";

import { useMemo, type PointerEvent } from "react";
import type { ProgressionPoint } from "./ProfitProgressionPanel";

export default function ProfitProgressionChart({ points, activePointId, onSelect, activeName, positive }: {
  points: Omit<ProgressionPoint, "x" | "y">[];
  activePointId: number | null;
  onSelect: (id: number | null) => void;
  activeName: string;
  positive: boolean;
}) {
  const chart = useMemo(() => buildChart(points), [points]);
  const liveCount = points.filter((point) => !point.isArchiveReconstruction && !point.isOriginPoint).length;
  const liveNodeEvery = Math.max(1, Math.ceil(liveCount / 14));
  const liveStart = chart.points.length - liveCount;
  const stroke = positive ? "#34d399" : "#fb7185";
  const fill = positive ? "rgba(16,185,129,0.16)" : "rgba(251,113,133,0.14)";

  // One hit surface replaces hundreds of invisible SVG nodes. All points remain
  // in the line and are selectable with pointer, touch or arrow keys.
  function selectAt(event: PointerEvent<SVGSVGElement>) {
    const svg = event.currentTarget;
    const transform = svg.getScreenCTM();
    if (!transform || chart.points.length === 0) return;
    const pointer = svg.createSVGPoint();
    pointer.x = event.clientX;
    pointer.y = event.clientY;
    const x = pointer.matrixTransform(transform.inverse()).x;
    let nearest = chart.points[0];
    for (const point of chart.points) {
      if (Math.abs(point.x - x) < Math.abs(nearest.x - x)) nearest = point;
    }
    onSelect(nearest.id);
  }

  return <svg viewBox={`0 0 ${chart.width} ${chart.height}`} className="h-full w-full"
    role="img" tabIndex={0} aria-label={`${activeName} profit and loss progression. Use left and right arrow keys to inspect every point.`}
    onPointerMove={(event) => { if (event.pointerType === "mouse") selectAt(event); }}
    onPointerDown={selectAt} onPointerLeave={() => onSelect(null)}
    onKeyDown={(event) => {
      if (!chart.points.length || !["ArrowLeft", "ArrowRight", "Home", "End"].includes(event.key)) return;
      event.preventDefault();
      const current = chart.points.findIndex((point) => point.id === activePointId);
      const index = event.key === "Home" ? 0 : event.key === "End" ? chart.points.length - 1
        : Math.max(0, Math.min(chart.points.length - 1, (current < 0 ? chart.points.length - 1 : current) + (event.key === "ArrowLeft" ? -1 : 1)));
      onSelect(chart.points[index].id);
    }}>
    <line x1="0" x2={chart.width} y1={chart.zeroY} y2={chart.zeroY} stroke="rgba(148,163,184,0.20)" strokeDasharray="2 6" />
    {chart.bridgeX !== null && chart.archivePath ? <line x1={chart.bridgeX} x2={chart.bridgeX} y1="14" y2={chart.height - 16} stroke="rgba(148,163,184,0.16)" strokeDasharray="3 5" /> : null}
    {chart.archiveAreaPath ? <path d={chart.archiveAreaPath} fill="rgba(148,163,184,0.06)" /> : null}
    {chart.liveAreaPath ? <path d={chart.liveAreaPath} fill={fill} /> : null}
    {chart.archivePath ? <path d={chart.archivePath} fill="none" stroke="rgba(148,163,184,0.85)" strokeDasharray="6 5" strokeLinecap="round" strokeLinejoin="round" strokeWidth="2.25" /> : null}
    {chart.livePath ? <path d={chart.livePath} fill="none" stroke={stroke} strokeLinecap="round" strokeLinejoin="round" strokeWidth="3.25" /> : null}
    {chart.points.map((point, index) => {
      const active = activePointId === point.id;
      const archive = Boolean(point.isArchiveReconstruction);
      const live = !archive && !point.isOriginPoint;
      const archiveNodeEvery = Math.max(1, Math.ceil((point.archiveSteps ?? 56) / 4));
      const visible = active || point.isOriginPoint || (archive && (point.archiveStep ?? 0) % archiveNodeEvery === 0)
        || (live && (index === chart.points.length - 1 || (index - liveStart) % liveNodeEvery === 0));
      return visible ? <circle key={`${point.id}-${index}`} cx={point.x} cy={point.y}
        r={active ? 6 : live ? 3.5 : 3} fill={active ? "#fbbf24" : live ? stroke : "#0b1220"}
        stroke={active ? "rgba(251,191,36,0.45)" : live ? `${stroke}88` : "rgba(148,163,184,0.85)"}
        strokeWidth={active ? 6 : 1.5} /> : null;
    })}
    <rect width={chart.width} height={chart.height} fill="transparent" className="cursor-crosshair" />
  </svg>;
}

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

function buildPath(points: ChartPoint[]): string {
  if (points.length === 0) return "";
  return points.map((point, index) => `${index === 0 ? "M" : "L"} ${point.x.toFixed(1)} ${point.y.toFixed(1)}`).join(" ");
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

  const leadWidth = 0; // Aggregate balance is a single point, not a time series.
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
