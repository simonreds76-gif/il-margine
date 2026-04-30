type TierIndicatorProps = {
  tier: string;
  size?: "sm" | "md";
  variant?: "quality" | "outlook" | "weakness";
};

function tierLevel(tier: string) {
  const normalized = tier.trim().toLowerCase();

  if (["strong", "high", "very high"].includes(normalized)) return 4;
  if (["good", "positive"].includes(normalized)) return 3;
  if (["average", "medium"].includes(normalized)) return 2;
  return 1;
}

function fillClass(level: number, variant: TierIndicatorProps["variant"]) {
  if (variant === "weakness" && level >= 4) {
    return "bg-emerald-300 shadow-[0_0_10px_rgba(52,211,153,0.65)]";
  }

  if (variant === "weakness" && level >= 3) {
    return "bg-emerald-500/85";
  }

  if (variant === "outlook" && level >= 3) {
    return "bg-sky-300 shadow-[0_0_10px_rgba(125,211,252,0.45)]";
  }

  if (level >= 3) return "bg-cyan-300 shadow-[0_0_10px_rgba(34,211,238,0.45)]";
  if (level === 2) return "bg-cyan-500/60";
  return "bg-slate-500";
}

export function TierIndicator({
  tier,
  size = "md",
  variant = "quality",
}: TierIndicatorProps) {
  const level = tierLevel(tier);
  const segmentClass = size === "sm" ? "h-2 w-4" : "h-2.5 w-6";

  return (
    <div className="inline-flex items-center gap-1.5" aria-label={`${tier} tier`}>
      {[1, 2, 3, 4].map((segment) => (
        <span
          key={segment}
          className={`${segmentClass} rounded-full border ${
            segment <= level
              ? `${fillClass(level, variant)} border-white/15`
              : "border-slate-700/70 bg-slate-900"
          }`}
        />
      ))}
    </div>
  );
}
