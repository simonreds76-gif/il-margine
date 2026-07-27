type SampleSizeBadgeProps = {
  settled: number;
  compact?: boolean;
  className?: string;
};

export function sampleSizeLabel(settled: number, compact = false): string {
  if (settled <= 0) return "No settled bets";
  if (settled < 25) return compact ? "Early sample" : `Early sample · ${settled} bets`;
  if (settled < 50) return compact ? "Small sample" : `Small sample · ${settled} bets`;
  return compact ? "Established" : `Established record · ${settled} bets`;
}

export default function SampleSizeBadge({
  settled,
  compact = false,
  className = "",
}: SampleSizeBadgeProps) {
  const isEmpty = settled <= 0;
  const isEarly = settled > 0 && settled < 25;
  const isSmall = settled >= 25 && settled < 50;
  const tone = isEmpty
    ? "border-slate-700/70 bg-slate-900/70 text-slate-500"
    : isEarly
      ? "border-amber-400/25 bg-amber-400/10 text-amber-200"
      : isSmall
        ? "border-sky-400/20 bg-sky-400/10 text-sky-200/80"
        : "border-emerald-400/20 bg-emerald-400/[0.07] text-emerald-200/75";

  return (
    <span
      className={`inline-flex items-center rounded-full border font-mono font-semibold uppercase ${
        compact ? "px-2 py-0.5 text-[8px] tracking-[0.08em]" : "px-3 py-1.5 text-[10px] tracking-[0.12em]"
      } ${tone} ${className}`}
    >
      {sampleSizeLabel(settled, compact)}
    </span>
  );
}
