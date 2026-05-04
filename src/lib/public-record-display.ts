import { BASELINE_STATS, calculateROI, calculateWinRate, getBaselineDisplayStats } from "@/lib/baseline";
import { type MarketStats } from "@/lib/supabase";

export type DisplayStats = ReturnType<typeof getBaselineDisplayStats>;

type CombinedMarketStats = {
  total_bets: number;
  roi: number;
  win_rate: number;
  avg_odds: number;
  total_profit: number;
};

export function buildCombinedDisplayStats(liveStats: MarketStats[]): DisplayStats {
  const propsLive = liveStats.find((stat) => stat.market === "props");
  const tennisLive = liveStats.find((stat) => stat.market === "tennis");

  const propsLiveBets = propsLive?.total_bets || 0;
  const propsLiveWins = propsLive?.wins || 0;
  const propsLiveLosses = propsLive?.losses || 0;
  const propsLiveProfit = Number(propsLive?.total_profit) || 0;
  const propsLiveStake = Number(propsLive?.total_stake) || propsLiveBets;

  const propsWins = BASELINE_STATS.props.wins + propsLiveWins;
  const propsLosses = BASELINE_STATS.props.losses + propsLiveLosses;
  const propsProfit = BASELINE_STATS.props.total_profit + propsLiveProfit;
  const propsStake = BASELINE_STATS.props.total_stake + propsLiveStake;

  const propsCombined: CombinedMarketStats = {
    total_bets: BASELINE_STATS.props.total_bets + propsLiveBets,
    roi: calculateROI(propsProfit, propsStake || 1),
    win_rate: calculateWinRate(propsWins, propsLosses),
    avg_odds: propsLive?.avg_odds && propsLiveBets > 0 ? Number(propsLive.avg_odds) : 0,
    total_profit: propsProfit,
  };

  const tennisLiveBets = tennisLive?.total_bets || 0;
  const tennisLiveWins = tennisLive?.wins || 0;
  const tennisLiveLosses = tennisLive?.losses || 0;
  const tennisLiveProfit = Number(tennisLive?.total_profit) || 0;
  const tennisLiveStake = Number(tennisLive?.total_stake) || tennisLiveBets;

  const tennisWins = BASELINE_STATS.tennis.wins + tennisLiveWins;
  const tennisLosses = BASELINE_STATS.tennis.losses + tennisLiveLosses;
  const tennisProfit = BASELINE_STATS.tennis.total_profit + tennisLiveProfit;
  const tennisStake = BASELINE_STATS.tennis.total_stake + tennisLiveStake;

  const tennisCombined: CombinedMarketStats = {
    total_bets: BASELINE_STATS.tennis.total_bets + tennisLiveBets,
    roi: calculateROI(tennisProfit, tennisStake || 1),
    win_rate: calculateWinRate(tennisWins, tennisLosses),
    avg_odds: tennisLive?.avg_odds && tennisLiveBets > 0 ? Number(tennisLive.avg_odds) : 0,
    total_profit: tennisProfit,
  };

  const overallProfit = propsProfit + tennisProfit;
  const overallStake = propsStake + tennisStake;
  const overallWins = propsWins + tennisWins;
  const overallLosses = propsLosses + tennisLosses;

  const overallCombined: CombinedMarketStats = {
    total_bets: propsCombined.total_bets + tennisCombined.total_bets,
    roi: calculateROI(overallProfit, overallStake || 1),
    win_rate: calculateWinRate(overallWins, overallLosses),
    avg_odds: 0,
    total_profit: overallProfit,
  };

  if (propsCombined.avg_odds > 0 || tennisCombined.avg_odds > 0) {
    const totalOddsWeight =
      propsCombined.avg_odds * propsCombined.total_bets + tennisCombined.avg_odds * tennisCombined.total_bets;
    overallCombined.avg_odds = overallCombined.total_bets > 0 ? totalOddsWeight / overallCombined.total_bets : 0;
  }

  return {
    props: propsCombined,
    tennis: tennisCombined,
    overall: overallCombined,
  };
}

export function formatBetCount(value: number) {
  return `${Math.round(value).toLocaleString("en-GB")}+`;
}

export function formatSignedPercent(value: number) {
  return `${value > 0 ? "+" : ""}${value.toFixed(1)}%`;
}

export function formatCashExample(unitsProfit: number, poundsPerUnit = 100) {
  const value = Math.round(unitsProfit * poundsPerUnit);
  return `${value >= 0 ? "+" : "-"}${String.fromCharCode(163)}${Math.abs(value).toLocaleString("en-GB")}`;
}
