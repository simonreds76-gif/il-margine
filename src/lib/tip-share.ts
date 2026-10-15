import { formatOdds, formatStake } from "./format";

export type ShareTip = {
  id: number; event: string; market: string; category: string;
  player: string | null; selection: string; odds: number; stake: number; match_date: string;
};
export function shareSelection(bet: ShareTip): string {
  const selection = bet.selection.trim().toUpperCase() === "ML" ? "Match winner" : bet.selection.trim();
  return bet.player ? `${bet.player} · ${selection}` : selection;
}
export function shareDate(value: string): string {
  const date = new Date(`${value.slice(0, 10)}T12:00:00Z`);
  return Number.isNaN(date.getTime()) ? "" : new Intl.DateTimeFormat("en-GB", {
    day: "numeric", month: "short", year: "numeric", timeZone: "UTC",
  }).format(date);
}
export function tipShareDetails(bets: ShareTip[]) {
  if (!bets.length) throw new Error("A share preview requires a published selection");
  const first = bets[0];
  const single = bets.length === 1;
  const title = single ? `${first.event}: ${shareSelection(first)} at ${formatOdds(first.odds)}` : `${first.event}: ${bets.length} published selections`;
  const description = single
    ? `${shareSelection(first)}. Recorded odds ${formatOdds(first.odds)}, stake ${formatStake(first.stake)}u. ${shareDate(first.match_date)}. View the published pick and result.`
    : `${shareDate(first.match_date)}. ${bets.slice(0, 2).map(bet => `${shareSelection(bet)} at ${formatOdds(bet.odds)}`).join("; ")}${bets.length > 2 ? `; plus ${bets.length - 2} more` : ""}. View the full match card.`;
  return { title, description, alt: `Il Margine. ${title}. ${shareDate(first.match_date)}. Prices as published.` };
}
