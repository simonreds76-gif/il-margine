/** Small process-local cache for public, non-personalized payloads only.
 * Coalesces concurrent callers; bounds memory; never retains failed loads.
 * TTL begins when loading starts so slow requests cannot extend freshness.
 */
export function createBoundedAsyncCache<T>(maxEntries: number, now = Date.now) {
  if (!Number.isInteger(maxEntries) || maxEntries < 1) throw new Error("Invalid cache capacity");
  const entries = new Map<string, { expires: number; promise: Promise<T>; pending: boolean }>();
  return {
    get(key: string, ttlMs: number, load: () => Promise<T>): Promise<T> {
      const existing = entries.get(key);
      if (existing && (existing.pending || existing.expires > now())) return existing.promise;
      entries.delete(key);
      if (entries.size >= maxEntries) entries.delete(entries.keys().next().value!);
      const entry: { expires: number; promise: Promise<T>; pending: boolean } = { expires: now() + ttlMs, promise: Promise.resolve(undefined as T), pending: true };
      entry.promise = Promise.resolve().then(load).then(value => {
        entry.pending = false;
        return value;
      }, error => {
        if (entries.get(key) === entry) entries.delete(key);
        throw error;
      });
      entries.set(key, entry);
      return entry.promise;
    },
  };
}
