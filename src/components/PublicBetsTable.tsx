"use client";

import Link from "next/link";
import { type Bet, type Bookmaker } from "@/lib/supabase";
import BookmakerLogo from "@/components/BookmakerLogo";
import MarketBadge from "@/components/MarketBadge";
import PnL from "@/components/PnL";
import ResultBadge from "@/components/ResultBadge";
import { formatMatchDate, formatOdds, formatStake } from "@/lib/format";
import { slugifyTip } from "@/lib/slugify";

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
  icon: "w-[3.75rem] border-r border-slate-800/40 px-2.5 py-3 text-center",
  date: "w-[5.25rem] border-r border-slate-800/40 px-2.5 py-3 text-center",
  match: "w-[25%] border-r border-slate-800/40 px-4 py-3 text-left",
  player: "w-[15%] border-r border-slate-800/40 px-4 py-3 text-left",
  selection: "w-[18%] border-r border-slate-800/40 px-4 py-3 text-left",
  odds: "w-[5.5rem] border-r border-slate-800/40 px-4 py-3 text-right",
  bookmaker: "w-32 border-r border-slate-800/40 px-4 py-3 text-center",
  stake: "w-[5.5rem] border-r border-slate-800/40 px-4 py-3 text-right",
  stakeLast: "w-[5.5rem] px-4 py-3 text-right",
  status: "w-24 border-r border-slate-800/40 px-3 py-3 text-center",
  pnl: "w-24 px-4 py-3 text-right",
} as const;

const td = {
  icon: "border-r border-slate-800/40 px-2.5 py-3.5 text-center align-middle",
  date: "border-r border-slate-800/40 px-2.5 py-3.5 text-center align-middle text-sm whitespace-nowrap text-slate-400",
  match: "border-r border-slate-800/40 px-4 py-3.5 align-middle font-medium text-slate-200",
  player: "border-r border-slate-800/40 px-4 py-3.5 align-middle text-slate-300",
  selection: "border-r border-slate-800/40 px-4 py-3.5 align-middle text-slate-300",
  odds: "border-r border-slate-800/40 px-4 py-3.5 text-right align-middle",
  bookmaker: "border-r border-slate-800/40 px-4 py-3.5 align-middle text-center",
  stake: "border-r border-slate-800/40 px-4 py-3.5 text-right align-middle font-mono tabular-nums text-slate-200",
  stakeLast: "px-4 py-3.5 text-right align-middle font-mono tabular-nums text-slate-200",
  status: "border-r border-slate-800/40 px-2.5 py-3.5 align-middle text-center",
  pnl: "px-4 py-3.5 text-right align-middle",
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
          <tr key={bet.id} className="border-b border-slate-800/40 last:border-b-0 hover:bg-slate-800/20">
            <td className={td.icon}>
              <MarketBadge market={bet.market} category={bet.category} event={bet.event} hideOnMobile />
            </td>
            <td className={td.date}>{formatMatchDate(bet.match_date)}</td>
            <td className={td.match}>
              <Link
                href={`/tips/${slugifyTip(bet.event, bet.id)}`}
                className="block truncate transition-colors hover:text-emerald-400"
                title={bet.event}
              >
                {bet.event}
              </Link>
            </td>
            <td className={td.player}>
              <span className="block truncate">{bet.player || "-"}</span>
            </td>
            <td className={td.selection}>
              <span className="block whitespace-normal break-words leading-snug" title={bet.selection}>
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
