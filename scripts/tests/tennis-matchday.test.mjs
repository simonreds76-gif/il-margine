import test from 'node:test';
import assert from 'node:assert/strict';
import { buildTennisMatchday, fixturesFor, matchdayQuote, QUOTE_MAX_AGE_MS } from '../../src/lib/tennis-matchday.mjs';
import { readMatchupResearch } from '../../src/components/return-atlas/research-links.mjs';

const now = new Date('2026-10-09T10:00:00Z');
const row = { captured_at: '2026-10-09T09:00:00Z', league: 'ATP', league_name: 'ATP Shanghai', player1_name: 'Player One', player2_name: 'Player Two', kickoff_iso: '2026-10-10T05:00:00Z' };
const history = { asOf: '2026-10-09', through: '2026-10-08', version: 'test',
  players: [{ id: 'one', name: 'Player One' }, { id: 'two', name: 'Player Two' }],
  matches: [['2026-01-01', 0, 1, 0, 2.5, 1.6, 'clay'], ['2026-03-01', 1, 0, 0, 3, 1.5, 'outdoor-hard'], ['2026-10-09', 0, 1, 0, 10, 1.1, 'grass']] };

test('H2H uses exact identities, correct odds orientation and no same-day or future results', () => {
  const { fixtures } = buildTennisMatchday([row], history, now), f = fixtures[0];
  assert.deepEqual(f.wins, [1, 1]); assert.deepEqual(f.roi, [25, 50]); assert.equal(f.priced, 2);
  const selected = readMatchupResearch(new URL(f.href, 'https://ilmargine.bet').search, history.players);
  assert.deepEqual(selected, { ids: ['one', 'two'], surface: 'all', missing: false, ready: true, mode: 'h2h', months: 'archive' });
});
test('unknown, ambiguous and similar names never become another player or a zero-zero career record', () => {
  const f = buildTennisMatchday([{ ...row, player1_name: 'Player Ones' }], history, now).fixtures[0];
  assert.equal(f.meetings, null); assert.equal(f.href, null); assert.deepEqual(f.roi, [null, null]);
  const duplicate = { ...history, players: [...history.players, { id: 'other', name: 'Player One' }] };
  assert.equal(buildTennisMatchday([row], duplicate, now).fixtures[0].meetings, null);
});
test('recorded alias and accent normalization preserve stable identities', () => {
  const h = { ...history, players: [{ id: 'vbt-10698', name: 'Jaume Antoni Munar Clar' }, { id: 'two', name: 'Pláyer Two' }] };
  const f = buildTennisMatchday([{ ...row, player1_name: 'Jaume Munar' }], h, now).fixtures[0];
  assert.equal(f.players[0].id, 'vbt-10698'); assert.equal(f.players[1].id, 'two');
  const variant = { ...history, players: [{ id: 'vbt-9023', name: 'Taylor Harry Fritz' }, { id: 'vbt-25003', name: 'Bu Yunchaokete' }] };
  const linked = buildTennisMatchday([{ ...row, player1_name: 'Taylor Fritz', player2_name: 'Yunchaokete Bu' }], variant, now).fixtures[0];
  assert.deepEqual(linked.players.map(p => p.id), ['vbt-9023', 'vbt-25003']);
});
test('stale, future-dated or mixed captures fail closed', () => {
  assert.equal(buildTennisMatchday([{ ...row, captured_at: '2026-10-07T09:00:00Z' }], history, now).fixtures.length, 0);
  assert.equal(buildTennisMatchday([{ ...row, captured_at: '2026-10-10T09:00:00Z' }], history, now).stale, true);
  assert.equal(buildTennisMatchday([row, { ...row, captured_at: '2026-10-09T08:00:00Z' }], history, now).stale, true);
});
test('started, doubles and placeholders are excluded; named qualifying remains eligible', () => {
  for (const patch of [{ kickoff_iso: now.toISOString() }, { player1_name: 'A / B' }, { player1_name: 'Qualifier' }, { league_name: 'ATP Shanghai Doubles' }]) {
    assert.equal(buildTennisMatchday([{ ...row, ...patch }], history, now).fixtures.length, 0);
  }
  const f = buildTennisMatchday([{ ...row, league_name: 'ATP Shanghai Qualifying' }], history, now).fixtures[0];
  assert.equal(f.qualifying, true);
});
test('conflicting fixture start times do not produce duplicate or arbitrarily timed cards', () => {
  assert.equal(buildTennisMatchday([row, { ...row, kickoff_iso: '2026-10-10T07:00:00Z' }], history, now).fixtures.length, 0);
});
test('zero meetings is separate from unavailable coverage and missing odds never dilute ROI', () => {
  assert.equal(buildTennisMatchday([row], { ...history, matches: [] }, now).fixtures[0].meetings, 0);
  const h = { ...history, matches: [...history.matches, ['2026-05-01', 0, 1, 0, null, 2, 'clay']] };
  const f = buildTennisMatchday([row], h, now).fixtures[0];
  assert.equal(f.meetings, 3); assert.equal(f.priced, 2); assert.deepEqual(f.roi, [25, 50]);
});
test('tomorrow follows UK calendar over the autumn clock change; past fixtures disappear', () => {
  const fixtures = [{ start: '2026-10-26T01:00:00Z', tour: 'ATP', event: 'Test', players: [{ name: 'Player One' }] }];
  assert.equal(fixturesFor(fixtures, 'tomorrow', 'ATP', '', new Date('2026-10-24T23:30:00Z')).length, 1);
  assert.equal(fixturesFor(fixtures, 'upcoming', 'ATP', '', new Date('2026-10-26T02:00:00Z')).length, 0);
});
test('invalid or repeated URL identities never initialise a different H2H', () => {
  assert.equal(readMatchupResearch('?player=one&compare=one', history.players).ready, false);
  assert.equal(readMatchupResearch('?player=one&compare=unknown', history.players).ready, false);
});

