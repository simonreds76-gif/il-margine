import test from 'node:test';
import fs from 'node:fs';
import assert from 'node:assert/strict';
import { managerRows, matchMarket, marketContext, clubRecords, observedSpells, strategyReturns, rankingMinimum, isVerifiedActive, activeReviewDue } from '../../research/manager-atlas/core.mjs';
import { defaults, summary, bands } from '../../src/components/football-atlas/football-core.ts';
const fixture=(patch={})=>({id:'1',date:'2024-01-01',league:'premier-league',season:'2023-2024',home:'A',away:'B',homeManager:'x',awayManager:'y',hg:1,ag:1,odds:[2,3,4],basis:'closing',...patch});
test('review deadlines preserve the last verified roster without claiming fresh evidence',()=>{
 const entry={status:'active',checkedAt:'2026-09-27',reviewBy:'2026-10-04'};
 const registry={entries:{active:entry,retired:{...entry,status:'retired'},dead:{...entry,status:'deceased'},unemployed:{...entry,status:'not-currently-coaching'}}};
 assert.equal(isVerifiedActive('active',registry,'2026-09-27'),true);
 for(const id of ['retired','dead','unemployed','unknown']) assert.equal(isVerifiedActive(id,registry,'2026-09-27'),false);
 assert.equal(isVerifiedActive('active',registry,'2026-10-05'),true);
 assert.equal(isVerifiedActive('active',registry,'2027-01-01'),true);
 assert.equal(activeReviewDue('active',registry,'2026-10-04'),false);
 assert.equal(activeReviewDue('active',registry,'2026-10-05'),true);
 assert.equal(activeReviewDue('retired',registry,'2026-10-05'),false);
 registry.entries.active={...entry,status:'unknown'};
 assert.equal(isVerifiedActive('active',registry,'2026-10-05'),false);
 registry.entries.active=entry;
 assert.equal(isVerifiedActive('active',registry,'2026-09-26'),false);
 assert.equal(isVerifiedActive('active',undefined,'2026-09-27'),false);
});
test('draw settlement and opposite-manager orientation',()=>{
 const matches=[fixture()];
 assert.equal(summary(managerRows(matches,'x',defaults,'y')).profit,-1);
 assert.equal(summary(managerRows(matches,'x',{...defaults,side:'draw'},'y')).profit,2);
 assert.equal(summary(managerRows(matches,'y',{...defaults,side:'opponent'},'x')).profit,-1);
});
test('manager follows the actual fixture across clubs and excludes predecessor',()=>{
 const matches=[fixture({hg:2,ag:0}),fixture({id:'2',home:'C',homeManager:'z',awayManager:'x',hg:0,ag:1}),fixture({id:'3',homeManager:'old'})];
 const rows=managerRows(matches,'x',defaults);
 assert.equal(rows.length,2);assert.deepEqual(rows.map(r=>r.team),['A','B']);assert.equal(summary(rows).profit,4);
 assert.equal(managerRows(matches,'x',defaults,'y').length,1);
});
test('venue role and odds refer to selected manager team when backing opponent',()=>{
 const matches=[fixture()];
 assert.equal(managerRows(matches,'y',{...defaults,venue:'away',role:'underdog',min:3,max:5,side:'opponent'}).length,1);
 assert.equal(managerRows(matches,'y',{...defaults,role:'favourite'}).length,0);
});
test('latest season window anchored to the full archive, not retired manager last match',()=>{
 const matches=[fixture(),fixture({id:'new',season:'2025-2026',date:'2026-01-01',homeManager:'new',awayManager:'new2'})];
 assert.equal(managerRows(matches,'x',{...defaults,season:'latest:1'}).length,0);
});

test('three-way market probabilities include draw and are independent of bet side',()=>{
 const matches=[fixture({hg:2,ag:0})];
 const rows=managerRows(matches,'x',defaults),s=marketContext(rows);
 assert.ok(Math.abs(s.expectedWins-6/13)<1e-10);
 assert.ok(Math.abs(s.expectedPoints-22/13)<1e-10);
 assert.equal(s.actualPoints,3);
 assert.deepEqual(s,marketContext(managerRows(matches,'x',{...defaults,side:'draw'})));
 const away=marketContext(managerRows(matches,'y',defaults));
 assert.ok(Math.abs(away.expectedWins-3/13)<1e-10);
 assert.equal(away.actualWins,0);
});

