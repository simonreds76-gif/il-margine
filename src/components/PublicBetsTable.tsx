"use client";

import Link from "next/link";
import { type Bet, type Bookmaker } from "@/lib/supabase";
import BookmakerLogo from "@/components/BookmakerLogo";
import MarketBadge from "@/components/MarketBadge";
import PnL from "@/components/PnL";
import ResultBadge from "@/components/ResultBadge";
import { formatMatchDate, formatOdds, formatStake } from "@/lib/format";
import { publicTipPath } from "@/lib/tip-seo";

type PublicBet = Bet & {
  bookmaker?: Bookmaker | Bookmaker[] | null;
};

type PublicBetsTableMode = "pending" | "settled";

interface PublicBetsTableProps {
  bets: PublicBet[];
  mode: PublicBetsTableMode;
  playerHeader?: string;
}

const th = {
  icon: "w-[2.75rem] px-1.5 py-3 text-center md:w-[3.75rem] md:px-2.5",
  date: "w-[5.25rem] px-2.5 py-3 text-center",
  match: "w-[25%] px-4 py-3 text-center",
  player: "w-[15%] px-4 py-3 text-center",
  selection: "w-[18%] px-4 py-3 text-center",
  odds: "w-[5.5rem] border-l border-slate-800/50 px-4 py-3 text-center",
  bookmaker: "w-32 px-4 py-3 text-center",
  stake: "w-[5.5rem] border-l border-slate-800/50 px-4 py-3 text-center",
  stakeLast: "w-[5.5rem] px-4 py-3 text-center",
  status: "w-24 border-l border-slate-800/50 px-3 py-3 text-center",
  pnl: "w-24 px-4 py-3 text-center",
} as const;

const td = {
  icon: "px-1.5 py-3.5 text-center align-middle md:px-2.5",
  date: "px-2.5 py-3.5 text-center align-middle text-sm whitespace-nowrap text-slate-400",
  match: "px-4 py-3.5 text-center align-middle font-medium text-slate-200",
  player: "px-4 py-3.5 text-center align-middle text-slate-300",
  selection: "px-4 py-3.5 text-center align-middle text-slate-300",
  odds: "border-l border-slate-800/50 px-4 py-3.5 text-center align-middle",
  bookmaker: "px-4 py-3.5 align-middle text-center",
  stake: "border-l border-slate-800/50 px-4 py-3.5 text-center align-middle font-mono tabular-nums text-slate-200",
  stakeLast: "px-4 py-3.5 text-center align-middle font-mono tabular-nums text-slate-200",
  status: "border-l border-slate-800/50 px-2.5 py-3.5 align-middle text-center",
  pnl: "px-4 py-3.5 text-center align-middle",
} as const;

export default function PublicBetsTable({
  bets,
  mode,
  playerHeader = "Player",
}: PublicBetsTableProps) {
  const isSettled = mode === "settled";

  return (
    <table
      className={`w-full table-fixed border-collapse text-sm ${
        isSettled ? "min-w-[1180px]" : "min-w-[1100px]"
      }`}
    >
      <thead>
        <tr className="border-b border-slate-800/40 bg-slate-950/40 text-[11px] uppercase tracking-[0.08em] text-slate-500">
          <th className={th.icon}></th>
          <th className={th.date}>Date</th>
          <th className={th.match}>Match</th>
          <th className={th.player}>{playerHeader}</th>
          <th className={th.selection}>Selection</th>
          <th className={th.odds}>Odds</th>
          <th className={th.bookmaker}>Bookmaker</th>
          <th className={isSettled ? th.stake : th.stakeLast}>Stake</th>
          {isSettled ? (
            <>
              <th className={th.status}>Result</th>
              <th className={th.pnl}>P/L</th>
            </>
          ) : null}
        </tr>
      </thead>
      <tbody>
        {bets.map((bet) => (
          <tr key={bet.id} className="border-b border-slate-800/40 even:bg-slate-950/[0.18] last:border-b-0 hover:bg-slate-800/20">
            <td className={td.icon}>
              <div className="flex justify-center">
                <MarketBadge market={bet.market} category={bet.category} event={bet.event} compact className="md:hidden" />
                <MarketBadge market={bet.market} category={bet.category} event={bet.event} className="hidden md:inline-flex" />
              </div>
            </td>
            <td className={td.date}>{formatMatchDate(bet.match_date)}</td>
            <td className={td.match}>
              <Link
                href={publicTipPath(bet)}
                className="block min-w-0 transition-colors hover:text-emerald-400"
                title={bet.event}
              >
                <span className="min-w-0 truncate">{bet.event}</span>
              </Link>
            </td>
            <td className={td.player}>
              <span className="block truncate">{bet.player || "-"}</span>
            </td>
            <td className={td.selection}>
              <span className="block whitespace-normal break-words text-center leading-snug" title={bet.selection}>
                {bet.selection}
              </span>
            </td>
            <td className={td.odds}>
              <span className="font-mono tabular-nums text-slate-200">{formatOdds(bet.odds)}</span>
            </td>
            <td className={td.bookmaker}>
              <div className="flex justify-center">
                <BookmakerLogo bookmaker={bet.bookmaker} size="sm" />
              </div>
            </td>
            <td className={isSettled ? td.stake : td.stakeLast}>
              {formatStake(bet.stake)}u
            </td>
            {isSettled ? (
              <>
                <td className={td.status}>
                  <ResultBadge status={bet.status} />
                </td>
                <td className={td.pnl}>
                  <PnL value={bet.profit_loss} status={bet.status} />
                </td>
              </>
            ) : null}
          </tr>
        ))}
      </tbody>
    </table>
  );
}
