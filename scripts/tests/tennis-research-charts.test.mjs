import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import {profitSeries} from '../../src/components/return-atlas/profit-chart.mjs';
import {decodeAtlas} from '../../src/components/return-atlas/decode.mjs';
import {observations,summarise} from '../../src/components/return-atlas/returns-core.mjs';
import {comparisonMetrics,compactOddsComparison} from '../../src/app/tennis-matchup/runtime/comparison.mjs';
import {summary} from '../../src/app/tennis-matchup/runtime/core.mjs';

test('profit views keep zero months, year boundaries, losses and selection identity',()=>{
  const rows=[
    {id:'a',date:'2025-12-31',profit:1.5,won:true},
    {id:'b',date:'2025-12-31',profit:-1,won:false},
    {id:'c',date:'2026-02-01',profit:-1,won:false},
  ];
  const result=profitSeries(rows);
  assert.deepEqual(result.cumulative.map(p=>[p.id,p.number,p.value]),[['a',1,1.5],['b',2,.5],['c',3,-.5]]);
  assert.deepEqual(result.monthly,[{key:'2025-12',value:.5,bets:2,wins:1},{key:'2026-01',value:0,bets:0,wins:0},{key:'2026-02',value:-1,bets:1,wins:0}]);
  assert.deepEqual(profitSeries([]),{cumulative:[],monthly:[]});
  assert.equal(profitSeries([rows[1]]).cumulative[0].value,-1);
  assert.ok(!Object.hasOwn(rows[0],'value'));
});

test('both chart views reconcile with the live archive ledger across backing sides and filters',()=>{
  const release=JSON.parse(fs.readFileSync('src/data/return-atlas-release.json','utf8'));
  const data=decodeAtlas(JSON.parse(fs.readFileSync('public'+release.indexUrl,'utf8')),release.checkedAt);
  for(const player of data.players)for(const side of ['player','opponent'])for(const role of ['all','underdog']){
    const rows=observations(data.matches,player.id,{side,role,year:'2026'});
    const result=profitSeries(rows),total=summarise(rows);
    assert.ok(Math.abs((result.cumulative.at(-1)?.value??0)-total.profit)<1e-8);
    assert.ok(Math.abs(result.monthly.reduce((a,m)=>a+m.value,0)-total.profit)<1e-8);
    assert.equal(result.monthly.reduce((a,m)=>a+m.bets,0),total.bets);
    assert.deepEqual(result.cumulative.map(p=>p.id),rows.map(p=>p.id));
  }
});

test('comparison keeps missing statistics distinct from a recorded zero and escapes player names',()=>{
  const players=[{name:'A <Player>'},{name:'B & Player'}];
  const empty=summary([]);
  const html=comparisonMetrics(players,[empty,empty]);
  assert.match(html,/No recorded statistics/);
  assert.doesNotMatch(html,/0 aces recorded|0 double faults recorded|0 of 0 points won/);
  assert.match(html,/A &lt;Player&gt;/);
  assert.match(html,/lower is better/);
  assert.doesNotMatch(html,/width:(?:NaN|Infinity)/);
  const odds=compactOddsComparison(players,[empty,empty]);
  assert.match(odds,/0 matches with odds/);
  assert.match(odds,/percentage points/);
  assert.doesNotMatch(odds,/NaN|Infinity/);
});
