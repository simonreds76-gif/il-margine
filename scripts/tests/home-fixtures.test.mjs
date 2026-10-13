import test from 'node:test';
import assert from 'node:assert/strict';
import { footballHomeFeed, tennisHomeFeed, upcomingHomeFixtures, londonDay } from '../../src/lib/home-fixtures.ts';

const now = Date.parse('2026-10-13T12:00:00Z');
test('only upcoming, fresh fixtures appear, in time order rather than return order', () => {
  const fixtures = [{ id: 'later', start: '2026-10-14T12:00:00Z' }, { id: 'started', start: '2026-10-13T12:00:00Z' }, { id: 'next', start: '2026-10-13T13:00:00Z' }];
  const feed = { checkedAt: '2026-10-13T10:00:00Z', expiresAt: '2026-10-14T10:00:00Z', fixtures };
  assert.deepEqual(upcomingHomeFixtures(feed, now).map(f => f.id), ['next', 'later']);
  assert.deepEqual(upcomingHomeFixtures(feed, Date.parse(feed.expiresAt)), []);
  assert.deepEqual(upcomingHomeFixtures({ ...feed, checkedAt: null }, now), []);
  assert.deepEqual(upcomingHomeFixtures({ ...feed, expiresAt: 'invalid' }, now), []);
  assert.equal(fixtures[0].id, 'later');
});
test('day labels respect UK midnight and daylight saving', () => {
  assert.equal(londonDay('2026-10-13T23:15:00Z'), '2026-10-14');
  assert.equal(londonDay('2026-12-13T23:15:00Z'), '2026-12-13');
});
test('football keeps result orientation and unpriced meetings, with exact separate links', () => {
  const record = { count: 2, meetings: 3, results: [2, 0, 1], outcomes: [{ roi: 999 }] };
  const board = { checkedAt: '2026-10-13', expiresAt: '2026-10-20', fixtures: [{ id: 'fm-1', league: 'serie-a', kickoff: '2026-10-14', home: { name: 'A', crest: '/a.png', manager: { id: 'm1', name: 'First', portrait: '/m1.png' } }, away: { name: 'B', crest: null, manager: null }, clubs: record, managers: record }] };
  const f = footballHomeFeed(board).fixtures[0];
  assert.deepEqual(f.history, { meetings: 3, results: [2, 0, 1] });
  assert.equal(f.href, '/football-atlas/fixtures?fixture=fm-1&history=clubs#fm-1');
  assert.equal(f.managers.href, '/football-atlas/fixtures?fixture=fm-1&history=managers#fm-1');
  assert.equal(f.managers.history.meetings, null);
  assert.equal(JSON.stringify(f).includes('999'), false);
});
test('tennis uses existing pair link and does not ship history or odds; zero is not unknown', () => {
  const board = { capturedAt: '2026-10-13T10:00:00Z', fixtures: [{ id: 'a-b', start: '2026-10-14', tour: 'ATP', event: 'Example', players: [{ name: 'A', portrait: null }, { name: 'B', portrait: null }], wins: [0, 0], meetings: 0, href: '/tennis-matchup?player=a&compare=b', history: [{ secret: 'large history' }], quote: { odds: [2, 2] } }] };
  const feed = tennisHomeFeed(board);
  assert.equal(feed.expiresAt, '2026-10-14T10:00:00.000Z');
  assert.equal(feed.fixtures[0].history.meetings, 0);
  assert.equal(feed.fixtures[0].tour, 'ATP');
  assert.equal(feed.fixtures[0].href, board.fixtures[0].href);
  assert.equal(JSON.stringify(feed).includes('large history'), false);
  assert.equal(JSON.stringify(feed).includes('odds'), false);
});
