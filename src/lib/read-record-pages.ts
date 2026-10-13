// Stay below the database response cap; never publish a silently truncated record.
export async function readRecordPages<T>(read: (from: number, to: number) => Promise<T[]>, pageSize = 500, maxPages = 100): Promise<T[]> {
  const rows: T[] = [];
  for (let page = 0; page < maxPages; page++) {
    const batch = await read(page * pageSize, (page + 1) * pageSize - 1);
    rows.push(...batch);
    if (batch.length < pageSize) return rows;
  }
  throw new Error('Record exceeds the bounded pagination limit; refusing a partial total');
}
