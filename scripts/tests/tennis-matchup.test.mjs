import test from 'node:test';
import assert from 'node:assert/strict';
import {marketProbability,rowsFor,summary,startDate,residualRange,recordedCount} from '../../research/tennis-matchup/core.mjs';

const filters={asOf:'2026-09-26',months:'24',region:'Asia',country:'all',surface:'all'};
const match=(id,date,other={})=>({id,date,p1:0,p2:1,winner:0,o1:1.8,o2:2.2,region:'Asia',country:'CHN',surface:'outdoor-hard',eventKey:id,stats1:null,stats2:null,...other});
test('ace and double-fault averages exclude missing records and keep real zeros',()=>{
  const data={matches:[match('a','2026-09-20',{stats1:{aces:[10,100],doubleFaults:[0,100]},stats2:{aces:[4,80]}}),match('b','2026-09-21',{stats1:{aces:[2,20]}}),match('c','2026-09-22')]};
  const a=summary(rowsFor(data,0,filters)),b=summary(rowsFor(data,1,filters));
  assert.equal(a.metrics.aces.numerator,12);
  assert.equal(a.metrics.aces.perMatch,6);
  assert.equal(a.metrics.aces.rate,10);
  assert.equal(a.metrics.doubleFaults.perMatch,0);
  assert.equal(a.metrics.doubleFaults.matches,1);
  assert.equal(b.metrics.aces.perMatch,4);
  assert.equal(b.metrics.doubleFaults.perMatch,null);
  assert.equal(recordedCount(data.matches[0].stats1,'doubleFaults'),0);
  assert.equal(recordedCount(null,'aces'),null);
  assert.equal(recordedCount({aces:[5,2]},'aces'),null);
  assert.equal(rowsFor(data,1,filters)[0].odds,2.2);
});
test('head-to-head excludes other opponents and reverses consistently when players swap',()=>{
  const data={matches:[match('a','2026-09-20'),match('b','2026-09-21',{p1:1,p2:0}),match('other','2026-09-22',{p2:2}),match('other-b','2026-09-23',{p1:1,p2:2})]};
  const a=rowsFor(data,0,{...filters,opponent:1});
  const b=rowsFor(data,1,{...filters,opponent:0});
  assert.deepEqual(a.map(m=>m.id),['a','b']);
  assert.deepEqual(a.map(m=>m.id),b.map(m=>m.id));
  assert.equal(summary(a).wins,summary(b).losses);
  assert.equal(summary(a).n,2);
  assert.equal(rowsFor(data,0,filters).length,3);
  assert.equal(rowsFor(data,0,{...filters,opponent:0}).length,0);
});
test('head-to-head still applies date, region, country and surface boundaries',()=>{
  const data={matches:[match('hard','2026-09-20'),match('clay','2026-09-21',{surface:'clay'}),match('japan','2026-09-22',{country:'JPN'}),match('old','2024-09-25'),match('today','2026-09-26'),match('europe','2026-09-23',{region:'Europe'})]};
  assert.deepEqual(rowsFor(data,0,{...filters,opponent:1,country:'CHN',surface:'outdoor-hard'}).map(m=>m.id),['hard']);
});
test('strict date boundary excludes same-day and future outcomes',()=>{
  const data={matches:[match('old','2024-09-25'),match('start','2024-09-26'),match('prior','2026-09-25'),match('today','2026-09-26'),match('future','2026-09-27')]};
  assert.deepEqual(rowsFor(data,0,filters).map(m=>m.id),['start','prior']);
  assert.equal(startDate('2024-02-29','12'),'2023-02-28');
});
test('country, region and surface intersect without adding overlapping samples',()=>{
  const data={matches:[match('china','2026-09-20'),match('japan','2026-09-20',{country:'JPN'}),match('france','2026-09-20',{country:'FRA',region:'Europe'}),match('unknown','2026-09-20',{country:null,region:null})]};
  assert.equal(rowsFor(data,0,filters).length,2);
  assert.equal(rowsFor(data,0,{...filters,country:'CHN'}).length,1);
  assert.equal(rowsFor(data,0,{...filters,country:'CHN',surface:'clay'}).length,0);
  assert.equal(rowsFor(data,0,{...filters,region:'all'}).length,4);
});
test('market probabilities complement and player swap reverses result and residual',()=>{
  assert.equal(marketProbability(2,2),.5);
  assert.ok(Math.abs(marketProbability(1.8,2.2)+marketProbability(2.2,1.8)-1)<1e-12);
  assert.equal(marketProbability(0,2),null);
  const data={matches:[match('one','2026-09-20')]};
  const a=summary(rowsFor(data,0,filters)),b=summary(rowsFor(data,1,filters));
  assert.equal(a.wins,1);assert.equal(b.losses,1);assert.ok(Math.abs(a.residual+b.residual)<1e-12);
});
test('rates aggregate counts rather than averaging percentages; zero is valid',()=>{
  const data={matches:[match('one','2026-09-20',{stats1:{serve:[9,10],doubleFaults:[0,10]}}),match('two','2026-09-21',{stats1:{serve:[10,100]}}),match('three','2026-09-22')]};
  const s=summary(rowsFor(data,0,filters));
  assert.equal(s.metrics.serve.denominator,110);assert.equal(s.metrics.serve.numerator,19);
  assert.equal(s.metrics.serve.matches,2);assert.equal(s.n,3);
  assert.equal(s.metrics.doubleFaults.rate,0);assert.equal(s.metrics.return.rate,null);
});
test('bad numerators cannot contaminate metrics and a zero result stays zero',()=>{
  const data={matches:[match('one','2026-09-20',{winner:1,stats1:{serve:[12,10]}})]};
  const s=summary(rowsFor(data,0,filters));
  assert.equal(s.winRate,0);assert.equal(s.metrics.serve.rate,null);
  assert.equal(summary([]).winRate,null);assert.equal(summary([]).residual,null);
});
test('small or ungrouped cohorts do not acquire uncertainty bands',()=>{
  const rows=Array.from({length:40},(_,i)=>({id:String(i),won:i%2===0,probability:.5,eventKey:'same'}));
  assert.equal(residualRange(rows),null);
  assert.equal(residualRange(rows.slice(0,10).map((r,i)=>({...r,eventKey:String(i)}))),null);
  assert.equal(residualRange(rows.map((r,i)=>({...r,eventKey:i===0?null:String(i)}))),null);
});
test('cluster resampling is deterministic and reverses with swapped players',()=>{
  const rows=Array.from({length:80},(_,i)=>({id:String(i),won:i%3!==0,probability:.53,eventKey:String(i%12)}));
  const a=residualRange(rows),b=residualRange(rows.map(r=>({...r,won:!r.won,probability:1-r.probability})));
  assert.deepEqual(a,residualRange(rows));
  assert.ok(Math.abs(a[0]+b[1])<1e-10);assert.ok(Math.abs(a[1]+b[0])<1e-10);
});

