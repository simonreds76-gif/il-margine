import type { TipPortrait } from "./tip-artwork-types";
import { foldNameText } from "./player-name-matching";

export const PROP_LABELS = {
  saves: "Goalkeeper saves", shots: "Shots", sot: "Shots on target", tackles: "Tackles",
  fouls: "Fouls committed", foulsWon: "Fouls won", cards: "Cards", goals: "Goalscorer",
  assists: "Assists", passes: "Passes", offsides: "Offsides", team: "Team / match bets", other: "Other selections",
} as const;
export type PropKey = keyof typeof PROP_LABELS;
export type PropRow = { artwork?: TipPortrait[]; id: number; event: string; player: string | null; selection: string; status: string; stake: number; profit_loss?: number | null; odds?: number | null; date?: string | null; match_date?: string | null; category?: string };
const normal = (s: string) => foldNameText(s).toLowerCase().replace(/\s+/g, " ").trim();

export function classifyProp(row: Pick<PropRow, "event" | "player" | "selection">): PropKey {
  const player = normal(row.player || ""), selection = normal(row.selection);
  const sides = row.event.split(/\s+(?:vs?\.?|versus)\s+|\s+[–—]\s+/i).map(normal);
  if (/\b(total|match|both teams|first goal method)\b/.test(player) || sides.includes(player)) return "team";
  const text = `${player} ${selection}`;
  if (/\b(and|or)\b|\s&\s/.test(selection)) {
    // Do not attribute combination bets to one leg. "2 or More Goals" is one market.
    if (!/\b\d+ or more goals\b/.test(selection)) return "other";
  }
  if (/\bsaves?\b/.test(text)) return "saves";
  if (/\bshots? on target\b|\bsot\b/.test(text)) return "sot";
  if (/\bshots?\b/.test(text)) return "shots";
  if (/\btackles?\b/.test(text)) return "tackles";
  if (/\bfouls? won\b/.test(text)) return "foulsWon";
  if (/\bfouls?\b/.test(text) || /^over \d+(?:\.\d+)? fous$/.test(selection)) return "fouls";
  if (/\bcards?\b|\bbooked\b/.test(text)) return "cards";
  if (/\bgoals?\b|\bgoalscorer\b|\bscore\b/.test(text)) return "goals";
  if (/\bassists?\b/.test(text)) return "assists";
  if (/\boffsides?\b/.test(text)) return "offsides";
  if (/\bpasses\b/.test(text)) return "passes";
  if (/\bcorners?\b/.test(text)) return "team";
  return "other";
}

export function buildPropPerformance(rows: PropRow[], pending: PropRow[] = []) {
  const buckets = new Map<PropKey, { key: PropKey; label: string; rows: PropRow[]; pending: PropRow[]; stake: number; profit: number; wins: number; losses: number; roi: number | null }>();
  const bucket = (key: PropKey) => {
    if (!buckets.has(key)) buckets.set(key, { key, label: PROP_LABELS[key], rows: [], pending: [], stake: 0, profit: 0, wins: 0, losses: 0, roi: null });
    return buckets.get(key)!;
  };
  const seen = new Set<number>();
  for (const row of rows) {
    if (seen.has(row.id) || !["won", "lost"].includes(row.status) || row.profit_loss == null || !Number.isFinite(row.profit_loss) || !Number.isFinite(row.stake) || row.stake <= 0) continue;
    seen.add(row.id);
    const item = bucket(classifyProp(row));
    item.rows.push(row); item.stake += row.stake; item.profit += row.profit_loss;
    if (row.status === "won") item.wins++; else item.losses++;
  }
  for (const row of pending) {
    if (row.status !== "pending" || seen.has(row.id)) continue;
    seen.add(row.id); bucket(classifyProp(row)).pending.push(row);
  }
  return [...buckets.values()].map(item => ({ ...item, roi: item.stake > 0 ? 100 * item.profit / item.stake : null,
    rows: item.rows.sort((a, b) => (b.date || b.match_date || "").localeCompare(a.date || a.match_date || "") || b.id - a.id),
  }));
}
