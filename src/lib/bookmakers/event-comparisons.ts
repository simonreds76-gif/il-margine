import { readFileSync } from "node:fs";
import { join } from "node:path";
import { createHash } from "node:crypto";
import type { MarginSegment } from "./margin-index";

type Price = { code: string; bookmaker: string; fractional: string };
type CapturePage = { sport: string; home: string; away: string; url: string; captured_at: string; grids: { market: string; selections: { label: string; prices: Price[] }[] }[] };
export type TennisEventComparison = { label: string; source: string; capturedAt: string; segment: MarginSegment };
const excluded = new Set(["SI", "SX", "BF", "MA"]);
const aliases: Record<string, string> = { B3: "Bet365", WH: "William Hill", UN: "Unibet", FR: "Betfred", FB: "Betfair Sportsbook", LD: "Ladbrokes", VC: "BetVictor", KN: "BetMGM", BY: "BoyleSports", OE: "10BET", S6: "Star Sports", SK: "Sky Bet", PP: "Paddy Power" };

/** Keep a one-match comparison separate from the multi-event qualification gate. */
export function tennisEventComparisons(pages: CapturePage[]): TennisEventComparison[] {
  return pages.filter(page => page.sport === "tennis").flatMap(page => {
    const selections = page.grids.find(grid => grid.market === "Win Market")?.selections;
    if (!selections || selections.length !== 2 || ![page.home, page.away].every(name => selections.some(row => row.label === name))) return [];
    const codes = [...new Set(selections[0].prices.map(price => price.code))];
    const operators = codes.flatMap(code => {
      if (excluded.has(code)) return [];
      const quotes = selections.map(row => row.prices.filter(price => price.code === code));
      if (quotes.some(items => items.length !== 1)) return [];
      const prices = quotes.map(items => {
        const value = items[0].fractional.trim();
        if (/^(evs|evens)$/i.test(value)) return 2;
        const match = /^(\d+(?:\.\d+)?)\/(\d+(?:\.\d+)?)$/.exec(value);
        return match && Number(match[2]) > 0 ? 1 + Number(match[1]) / Number(match[2]) : NaN;
      });
      if (prices.some(price => !Number.isFinite(price) || price <= 1)) return [];
      const total = prices.reduce((sum, price) => sum + 1 / price, 0);
      return [{ name: aliases[code] ?? quotes[0][0].bookmaker, rank: 0, samples: 1, raw_overround_pct: Number(((total - 1) * 100).toFixed(2)), normalized_hold_pct: Number(((1 - 1 / total) * 100).toFixed(2)) }];
    }).sort((a, b) => a.normalized_hold_pct - b.normalized_hold_pct);
    if (operators.length < 2) return [];
    return [{ label: `${page.home} v ${page.away}`, source: page.url, capturedAt: page.captured_at, segment: { sport: "Tennis", sport_slug: "tennis", market_family: "Match Winner", events: 1, observations: operators.length, status: "SINGLE_EVENT", operators: operators.map((row, i) => ({ ...row, rank: i + 1 })) } }];
  });
}

/** Build-time only: follow the current snapshot, never carry an older capture forward. */
export function loadTennisEventComparisons(generatedAt: string | null, hash?: string): TennisEventComparison[] {
  if (!generatedAt || !/^\d{4}-\d{2}-\d{2}T[\d:.]+Z$/.test(generatedAt) || !hash) return [];
  try {
    const bytes = readFileSync(join(process.cwd(), "data/bookmakers/captures", generatedAt.replace(/[-:.]/g, ""), "oddschecker.json"));
    if (createHash("sha256").update(bytes).digest("hex") !== hash) throw new Error("Capture hash mismatch");
    return tennisEventComparisons(JSON.parse(bytes.toString("utf8")).pages);
  } catch (error) {
    console.warn("Per-match bookmaker comparison unavailable:", error instanceof Error ? error.message : "invalid capture");
    return [];
  }
}
