export type FixturePlayer = { id: string | null; name: string; portrait: string | null };
export type MatchdayQuote = { capturedAt: string; bookmaker: string; odds: number[] };
export type TennisFixture = { id: string; start: string; tour: string; event: string; qualifying: boolean; players: FixturePlayer[]; wins: number[] | null; meetings: number | null; priced: number; roi: (number | null)[]; profit: number[]; history: { date: string; winner: number; odds: (number | null)[]; surface: string; score: string; event: string; competition?: string | null; priceBasis?: string | null }[]; quote: MatchdayQuote | null; href: string | null; ambiguous: boolean };
export type TennisBoard = { capturedAt: string | null; historyThrough: string; historyVersion: string; stale: boolean; excluded: Record<string, number>; fixtures: TennisFixture[] };
export function buildTennisMatchday(rows: Record<string, unknown>[], history: unknown, now?: Date): TennisBoard;
export const QUOTE_MAX_AGE_MS: number;
export function matchdayQuote(fixture: TennisFixture, now?: Date): MatchdayQuote | null;
export function fixturesFor(fixtures: TennisFixture[], filter: string, tour: string, search: string, now: Date, zone?: string): TennisFixture[];
export function matchdayHref(a: string, b: string): string;
