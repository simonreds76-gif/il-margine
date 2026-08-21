"use client";

import { useState, useEffect } from "react";
import { supabase } from "@/lib/supabase";
import { formatStake } from "@/lib/format";

export type MonthlyBreakdownScope = "combined" | "props" | "tennis";

export interface MonthRow {
  month: string;
  total_bets: number;
  wins: number;
  losses: number;
  total_stake: number;
  total_profit: number;
  roi: number;
}

const VIEW_BY_SCOPE: Record<MonthlyBreakdownScope, string> = {
  combined: "monthly_stats",
  props: "monthly_stats_props",
  tennis: "monthly_stats_tennis",
};

const SUBTITLE_BY_SCOPE: Record<MonthlyBreakdownScope, string> = {
  combined: "Tennis + player props combined",
  props: "Player props only",
  tennis: "ATP tennis only",
};

function formatMonth(ym: string): string {
  const [y, m] = ym.split("-");
  const months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
  return `${months[parseInt(m, 10) - 1]} ${y}`;
}

const INITIAL_ROWS = 6;

interface MonthlyBreakdownProps {
  scope: MonthlyBreakdownScope;
  /** If true, always show all rows (e.g. in admin) */
  showAll?: boolean;
  /** Public pages can pass cached API rows to avoid direct Supabase reads. */
  rowsOverride?: MonthRow[];
}

export default function MonthlyBreakdown({ scope, showAll = false, rowsOverride }: MonthlyBreakdownProps) {
  const [rows, setRows] = useState<MonthRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [expanded, setExpanded] = useState(false);
  const [openMonth, setOpenMonth] = useState<string | null>(null);

  const view = VIEW_BY_SCOPE[scope];

  useEffect(() => {
    if (rowsOverride) {
      setRows(rowsOverride);
      setLoading(false);
      return;
    }

    async function fetch_() {
      const { data, error } = await supabase
        .from(view)
        .select("*")
        .order("month", { ascending: false })
        .limit(24);
      if (!error) setRows(data || []);
      setLoading(false);
    }
    fetch_();
  }, [rowsOverride, view]);

  if (loading) return null;
  if (rows.length === 0) return null;

  const displayAll = showAll || expanded;
  const displayed = displayAll ? rows : rows.slice(0, INITIAL_ROWS);
  const hasMore = rows.length > INITIAL_ROWS;

  return (
    <div className="overflow-hidden rounded-2xl border border-slate-700/40 bg-[#0c0f14]">
      <div className="border-b border-slate-800/40 px-5 py-4">
        <span className="block text-xs font-mono font-bold uppercase tracking-[0.18em] text-emerald-400/95">
          Month by month
        </span>
        <h2 className="mt-2 text-2xl font-semibold text-slate-100">Monthly breakdown</h2>
        <p className="mt-1 text-sm text-slate-400">{SUBTITLE_BY_SCOPE[scope]}</p>
      </div>
      {/* Mobile: tap to expand each month */}
      <div className="divide-y divide-slate-800/40 md:hidden">
        {displayed.map((r) => {
          const isOpen = openMonth === r.month;
          return (
            <button
              key={r.month}
              type="button"
              aria-expanded={isOpen}
              onClick={() => setOpenMonth(isOpen ? null : r.month)}
              className="w-full px-4 py-3 text-left transition-colors active:bg-slate-800/35"
            >
              <div className="flex items-center justify-between gap-2">
                <span className="font-medium text-slate-200">{formatMonth(r.month)}</span>
                <span className="flex items-center gap-2">
                  <span className={`font-mono font-medium ${Number(r.total_profit) >= 0 ? "text-emerald-400" : "text-red-400"}`}>
                    {Number(r.total_profit) >= 0 ? "+" : ""}{Number(r.total_profit).toFixed(2)}u
                  </span>
                  <span className={`shrink-0 text-slate-400 transition-transform ${isOpen ? "rotate-180" : ""}`}>
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                      <polyline points="6 9 12 15 18 9" />
                    </svg>
                  </span>
                </span>
              </div>
              {isOpen && (
                <div className="mt-2 flex flex-wrap gap-x-4 gap-y-1 border-t border-slate-800/40 pt-2 font-mono text-xs text-slate-400">
                  <span>{r.total_bets} bets</span>
                  <span>{r.wins}-{r.losses}</span>
                  <span>{formatStake(r.total_stake)}u staked</span>
                  <span className={Number(r.roi) >= 0 ? "text-emerald-400" : "text-red-400"}>
                    {Number(r.roi) >= 0 ? "+" : ""}{Number(r.roi).toFixed(1)}% ROI
                  </span>
                </div>
              )}
            </button>
          );
        })}
      </div>
      {/* Desktop: table */}
      <div className="hidden md:block overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-slate-800/40 text-[11px] uppercase text-slate-400">
              <th className="px-4 py-3 text-left">Month</th>
              <th className="px-4 py-3 text-right">Bets</th>
              <th className="px-4 py-3 text-right">W-L</th>
              <th className="px-4 py-3 text-right">Staked</th>
              <th className="px-4 py-3 text-right">P/L</th>
              <th className="px-4 py-3 text-right">ROI</th>
            </tr>
          </thead>
          <tbody>
            {displayed.map((r) => (
              <tr key={r.month} className="border-b border-slate-800/40 last:border-b-0">
                <td className="px-4 py-3 text-slate-200">{formatMonth(r.month)}</td>
                <td className="px-4 py-3 text-right font-mono text-slate-300">{r.total_bets}</td>
                <td className="px-4 py-3 text-right font-mono text-slate-300">{r.wins}-{r.losses}</td>
                <td className="px-4 py-3 text-right font-mono text-slate-300">{formatStake(r.total_stake)}u</td>
                <td className={`px-4 py-3 text-right font-mono font-medium ${Number(r.total_profit) >= 0 ? "text-emerald-400" : "text-red-400"}`}>
                  {Number(r.total_profit) >= 0 ? "+" : ""}{Number(r.total_profit).toFixed(2)}u
                </td>
                <td className={`px-4 py-3 text-right font-mono font-medium ${Number(r.roi) >= 0 ? "text-emerald-400" : "text-red-400"}`}>
                  {Number(r.roi) >= 0 ? "+" : ""}{Number(r.roi).toFixed(1)}%
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className="border-t border-slate-800/40 px-4 py-3 text-xs text-slate-400">
        <span className="font-medium text-slate-400">Guide:</span>{" "}
        <span>
          <strong className="font-semibold text-slate-300">W-L</strong> = wins-losses,{" "}
          <strong className="font-semibold text-slate-300">Staked</strong> = total units risked,{" "}
          <strong className="font-semibold text-slate-300">P/L</strong> = profit or loss in units,{" "}
          <strong className="font-semibold text-slate-300">ROI</strong> = profit divided by staked.
        </span>
      </div>
      {hasMore && !displayAll && (
        <div className="border-t border-slate-800/40 px-4 py-3 text-center">
          <button
            onClick={() => setExpanded(true)}
            className="text-sm text-emerald-400 hover:text-emerald-300 font-medium transition-colors"
          >
            Show all {rows.length} months
          </button>
        </div>
      )}
      {hasMore && displayAll && !showAll && (
        <div className="border-t border-slate-800/40 px-4 py-2 text-center">
          <button
            onClick={() => setExpanded(false)}
            className="text-xs text-slate-400 transition-colors hover:text-slate-300"
          >
            Show less
          </button>
        </div>
      )}
    </div>
  );
}

