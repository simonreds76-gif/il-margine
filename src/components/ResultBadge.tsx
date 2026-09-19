"use client";

type ResultStatus = string | null | undefined;

const STATUS_STYLES: Record<string, string> = {
  won: "border-emerald-500/30 bg-emerald-500/10 text-emerald-300",
  lost: "border-red-500/30 bg-red-500/10 text-red-300",
  void: "border-slate-500/30 bg-slate-500/10 text-slate-300",
  pending: "border-amber-400/30 bg-amber-400/10 text-amber-300",
};

interface ResultBadgeProps {
  status: ResultStatus;
  size?: "sm" | "md";
  className?: string;
}

export default function ResultBadge({ status, size = "md", className = "" }: ResultBadgeProps) {
  const normalized = (status ?? "void").toLowerCase();
  const label = normalized.toUpperCase();
  const sizeClassName =
    size === "sm"
      ? "min-w-[3.75rem] px-2 py-1 text-[10px]"
      : "min-w-[4rem] px-2.5 py-1.5 text-[11px]";

  return (
    <span
      className={`inline-flex items-center justify-center gap-1.5 whitespace-nowrap rounded-lg border font-semibold tracking-[0.02em] ${sizeClassName} ${
        STATUS_STYLES[normalized] ?? STATUS_STYLES.void
      } ${className}`}
    >
      <svg aria-hidden="true" focusable="false" viewBox="0 0 20 20" className="h-3.5 w-3.5 shrink-0" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
        <circle cx="10" cy="10" r="7.5" fill={normalized === "won" ? "currentColor" : "none"} />
        {normalized === "won" ? <path d="m6.5 10 2.3 2.3 4.7-5" stroke="#10271f" /> : normalized === "lost" ? <path d="m7.5 7.5 5 5m0-5-5 5" /> : normalized === "pending" ? <path d="M10 5.5V10l3 1.5" /> : <path d="M7 10h6" />}
      </svg>
      {label.charAt(0) + label.slice(1).toLowerCase()}
    </span>
  );
}
