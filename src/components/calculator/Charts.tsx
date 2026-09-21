"use client";

import { useCallback, useMemo, useRef, useState } from "react";

/**
 * Shared SVG chart primitives for the calculator.
 * No chart library: plain SVG keeps the bundle small and the styling on-brand.
 */

export const CHART_INK = {
  mint: "#7df4c9",
  mintDeep: "#34a37b",
  grid: "rgba(255,255,255,0.07)",
  axis: "#93aab6",
  loss: "#f0968b",
  amber: "#eac77b",
  blue: "#6fb6d8",
  slate: "#93a7b5",
};

export const FRACTION_COLOURS: Record<string, string> = {
  "0.1x": "#6fb6d8",
  "0.25x": "#7df4c9",
  "0.5x": "#eac77b",
  "1x": "#f0968b",
};

interface Scale {
  x: (value: number) => number;
  y: (value: number) => number;
}

function buildScale(
  xDomain: [number, number],
  yDomain: [number, number],
  box: { left: number; right: number; top: number; bottom: number; width: number; height: number }
): Scale {
  const xSpan = xDomain[1] - xDomain[0] || 1;
  const ySpan = yDomain[1] - yDomain[0] || 1;
  const plotWidth = box.width - box.left - box.right;
  const plotHeight = box.height - box.top - box.bottom;
  return {
    x: (value) => box.left + ((value - xDomain[0]) / xSpan) * plotWidth,
    y: (value) => box.top + (1 - (value - yDomain[0]) / ySpan) * plotHeight,
  };
}

function path(points: Array<[number, number]>): string {
  return points
    .map(([x, y], index) => `${index === 0 ? "M" : "L"}${x.toFixed(1)},${y.toFixed(1)}`)
    .join(" ");
}

function niceTicks(min: number, max: number, count = 4): number[] {
  const span = max - min || 1;
  const step = Math.pow(10, Math.floor(Math.log10(span / count)));
  const candidates = [step, step * 2, step * 2.5, step * 5, step * 10];
  const chosen = candidates.find((value) => span / value <= count + 1) ?? step * 10;
  const start = Math.ceil(min / chosen) * chosen;
  const ticks: number[] = [];
  for (let value = start; value <= max + 1e-9; value += chosen) ticks.push(value);
  return ticks;
}

/** Readouts: exact pounds up to 100k, compact above. */
export function formatMoney(value: number, currency = "£"): string {
  const abs = Math.abs(value);
  const sign = value < 0 ? "-" : "";
  if (abs >= 1000000) return `${sign}${currency}${(abs / 1000000).toFixed(2)}m`;
  if (abs >= 100000) return `${sign}${currency}${(abs / 1000).toFixed(0)}k`;
  return `${sign}${currency}${Math.round(abs).toLocaleString("en-GB")}`;
}

/** Axis labels: short enough to sit in a 60px gutter. */
export function formatAxisMoney(value: number, currency = "£"): string {
  const abs = Math.abs(value);
  const sign = value < 0 ? "-" : "";
  if (abs >= 1000000) return `${sign}${currency}${(abs / 1000000).toFixed(1)}m`;
  if (abs >= 1000) {
    const k = abs / 1000;
    return `${sign}${currency}${k >= 100 ? k.toFixed(0) : k.toFixed(1)}k`;
  }
  return `${sign}${currency}${Math.round(abs)}`;
}

/** Ticks at 1, 2 and 5 times a power of ten, for log axes. */
function logTicks(minLog: number, maxLog: number): number[] {
  const ticks: number[] = [];
  const startExp = Math.floor(minLog);
  const endExp = Math.ceil(maxLog);
  for (let exp = startExp; exp <= endExp; exp += 1) {
    for (const multiple of [1, 2, 5]) {
      const value = Math.log10(multiple * Math.pow(10, exp));
      if (value >= minLog && value <= maxLog) ticks.push(value);
    }
  }
  return ticks.length >= 2 ? ticks : [minLog, maxLog];
}

/* ------------------------------------------------------------------ */
/* Fan chart: percentile bands around a median path                    */
/* ------------------------------------------------------------------ */

export interface FanChartProps {
  x: number[];
  p05: number[];
  p25: number[];
  p50: number[];
  p75: number[];
  p95: number[];
  expected?: number[];
  startValue: number;
  currency?: string;
  xLabel?: string;
  ariaLabel: string;
}

