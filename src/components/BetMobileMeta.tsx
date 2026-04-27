"use client";

import type { ReactNode } from "react";
import type { Bookmaker } from "@/lib/supabase";
import { formatOdds, formatStake } from "@/lib/format";
import BookmakerLogo from "@/components/BookmakerLogo";

interface BetMobileMetaProps {
  odds: number | string;
  bookmaker: Bookmaker | Bookmaker[] | null | undefined;
  stake: number | string;
  status?: string | null;
  profitLoss?: number | null;
  showProfit?: boolean;
}

function MetaBox({
  label,
  children,
  valueClassName = "text-slate-100",
}: {
  label: string;
  children: ReactNode;
  valueClassName?: string;
}) {
  return (
    <div className="rounded-xl border border-slate-800/70 bg-slate-950/35 px-3 py-2">
      <div className="mb-1 text-[10px] font-mono uppercase tracking-[0.16em] text-slate-500">{label}</div>
      <div className={`min-h-8 flex items-center text-sm font-semibold ${valueClassName}`}>
        {children}
      </div>
    </div>
  );
}

export default function BetMobileMeta({
  odds,
  bookmaker,
  stake,
  status,
  profitLoss,
  showProfit = false,
}: BetMobileMetaProps) {
  const isVoid = status === "void";
  const profit = Number(profitLoss ?? 0);
  const profitClassName = isVoid ? "text-slate-400" : profit > 0 ? "text-emerald-400" : "text-red-400";
  const profitText = isVoid ? "0.00u" : `${profit > 0 ? "+" : ""}${profit.toFixed(2)}u`;

  return (
    <div className={`mt-4 grid gap-2 ${showProfit ? "grid-cols-2" : "grid-cols-3"}`}>
      <MetaBox label="Odds">
        <span className="font-mono">{formatOdds(odds)}</span>
      </MetaBox>
      <MetaBox label="Book">
        <BookmakerLogo bookmaker={bookmaker} size="sm" stopPropagationOnClick noLink />
      </MetaBox>
      <MetaBox label="Stake">
        <span className="font-mono">{formatStake(stake)}u</span>
      </MetaBox>
      {showProfit ? (
        <MetaBox label="P/L" valueClassName={profitClassName}>
          <span className="font-mono">{profitText}</span>
        </MetaBox>
      ) : null}
    </div>
  );
}
