/**
 * Calculator maths. Pure functions only, no React, no side effects.
 *
 * Everything here is deterministic: the simulators take an explicit seed so the
 * server render and the client render produce identical output and React does
 * not warn about a hydration mismatch.
 */

/* ------------------------------------------------------------------ */
/* Random numbers                                                      */
/* ------------------------------------------------------------------ */

/** Small, fast, seedable PRNG (mulberry32). Same seed, same sequence. */
export function mulberry32(seed: number): () => number {
  let a = seed >>> 0;
  return function next(): number {
    a = (a + 0x6d2b79f5) >>> 0;
    let t = a;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

/* ------------------------------------------------------------------ */
/* Odds conversion                                                     */
/* ------------------------------------------------------------------ */

export type OddsFormat = "decimal" | "fractional" | "american";

export function decimalToImplied(decimalOdds: number): number {
  return decimalOdds > 1 ? 1 / decimalOdds : 0;
}

export function impliedToDecimal(probability: number): number {
  return probability > 0 && probability < 1 ? 1 / probability : 0;
}

export function decimalToAmerican(decimalOdds: number): number {
  if (decimalOdds <= 1) return 0;
  return decimalOdds >= 2
    ? Math.round((decimalOdds - 1) * 100)
    : Math.round(-100 / (decimalOdds - 1));
}

export function americanToDecimal(american: number): number {
  if (american === 0) return 0;
  return american > 0 ? american / 100 + 1 : 100 / Math.abs(american) + 1;
}

/** Nearest sensible fraction, using a bounded Stern-Brocot search. */
export function decimalToFractional(decimalOdds: number): string {
  if (decimalOdds <= 1) return "0/1";
  const target = decimalOdds - 1;
  let bestNum = 1;
  let bestDen = 1;
  let bestErr = Number.POSITIVE_INFINITY;
  const denominators = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 16, 20, 25, 33, 40, 50, 66, 100];
  for (const den of denominators) {
    const num = Math.round(target * den);
    if (num < 1) continue;
    const err = Math.abs(num / den - target);
    if (err < bestErr - 1e-9) {
      bestErr = err;
      bestNum = num;
      bestDen = den;
    }
  }
  const g = gcd(bestNum, bestDen);
  return `${bestNum / g}/${bestDen / g}`;
}

export function fractionalToDecimal(input: string): number {
  const parts = input.split(/[/\-:]/);
  if (parts.length !== 2) return 0;
  const num = Number(parts[0]);
  const den = Number(parts[1]);
  if (!Number.isFinite(num) || !Number.isFinite(den) || den === 0) return 0;
  return num / den + 1;
}

function gcd(a: number, b: number): number {
  return b === 0 ? a : gcd(b, a % b);
}

export function parseNumber(value: string): number {
  const n = Number.parseFloat(value.replace(/[, ]/g, ""));
  return Number.isFinite(n) ? n : 0;
}

/* ------------------------------------------------------------------ */
/* Kelly                                                               */
/* ------------------------------------------------------------------ */

/** Full Kelly stake as a share of bankroll. Returns 0 when there is no edge. */
export function kellyFraction(decimalOdds: number, probability: number): number {
  if (decimalOdds <= 1 || probability <= 0 || probability >= 1) return 0;
  const b = decimalOdds - 1;
  const f = (b * probability - (1 - probability)) / b;
  return f > 0 ? f : 0;
}

/**
 * Expected log growth per bet at stake share f.
 * This is the quantity Kelly maximises, and the reason overbetting destroys a
 * bankroll: past full Kelly the curve turns down and eventually goes negative.
 */
export function growthRate(decimalOdds: number, probability: number, f: number): number {
  const b = decimalOdds - 1;
  if (f <= 0) return 0;
  if (f >= 1) return Number.NEGATIVE_INFINITY;
  return probability * Math.log(1 + f * b) + (1 - probability) * Math.log(1 - f);
}

/** Expected value per 1 unit staked. */
export function expectedValue(decimalOdds: number, probability: number): number {
  return probability * decimalOdds - 1;
}

/**
 * Average winning price implied by a flat-stake record.
 * From EV per bet = p(o - 1) - (1 - p) = roi, solve for o.
 */
export function impliedAverageWinOdds(winRate: number, roi: number): number {
  if (winRate <= 0) return 0;
  return 1 + (roi + 1 - winRate) / winRate;
}

/* ------------------------------------------------------------------ */
/* Path statistics                                                     */
/* ------------------------------------------------------------------ */

export function percentileOfSorted(sorted: number[], q: number): number {
  if (sorted.length === 0) return 0;
  const pos = (sorted.length - 1) * q;
  const lower = Math.floor(pos);
  const upper = Math.ceil(pos);
  if (lower === upper) return sorted[lower];
  return sorted[lower] + (sorted[upper] - sorted[lower]) * (pos - lower);
}

/* ------------------------------------------------------------------ */
/* Flat-stake simulation                                               */
/* ------------------------------------------------------------------ */

export interface FlatStakeInput {
  /** Number of settled bets to simulate. */
  bets: number;
  /** Flat stake per bet, in currency. */
  stake: number;
  /** Strike rate, 0 to 1. */
  winRate: number;
  /** Return on turnover per bet, e.g. 0.153 for +15.3%. */
  roi: number;
  /** Starting bankroll, in currency. */
  startBankroll: number;
  paths?: number;
  seed?: number;
  checkpoints?: number;
}

export interface BandSeries {
  x: number[];
  p05: number[];
  p25: number[];
  p50: number[];
  p75: number[];
  p95: number[];
  expected: number[];
}

export interface FlatStakeResult {
  avgWinOdds: number;
  band: BandSeries;
  terminal: { p05: number; p25: number; p50: number; p75: number; p95: number; expected: number };
  medianDrawdown: number;
  severeDrawdown: number;
  lossProbability: number;
  bustProbability: number;
  longestLosingRun: number;
}

/**
 * Monte Carlo of a flat-stake sequence with the recorded strike rate and ROI.
 *
 * The published record is one realised sequence. Re-running the same edge shows
 * the spread of outcomes the same edge can produce, which is the part a single
 * equity curve hides.
 */
export function simulateFlatStake(input: FlatStakeInput): FlatStakeResult {
  const paths = input.paths ?? 400;
  const checkpointCount = Math.min(input.checkpoints ?? 60, Math.max(input.bets, 1));
  const bets = Math.max(1, Math.round(input.bets));
  const stake = Math.max(0, input.stake);
  const p = Math.min(0.999, Math.max(0.001, input.winRate));
  const avgWinOdds = impliedAverageWinOdds(p, input.roi);
  const win = stake * (avgWinOdds - 1);
  const loss = stake;
  const rand = mulberry32(input.seed ?? 20260921);

  const indices: number[] = [];
  for (let c = 0; c <= checkpointCount; c += 1) {
    indices.push(Math.round((c / checkpointCount) * bets));
  }

  const samples: number[][] = indices.map(() => []);
  const drawdowns: number[] = [];
  const terminals: number[] = [];
  let busts = 0;
  let longestLosingRun = 0;

  for (let path = 0; path < paths; path += 1) {
    let balance = input.startBankroll;
    let peak = balance;
    let maxDrawdown = 0;
    let losingRun = 0;
    let bust = stake > input.startBankroll;
    let cursor = 0;
    while (indices[cursor] === 0) {
      samples[cursor].push(balance);
      cursor += 1;
    }

    for (let i = 1; i <= bets; i += 1) {
      const outcome = rand();
      if (balance < stake) {
        bust = true;
      } else if (outcome < p) {
        balance += win;
        losingRun = 0;
      } else {
        balance -= loss;
        losingRun += 1;
        if (losingRun > longestLosingRun) longestLosingRun = losingRun;
      }
      if (balance > peak) peak = balance;
      const drawdown = peak - balance;
      if (drawdown > maxDrawdown) maxDrawdown = drawdown;
      if (balance <= 0) bust = true;
      while (cursor < indices.length && indices[cursor] === i) {
        samples[cursor].push(balance);
        cursor += 1;
      }
    }

    drawdowns.push(maxDrawdown);
    terminals.push(balance);
    if (bust) busts += 1;
  }

  const sortedColumns = samples.map((column) => [...column].sort((a, b) => a - b));
  const expected = indices.map((i) => input.startBankroll + i * stake * input.roi);

  const band: BandSeries = {
    x: indices,
    p05: sortedColumns.map((col) => percentileOfSorted(col, 0.05)),
    p25: sortedColumns.map((col) => percentileOfSorted(col, 0.25)),
    p50: sortedColumns.map((col) => percentileOfSorted(col, 0.5)),
    p75: sortedColumns.map((col) => percentileOfSorted(col, 0.75)),
    p95: sortedColumns.map((col) => percentileOfSorted(col, 0.95)),
    expected,
  };

  const sortedTerminals = [...terminals].sort((a, b) => a - b);
  const sortedDrawdowns = [...drawdowns].sort((a, b) => a - b);

  return {
    avgWinOdds,
    band,
    terminal: {
      p05: percentileOfSorted(sortedTerminals, 0.05),
      p25: percentileOfSorted(sortedTerminals, 0.25),
      p50: percentileOfSorted(sortedTerminals, 0.5),
      p75: percentileOfSorted(sortedTerminals, 0.75),
      p95: percentileOfSorted(sortedTerminals, 0.95),
      expected: expected[expected.length - 1],
    },
    medianDrawdown: percentileOfSorted(sortedDrawdowns, 0.5),
    severeDrawdown: percentileOfSorted(sortedDrawdowns, 0.95),
    lossProbability:
      terminals.filter((value) => value < input.startBankroll).length / Math.max(terminals.length, 1),
    bustProbability: busts / Math.max(paths, 1),
    longestLosingRun,
  };
}

/* ------------------------------------------------------------------ */
/* Kelly simulation                                                    */
/* ------------------------------------------------------------------ */

export interface KellyPathInput {
  bankroll: number;
  odds: number;
  /** The probability you believe, used to size the stake. */
  estimatedProbability: number;
  /** The probability that actually governs outcomes. */
  trueProbability: number;
  fraction: number;
  bets: number;
  paths?: number;
  seed?: number;
  checkpoints?: number;
}

export interface KellyPathResult {
  fraction: number;
  stakeShare: number;
  growthPerBet: number;
  x: number[];
  median: number[];
  lo: number[];
  hi: number[];
  terminal: { p05: number; p50: number; p95: number };
  medianDrawdownPct: number;
  severeDrawdownPct: number;
  halvedProbability: number;
  lossProbability: number;
}

/**
 * Monte Carlo of fractional Kelly staking. Stakes are sized from the estimated
 * probability while results are drawn from the true probability, so an
 * optimistic estimate shows up as the overbetting it is.
 */
export function simulateKelly(input: KellyPathInput): KellyPathResult {
  const paths = input.paths ?? 400;
  const bets = Math.max(1, Math.round(input.bets));
  const checkpointCount = Math.min(input.checkpoints ?? 50, bets);
  const rand = mulberry32(input.seed ?? 8675309);
  const b = input.odds - 1;
  const stakeShare = kellyFraction(input.odds, input.estimatedProbability) * input.fraction;
  const trueP = Math.min(0.999, Math.max(0.001, input.trueProbability));

  const indices: number[] = [];
  for (let c = 0; c <= checkpointCount; c += 1) {
    indices.push(Math.round((c / checkpointCount) * bets));
  }
  const samples: number[][] = indices.map(() => []);
  const drawdownPcts: number[] = [];
  const terminals: number[] = [];
  let halved = 0;

  const safeShare = Math.min(Math.max(stakeShare, 0), 0.999);

  for (let path = 0; path < paths; path += 1) {
    let balance = input.bankroll;
    let peak = balance;
    let maxDrawdownPct = 0;
    let cursor = 0;
    while (indices[cursor] === 0) {
      samples[cursor].push(balance);
      cursor += 1;
    }
    for (let i = 1; i <= bets; i += 1) {
      const stake = balance * safeShare;
      balance += rand() < trueP ? stake * b : -stake;
      if (balance > peak) peak = balance;
      const drawdownPct = peak > 0 ? (peak - balance) / peak : 0;
      if (drawdownPct > maxDrawdownPct) maxDrawdownPct = drawdownPct;
      while (cursor < indices.length && indices[cursor] === i) {
        samples[cursor].push(balance);
        cursor += 1;
      }
    }
    terminals.push(balance);
    drawdownPcts.push(maxDrawdownPct);
    if (balance < input.bankroll / 2) halved += 1;
  }

  const sortedColumns = samples.map((column) => [...column].sort((a, b2) => a - b2));
  const sortedTerminals = [...terminals].sort((a, b2) => a - b2);
  const sortedDrawdowns = [...drawdownPcts].sort((a, b2) => a - b2);

  return {
    fraction: input.fraction,
    stakeShare: safeShare,
    growthPerBet: growthRate(input.odds, trueP, safeShare),
    x: indices,
    median: sortedColumns.map((col) => percentileOfSorted(col, 0.5)),
    lo: sortedColumns.map((col) => percentileOfSorted(col, 0.05)),
    hi: sortedColumns.map((col) => percentileOfSorted(col, 0.95)),
    terminal: {
      p05: percentileOfSorted(sortedTerminals, 0.05),
      p50: percentileOfSorted(sortedTerminals, 0.5),
      p95: percentileOfSorted(sortedTerminals, 0.95),
    },
    medianDrawdownPct: percentileOfSorted(sortedDrawdowns, 0.5),
    severeDrawdownPct: percentileOfSorted(sortedDrawdowns, 0.95),
    halvedProbability: halved / Math.max(paths, 1),
    lossProbability:
      terminals.filter((value) => value < input.bankroll).length / Math.max(terminals.length, 1),
  };
}

/* ------------------------------------------------------------------ */
/* Margin removal                                                      */
/* ------------------------------------------------------------------ */

export type DevigMethod = "proportional" | "shin" | "oddsRatio";

export interface DevigResult {
  method: DevigMethod;
  probabilities: number[];
  fairOdds: number[];
  parameter: number;
}

export function bookSum(prices: number[]): number {
  return prices.reduce((sum, price) => sum + (price > 1 ? 1 / price : 0), 0);
}

/** Overround as a percentage, e.g. 5.26 for a 1.90 / 1.90 pair. */
export function overroundPct(prices: number[]): number {
  return (bookSum(prices) - 1) * 100;
}

/** Margin expressed on turnover, which is what the book actually keeps. */
export function marginOnTurnoverPct(prices: number[]): number {
  const sum = bookSum(prices);
  return sum > 0 ? ((sum - 1) / sum) * 100 : 0;
}

/** Equal proportional shrink. Simple, and it over-taxes the longshot. */
export function proportionalNoVig(prices: number[]): DevigResult {
  const sum = bookSum(prices);
  const probabilities = prices.map((price) => (price > 1 ? 1 / price / sum : 0));
  return {
    method: "proportional",
    probabilities,
    fairOdds: probabilities.map((p) => (p > 0 ? 1 / p : 0)),
    parameter: sum,
  };
}

/**
 * Shin (1992). Models the book's margin as protection against insiders, which
 * pushes more of the margin onto the longshot than a flat shrink does.
 */
export function shinNoVig(prices: number[]): DevigResult {
  const raw = prices.map((price) => (price > 1 ? 1 / price : 0));
  const sum = raw.reduce((total, value) => total + value, 0);
  if (sum <= 1 || raw.some((value) => value <= 0)) {
    return { ...proportionalNoVig(prices), method: "shin", parameter: 0 };
  }

  const probabilitiesAt = (z: number): number[] =>
    raw.map((pi) => {
      const inner = z * z + (4 * (1 - z) * pi * pi) / sum;
      return (2 * pi * pi / sum) / (Math.sqrt(Math.max(inner, 0)) + z);
    });

  let lo = 0;
  let hi = 1 - 1e-10;
  let z = 0;
  for (let i = 0; i < 80; i += 1) {
    z = (lo + hi) / 2;
    const total = probabilitiesAt(z).reduce((t, value) => t + value, 0);
    if (total > 1) lo = z;
    else hi = z;
  }
  const probabilities = probabilitiesAt(z);
  return {
    method: "shin",
    probabilities,
    fairOdds: probabilities.map((p) => (p > 0 ? 1 / p : 0)),
    parameter: z,
  };
}

/**
 * Odds-ratio method (Cheung / Buchdahl). Keeps the odds ratio between the book
 * price and the fair price constant across outcomes.
 */
export function oddsRatioNoVig(prices: number[]): DevigResult {
  const raw = prices.map((price) => (price > 1 ? 1 / price : 0));
  if (raw.some((value) => value <= 0)) {
    return { ...proportionalNoVig(prices), method: "oddsRatio", parameter: 1 };
  }
  const probabilitiesAt = (c: number): number[] =>
    raw.map((pi) => (c * pi) / (1 - pi + c * pi));

  let lo = 0.0001;
  let hi = 1;
  while (probabilitiesAt(hi).reduce((a, b) => a + b, 0) < 1 && hi < 1e12) hi *= 2;
  let c = 1;
  for (let i = 0; i < 80; i += 1) {
    c = (lo + hi) / 2;
    const total = probabilitiesAt(c).reduce((t, value) => t + value, 0);
    if (total > 1) hi = c;
    else lo = c;
  }
  const probabilities = probabilitiesAt(c);
  return {
    method: "oddsRatio",
    probabilities,
    fairOdds: probabilities.map((p) => (p > 0 ? 1 / p : 0)),
    parameter: c,
  };
}

export function devig(prices: number[], method: DevigMethod): DevigResult {
  if (method === "shin") return shinNoVig(prices);
  if (method === "oddsRatio") return oddsRatioNoVig(prices);
  return proportionalNoVig(prices);
}

/* ------------------------------------------------------------------ */
/* Closing line value                                                  */
/* ------------------------------------------------------------------ */

export interface ClvResult {
  /** Price movement, your odds against the closing odds. */
  priceClvPct: number;
  /** Probability movement, the version that maps to expected value. */
  probabilityClvPct: number;
  fairClosingProbability: number;
  expectedValuePct: number;
  beatTheClose: boolean;
}

/**
 * Closing line value against a two-way closing market.
 * The closing pair is de-vigged first, so the comparison is against a fair
 * closing probability rather than against a price that still carries margin.
 */
export function closingLineValue(
  takenOdds: number,
  closingOdds: number,
  closingOpposite: number,
  method: DevigMethod = "shin"
): ClvResult {
  const usable = closingOdds > 1 && takenOdds > 1 && closingOpposite > 1;
  if (!usable) {
    return {
      priceClvPct: 0,
      probabilityClvPct: 0,
      fairClosingProbability: 0,
      expectedValuePct: 0,
      beatTheClose: false,
    };
  }
  const fair =
    closingOpposite > 1
      ? devig([closingOdds, closingOpposite], method).probabilities[0]
      : 1 / closingOdds;
  const priceClvPct = (takenOdds / closingOdds - 1) * 100;
  const probabilityClvPct = (fair * takenOdds - 1) * 100;
  return {
    priceClvPct,
    probabilityClvPct,
    fairClosingProbability: fair,
    expectedValuePct: (fair * takenOdds - 1) * 100,
    beatTheClose: takenOdds > closingOdds,
  };
}
