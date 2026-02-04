/**
 * Baseline Statistics - Historical data before database tracking began
 * These numbers represent the starting point and will be combined with live database data
 */

export interface BaselineMarketStats {
  total_bets: number;
  wins: number;
  losses: number;
  total_profit: number; // in units
  total_stake: number; // total units staked
  avg_odds: number;
}

export interface BaselineStats {
  props: BaselineMarketStats;
  tennis: BaselineMarketStats;
  overall: {
    total_bets: number;
    wins: number;
    losses: number;
    total_profit: number;
    total_stake: number;
    avg_odds: number;
  };
  // Category-level baselines
  categoryBaselines: {
    props: {
      [category: string]: BaselineMarketStats;
    };
    tennis: {
      [category: string]: BaselineMarketStats;
    };
  };
}

// Baseline stats extracted from homepage hardcoded values
export const BASELINE_STATS: BaselineStats = {
  props: {
    total_bets: 780,
    wins: Math.round(780 * 0.58), // 58% win rate = 452 wins
    losses: 780 - Math.round(780 * 0.58), // 328 losses
    total_profit: 780 * 0.25, // +25% ROI means profit = 25% of total bets (assuming 1u avg stake)
    total_stake: 780, // Assuming average 1u stake
    avg_odds: 0, // Will calculate from ROI and win rate if needed, or leave as placeholder
  },
  tennis: {
    total_bets: 447,
    wins: Math.round(447 * 0.54), // 54% win rate = 241 wins
    losses: 447 - Math.round(447 * 0.54), // 206 losses
    total_profit: 447 * 0.086, // +8.6% ROI
    total_stake: 447, // Assuming average 1u stake
    avg_odds: 0, // Will calculate from ROI and win rate if needed
  },
  overall: {
    total_bets: 1200,
    wins: Math.round(1200 * 0.56), // 56% win rate = 672 wins
    losses: 1200 - Math.round(1200 * 0.56), // 528 losses
    total_profit: 1200 * 0.18, // +18% ROI
    total_stake: 1200, // Assuming average 1u stake
    avg_odds: 0, // Will calculate if needed
  },
  // Category-level baselines - Calculated from market totals with distribution rules
  categoryBaselines: {
    props: {
      // Serie A = 2x PL, Champions League < PL, Other = 25
      // Distribution: PL=200, SerieA=400 (double PL), UCL=155 (lower than PL), Other=25 (Total: 780)
      pl: {
        total_bets: 200,
        wins: Math.round(200 * 0.58), // 58% win rate = 116 wins
        losses: 200 - Math.round(200 * 0.58), // 84 losses
        total_profit: 200 * 0.25, // 25% ROI = 50u profit
        total_stake: 200,
        avg_odds: 0,
      },
      seriea: {
        total_bets: 400, // Double of PL (Serie A expert)
        wins: Math.round(400 * 0.58), // 58% win rate = 232 wins
        losses: 400 - Math.round(400 * 0.58), // 168 losses
        total_profit: 400 * 0.25, // 25% ROI = 100u profit
        total_stake: 400,
        avg_odds: 0,
      },
      ucl: {
        total_bets: 155, // Lower than PL
        wins: Math.round(155 * 0.58), // 58% win rate = 90 wins
        losses: 155 - Math.round(155 * 0.58), // 65 losses
        total_profit: 155 * 0.25, // 25% ROI = 38.75u profit
        total_stake: 155,
        avg_odds: 0,
      },
      other: {
        total_bets: 25, // As specified
        wins: Math.round(25 * 0.58), // 58% win rate = 15 wins
        losses: 25 - Math.round(25 * 0.58), // 10 losses
        total_profit: 25 * 0.25, // 25% ROI = 6.25u profit
        total_stake: 25,
        avg_odds: 0,
      },
    },
    tennis: {
      // Australian Open: 57 bets, 0.5% ROI, 51% win rate
      // Challenger: 60 bets, 5.9% ROI, 53% win rate
      // Remaining (ATP Tour + Other): 447 - 57 - 60 = 330 bets
      // ATP Tour gets most: 280 bets, Other: 50 bets
      ausopen: {
        total_bets: 57,
        wins: Math.round(57 * 0.51), // 51% win rate = 29 wins
        losses: 57 - Math.round(57 * 0.51), // 28 losses
        total_profit: 57 * 0.005, // 0.5% ROI = 0.285u profit
        total_stake: 57,
        avg_odds: 0,
      },
      challenger: {
        total_bets: 60,
        wins: Math.round(60 * 0.53), // 53% win rate = 32 wins
        losses: 60 - Math.round(60 * 0.53), // 28 losses
        total_profit: 60 * 0.059, // 5.9% ROI = 3.54u profit
        total_stake: 60,
        avg_odds: 0,
      },
      atp: {
        total_bets: 280, // Most of remaining (330 - 50)
        wins: Math.round(280 * 0.54), // 54% win rate = 151 wins
        losses: 280 - Math.round(280 * 0.54), // 129 losses
        // Calculate profit to maintain overall 8.6% ROI for tennis
        // Total tennis profit = 447 * 0.086 = 38.442u
        // ausopen: 0.285u, challenger: 3.54u, other: ~0.5u
        // atp profit = 38.442 - 0.285 - 3.54 - 0.5 = 34.117u
        total_profit: 34.117,
        total_stake: 280,
        avg_odds: 0,
      },
      other: {
        total_bets: 50,
        wins: Math.round(50 * 0.54), // 54% win rate = 27 wins
        losses: 50 - Math.round(50 * 0.54), // 23 losses
        // Remaining profit to balance total
        total_profit: 0.5,
        total_stake: 50,
        avg_odds: 0,
      },
    },
  },
};

// Helper function to calculate ROI from profit and stake
export function calculateROI(profit: number, stake: number): number {
  if (stake === 0) return 0;
  return (profit / stake) * 100;
}

// Helper function to calculate win rate
export function calculateWinRate(wins: number, losses: number): number {
  const total = wins + losses;
  if (total === 0) return 0;
  return (wins / total) * 100;
}
