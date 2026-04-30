type PenaltyBadgeProps = {
  role: string;
  size?: "mini" | "sm" | "md";
};

function roleTone(role: string) {
  const normalized = role.trim().toLowerCase();

  if (normalized.includes("primary")) {
    return {
      label: "Primary",
      className: "border-emerald-300/35 bg-emerald-400/15 text-emerald-100",
      strike: false,
    };
  }

  if (normalized.includes("secondary") || normalized.includes("set-piece")) {
    return {
      label: "Secondary",
      className: "border-slate-600 bg-slate-900/80 text-slate-200",
      strike: false,
    };
  }

  return {
    label: "No pens",
    className: "border-slate-700 bg-slate-900/55 text-slate-500",
    strike: true,
  };
}

export function PenaltyBadge({ role, size = "md" }: PenaltyBadgeProps) {
  const tone = roleTone(role);
  const mini = size === "mini";
  const compact = size === "sm" || mini;
  const label =
    mini && tone.label === "Primary"
      ? "1st"
      : mini && tone.label === "Secondary"
        ? "2nd"
        : mini && tone.label === "No pens"
          ? "No"
          : tone.label;

  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full border font-semibold ${
        mini ? "px-1.5 py-1 text-[10px]" : compact ? "px-2 py-1 text-[10px]" : "px-3 py-1.5 text-xs"
      } ${tone.className}`}
    >
      <span className={`relative inline-flex items-center justify-center ${mini ? "h-3 w-3" : "h-3.5 w-3.5"}`}>
        <span className="h-2 w-2 rounded-full border border-current" />
        {tone.strike ? (
          <span className="absolute h-px w-4 rotate-[-35deg] bg-current" />
        ) : null}
      </span>
      {label}
    </span>
  );
}
