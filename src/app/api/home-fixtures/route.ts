import board from '@/data/atlas-fixtures.json';
import type { FixtureBoard } from '@/components/football-atlas/fixtures/types';
import { getTennisMatchday } from '@/lib/tennis-matchday-data';
import { footballHomeFeed, tennisHomeFeed, upcomingHomeFixtures } from '@/lib/home-fixtures';

// One shared hourly response. No bookmaker requests and no browser polling.
export const dynamic = 'force-static';
export const revalidate = 3600;
export async function GET() {
  const football = footballHomeFeed(board as FixtureBoard);
  const tennis = tennisHomeFeed(await getTennisMatchday());
  const now = Date.now();
  return Response.json({ football: { ...football, fixtures: upcomingHomeFixtures(football, now, 36) }, tennis: { ...tennis, fixtures: ['ATP', 'Challenger'].flatMap(tour => upcomingHomeFixtures({ ...tennis, fixtures: tennis.fixtures.filter(f => f.tour === tour) }, now, 24)) } });
}
