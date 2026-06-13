export const WORLD_CUP_TIP_IMAGE_PATH = "/brand/world-cup-2026-free-picks.png";

export function normalizeWorldCupCategory(category: string | null | undefined): string {
  return (category || "")
    .toLowerCase()
    .replace(/[^a-z0-9]/g, "");
}

export function isWorldCupCategory(category: string | null | undefined): boolean {
  const normalized = normalizeWorldCupCategory(category);
  return (
    normalized === "worldcup" ||
    normalized === "worldcup2026" ||
    normalized === "fifaworldcup" ||
    normalized === "fifaworldcup2026" ||
    normalized === "wc" ||
    normalized === "wc2026"
  );
}

export function isWorldCupPropsTip(value: {
  market?: string | null;
  category?: string | null;
}): boolean {
  return (value.market || "").toLowerCase() === "props" && isWorldCupCategory(value.category);
}
