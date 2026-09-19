export type MonthlyBetRow = {
  match_date: string | null;
  settled_at: string | null;
  status: string | null;
  stake: number | string | null;
  profit_loss: number | string | null;
};

type MonthlyAccumulator = {
  month: string;
  total_bets: number;
  wins: number;
  losses: number;
  total_stake: number;
  total_profit: number;
};


function roundUnits(value: number): number { return Math.round((value + Number.EPSILON) * 10000) / 10000; }

function monthKeyFromBet(row: MonthlyBetRow): string | null {
  const raw = row.match_date || row.settled_at;
  if (!raw || raw.length < 7) return null;
  return raw.slice(0, 7);
}

export function buildMonthlyRows(rows: MonthlyBetRow[]) {
  const byMonth = new Map<string, MonthlyAccumulator>();

  for (const row of rows) {
    const status = (row.status || "").toLowerCase();
    if (status !== "won" && status !== "lost") continue;

    const month = monthKeyFromBet(row);
    if (!month) continue;

    const stake = Number(row.stake);
    const profit = Number(row.profit_loss);
    const safeStake = Number.isFinite(stake) && stake > 0 ? stake : 1;
    const safeProfit = Number.isFinite(profit) ? profit : status === "lost" ? -safeStake : 0;

    const acc = byMonth.get(month) ?? {
      month,
      total_bets: 0,
      wins: 0,
      losses: 0,
      total_stake: 0,
      total_profit: 0,
    };

    acc.total_bets += 1;
    if (status === "won") acc.wins += 1;
    if (status === "lost") acc.losses += 1;
    acc.total_stake += safeStake;
    acc.total_profit += safeProfit;
    byMonth.set(month, acc);
  }

  return Array.from(byMonth.values())
    .sort((a, b) => b.month.localeCompare(a.month))
    .slice(0, 24)
    .map((row) => {
      const totalStake = roundUnits(row.total_stake);
      const totalProfit = roundUnits(row.total_profit);
      return {
        month: row.month,
        total_bets: row.total_bets,
        wins: row.wins,
        losses: row.losses,
        total_stake: totalStake,
        total_profit: totalProfit,
        roi: totalStake > 0 ? roundUnits((totalProfit / totalStake) * 100) : 0,
      };
    });
}

