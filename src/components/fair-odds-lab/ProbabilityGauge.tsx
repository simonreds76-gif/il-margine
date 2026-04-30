type ProbabilityGaugeProps = {
  modelProb: number;
  marketProb: number;
  gapPp: number;
};

function arcStyle(percent: number, circumference: number) {
  return {
    strokeDasharray: `${(Math.max(0, Math.min(100, percent)) / 100) * circumference} ${circumference}`,
  };
}

function segmentArcStyle(start: number, end: number, circumference: number) {
  const safeStart = Math.max(0, Math.min(100, start));
  const safeEnd = Math.max(0, Math.min(100, end));
  const length = Math.max(0, safeEnd - safeStart);

  return {
    strokeDasharray: `${(length / 100) * circumference} ${circumference}`,
    strokeDashoffset: `${-(safeStart / 100) * circumference}`,
  };
}

export function ProbabilityGauge({ modelProb, marketProb, gapPp }: ProbabilityGaugeProps) {
  const radius = 78;
  const gapRadius = 68;
  const innerRadius = 56;
  const circumference = 2 * Math.PI * radius;
  const gapCircumference = 2 * Math.PI * gapRadius;
  const innerCircumference = 2 * Math.PI * innerRadius;
  const gapStart = Math.min(modelProb, marketProb);
  const gapEnd = Math.max(modelProb, marketProb);

  return (
    <div className="rounded-[1.75rem] border border-slate-700/55 bg-slate-950/70 p-6 text-center">
      <div className="text-[10px] font-semibold uppercase tracking-[0.22em] text-slate-500">
        Probability gauge
      </div>
      <svg className="mx-auto mt-3 h-64 w-64" viewBox="0 0 200 200" aria-hidden="true">
        <circle
          cx="100"
          cy="100"
          fill="none"
          r={radius}
          stroke="rgba(51,65,85,0.78)"
          strokeWidth="13"
        />
        <circle
          cx="100"
          cy="100"
          fill="none"
          r={radius}
          stroke="rgba(148,163,184,0.9)"
          strokeLinecap="round"
          strokeWidth="13"
          style={arcStyle(marketProb, circumference)}
          transform="rotate(-90 100 100)"
        />
        <circle
          cx="100"
          cy="100"
          fill="none"
          r={gapRadius}
          stroke="rgba(251,191,36,0.96)"
          strokeLinecap="round"
          strokeWidth="12"
          style={segmentArcStyle(gapStart, gapEnd, gapCircumference)}
          transform="rotate(-90 100 100)"
        />
        <circle
          cx="100"
          cy="100"
          fill="none"
          r={innerRadius}
          stroke="rgba(6,78,59,0.85)"
          strokeWidth="15"
        />
        <circle
          cx="100"
          cy="100"
          fill="none"
          r={innerRadius}
          stroke="rgba(52,211,153,0.98)"
          strokeLinecap="round"
          strokeWidth="15"
          style={arcStyle(modelProb, innerCircumference)}
          transform="rotate(-90 100 100)"
        />
        <text
          x="100"
          y="94"
          fill="#fbbf24"
          fontFamily="ui-monospace, SFMono-Regular, Menlo, monospace"
          fontSize="26"
          fontWeight="900"
          textAnchor="middle"
        >
          +{gapPp.toFixed(1)}
        </text>
      </svg>
      <div className="-mt-4 text-xs font-medium text-slate-400">
        Model {modelProb.toFixed(1)}% vs Market {marketProb.toFixed(1)}%
      </div>
      <div className="grid grid-cols-2 gap-3 text-sm">
        <div className="rounded-xl border border-emerald-400/20 bg-emerald-400/[0.07] px-3 py-2">
          <div className="text-[10px] uppercase tracking-[0.16em] text-emerald-300">
            Model
          </div>
          <div className="mt-1 font-mono font-bold text-emerald-100">
            {modelProb.toFixed(1)}%
          </div>
        </div>
        <div className="rounded-xl border border-slate-700/65 bg-slate-900/75 px-3 py-2">
          <div className="text-[10px] uppercase tracking-[0.16em] text-slate-500">
            Market
          </div>
          <div className="mt-1 font-mono font-bold text-slate-100">
            {marketProb.toFixed(1)}%
          </div>
        </div>
      </div>
    </div>
  );
}
