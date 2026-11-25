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
  if (landmarks.size > 0) {
    const first = Math.min(...landmarks);
    const last = Math.max(...landmarks);
    for (let i = first + 1; i <= last; i += 1) {
      if (quotes[i].gap === true) {
        landmarks.add(i - 1);
        landmarks.add(i);
      }
    }
  }

  const chart: Quote[] = [];
  for (const [i, quote] of quotes.entries()) {
    if (!landmarks.has(i)) continue;
    chart.push({ time:quote.time, price:quote.price, gap:chart.length > 0 && quote.gap === true });
  }
  return { ...move, quotes:chart, chartSummary:true };
}

export function publicFixture({tour,league,home,away,start,activeUntil}: Fixture): Fixture {
  return {tour,league,home,away,start,activeUntil};
}
