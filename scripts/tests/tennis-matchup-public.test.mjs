import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import { rowsFor, summary } from '../../src/app/tennis-matchup/runtime/core.mjs';

test('published player shards keep H2H totals and swapped statistics consistent',()=>{
  const release=JSON.parse(fs.readFileSync('src/data/tennis-matchup-release.json','utf8'));
  const base='public'+release.indexUrl.replace('/index.json','/');
  const index=JSON.parse(fs.readFileSync(base+'index.json','utf8'));
  const a=index.players.findIndex(p=>p.name==='Carlos Alcaraz');
  const b=index.players.findIndex(p=>p.name==='Jannik Sinner');
  const shards=[a,b].map(i=>JSON.parse(fs.readFileSync(base+i+'.json','utf8')));
  assert.ok(shards.every(s=>s.version===index.version));
  const data={...index,matches:[...new Map(shards.flatMap(s=>s.matches).map(m=>[m.id,m])).values()]};
  const f={asOf:'2026-09-26',months:'archive',surface:'outdoor-hard',country:'all',region:'all'};
  const ar=rowsFor(data,a,{...f,opponent:b}),br=rowsFor(data,b,{...f,opponent:a});
  const sa=summary(ar),sb=summary(br);
  assert.equal(sa.n,7);assert.equal(sa.wins,5);assert.equal(sb.wins,2);
  assert.equal(sa.metrics.aces.numerator,35);assert.equal(sb.metrics.aces.numerator,30);
  assert.equal(sa.metrics.doubleFaults.numerator,19);assert.equal(sb.metrics.doubleFaults.numerator,29);
  assert.ok(Math.abs(sa.expected+sb.expected-7)<1e-10);
  assert.ok(Math.abs(sa.residual+sb.residual)<1e-10);
});
