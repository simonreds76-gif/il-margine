// Derived only from the published ledger. No invented form, team news or model probabilities.
type CopyBet = {
  event: string; market: string; category: string; match_date: string;
  player: string | null; selection: string; odds: number; status: string;
};

export function tipSelectionLabel(bet: Pick<CopyBet, "player" | "selection">): string {
  const selection = bet.selection.trim().toUpperCase() === "ML" ? "Match winner" : bet.selection.trim();
  return bet.player ? `${bet.player} - ${selection}` : selection;
}

export function competitionName(category: string): string {
  const names: Record<string, string> = {
    pl: "Premier League", seriea: "Serie A", laliga: "La Liga", bundesliga: "Bundesliga",
    ligue1: "Ligue 1", ucl: "Champions League", worldcup: "World Cup", atp: "ATP tennis", challenger: "Challenger tennis",
    ausopen: "Australian Open", rolandgarros: "Roland-Garros", wimbledon: "Wimbledon", usopen: "US Open",
  };
  return names[category.toLowerCase().replace(/[^a-z0-9]/g, "")] || "";
}

export function buildTipPageCopy(seed: CopyBet, bets: CopyBet[], dateLabel: string) {
  const subject = seed.market === "tennis" ? "tennis betting tips" : "football player prop tips";
  const competition = competitionName(seed.category);
  const selections = bets.slice(0, 3).map(tipSelectionLabel).join("; ");
  const remainder = bets.length > 3 ? `, plus ${bets.length - 3} more selections` : "";
  const introduction = `Independent ${subject} for ${seed.event} on ${dateLabel}${competition ? ` (${competition})` : ""}. The published card covers ${selections}${remainder}. Compare the recorded odds and stakes below, read any published analysis, and check each result after settlement.`;
  const pending = bets.filter((bet) => bet.status === "pending").length;
  const statusCopy = pending === 0
    ? "Completed betting record: these selections have been settled. For upcoming matches, use the current picks page."
    : `${pending} ${pending === 1 ? "selection is" : "selections are"} awaiting settlement. A pending result does not mean the original odds are still available.`;
  const description = `${seed.event} ${seed.market === "tennis" ? "tennis tips" : "player props"}, ${dateLabel}. ${tipSelectionLabel(bets[0] || seed)}. Recorded odds, stakes${pending === 0 ? " and results" : " and analysis"}.`;
  // Keep snippets concise without cutting a name halfway through a word.
  const metaDescription = description.length <= 170 ? description : `${description.slice(0, 167).replace(/\s+\S*$/, "")}…`;
  return { introduction, statusCopy, metaDescription, competition };
}

export function priceContext(odds: number): string | null {
  if (!Number.isFinite(odds) || odds <= 1) return null;
  return `At decimal odds of ${odds.toFixed(2)}, the break-even win rate is ${(100 / odds).toFixed(1)}% among bets that win or lose. This is calculated from the price, not our predicted chance. Voids return the stake; part-win or part-loss markets need a different calculation.`;
}

export function serializeTipSchema(value: unknown): string {
  // Notes and names can contain HTML-like text; never let them terminate a script tag.
  return JSON.stringify(value).replace(/</g, "\\u003c");
}
