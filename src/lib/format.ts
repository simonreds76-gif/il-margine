/** Stake display: no trailing zeros (0.5 not 0.50, 0.75 stays 0.75). Use everywhere we show stake. */
export function formatStake(stake: number | string): string {
  const n = Number(stake);
  return String(parseFloat(n.toFixed(2)));
}

/** Match date display: e.g. "7 Feb" */
export function formatMatchDate(dateStr: string | null | undefined): string {
  if (!dateStr) return "–";
  const d = new Date(dateStr + "T12:00:00");
  if (isNaN(d.getTime())) return "–";
  return d.toLocaleDateString("en-GB", { day: "numeric", month: "short" });
}
