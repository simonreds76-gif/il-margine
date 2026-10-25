import fs from 'node:fs';
import assert from 'node:assert/strict';

const read = p => JSON.parse(fs.readFileSync(p, 'utf8'));
const release = read('src/data/covered-leagues-release.json');
const original = read('src/data/atlas-fixtures.json');
const football = read('src/data/football-atlas-release.json');
const managers = read('src/data/manager-atlas-release.json');
const expanded = read(`public${release.boardUrl}`);
const history = read(`public${release.historyUrl}`);
const oldEvidence = read(`public${original.evidenceUrl}`).fixtures;
const newEvidence = read(`public${expanded.evidenceUrl}`).fixtures;
assert.equal(release.scope, 'historical-clubs-only');
assert.equal(release.baseBoardVersion, original.version);
assert.equal(release.footballVersion, football.version);
assert.equal(release.managerVersion, managers.version);
assert.equal(expanded.version, release.version);
assert.equal(history.rows.length, release.matches);
assert.equal(history.rows.filter(r => r[8] !== null).length, release.priced);
assert.deepEqual(history.managerRows, []);
assert(history.rows.every(r => r[2] === 'championship'));
const fixtures = new Map(original.fixtures.map(f => [f.id, f]));
assert.equal(expanded.fixtures.length, fixtures.size);
assert.equal(new Set(expanded.fixtures.map(f => f.id)).size, fixtures.size);
for (const f of expanded.fixtures) {
  const before = fixtures.get(f.id);
  assert(before, `Unexpected upcoming fixture ${f.id}`);
  assert.notEqual(f.league, 'championship');
  for (const key of ['league', 'round', 'kickoff', 'home', 'away', 'managers']) assert.deepEqual(f[key], before[key]);
  assert.deepEqual(newEvidence[f.id].managers, oldEvidence[f.id].managers);
  const oldRows = new Map(oldEvidence[f.id].clubs.map(r => [r.id, r]));
  const newRows = new Map(newEvidence[f.id].clubs.map(r => [r.id, r]));
  for (const [id, row] of oldRows) assert.deepEqual(newRows.get(id), row);
  for (const [id, row] of newRows) if (!oldRows.has(id)) assert.equal(row.league, 'championship');
}
console.log(`Historical-only release validated: ${release.matches} Championship results; ${fixtures.size} original fixtures and all manager records preserved.`);
