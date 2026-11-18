import type { ModelRow } from "./admin-model-summary";

const catalogue = [
  ["match", "Tennis", "Match odds"],
  ["challenger", "Tennis", "Challenger match odds"],
  ["indoor", "Tennis", "Indoor Scout"],
  ["shape", "Tennis", "Total games & handicaps"],
  ["props", "Tennis", "Aces & double faults"],
  ["compass", "Tennis", "Ace Compass"],
  ["most-aces", "Tennis", "Most Aces 1X2"],
  ["most-df", "Tennis", "Most Double Faults 1X2"],
  ["breaks", "Tennis", "Break-point chances"],
  ["sisal", "Tennis", "Sisal 50/50"],
  ["shots", "Football", "Team shots"],
  ["corners", "Football", "Corners"],
  ["keepers", "Football", "Goalkeeper saves"],
  ["skyline", "Football", "Skyline · headed shots on target"],
  ["goals", "Football", "Goalscorers"],
  ["other-tennis", "Tennis", "Other tennis models"],
  ["other-football", "Football", "Other football models"],
  ["other", "Other", "Other running models"],
] as const;

type FamilyId = typeof catalogue[number][0];
const dedicatedPanels: FamilyId[] = ["shape", "breaks", "sisal", "shots", "skyline", "goals"];

function familyFor(row: ModelRow): FamilyId {
  const id = row.id;
  if (id.startsWith("ace-compass-")) return "compass";
  if (id.startsWith("most-aces-")) return "most-aces";
  if (id === "most-df") return "most-df";
  if (id === "challenger" || id.startsWith("challenger-") || id === "tennis_hardcourt_scout" || id.startsWith("scout-")) return "challenger";
  if (id.startsWith("tennis_indoor_")) return "indoor";
  if (id === "spread_v1" || id === "slam-bo5") return "shape";
  if (id === "props" || /^(props-|aces-v|trend-|venue-aces)/.test(id)) return "props";
  if (/^(gk($|[-_])|keeper-)/.test(id)) return "keepers";
  if (id.startsWith("team_shots")) return "shots";
  if (id.startsWith("corners")) return "corners";
  if (["strict","volume_200","provisional_hard","provisional_expansion","astra","tennis_astrissimo","first-return","category-calibration","atp-overlays","grass_bo3","clay_bo3"].includes(id)) return "match";
  if (row.group.includes("Football")) return "other-football";
  if (row.group.includes("Tennis")) return "other-tennis";
  return "other";
}

export function monitorFamilies(rows: ModelRow[]) {
  const assigned = new Map(rows.map(row => [row.id, familyFor(row)]));
  // Preserve the published group-N bookmarks in the original group order.
  const oldGroups = [...new Set(rows.filter(row => !row.id.startsWith("props-")).map(row => row.group))];
  const anchors = oldGroups.map((group, i) => ({
    id: `group-${i}`,
    family: assigned.get(rows.find(row => row.group === group)!.id),
  }));
  return catalogue.map(([id, sport, label]) => ({
    id, sport, label,
    rows: rows.filter(row => assigned.get(row.id) === id),
    aliases: anchors.filter(anchor => anchor.family === id).map(anchor => anchor.id),
  })).filter(family => family.rows.length > 0 || dedicatedPanels.includes(family.id));
}
