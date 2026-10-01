import { test } from 'node:test';
import assert from 'node:assert/strict';
import { bothPositiveOutcomes, matchesHistoryFilter } from '../../src/components/football-atlas/fixtures/history-filter.ts';
import board from '../../src/data/atlas-fixtures.json' with { type: 'json' };

function fixture(managerRoi, clubRoi, managerCount = 3, clubCount = 3) {
  const record = (values, count) => ({ count, outcomes: values.map(roi => ({ roi, positive: roi > 0 })) });
  return { home: { manager: { id: 'a', status: 'verified' } }, away: { manager: { id: 'b', status: 'verified' } }, managers: record(managerRoi, managerCount), clubs: record(clubRoi, clubCount) };
}

test('positive manager draw and club home do not form a same-outcome match', () => {
  const f = fixture([-10, 20, -30], [15, -20, -40]);
  assert.equal(matchesHistoryFilter(f, 'any', 'all'), true);
  assert.equal(matchesHistoryFilter(f, 'both', 'all'), false);
});

test('each outcome qualifies separately and the outcome filter follows the same column', () => {
  for (const [index, name] of ['home', 'draw', 'away'].entries()) {
    const values = [-10, -20, -30]; values[index] = 5;
    const f = fixture(values, values);
    assert.deepEqual(bothPositiveOutcomes(f), [index]);
    assert.equal(matchesHistoryFilter(f, 'both', name), true);
    for (const other of ['home', 'draw', 'away'].filter(value => value !== name)) {
      assert.equal(matchesHistoryFilter(f, 'both', other), false);
    }
  }
});

test('both histories need three meetings and strictly positive ROI', () => {
  for (const counts of [[2, 20], [20, 2], [0, 0]]) {
    assert.equal(matchesHistoryFilter(fixture([10, -1, -1], [20, -1, -1], ...counts), 'both', 'all'), false);
  }
  const zero = fixture([0, -1, -1], [20, -1, -1]);
  zero.managers.outcomes[0].positive = true;
  assert.equal(matchesHistoryFilter(zero, 'both', 'all'), false);
  zero.managers.outcomes[0].roi = null;
  assert.equal(matchesHistoryFilter(zero, 'both', 'all'), false);
});

test('unverified managers and stale snapshots never qualify as both positive', () => {
  const f = fixture([5, 10, -1], [15, 20, -1]);
  assert.equal(matchesHistoryFilter(f, 'both', 'draw', true), false);
  assert.deepEqual(bothPositiveOutcomes(f, true), []);
  assert.equal(matchesHistoryFilter(f, 'all', 'draw', true), true);
  f.home.manager.status = 'unmatched';
  assert.equal(matchesHistoryFilter(f, 'both', 'all'), false);
  assert.equal(matchesHistoryFilter(f, 'any', 'draw'), true); // Verified club history still qualifies.
  f.home.manager = null;
  assert.deepEqual(bothPositiveOutcomes(f), []);
});

test('Barcelona Getafe qualifies on the draw; Betis Barcelona does not qualify on different outcomes', () => {
  const barca = fixture([4, 14.25, -100], [-5.58, 98.42, -80.5], 4, 26);
  const betis = fixture([-100, 161.5, -19], [-17.31, -35.54, 17.31], 4, 26);
  assert.deepEqual(bothPositiveOutcomes(barca), [1]);
  assert.equal(matchesHistoryFilter(barca, 'both', 'draw'), true);
  assert.equal(matchesHistoryFilter(barca, 'both', 'home'), false);
  assert.equal(matchesHistoryFilter(betis, 'both', 'all'), false);
});

test('all generated fixture alignments match the independent frontend eligibility check', () => {
  for (const f of board.fixtures) assert.deepEqual(bothPositiveOutcomes(f), f.alignment, f.id);
});
