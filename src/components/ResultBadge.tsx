"use client";

type ResultStatus = string | null | undefined;

const STATUS_STYLES: Record<string, string> = {
  won: "border-emerald-500/30 bg-emerald-500/10 text-emerald-300",
  lost: "border-red-500/30 bg-red-500/10 text-red-300",
  void: "border-slate-500/30 bg-slate-500/10 text-slate-300",
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
      className={`inline-flex items-center justify-center rounded-md border font-mono font-bold uppercase tracking-[0.04em] ${sizeClassName} ${
        STATUS_STYLES[normalized] ?? STATUS_STYLES.void
      } ${className}`}
    >
      {label}
    </span>
  );
}
