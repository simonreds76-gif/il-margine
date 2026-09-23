import { BASELINE_STATS, calculateROI } from "@/lib/baseline";
import type { RecordSummary } from "@/components/calculator/ReturnsLab";

export type RecordRow = {
  market: string; total_bets: number; wins: number; losses: number;
  total_profit: number; total_stake?: number;
};

export function summarizeCalculatorRecord(rows: RecordRow[] | null): RecordSummary {
  const included = (rows ?? []).filter(row => row.market === "props" || row.market === "tennis");
  const sum = (key: "total_bets" | "wins" | "losses" | "total_profit") =>
    included.reduce((total, row) => total + Number(row[key] ?? 0), 0);
  const totalStake = BASELINE_STATS.overall.total_stake + included.reduce((total, row) =>
    total + Number(row.total_stake ?? row.total_bets), 0);
  const totalProfit = BASELINE_STATS.overall.total_profit + sum("total_profit");
  return {
    totalBets: BASELINE_STATS.overall.total_bets + sum("total_bets"),
    wins: BASELINE_STATS.overall.wins + sum("wins"),
    losses: BASELINE_STATS.overall.losses + sum("losses"),
    totalProfit, totalStake, roi: calculateROI(totalProfit, totalStake),
    source: rows === null ? "fallback" : "live",
  };
}
