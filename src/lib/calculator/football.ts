import { devig, type DevigMethod } from "./math";

export type FootballMarket = "homeDraw" | "homeAway" | "drawAway" | "homeDnb" | "awayDnb";
export type FootballPrice = { win: number; refund: number; lose: number; fairOdds: number };

/** Full-time 1X2 probabilities, then settlement-aware fair prices. No archived quotes are created. */
export function footballFairPrices(prices: number[], method: DevigMethod = "proportional") {
  if (prices.length !== 3 || prices.some(price => !Number.isFinite(price) || price <= 1 || price > 1000)) return null;
  const probabilities = devig(prices, method).probabilities;
  if (probabilities.some(p => !Number.isFinite(p) || p <= 0 || p >= 1)) return null;
  const [home, draw, away] = probabilities;
  const market = (win: number, refund: number, lose: number): FootballPrice => ({ win, refund, lose, fairOdds: (win + lose) / win });
  const markets: Record<FootballMarket, FootballPrice> = {
    homeDraw: market(home + draw, 0, away),
    homeAway: market(home + away, 0, draw),
    drawAway: market(draw + away, 0, home),
    homeDnb: market(home, draw, away),
    awayDnb: market(away, draw, home),
  };
  return { probabilities, markets, overround: (prices.reduce((sum, price) => sum + 1 / price, 0) - 1) * 100 };
}

/** Net expectation per unit originally staked; a refunded draw earns zero. */
export function footballExpectedValue(market: FootballPrice, offered: number) {
  return market.win * (offered - 1) - market.lose;
}
