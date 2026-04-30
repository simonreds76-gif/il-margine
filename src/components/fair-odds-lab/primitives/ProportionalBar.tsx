type ProportionalBarProps = {
  value: number;
  maxValue?: number;
  label?: string;
};

export function ProportionalBar({
  value,
  maxValue = 100,
  label,
}: ProportionalBarProps) {
  const percentage = Math.max(0, Math.min(100, (value / maxValue) * 100));

  return (
    <div className="w-full min-w-[120px]">
      <div className="h-1.5 overflow-hidden rounded-full bg-slate-800">
        <div
          className="h-full rounded-full bg-cyan-300 shadow-[0_0_10px_rgba(34,211,238,0.35)]"
          style={{ width: `${percentage}%` }}
        />
      </div>
      <div className="mt-1 flex justify-between text-[9px] font-medium uppercase tracking-[0.12em] text-slate-600">
        <span>0</span>
        <span>{label ?? `${maxValue}% cap`}</span>
      </div>
    </div>
  );
}
