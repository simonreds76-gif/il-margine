"use client";

import type { ReactNode } from "react";
import type { Bookmaker } from "@/lib/supabase";
import { formatOdds, formatStake } from "@/lib/format";
import BookmakerLogo from "@/components/BookmakerLogo";
import PnL from "@/components/PnL";

interface BetMobileMetaProps {
  odds: number | string;
  bookmaker: Bookmaker | Bookmaker[] | null | undefined;
  stake: number | string;
  status?: string | null;
  profitLoss?: number | null;
  showProfit?: boolean;
  tipsLayout?: boolean;
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
  tipsLayout = false,
}: BetMobileMetaProps) {
  const isVoid = status === "void";
  const profit = Number(profitLoss ?? 0);
  const profitClassName = isVoid ? "text-slate-400" : profit > 0 ? "text-emerald-400" : "text-red-400";

  if (tipsLayout) return <div className="mt-3">
    <div className="grid grid-cols-3 divide-x divide-slate-700/60 rounded-lg bg-slate-950/60 py-2.5">
      <div className="min-w-0 px-2.5"><div className="text-[9px] uppercase tracking-wider text-slate-400">Odds</div><div className="mt-1 flex h-8 items-center font-mono text-sm font-semibold text-slate-100">{formatOdds(odds)}</div></div>
      <div className="min-w-0 px-2.5"><div className="text-[9px] uppercase tracking-wider text-slate-400">Stake</div><div className="mt-1 flex h-8 items-center font-mono text-sm font-semibold text-slate-100">{formatStake(stake)}u</div></div>
      <div className="min-w-0 px-2"><div className="text-[9px] uppercase tracking-wider text-slate-400">Bookmaker</div><div className="mt-1 flex h-8 items-center [&>div]:max-w-full [&>div>div]:max-w-full"><BookmakerLogo bookmaker={bookmaker} size="sm" noLink /></div></div>
    </div>
    {showProfit ? <div className="mt-3 flex items-center justify-between gap-3 text-xs"><span className="text-slate-400">Profit / loss</span><span className={`font-mono text-sm font-semibold ${isVoid || profit === 0 ? "text-slate-300" : profit > 0 ? "text-emerald-300" : "text-rose-300"}`}><PnL value={profitLoss} status={status} /></span></div> : null}
  </div>;

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
          <PnL value={profitLoss} status={status} />
        </MetaBox>
      ) : null}
    </div>
  );
}
