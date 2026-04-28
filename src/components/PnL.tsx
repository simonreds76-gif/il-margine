"use client";

interface PnLProps {
  value?: number | null;
  status?: string | null;
  className?: string;
}

export default function PnL({ value, status, className = "" }: PnLProps) {
  const isVoid = status === "void";
  const amount = isVoid ? 0 : Number(value ?? 0);
  const colour = isVoid ? "text-slate-400" : amount > 0 ? "text-emerald-400" : "text-red-400";
  const sign = amount > 0 ? "+" : "";
  const text = `${sign}${amount.toFixed(2)}u`;

  return (
    <span className={`font-mono text-sm font-semibold tabular-nums ${colour} ${className}`}>
      {text}
    </span>
  );
}
