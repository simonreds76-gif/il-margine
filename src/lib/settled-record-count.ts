/** Public settled counts include wins and losses, excluding pending and void picks. */
export function settledRecordCount(row?: { wins?: number; losses?: number } | null): number {
  return Number(row?.wins ?? 0) + Number(row?.losses ?? 0);
}
