"use client";
import Link from "next/link";
import TipPortraits from "@/components/TipPortraits";
import PropMarketIcon from "@/components/PropMarketIcon";
import BookmakerLogo from "@/components/BookmakerLogo";
import type { Bookmaker } from "@/lib/supabase";
import type { PropKey, PropRow } from "@/lib/prop-performance";
const tone = (n: number | null) => n == null || n === 0 ? "text-slate-300" : n > 0 ? "text-emerald-300" : "text-rose-300";
const signed = (n: number, digits = 2) => `${n > 0 ? "+" : ""}${n.toFixed(digits)}`;
const dateLabel = (value?: string | null) => value ? new Date(value.slice(0, 10) + "T12:00:00Z").toLocaleDateString("en-GB", { day: "numeric", month: "short", year: "numeric", timeZone: "UTC" }) : "Date unavailable";

export default function PropSelectionCard({ row, market, href, bookmaker }: { row: PropRow; market: PropKey; href?: string; bookmaker?: Bookmaker }) {
  // Preserve older entries where the player and selection fields were reversed.
  const reversed = /^(over|under) \d/i.test(row.player || "") && !/^(over|under) \d/i.test(row.selection);
  const player = reversed ? row.selection : row.player || "Selection";
  const selection = reversed ? row.player : row.selection;
  const settled = row.status === "won" || row.status === "lost";
  const voided = row.status === "void";
  const won = row.status === "won";
  const content = <>
    <div className="flex items-start gap-3">
      <span className="flex min-h-12 shrink-0 items-center justify-center">
        {row.artwork?.length ? <TipPortraits portraits={row.artwork} size="card" /> : <span className="flex h-12 w-12 items-center justify-center rounded-full border border-slate-700 bg-slate-800 text-slate-400"><PropMarketIcon market={market} className="h-7 w-7" /></span>}
      </span>
      <div className="min-w-0 flex-1">
        <p className="break-words text-base font-semibold leading-5 text-slate-100">{player}</p>
        <p className="mt-1 break-words text-sm leading-5 text-slate-300">{selection}</p>
      </div>
      <span className={`flex shrink-0 items-center gap-1 rounded-full border px-2 py-1 text-[10px] font-semibold ${won ? "border-emerald-300/20 bg-emerald-300/5 text-emerald-300" : settled ? "border-rose-300/20 bg-rose-300/5 text-rose-300" : voided ? "border-slate-600 bg-slate-800 text-slate-300" : "border-amber-300/20 bg-amber-300/5 text-amber-200"}`}>
        <svg viewBox="0 0 16 16" className="hidden h-3 w-3 sm:block" fill="none" stroke="currentColor" strokeWidth="1.5" aria-hidden="true">{voided ? <path d="M4 8h8" /> : settled ? <path d={won ? "m3 8 3 3 7-7" : "m4 4 8 8M12 4l-8 8"} /> : <><circle cx="8" cy="8" r="5.5"/><path d="M8 4.5V8l2 1.5"/></>}</svg>
        {won ? "Won" : settled ? "Lost" : voided ? "Void" : "Pending"}
      </span>
    </div>
    <div className="mt-3 border-t border-slate-700/50 pt-3"><p className="break-words text-xs font-medium leading-5 text-slate-300">{row.event}</p><p className="mt-0.5 text-[11px] text-slate-400">{dateLabel(row.date || row.match_date)}</p></div>
    <dl className="mt-3 grid grid-cols-3 divide-x divide-slate-700/60 rounded-lg bg-slate-950/60 py-2.5">
      <div className="min-w-0 px-2.5"><dt className="text-[9px] font-medium uppercase tracking-wider text-slate-400">Odds</dt><dd className="mt-1 font-mono text-sm font-semibold tabular-nums text-slate-100">{row.odds && row.odds > 1 ? row.odds.toFixed(2) : "N/A"}</dd></div>
      <div className="min-w-0 px-2.5"><dt className="text-[9px] font-medium uppercase tracking-wider text-slate-400">Stake</dt><dd className="mt-1 font-mono text-sm font-semibold tabular-nums text-slate-100">{row.stake.toFixed(2)}u</dd></div>
      <div className="min-w-0 px-2.5"><dt className="text-[9px] font-medium uppercase tracking-wider text-slate-400">Profit</dt><dd className={`mt-1 font-mono text-sm font-semibold tabular-nums ${tone(settled ? row.profit_loss ?? null : null)}`}>{settled && row.profit_loss != null ? `${signed(row.profit_loss)}u` : voided ? "0.00u" : "Pending"}</dd></div>
    </dl>
    {href || bookmaker ? <div className="mt-3 flex min-h-8 items-center justify-between gap-3">
      {bookmaker ? <BookmakerLogo bookmaker={bookmaker} size="sm" noLink /> : <span />}
      {href ? <span className="flex items-center gap-1.5 text-xs font-medium text-emerald-200">View pick<svg viewBox="0 0 16 16" className="h-3.5 w-3.5" fill="none" stroke="currentColor" strokeWidth="1.5" aria-hidden="true"><path d="M3 13 13 3M4 3h9v9" /></svg></span> : null}
    </div> : null}
  </>;
  const classes = "block h-full rounded-xl border border-slate-700/60 bg-slate-900/60 p-3.5 sm:p-4";
  return <article className="min-w-0">{href ? <Link href={href} prefetch={false} className={`${classes} transition-colors hover:border-emerald-300/40 hover:bg-slate-800/50 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-emerald-300`}>{content}</Link> : <div className={classes}>{content}</div>}</article>;
}
