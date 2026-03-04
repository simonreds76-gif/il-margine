/**
 * Build a URL slug for a tip: "Sakatsume vs Parks" + id 123 → "sakatsume-vs-parks-123".
 * Used for /tips/[slugId] so Google and users see readable URLs.
 */
export function slugifyTip(event: string, id: number): string {
  const slug = (event || "tip")
    .toLowerCase()
    .replace(/[^a-z0-9\s-]/g, "")
    .replace(/\s+/g, "-")
    .replace(/-+/g, "-")
    .replace(/^-|-$/g, "");
  const base = slug || "tip";
  return `${base}-${id}`;
}

/**
 * Extract tip id from a slugId param: "sakatsume-vs-parks-123" → 123.
 * Also accepts plain "123" for backwards compatibility.
 */
export function parseTipSlugId(slugId: string): number | null {
  const trimmed = (slugId || "").trim();
  if (!trimmed) return null;
  if (/^\d+$/.test(trimmed)) return parseInt(trimmed, 10);
  const parts = trimmed.split("-");
  for (let i = parts.length - 1; i >= 0; i--) {
    if (/^\d+$/.test(parts[i]!)) return parseInt(parts[i]!, 10);
  }
  return null;
}
