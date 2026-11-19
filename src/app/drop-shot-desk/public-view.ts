import type { Fixture, Move, Quote } from "./types";

// Publish analytical landmarks for a selection. The full two-sided tape stays on the server.
export function publicMove(move: Move): Move {
  const quotes = move.quotes;
  const landmarks = new Set<number>();
  let low = -1;
  let high = -1;
  const before = Date.parse(move.before);
  const detection = Date.parse(move.after);
  for (const [i, quote] of quotes.entries()) {
    const t = Date.parse(quote.time);
    if (t === before || t === detection) landmarks.add(i);
    if (t < detection) continue;
    if (low < 0 || quote.price < quotes[low].price) low = i;
    if (high < 0 || quote.price > quotes[high].price) high = i;
  }
  for (const i of [low, high, quotes.length - 1]) if (i >= 0) landmarks.add(i);

  const chart: Quote[] = [];
  let gap = false;
  for (const [i, quote] of quotes.entries()) {
    gap ||= quote.gap === true;
    if (!landmarks.has(i)) continue;
    chart.push({ time:quote.time, price:quote.price, gap:chart.length > 0 && gap });
    gap = false;
  }
  return { ...move, quotes:chart, chartSummary:true };
}

export function publicFixture({tour,league,home,away,start,activeUntil}: Fixture): Fixture {
  return {tour,league,home,away,start,activeUntil};
}
