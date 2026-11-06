import type { PenaltyArticle } from './penalty-news';
import type { FixtureBoard } from '@/components/football-atlas/fixtures/types';

// Original preview cohort, retained for regression checks. The shared layout now
// covers all current clubs; the observational GSC baseline is not an A/B test.
export const PENALTY_GROWTH_PAGES = [
  'epl/chelsea', 'epl/sunderland', 'ligue-1/paris-saint-germain',
  'serie-a/atalanta', 'serie-a/bologna', 'ligue-1/rennes', 'ligue-1/lorient',
  'la-liga/real-madrid', 'bundesliga/werder-bremen', 'bundesliga/sv-elversberg',
] as const;

export function isPenaltyGrowthPage(league: string, slug: string, archived = false) {
  return !archived && Boolean(slug) && ['epl', 'serie-a', 'la-liga', 'bundesliga', 'ligue-1'].includes(league);
}

export function recordedClubPenalties(articles: PenaltyArticle[], clubUrl: string, coverageStart: string) {
  const unique = new Map<string, PenaltyArticle>();
  for (const article of articles) {
    if (article.clubUrl !== clubUrl || !article.matchId || !article.eventId || !article.slug
      || !Number.isFinite(Date.parse(article.kickoff)) || article.date < coverageStart) continue;
    const key = `${article.matchId}:${article.eventId}`;
    const previous = unique.get(key);
    if (!previous || article.updatedAt > previous.updatedAt) unique.set(key, article);
  }
  return [...unique.values()].sort((a, b) => b.kickoff.localeCompare(a.kickoff)
    || b.eventId.localeCompare(a.eventId, 'en', { numeric: true }));
}

export type ClubFixtureLink = {
  id: string; kickoff: string; home: string; away: string; homeCrest: string | null;
  awayCrest: string | null; href: string;
};
type ClubLogoMap = { leagues?: Record<string, { teams?: Record<string, { logo_path?: string; fotmob_team_id?: number | string }> }> };
export function clubFixtureLinks(board: FixtureBoard, league: string, crest: string, identities?: ClubLogoMap): ClubFixtureLink[] {
  if (!crest) return [];
  const fixtureLeague = league === 'epl' ? 'premier-league' : league;
  const ids = [...new Set(Object.values(identities?.leagues?.[league]?.teams ?? {})
    .filter(row => row.logo_path === crest && row.fotmob_team_id)
    .map(row => String(row.fotmob_team_id)))];
  if (ids.length > 1) return []; // An ambiguous identity cannot produce a fixture link.
  // Prefer the existing exact team ID: Atlas and penalty pages can use different crest files.
  // Without an ID, only an identical crest in the same league is accepted; no fuzzy names.
  return board.fixtures.filter(f => f.league === fixtureLeague && (ids.length
    ? f.home.providerId === ids[0] || f.away.providerId === ids[0]
    : f.home.crest === crest || f.away.crest === crest))
    .map(f => ({ id: f.id, kickoff: f.kickoff, home: f.home.name, away: f.away.name,
      homeCrest: f.home.crest, awayCrest: f.away.crest,
      href: `/football-atlas/fixtures?fixture=${encodeURIComponent(f.id)}&history=clubs#${encodeURIComponent(f.id)}` }));
}
export function nextClubFixture(fixtures: ClubFixtureLink[], checkedAt: string, expiresAt: string, now: number) {
  if (!Number.isFinite(Date.parse(checkedAt)) || !Number.isFinite(Date.parse(expiresAt))
    || Date.parse(checkedAt) > now || now >= Date.parse(expiresAt)) return null;
  return fixtures.filter(f => Date.parse(f.kickoff) > now)
    .sort((a, b) => Date.parse(a.kickoff) - Date.parse(b.kickoff) || a.id.localeCompare(b.id))[0] ?? null;
}

export function sameEvidenceText(a: string, b: string) {
  const tidy = (text: string) => text.replace(/\s+/g, ' ').trim();
  return Boolean(tidy(a)) && tidy(a) === tidy(b);
}
