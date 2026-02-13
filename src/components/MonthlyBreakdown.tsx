"use client";

import { useState, useEffect } from "react";
import { supabase } from "@/lib/supabase";

export type MonthlyBreakdownScope = "combined" | "props" | "tennis";

interface MonthRow {
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
}

export default function MonthlyBreakdown({ scope, showAll = false }: MonthlyBreakdownProps) {
  const [rows, setRows] = useState<MonthRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [expanded, setExpanded] = useState(false);

  const view = VIEW_BY_SCOPE[scope];

  useEffect(() => {
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
  }, [view]);

  if (loading) return null;
  if (rows.length === 0) return null;

  const displayAll = showAll || expanded;
  const displayed = displayAll ? rows : rows.slice(0, INITIAL_ROWS);
  const hasMore = rows.length > INITIAL_ROWS;

  return (
    <div className="rounded-lg border border-slate-800 bg-slate-900/50 overflow-hidden">
      <div className="px-4 py-3 border-b border-slate-800">
        <h3 className="text-sm font-semibold text-slate-200">Monthly breakdown</h3>
        <p className="text-xs text-slate-500 mt-0.5">{SUBTITLE_BY_SCOPE[scope]}</p>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-slate-700 text-xs text-slate-500 uppercase">
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
              <tr key={r.month} className="border-b border-slate-800/50">
                <td className="px-4 py-3 text-slate-200">{formatMonth(r.month)}</td>
                <td className="px-4 py-3 text-right font-mono text-slate-300">{r.total_bets}</td>
                <td className="px-4 py-3 text-right font-mono text-slate-300">{r.wins}-{r.losses}</td>
                <td className="px-4 py-3 text-right font-mono text-slate-300">{Number(r.total_stake).toFixed(1)}u</td>
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
      {hasMore && !displayAll && (
        <div className="px-4 py-3 border-t border-slate-800 text-center">
          <button
            onClick={() => setExpanded(true)}
            className="text-sm text-emerald-400 hover:text-emerald-300 font-medium transition-colors"
          >
            Show all {rows.length} months
          </button>
        </div>
      )}
      {hasMore && displayAll && !showAll && (
        <div className="px-4 py-2 border-t border-slate-800 text-center">
          <button
            onClick={() => setExpanded(false)}
            className="text-xs text-slate-500 hover:text-slate-400 transition-colors"
          >
            Show less
          </button>
        </div>
      )}
    </div>
  );
}
