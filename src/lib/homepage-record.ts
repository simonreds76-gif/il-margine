import type { MarketStats } from "./supabase";
import { BASELINE_STATS, calculateROI, calculateWinRate } from "./baseline";

export interface CombinedMarketStats {
  total_bets: number;
  roi: number;
  win_rate: number;
  avg_odds: number;
  total_profit: number;
}

// Settled counts exclude pending and void picks; other existing headline calculations are preserved.
export function buildCombinedStats(liveStats: MarketStats[]) {
  const propsLive = liveStats.find((stat) => stat.market === "props");
  const tennisLive = liveStats.find((stat) => stat.market === "tennis");

  const propsLiveBets = propsLive?.total_bets || 0;
  const propsLiveWins = propsLive?.wins || 0;
  const propsLiveLosses = propsLive?.losses || 0;
  const propsLiveProfit = Number(propsLive?.total_profit) || 0;
  const propsLiveStake = Number(propsLive?.total_stake) || propsLiveBets;
  const propsProfit = BASELINE_STATS.props.total_profit + propsLiveProfit;
  const propsStake = BASELINE_STATS.props.total_stake + propsLiveStake;
  const propsCombined: CombinedMarketStats = {
    total_bets: BASELINE_STATS.props.total_bets + propsLiveWins + propsLiveLosses,
    roi: calculateROI(propsProfit, propsStake || 1),
    win_rate: calculateWinRate(BASELINE_STATS.props.wins + propsLiveWins, BASELINE_STATS.props.losses + propsLiveLosses),
    avg_odds: propsLive?.avg_odds && propsLiveBets > 0 ? Number(propsLive.avg_odds) : BASELINE_STATS.props.avg_odds,
    total_profit: propsProfit,
  };

  const tennisLiveBets = tennisLive?.total_bets || 0;
  const tennisLiveWins = tennisLive?.wins || 0;
  const tennisLiveLosses = tennisLive?.losses || 0;
  const tennisLiveProfit = Number(tennisLive?.total_profit) || 0;
  const tennisLiveStake = Number(tennisLive?.total_stake) || tennisLiveBets;
  const tennisProfit = BASELINE_STATS.tennis.total_profit + tennisLiveProfit;
  const tennisStake = BASELINE_STATS.tennis.total_stake + tennisLiveStake;
  const tennisCombined: CombinedMarketStats = {
    total_bets: BASELINE_STATS.tennis.total_bets + tennisLiveWins + tennisLiveLosses,
    roi: calculateROI(tennisProfit, tennisStake || 1),
    win_rate: calculateWinRate(BASELINE_STATS.tennis.wins + tennisLiveWins, BASELINE_STATS.tennis.losses + tennisLiveLosses),
    avg_odds: tennisLive?.avg_odds && tennisLiveBets > 0 ? Number(tennisLive.avg_odds) : BASELINE_STATS.tennis.avg_odds,
    total_profit: tennisProfit,
  };

  const overallLiveBets = propsLiveBets + tennisLiveBets;
  const overallLiveWins = propsLiveWins + tennisLiveWins;
  const overallLiveLosses = propsLiveLosses + tennisLiveLosses;
  const overallLiveProfit = propsLiveProfit + tennisLiveProfit;
  const overallLiveStake = propsLiveStake + tennisLiveStake;
  const overallProfit = BASELINE_STATS.overall.total_profit + overallLiveProfit;
  const overallStake = BASELINE_STATS.overall.total_stake + overallLiveStake;
  const totalOddsWeight = propsCombined.avg_odds * (BASELINE_STATS.props.total_bets + propsLiveBets) + tennisCombined.avg_odds * (BASELINE_STATS.tennis.total_bets + tennisLiveBets);
  const overallCombined: CombinedMarketStats = {
    total_bets: BASELINE_STATS.overall.total_bets + overallLiveWins + overallLiveLosses,
    roi: calculateROI(overallProfit, overallStake || 1),
    win_rate: calculateWinRate(BASELINE_STATS.overall.wins + overallLiveWins, BASELINE_STATS.overall.losses + overallLiveLosses),
    avg_odds: totalOddsWeight > 0 ? totalOddsWeight / (BASELINE_STATS.overall.total_bets + overallLiveBets) : BASELINE_STATS.overall.avg_odds,
    total_profit: overallProfit,
  };

  return {
    props: propsCombined,
    tennis: tennisCombined,
    overall: overallCombined,
  };
}

