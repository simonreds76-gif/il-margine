export type BoardPlayer = {
  id: string; name: string; number?: string | number | null; role: string; lineIndex?: number | null;
  photoUrl?: string | null; modelProbability: number | null; fairOdds: number | null;
  bookmakerOdds: number | null; priceCapturedAt: string | null; expectedMinutes: number | null;
  modelGeneratedAt: string | null; modelVersion: string | null; pricingStatus: string;
  penaltyActive: boolean; penaltyInheritedFrom: string | null;
};
export type BoardTeam = { name: string; formation: string; players: BoardPlayer[]; substitutes: string[]; primaryColor?: string; secondaryColor?: string; logoPath?: string;
  lineupComplete: boolean; activePenaltyTaker: string | null; penaltyInheritedFrom: string | null };
export type BoardFixture = { id: string; league: string; competition: string; date: string; kickoffUtc: string;
  lineupStatus: "expected" | "confirmed" | "pending"; lineupObservedAt: string | null; lineupChangedAt: string | null; teams: BoardTeam[] };
export type DailyBoard = { schemaVersion: number; generatedAt: string | null; fixtures: BoardFixture[]; leaguesCovered: string[] };
export const emptyBoard: DailyBoard = { schemaVersion: 1, generatedAt: null, fixtures: [], leaguesCovered: [] };
export function isDailyBoard(value: unknown): value is DailyBoard {
  if (!value || typeof value !== "object") return false;
  const b = value as DailyBoard;
  return b.schemaVersion === 1 && Array.isArray(b.fixtures) && b.fixtures.every(f =>
    typeof f.id === "string" && typeof f.date === "string" && Number.isFinite(Date.parse(f.kickoffUtc)) &&
    Array.isArray(f.teams) && f.teams.length === 2 && f.teams.every(t => typeof t.name === "string" &&
      Array.isArray(t.players) && t.players.every(p => typeof p.name === "string" && typeof p.id === "string" &&
        (p.modelProbability === null || typeof p.modelProbability === "number" && p.modelProbability > 0 && p.modelProbability < 1) &&
        (p.bookmakerOdds === null || typeof p.bookmakerOdds === "number" && Number.isFinite(p.bookmakerOdds) && p.bookmakerOdds > 1))));
}
