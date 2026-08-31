type MarginScaleBarProps = {
  valuePct: number;
  medianTickPct: number | null;
  cheapest?: boolean;
};

export default function MarginScaleBar({
  valuePct,
  medianTickPct,
  cheapest = false,
}: MarginScaleBarProps) {
  return (
    <div className="relative h-1.5 w-full overflow-visible rounded-full bg-slate-800" aria-hidden="true">
      <div
        className={`h-full rounded-full motion-reduce:transition-none ${
          cheapest
            ? "bg-[linear-gradient(90deg,#10b981,#5eead4)] shadow-[0_0_14px_rgba(16,185,129,0.28)]"
            : "bg-[linear-gradient(90deg,#155e75,#22d3ee)]"
        }`}
        style={{ width: `${valuePct}%` }}
      />
      {medianTickPct !== null && (
        <span
          className="absolute top-1/2 h-3 w-px -translate-y-1/2 bg-white/65"
          style={{ left: `${medianTickPct}%` }}
        />
      )}
    </div>
  );
}
