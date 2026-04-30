type MiniDonutProps = {
  value: number;
  size?: number;
  showValue?: boolean;
  displayValue?: string;
  tone?: "emerald" | "cyan";
};

export function MiniDonut({
  value,
  size = 34,
  showValue = false,
  displayValue,
  tone = "emerald",
}: MiniDonutProps) {
  const radius = 14;
  const circumference = 2 * Math.PI * radius;
  const clamped = Math.max(0, Math.min(100, value));
  const stroke = tone === "cyan" ? "rgba(34,211,238,0.98)" : "rgba(52,211,153,0.98)";
  const textClass = tone === "cyan" ? "text-cyan-100" : "text-emerald-100";

  return (
    <span
      className="relative inline-flex items-center justify-center"
      style={{ height: size, width: size }}
      aria-label={`${clamped.toFixed(1)}%`}
    >
      <svg aria-hidden="true" className="h-full w-full" viewBox="0 0 40 40">
        <circle
          cx="20"
          cy="20"
          fill="none"
          r={radius}
          stroke="rgba(30,41,59,0.95)"
          strokeWidth="5"
        />
        <circle
          cx="20"
          cy="20"
          fill="none"
          r={radius}
          stroke={stroke}
          strokeLinecap="round"
          strokeWidth="5"
          strokeDasharray={`${(clamped / 100) * circumference} ${circumference}`}
          transform="rotate(-90 20 20)"
        />
      </svg>
      {showValue ? (
        <span className={`absolute font-mono text-[8px] font-black ${textClass}`}>
          {displayValue ?? Math.round(clamped)}
        </span>
      ) : null}
    </span>
  );
}
