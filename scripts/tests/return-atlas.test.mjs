import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import { pathToFileURL } from 'node:url';
import path from 'node:path';
import { decodeAtlas } from '../../src/components/return-atlas/decode.mjs';
import { observations, summarise, recentlyActivePlayers, leaderboard, ODDS_BANDS, resolveOddsRange } from '../../src/components/return-atlas/returns-core.mjs';

const root = process.env.RETURN_ATLAS_OUTPUT_ROOT ? pathToFileURL(path.resolve(process.env.RETURN_ATLAS_OUTPUT_ROOT) + path.sep) : new URL('../../', import.meta.url);
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


test('featured pool excludes retired historical leaders without removing their records', () => {
  const current = recentlyActivePlayers(data.matches, data.players, release.checkedAt);
  assert.ok(current.length > 100 && current.length < data.players.length);
  assert.ok(data.players.some(p => p.name === 'Dominic Thiem'));
  assert.ok(!current.some(p => p.name === 'Dominic Thiem'));
  assert.ok(current.some(p => p.name === 'Alexander Shevchenko'));
  const thiem = data.players.find(p => p.name === 'Dominic Thiem');
  assert.ok(observations(data.matches, thiem.id).length > 0);
});

test('activity window uses check date, includes the boundary, and ignores future records', () => {
  const players = [{id:'active',name:'Active'}, {id:'old',name:'Old'}, {id:'future',name:'Future'}, {id:'thiem',name:'Dominic Thiem'}];
  const matches = [{date:'2025-09-19',p1:'active',p2:'thiem'}, {date:'2025-09-18',p1:'old',p2:'old'}, {date:'2026-09-20',p1:'future',p2:'future'}];
  assert.deepEqual(recentlyActivePlayers(matches,players,'2026-09-19').map(p=>p.id),['active']);
});

test('odds bands partition the complete archive without gaps, overlaps or strategy changes', () => {
  for (const player of data.players) {
    const all = observations(data.matches, player.id);
    const partition = ODDS_BANDS.flatMap(band => {
      const on = observations(data.matches, player.id, {oddsRange:band.id});
      const against = observations(data.matches, player.id, {oddsRange:band.id, side:'opponent'});
      assert.deepEqual(on.map(m => m.id), against.map(m => m.id));
      const expected = all.filter(m => m.playerOdds > band.min && m.playerOdds <= band.max);
      assert.deepEqual(on.map(m => m.id), expected.map(m => m.id));
      const profit = expected.reduce((sum,m) => sum + (m.winner === m.opponent ? m.opponentOdds - 1 : -1), 0);
      assert.ok(Math.abs(summarise(against).profit - profit) < 1e-8);
      return on;
    });
    assert.deepEqual(partition.map(m=>m.id).sort(), all.map(m=>m.id).sort());
  }
});

test('full-precision boundaries and custom inclusive ranges use the named player, on either side', () => {
  const fixtures = [1.2,1.205,1.21,1.5,1.8,1.95,2,2.2,2.201,2.5,3.5,5,12].map((price,i) => ({
    id:String(i), date:'2026-05-01', level:'ATP-main',status:'completed',surface:'clay',
    p1:i%2?'opponent':'player',p2:i%2?'player':'opponent',
    o1:i%2?1.9:price,o2:i%2?price:1.9,winner:'player'
  }));
  assert.deepEqual(observations(fixtures,'player',{oddsRange:'1.20-1.50'}).map(r=>r.playerOdds),[1.205,1.21,1.5]);
  const custom={oddsRange:'custom',oddsMin:'1.21',oddsMax:'1.50'};
  assert.deepEqual(observations(fixtures,'player',custom).map(r=>r.playerOdds),[1.21,1.5]);
  assert.equal(summarise(observations(fixtures,'player',{...custom,side:'opponent'})).profit,-2);
  assert.equal(observations(fixtures,'player',{oddsRange:'1.80-2.00',role:'underdog'}).length,2);
  assert.equal(observations(fixtures,'player',{...custom,year:'2025'}).length,0);
  assert.equal(observations(fixtures,'player',{...custom,surface:'grass'}).length,0);
  assert.equal(observations(fixtures,'player',{oddsRange:'custom',oddsMin:2,oddsMax:2}).length,1);
  for (const invalid of [{oddsRange:'bad'}, {...custom,oddsMin:3}, {...custom,oddsMin:1}, {...custom,oddsMax:'NaN'}]) {
    assert.equal(resolveOddsRange(invalid),null);
    assert.deepEqual(observations(fixtures,'player',invalid),[]);
  }
  assert.equal(observations(fixtures,'player',{oddsRange:'custom',oddsMin:5}).length,2);
  assert.equal(observations(fixtures,'player',{oddsRange:'custom'}).length,fixtures.length);
  assert.equal(leaderboard(fixtures,[{id:'player',name:'Player'}],{...custom,minimum:3}).length,0);
  assert.equal(leaderboard(fixtures,[{id:'player',name:'Player'}],{...custom,minimum:2})[0].bets,2);
});
