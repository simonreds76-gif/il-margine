import type { FixtureBoard } from '@/components/football-atlas/fixtures/types';
import type { TennisBoard } from './tennis-matchday.mjs';

export type HomePerson = { name: string; image: string | null };
export type HomeHistory = { results: number[] | null; meetings: number | null };
export type HomeFixture = { id: string; start: string; competition: string; tour?: string; sides: HomePerson[]; history: HomeHistory; href: string | null; managers?: { sides: HomePerson[]; history: HomeHistory; href: string } };
export type HomeFeed = { checkedAt: string | null; expiresAt: string | null; fixtures: HomeFixture[] };
export type HomeFixturesData = { football: HomeFeed; tennis: HomeFeed };
export const londonDay = (time: string | number) => new Intl.DateTimeFormat('en-CA', { timeZone: 'Europe/London', year: 'numeric', month: '2-digit', day: '2-digit' }).format(new Date(time));
export function upcomingHomeFixtures(feed: HomeFeed, now: number, limit = 2) {
  if (!feed.checkedAt || !feed.expiresAt || !Number.isFinite(Date.parse(feed.expiresAt)) || now >= Date.parse(feed.expiresAt)) return [];
  return feed.fixtures.filter(f => Date.parse(f.start) > now).sort((a, b) => Date.parse(a.start) - Date.parse(b.start) || a.id.localeCompare(b.id)).slice(0, limit);
}
const leagues: Record<string, string> = { 'premier-league': 'Premier League', 'serie-a': 'Serie A', 'la-liga': 'La Liga', bundesliga: 'Bundesliga', 'ligue-1': 'Ligue 1' };
export function footballHomeFeed(board: FixtureBoard): HomeFeed {
  return { checkedAt: board.checkedAt, expiresAt: board.expiresAt, fixtures: board.fixtures.map(f => {
    const href = `/football-atlas/fixtures?fixture=${encodeURIComponent(f.id)}`;
    const summary = (record: typeof f.clubs): HomeHistory => ({ results: record.results ?? null, meetings: record.meetings ?? null });
    return { id: f.id, start: f.kickoff, competition: leagues[f.league] ?? f.league, sides: [f.home, f.away].map(c => ({ name: c.name, image: c.crest })), history: summary(f.clubs), href: `${href}&history=clubs#${f.id}`, managers: { sides: [f.home, f.away].map(c => ({ name: c.manager?.name ?? 'Manager unconfirmed', image: c.manager?.portrait ?? null })), history: f.home.manager?.id && f.away.manager?.id ? summary(f.managers) : { results: null, meetings: null }, href: `${href}&history=managers#${f.id}` } };
  }) };
}
export function tennisHomeFeed(board: TennisBoard): HomeFeed {
  return { checkedAt: board.capturedAt, expiresAt: board.capturedAt ? new Date(Date.parse(board.capturedAt) + 86400000).toISOString() : null, fixtures: board.fixtures.map(f => ({ id: f.id, start: f.start, tour: f.tour, competition: `${f.event}${f.qualifying ? ' · Qualifying' : ''}`, sides: f.players.map(p => ({ name: p.name, image: p.portrait })), history: { results: f.wins, meetings: f.meetings }, href: f.href })) };
}
