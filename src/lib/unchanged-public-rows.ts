/** Keep React's existing references when a refresh returns the same record.
 * Compare every field, including edited identities, odds, results and artwork.
 * The fresh request still runs; genuinely changed rows always replace the old ones.
 */
export function unchangedPublicRows<T>(current: T[], incoming: T[]): T[] {
  if (current.length !== incoming.length) return incoming;
  return JSON.stringify(current) === JSON.stringify(incoming) ? current : incoming;
}