test('all five meetings reconcile two independently positive returns without dropping precision', () => {
  const matches = [
    ['2024-07-06', 0, 1, 0, 1.503, 2.79, 'grass'],
    ['2025-02-14', 0, 1, 0, 1.251, 4.45, 'indoor-hard'],
    ['2025-02-25', 0, 1, 0, 1.213, 4.89, 'outdoor-hard'],
    ['2026-07-03', 1, 0, 0, 5.33, 1.196, 'grass'],
    ['2026-10-03', 0, 1, 0, 1.161, 5.99, 'outdoor-hard'],
  ];
  const f = buildTennisMatchday([row], { ...history, matches: matches.toReversed() }, now).fixtures[0];
  assert.equal(f.history.length, 5);
  assert.deepEqual(f.history.map(m => m.date), matches.map(m => m[0]).toReversed());
  assert.deepEqual(f.wins, [4, 1]);
  assert.deepEqual(f.roi, [2.6, 6.6]);
  assert.deepEqual(f.profit, [.128, .33]);
  assert.deepEqual(f.history[1].odds, [1.196, 5.33]);
  assert.equal(f.history[1].winner, 1);
  for (const side of [0, 1]) {
    const pounds = f.history.reduce((sum, m) => sum + Math.round((m.winner === side ? m.odds[side] - 1 : -1) * 1000), 0) / 100;
    assert.equal(pounds, side === 0 ? 1.28 : 3.3);
  }
});

test('current paired prices stay with named players when the feed order reverses', () => {
  const f = buildTennisMatchday([{ ...row, player1_name: 'Player Two', player2_name: 'Player One', odds1: '6.04', odds2: 1.153 }], history, now).fixtures[0];
  assert.deepEqual(f.players.map(p => p.id), ['two', 'one']);
  assert.deepEqual(matchdayQuote(f, now).odds, [6.04, 1.153]);
  assert.equal(f.quote.capturedAt, row.captured_at);
  assert.deepEqual(f.roi, [50, 25]); // Current prices do not change historical returns.
  for (const missing of [null, '', 1, 'bad']) {
    assert.equal(buildTennisMatchday([{ ...row, odds1: 1.153, odds2: missing }], history, now).fixtures[0].quote, null);
  }
});

test('quotes expire independently of the schedule and stop at the start time', () => {
  const f = buildTennisMatchday([{ ...row, odds1: 1.153, odds2: 6.04 }], history, now).fixtures[0];
  assert.ok(matchdayQuote(f, now));
  const expired = new Date(Date.parse(row.captured_at) + QUOTE_MAX_AGE_MS);
  assert.equal(matchdayQuote(f, expired), null);
  assert.equal(buildTennisMatchday([row], history, expired).fixtures.length, 1);
  assert.equal(matchdayQuote({ ...f, start: now.toISOString() }, now), null);
  assert.equal(matchdayQuote({ ...f, quote: { ...f.quote, capturedAt: '2026-10-09T11:00:00Z' } }, now), null);
});