test('full archive includes 2021 while recent windows retain their cutoff',()=>{
 const data={matches:[match('older','2021-06-15'),match('recent','2026-09-20')]};
 assert.equal(startDate('2026-09-26','archive'),'2021-01-01');
 assert.deepEqual(rowsFor(data,0,{...filters,months:'archive'}).map(m=>m.id),['older','recent']);
 assert.deepEqual(rowsFor(data,0,filters).map(m=>m.id),['recent']);
});

 test('full H2H includes older unpriced results without changing profiles or market sample',()=>{
  const d={historyFrom:'2016-01-01',matches:[{id:'new',date:'2025-01-01',p1:0,p2:1,winner:0,o1:2,o2:2,surface:'clay'}],results:[{id:'old',date:'2016-01-01',p1:0,p2:1,winner:1,o1:null,o2:null,surface:'clay'}]};
  const f={asOf:'2026-01-01',months:'archive',surface:'all',region:'all',country:'all'};
  const rows=rowsFor(d,0,{...f,opponent:1}), result=summary(rows);
  assert.equal(rows.length,2);assert.equal(result.wins,1);assert.equal(result.losses,1);
  assert.equal(result.priced,1);assert.equal(result.expected,.5);assert.equal(result.actual,1);
  assert.equal(rowsFor(d,0,f).length,1);
  assert.equal(rowsFor(d,1,{...f,opponent:0}).filter(r=>r.won).length,1);
});
