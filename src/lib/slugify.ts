/**
 * Build a readable tip URL slug.
 * Example: "Sakatsume vs Parks" + id 123 -> "sakatsume-vs-parks-betting-tip-123".
 */
export function slugifyTip(event: string, id: number): string {
  const slug = (event || "tip")
    .toLowerCase()
    .replace(/[^a-z0-9\s-]/g, "")
    .replace(/\s+/g, "-")
    .replace(/-+/g, "-")
    .replace(/^-|-$/g, "");
  const base = slug || "tip";
  return `${base}-betting-tip-${id}`;
}

/**
 * Extract a tip id from a slug or plain numeric id.
 */
export function parseTipSlugId(slugId: string): number | null {
  const trimmed = (slugId || "").trim();
  if (!trimmed) return null;
  if (/^\d+$/.test(trimmed)) return parseInt(trimmed, 10);
  const parts = trimmed.split("-");
  for (let i = parts.length - 1; i >= 0; i -= 1) {
    if (/^\d+$/.test(parts[i]!)) return parseInt(parts[i]!, 10);
  }
  return null;
}
