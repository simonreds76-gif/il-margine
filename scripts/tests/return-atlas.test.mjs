import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import { decodeAtlas } from '../../src/components/return-atlas/decode.mjs';
import { observations, summarise } from '../../src/components/return-atlas/returns-core.mjs';

const root = new URL('../../', import.meta.url);
const release = JSON.parse(fs.readFileSync(new URL('src/data/return-atlas-release.json', root)));
const index = JSON.parse(fs.readFileSync(new URL('public' + release.indexUrl, root)));
const data = decodeAtlas(index, release.checkedAt);

test('static release keeps paired odds, identities and complete lazy histories', () => {
  assert.equal(data.matches.length, release.matches);
  assert.equal(new Set(data.matches.map(m => m.id)).size, release.matches);
  assert.equal(data.players.length, release.players);
  assert.equal(data.matches.map(m => m.date).sort().at(-1), release.through);
  assert.ok(release.checkedAt >= release.through);
  for (const player of data.players) {
    const detail = JSON.parse(fs.readFileSync(new URL(`public${release.detailsBase}/${player.id}.json`, root)));
    assert.equal(detail.playerId, player.id);
    assert.equal(detail.version, release.version);
    assert.deepEqual(detail.matches.map(m => m[0]).sort(), data.matches.filter(m => m.p1 === player.id || m.p2 === player.id).map(m => m.id).sort());
    assert.ok(detail.matches.every(([,event,score]) => typeof event === 'string' && event.length && typeof score === 'string' && score.length));
  }
});

test('every player return reconciles to independent flat-stake accounting on both sides', () => {
  for (const player of data.players) for (const side of ['player', 'opponent']) {
    const raw = data.matches.filter(m => m.p1 === player.id || m.p2 === player.id);
    const expected = raw.reduce((total,m) => {
      const backFirst = side === 'player' ? m.p1 === player.id : m.p1 !== player.id;
      return total + (m.winner === (backFirst ? m.p1 : m.p2) ? (backFirst ? m.o1 : m.o2) - 1 : -1);
    }, 0);
    const result = summarise(observations(data.matches, player.id, { side }));
    assert.equal(result.bets, raw.length);
    assert.ok(Math.abs(result.profit - expected) < 1e-8);
    for (const role of ['favourite','underdog']) {
      const on = observations(data.matches, player.id, {role, side:'player'});
      const against = observations(data.matches, player.id, {role, side:'opponent'});
      assert.deepEqual(on.map(m => m.id), against.map(m => m.id));
      assert.equal(summarise(on).wins + summarise(against).wins, on.length);
    }
  }
});

test('season and surface filters partition the same accepted records', () => {
  for (const player of data.players) {
    const all = observations(data.matches, player.id);
    const annual = release.years.flatMap(year => observations(data.matches, player.id, {year}));
    const courts = index.surfaces.flatMap(surface => observations(data.matches, player.id, {surface}));
    assert.deepEqual(annual.map(m=>m.id).sort(), all.map(m=>m.id).sort());
    assert.deepEqual(courts.map(m=>m.id).sort(), all.map(m=>m.id).sort());
  }
});
