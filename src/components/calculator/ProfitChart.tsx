"use client";

/** Lightweight SVG line chart: profit (units) vs total stake (units) for a given ROI. */
export default function ProfitChart({
  roi,
  maxStake = 200,
  steps = 5,
  className = "",
}: {
  roi: number;
  maxStake?: number;
  steps?: number;
  className?: string;
}) {
  const points: { stake: number; profit: number }[] = [];
  for (let i = 0; i <= steps; i++) {
    const stake = (i / steps) * maxStake;
    const profit = stake * (roi / 100);
    points.push({ stake, profit });
  }

  const width = 280;
  const height = 140;
  const padding = { top: 12, right: 12, bottom: 24, left: 44 };
  const innerWidth = width - padding.left - padding.right;
  const innerHeight = height - padding.top - padding.bottom;

  const maxProfit = Math.max(...points.map((p) => p.profit), 1);
  const minProfit = Math.min(...points.map((p) => p.profit), 0);

  const x = (stake: number) => padding.left + (stake / maxStake) * innerWidth;
  const y = (profit: number) => {
    const range = maxProfit - minProfit || 1;
    return padding.top + innerHeight - ((profit - minProfit) / range) * innerHeight;
  };

  const pathD = points
    .map((p, i) => `${i === 0 ? "M" : "L"} ${x(p.stake)} ${y(p.profit)}`)
    .join(" ");

  return (
    <figure className={className}>
      <figcaption className="text-xs font-mono text-slate-500 uppercase tracking-wider mb-2">
        Profit vs total stake (at {roi >= 0 ? "+" : ""}{roi.toFixed(1)}% ROI)
      </figcaption>
      <svg
        viewBox={`0 0 ${width} ${height}`}
        className="w-full max-w-[280px] h-auto text-slate-700"
        aria-hidden
      >
        <line
          x1={padding.left}
          y1={padding.top}
          x2={padding.left}
          y2={padding.top + innerHeight}
          stroke="currentColor"
          strokeWidth="1"
          opacity={0.3}
        />
        <line
          x1={padding.left}
          y1={padding.top + innerHeight}
          x2={padding.left + innerWidth}
          y2={padding.top + innerHeight}
          stroke="currentColor"
          strokeWidth="1"
          opacity={0.3}
        />
        <path
          d={pathD}
          fill="none"
          stroke="rgb(52 211 153)"
          strokeWidth="2"
          strokeLinecap="round"
          strokeLinejoin="round"
        />
        {points.map((p, i) => (
          <circle
            key={i}
            cx={x(p.stake)}
            cy={y(p.profit)}
            r={i === 0 || i === points.length - 1 ? 3 : 2}
            fill="rgb(52 211 153)"
            opacity={0.9}
          />
        ))}
      </svg>
    </figure>
  );
}