export function FanChart({
  x,
  p05,
  p25,
  p50,
  p75,
  p95,
  expected,
  startValue,
  currency = "£",
  xLabel = "settled bets",
  ariaLabel,
}: FanChartProps) {
  const width = 640;
  const height = 300;
  const box = { left: 62, right: 18, top: 18, bottom: 34, width, height };
  const [hover, setHover] = useState<number | null>(null);
  const svgRef = useRef<SVGSVGElement | null>(null);

  const { scale, ticks } = useMemo(() => {
    const values = [...p05, ...p95, startValue, ...(expected ?? [])];
    const min = Math.min(...values);
    const max = Math.max(...values);
    const pad = (max - min) * 0.08 || 1;
    const yDomain: [number, number] = [min - pad, max + pad];
    return {
      scale: buildScale([x[0], x[x.length - 1]], yDomain, box),
      ticks: niceTicks(yDomain[0], yDomain[1], 4),
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [x, p05, p95, expected, startValue]);

  const bandArea = useCallback(
    (lower: number[], upper: number[]) =>
      `${path(upper.map((value, i) => [scale.x(x[i]), scale.y(value)]))} L${scale
        .x(x[x.length - 1])
        .toFixed(1)},${scale.y(lower[lower.length - 1]).toFixed(1)} ${lower
        .slice(0, -1)
        .reverse()
        .map((value, i) => {
          const index = lower.length - 2 - i;
          return `L${scale.x(x[index]).toFixed(1)},${scale.y(value).toFixed(1)}`;
        })
        .join(" ")} Z`,
    [scale, x]
  );

  const onMove = (event: React.PointerEvent<SVGSVGElement>) => {
    const svg = svgRef.current;
    if (!svg) return;
    const rect = svg.getBoundingClientRect();
    const ratio = (event.clientX - rect.left) / rect.width;
    const plotStart = box.left / width;
    const plotEnd = (width - box.right) / width;
    const clamped = Math.min(Math.max((ratio - plotStart) / (plotEnd - plotStart), 0), 1);
    setHover(Math.round(clamped * (x.length - 1)));
  };

  const index = hover ?? x.length - 1;

  return (
    <figure className="calc-chart">
      <svg
        ref={svgRef}
        viewBox={`0 0 ${width} ${height}`}
        role="img"
        aria-label={ariaLabel}
        onPointerMove={onMove}
        onPointerLeave={() => setHover(null)}
      >
        <defs>
          <linearGradient id="calc-fan-outer" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="#57d196" stopOpacity="0.20" />
            <stop offset="100%" stopColor="#57d196" stopOpacity="0.04" />
          </linearGradient>
        </defs>

        {ticks.map((tick) => (
          <g key={tick}>
            <line x1={box.left} x2={width - box.right} y1={scale.y(tick)} y2={scale.y(tick)} stroke={CHART_INK.grid} />
            <text x={box.left - 10} y={scale.y(tick) + 4} textAnchor="end" fontSize="11" fill={CHART_INK.axis}>
              {formatAxisMoney(tick, currency)}
            </text>
          </g>
        ))}

        <path d={bandArea(p05, p95)} fill="url(#calc-fan-outer)" />
        <path d={bandArea(p25, p75)} fill="#57d19626" />

        <line
          x1={box.left}
          x2={width - box.right}
          y1={scale.y(startValue)}
          y2={scale.y(startValue)}
          stroke="#ffffff33"
          strokeDasharray="4 6"
        />

        {expected ? (
          <path
            d={path(expected.map((value, i) => [scale.x(x[i]), scale.y(value)]))}
            fill="none"
            stroke={CHART_INK.amber}
            strokeWidth="1.5"
            strokeDasharray="5 4"
            opacity="0.75"
          />
        ) : null}

        <path
          d={path(p50.map((value, i) => [scale.x(x[i]), scale.y(value)]))}
          fill="none"
          stroke={CHART_INK.mint}
          strokeWidth="2.6"
          strokeLinejoin="round"
        />

        <g>
          <line
            x1={scale.x(x[index])}
            x2={scale.x(x[index])}
            y1={box.top}
            y2={height - box.bottom}
            stroke="#ffffff30"
          />
          <circle cx={scale.x(x[index])} cy={scale.y(p50[index])} r="5" fill={CHART_INK.mint} stroke="#0c1620" strokeWidth="2" />
          <circle cx={scale.x(x[index])} cy={scale.y(p95[index])} r="3" fill="#57d19688" />
          <circle cx={scale.x(x[index])} cy={scale.y(p05[index])} r="3" fill="#57d19688" />
        </g>

        <text x={box.left} y={height - 8} fontSize="11" fill={CHART_INK.axis}>
          0
        </text>
        <text x={(box.left + width - box.right) / 2} y={height - 8} fontSize="11" fill={CHART_INK.axis} textAnchor="middle">
          {xLabel}
        </text>
        <text x={width - box.right} y={height - 8} fontSize="11" fill={CHART_INK.axis} textAnchor="end">
          {x[x.length - 1].toLocaleString("en-GB")}
        </text>
      </svg>

      <figcaption className="calc-chart-readout" aria-live="polite">
        <span>
          After <strong>{x[index].toLocaleString("en-GB")}</strong> bets
        </span>
        <span>
          Typical <strong className="gain">{formatMoney(p50[index], currency)}</strong>
        </span>
        <span>
          Middle half <strong>{formatMoney(p25[index], currency)} to {formatMoney(p75[index], currency)}</strong>
        </span>
        <span>
          Outer range <strong>{formatMoney(p05[index], currency)} to {formatMoney(p95[index], currency)}</strong>
        </span>
      </figcaption>
    </figure>
  );
}

/* ------------------------------------------------------------------ */
/* Multi-line chart with one highlighted band                          */
/* ------------------------------------------------------------------ */

export interface SeriesLine {
  label: string;
  colour: string;
  values: number[];
  active: boolean;
  band?: { lo: number[]; hi: number[] };
}

export function MultiLineChart({
  x,
  series,
  baseline,
  currency = "£",
  xLabel = "bets",
  ariaLabel,
  logScale = false,
}: {
  x: number[];
  series: SeriesLine[];
  baseline: number;
  currency?: string;
  xLabel?: string;
  ariaLabel: string;
  logScale?: boolean;
}) {
  const width = 640;
  const height = 300;
  const box = { left: 62, right: 18, top: 18, bottom: 34, width, height };
  const svgRef = useRef<SVGSVGElement | null>(null);
  const [hover, setHover] = useState<number | null>(null);

  const transform = (value: number) => (logScale ? Math.log10(Math.max(value, 1)) : value);

  const { scale, ticks } = useMemo(() => {
    const active = series.find((line) => line.active);
    const values = [
      ...series.flatMap((line) => line.values),
      ...(active?.band ? [...active.band.lo, ...active.band.hi] : []),
      baseline,
    ].map(transform);
    const min = Math.min(...values);
    const max = Math.max(...values);
    const pad = (max - min) * 0.1 || 1;
    const yDomain: [number, number] = [min - pad, max + pad];
    const rawTicks = logScale ? logTicks(yDomain[0], yDomain[1]) : niceTicks(yDomain[0], yDomain[1], 4);
    return { scale: buildScale([x[0], x[x.length - 1]], yDomain, box), ticks: rawTicks };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [x, series, baseline, logScale]);

  const onMove = (event: React.PointerEvent<SVGSVGElement>) => {
    const svg = svgRef.current;
    if (!svg) return;
    const rect = svg.getBoundingClientRect();
    const ratio = (event.clientX - rect.left) / rect.width;
    const plotStart = box.left / width;
    const plotEnd = (width - box.right) / width;
    const clamped = Math.min(Math.max((ratio - plotStart) / (plotEnd - plotStart), 0), 1);
    setHover(Math.round(clamped * (x.length - 1)));
  };

  const index = hover ?? x.length - 1;
  const active = series.find((line) => line.active);

  return (
    <figure className="calc-chart">
      <svg
        ref={svgRef}
        viewBox={`0 0 ${width} ${height}`}
        role="img"
        aria-label={ariaLabel}
        onPointerMove={onMove}
        onPointerLeave={() => setHover(null)}
      >
        {ticks.map((tick) => (
          <g key={tick}>
            <line x1={box.left} x2={width - box.right} y1={scale.y(tick)} y2={scale.y(tick)} stroke={CHART_INK.grid} />
            <text x={box.left - 10} y={scale.y(tick) + 4} textAnchor="end" fontSize="11" fill={CHART_INK.axis}>
              {formatAxisMoney(logScale ? Math.pow(10, tick) : tick, currency)}
            </text>
          </g>
        ))}

        <line
          x1={box.left}
          x2={width - box.right}
          y1={scale.y(transform(baseline))}
          y2={scale.y(transform(baseline))}
          stroke="#ffffff33"
          strokeDasharray="4 6"
        />

        {active?.band ? (
          <path
            d={`${path(active.band.hi.map((value, i) => [scale.x(x[i]), scale.y(transform(value))]))} ${active.band.lo
              .map((value, i) => [x.length - 1 - i, value] as [number, number])
              .map(([idx, value]) => `L${scale.x(x[idx]).toFixed(1)},${scale.y(transform(value)).toFixed(1)}`)
              .reverse()
              .join(" ")} Z`}
            fill={`${active.colour}1f`}
          />
        ) : null}

        {series.map((line) => (
          <path
            key={line.label}
            d={path(line.values.map((value, i) => [scale.x(x[i]), scale.y(transform(value))]))}
            fill="none"
            stroke={line.colour}
            strokeWidth={line.active ? 2.8 : 1.4}
            opacity={line.active ? 1 : 0.4}
            strokeLinejoin="round"
          />
        ))}

        <line x1={scale.x(x[index])} x2={scale.x(x[index])} y1={box.top} y2={height - box.bottom} stroke="#ffffff30" />
        {series.map((line) => (
          <circle
            key={`dot-${line.label}`}
            cx={scale.x(x[index])}
            cy={scale.y(transform(line.values[index]))}
            r={line.active ? 5 : 2.5}
            fill={line.colour}
            opacity={line.active ? 1 : 0.5}
          />
        ))}

        <text x={(box.left + width - box.right) / 2} y={height - 8} fontSize="11" fill={CHART_INK.axis} textAnchor="middle">
          {xLabel}
        </text>
      </svg>

      <figcaption className="calc-chart-readout" aria-live="polite">
        <span>
          After <strong>{x[index].toLocaleString("en-GB")}</strong> bets
        </span>
        {series.map((line) => (
          <span key={`read-${line.label}`} style={{ opacity: line.active ? 1 : 0.55 }}>
            {line.label} <strong style={{ color: line.colour }}>{formatMoney(line.values[index], currency)}</strong>
          </span>
        ))}
      </figcaption>
    </figure>
  );
}

/* ------------------------------------------------------------------ */
/* Growth rate curve                                                   */
/* ------------------------------------------------------------------ */

export function GrowthCurve({
  points,
  markers,
  ariaLabel,
}: {
  points: Array<{ f: number; g: number }>;
  markers: Array<{ f: number; g: number; label: string; colour: string; active: boolean }>;
  ariaLabel: string;
}) {
  const width = 640;
  const height = 240;
  const box = { left: 58, right: 18, top: 18, bottom: 36, width, height };
  const gValues = points.map((point) => point.g);
  const min = Math.min(...gValues, 0);
  const max = Math.max(...gValues, 0);
  const pad = (max - min) * 0.15 || 0.001;
  const scale = buildScale(
    [points[0].f, points[points.length - 1].f],
    [min - pad, max + pad],
    box
  );
  const ticks = niceTicks(min - pad, max + pad, 4);

  return (
    <figure className="calc-chart">
      <svg viewBox={`0 0 ${width} ${height}`} role="img" aria-label={ariaLabel}>
        <defs>
          <linearGradient id="calc-growth" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="#57d196" stopOpacity="0.22" />
            <stop offset="100%" stopColor="#57d196" stopOpacity="0" />
          </linearGradient>
        </defs>
        {ticks.map((tick) => (
          <g key={tick}>
            <line x1={box.left} x2={width - box.right} y1={scale.y(tick)} y2={scale.y(tick)} stroke={CHART_INK.grid} />
            <text x={box.left - 10} y={scale.y(tick) + 4} textAnchor="end" fontSize="11" fill={CHART_INK.axis}>
              {(tick * 100).toFixed(2)}%
            </text>
          </g>
        ))}
        <line x1={box.left} x2={width - box.right} y1={scale.y(0)} y2={scale.y(0)} stroke="#ffffff40" strokeDasharray="4 5" />
        <path
          d={`${path(points.map((point) => [scale.x(point.f), scale.y(point.g)]))} L${scale
            .x(points[points.length - 1].f)
            .toFixed(1)},${scale.y(0).toFixed(1)} L${scale.x(points[0].f).toFixed(1)},${scale.y(0).toFixed(1)} Z`}
          fill="url(#calc-growth)"
        />
        <path
          d={path(points.map((point) => [scale.x(point.f), scale.y(point.g)]))}
          fill="none"
          stroke={CHART_INK.mint}
          strokeWidth="2.4"
        />
        {markers.map((marker) => (
          <g key={marker.label}>
            <line
              x1={scale.x(marker.f)}
              x2={scale.x(marker.f)}
              y1={scale.y(marker.g)}
              y2={scale.y(0)}
              stroke={marker.colour}
              strokeOpacity={marker.active ? 0.65 : 0.25}
              strokeDasharray="3 4"
            />
            <circle
              cx={scale.x(marker.f)}
              cy={scale.y(marker.g)}
              r={marker.active ? 6 : 4}
              fill={marker.colour}
              stroke="#0c1620"
              strokeWidth="2"
              opacity={marker.active ? 1 : 0.6}
            />
            <text
              x={scale.x(marker.f)}
              y={scale.y(marker.g) - 12}
              fontSize="11"
              fontWeight="600"
              textAnchor="middle"
              fill={marker.colour}
              opacity={marker.active ? 1 : 0.7}
            >
              {marker.label}
            </text>
          </g>
        ))}
        <text x={(box.left + width - box.right) / 2} y={height - 8} fontSize="11" fill={CHART_INK.axis} textAnchor="middle">
          stake as a multiple of full Kelly
        </text>
        <text x={box.left} y={height - 8} fontSize="11" fill={CHART_INK.axis}>
          0x
        </text>
        <text x={width - box.right} y={height - 8} fontSize="11" fill={CHART_INK.axis} textAnchor="end">
          {points[points.length - 1].f.toFixed(1)}x
        </text>
      </svg>
    </figure>
  );
}

/* ------------------------------------------------------------------ */
/* Percentile range bars                                               */
/* ------------------------------------------------------------------ */

export function RangeBars({
  rows,
  baseline,
  currency = "£",
}: {
  rows: Array<{ label: string; colour: string; lo: number; mid: number; hi: number; active: boolean }>;
  baseline: number;
  currency?: string;
}) {
  const rawMin = Math.min(...rows.map((row) => row.lo), baseline);
  const rawMax = Math.max(...rows.map((row) => row.hi), baseline);
  // Compounded outcomes span orders of magnitude, so switch to log spacing
  // once the widest bar would otherwise collapse into a sliver.
  const useLog = rawMin > 0 && rawMax / rawMin > 12;
  const project = (value: number) => (useLog ? Math.log10(Math.max(value, 1)) : value);
  const min = project(rawMin);
  const max = project(rawMax);
  const span = max - min || 1;
  const position = (value: number) => ((project(value) - min) / span) * 100;

  return (
    <div className="calc-range">
      {rows.map((row) => (
        <div key={row.label} className={`calc-range-row${row.active ? " is-active" : ""}`}>
          <span className="calc-range-label" style={{ color: row.colour }}>
            {row.label}
          </span>
          <div className="calc-range-track">
            <span
              className="calc-range-baseline"
              style={{ left: `${position(baseline)}%` }}
              aria-hidden="true"
            />
            <span
              className="calc-range-span"
              style={{
                left: `${position(row.lo)}%`,
                width: `${Math.max(position(row.hi) - position(row.lo), 1)}%`,
                background: `linear-gradient(90deg, ${row.colour}33, ${row.colour}aa)`,
              }}
            />
            <span
              className="calc-range-median"
              style={{ left: `${position(row.mid)}%`, background: row.colour }}
            />
          </div>
          <span className="calc-range-value">{formatMoney(row.mid, currency)}</span>
        </div>
      ))}
      <p className="calc-range-key">
        Bar covers the 5th to 95th outcome out of 400 simulated runs. The tick is the typical run, the
        dotted mark is where you started.{useLog ? " Spacing is logarithmic." : ""}
      </p>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* Margin bar                                                          */
/* ------------------------------------------------------------------ */

export function MarginBar({
  segments,
  marginPct,
}: {
  segments: Array<{ label: string; fairPct: number; marginPct: number; colour: string }>;
  marginPct: number;
}) {
  const total = segments.reduce((sum, segment) => sum + segment.fairPct + segment.marginPct, 0) || 100;
  return (
    <div className="calc-margin-bar" role="img" aria-label={`Book total ${total.toFixed(2)} percent, of which ${marginPct.toFixed(2)} percent is margin.`}>
      {segments.map((segment) => (
        <span
          key={segment.label}
          className="calc-margin-fair"
          style={{ width: `${(segment.fairPct / total) * 100}%`, background: segment.colour }}
        >
          <em>{segment.label}</em>
          <strong>{segment.fairPct.toFixed(1)}%</strong>
        </span>
      ))}
      <span className="calc-margin-vig" style={{ width: `${(marginPct / total) * 100}%` }}>
        <strong>{marginPct.toFixed(2)}%</strong>
      </span>
    </div>
  );
}
