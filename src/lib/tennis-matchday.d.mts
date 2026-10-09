export type FixturePlayer = { id: string | null; name: string; portrait: string | null };
export type TennisFixture = { id: string; start: string; tour: string; event: string; qualifying: boolean; players: FixturePlayer[]; wins: number[] | null; meetings: number | null; priced: number; roi: (number | null)[]; profit: number[]; recent: { date: string; winner: number; surface: string; score: string; event: string }[]; href: string | null; ambiguous: boolean };
export type TennisBoard = { capturedAt: string | null; historyThrough: string; historyVersion: string; stale: boolean; excluded: Record<string, number>; fixtures: TennisFixture[] };
export function buildTennisMatchday(rows: Record<string, string>[], history: unknown, now?: Date): TennisBoard;
export function fixturesFor(fixtures: TennisFixture[], filter: string, tour: string, search: string, now: Date, zone?: string): TennisFixture[];
export function matchdayHref(a: string, b: string): string;