test('club totals and repeated club spells retain selected fixture chronology',()=>{
 const rows=managerRows([fixture({id:'1'}),fixture({id:'2',date:'2024-02-01',home:'C'}),fixture({id:'3',date:'2024-03-01'})],'x',defaults);
 assert.equal(clubRecords(rows).find(c=>c.club==='A').bets,2);
 assert.deepEqual(observedSpells(rows).map(s=>s.club),['A','C','A']);
});

test('same-sample strategies settle draw and away wins at actual three-way prices',()=>{
 const rows=managerRows([fixture(),fixture({id:'2',hg:0,ag:1})],'y',defaults);
 const choices=strategyReturns(rows);
 assert.equal(choices.find(c=>c.side==='team').profit,2);
 assert.equal(choices.find(c=>c.side==='draw').profit,1);
 assert.equal(choices.find(c=>c.side==='opponent').profit,-2);
 assert.ok(choices.every(c=>c.bets===2));
 assert.equal(marketContext([]).excessWins,0);
});

test('Overall and H2H rankings retain one to four matches',()=>{
 for(const n of [1,2,3,4]) {
  const fixtures=Array.from({length:n},(_,i)=>fixture({id:String(i)}));
  const count=managerRows(fixtures,'x',defaults,'y').length;
  assert.ok(count>=rankingMinimum('y',100));
  assert.ok(count>=rankingMinimum());
 }
 assert.equal(rankingMinimum(),1);
});

test('real match explanation uses the same quoted market and sums to 100%',()=>{
 const [home]=managerRows([fixture()],'x',defaults);
 const [away]=managerRows([fixture()],'y',{...defaults,side:'opponent'});
 const h=matchMarket(home),a=matchMarket(away);
 assert.ok(Math.abs(h.win+h.draw+h.opponent-1)<1e-12);
 assert.equal(a.win,h.opponent);
 assert.equal(a.opponent,h.win);
 assert.equal(a.draw,h.draw);
 assert.equal(marketContext([away]).expectedPoints,a.points);
});

test('odds-band boundaries belong to exactly one band',()=>{
 for(const price of [1.01,1.2,1.5,1.8,2,2.2,2.5,3,3.5,4,5,6,8,10,15]) {
  const matches=[fixture({odds:[price,3.5,6]})];
  const counts=bands.map(b=>managerRows(matches,'x',{...defaults,min:b.min,max:b.max,upperExclusive:true}).length);
  assert.equal(counts.reduce((a,b)=>a+b,0),1,`price ${price}`);
 }
});

test('missing or malformed evidence never establishes an active role',()=>{
 for(const checkedAt of [undefined,'','tomorrow','2026-02-30','2027-01-01']) {
  const registry={entries:{x:{status:'active',checkedAt,reviewBy:'2026-10-05'}}};
  assert.equal(isVerifiedActive('x',registry,'2026-10-05'),false);
 }
 const registry={entries:{x:{status:'active',checkedAt:'2026-09-27'}}};
 assert.equal(isVerifiedActive('x',registry,'2026-10-05'),true);
 assert.equal(activeReviewDue('x',registry,'2026-10-05'),true);
});

test('published roster stays populated beyond review dates and matches its source',()=>{
 const source=JSON.parse(fs.readFileSync(new URL('../../config/manager-atlas-activity.json',import.meta.url),'utf8'));
 const published=JSON.parse(fs.readFileSync(new URL('../../public/manager-atlas/activity.json',import.meta.url),'utf8'));
 assert.deepEqual(published,source);
 const activeAt=date=>Object.keys(source.entries).filter(id=>isVerifiedActive(id,source,date));
 assert.deepEqual(activeAt('2026-10-06'),activeAt('2026-10-05'));
 assert.deepEqual(activeAt('2026-12-01'),activeAt('2026-10-05'));
 assert.ok(activeAt('2026-10-06').length>0);
 assert.equal(isVerifiedActive('mgr-0094',source,'2026-10-06'),false);
 for(const id of ['mgr-0023','mgr-0032','mgr-0280'])assert.equal(isVerifiedActive(id,source,'2026-10-06'),true);
 assert.equal(source.entries['mgr-0644'].checkedAt,'2026-09-27');
});
