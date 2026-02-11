/** Stake display: no trailing zeros (0.5 not 0.50, 0.75 stays 0.75). Use everywhere we show stake. */
export function formatStake(stake: number | string): string {
  const n = Number(stake);
  return String(parseFloat(n.toFixed(2)));
}
