import test from 'node:test';
import assert from 'node:assert/strict';
import data from '../../src/data/tennis-tournament-returns.json' with {type:'json'};
import {reconciles,summaryForFamily,familyForFixture,projectTournamentReturns} from '../../src/lib/tennis-tournament-returns.mjs';
const family=id=>data.families.find(f=>f.familyId===id);
const summary=id=>summaryForFamily(data,family(id));
test('all accepted rows reconcile, without adding prices to uncovered results',()=>{
 let priced=0,completed=0;
 for(const f of data.families){
  const s=summaryForFamily(data,f);assert.equal(s.availability,'available',f.id);
  for(const e of s.editions){priced+=e.counts.paired;completed+=e.counts.completed;}
 }
 assert.equal(priced,14915);assert.equal(completed,15191);
});
test('same priced pairs; exact pickems excluded from both strategies',()=>{
 const s=summary('atp-finals').windows.three;
 assert.deepEqual(s.counts,{completed:44,paired:44,unpriced:0,pickems:1,bettable:43,notCompleted:2});
 assert.equal(s.favourite.wins,33);assert.equal(s.underdog.wins,10);
 assert.equal(s.favourite.profit,2.037);assert.equal(s.underdog.profit,-8.77);
 assert.ok(Math.abs(s.favourite.roi-100*2.037/43)<0.000001);
});
test('Queen’s sponsor rename preserves editions without doubling them',()=>{
 const s=summary('queens');assert.deepEqual(s.windows.three.years,[2023,2024,2025]);
 assert.equal(s.windows.three.counts.bettable,88);assert.equal(s.windows.three.favourite.profit,-8.082);
 assert.equal(s.windows.three.underdog.profit,6.2);
 assert.equal(new Set(s.editions.map(e=>e.editionId)).size,s.editions.length);
});
test('five editions does not pool opening odds or the current year',()=>{
 const s=summary('queens');assert.deepEqual(s.windows.five.years,[2022,2023,2024,2025]);
 assert.equal(s.editions.find(e=>e.year===2021).status,'opening-basis');
 assert.equal(s.editions.find(e=>e.year===2026).status,'current');
});
test('Paris venue change leaves only one eligible prior edition; missing price stays counted',()=>{
 const s=summary('paris-masters');assert.deepEqual(s.windows.three.years,[2025]);
 assert.equal(s.windows.three.counts.completed,54);assert.equal(s.windows.three.counts.paired,53);
 assert.equal(s.editions.find(e=>e.year===2024).status,'other-regime');
});
test('all pools respect frozen coverage, price basis, date and no backfill rules',()=>{
 for(const f of data.families)for(const n of ['3','5']){
  const w=f.windows[n];assert.ok(w.editions.length<=Number(n));
  assert.deepEqual(w.years,w.editions.filter(e=>e.status==='included').map(e=>e.year));
  assert.ok(w.editions.filter(e=>e.status==='included').every(e=>e.coveragePct>=80&&e.year>2021&&e.year<2026));
  assert.equal(w.bands.reduce((n,b)=>n+b.bettable,0),w.pool.bettable);
 }
});
test('inconsistent counts, nonfinite values and incorrect ROI fail closed',()=>{
 const w=summary('queens').windows.three;
 assert.ok(reconciles(w.counts,w.favourite,w.underdog));
 assert.equal(reconciles({...w.counts,paired:90},w.favourite,w.underdog),false);
 for(const wrong of [{profit:NaN},{profit:Infinity},{roi:99},{wins:-1},{stake:89}])
   assert.equal(reconciles(w.counts,{...w.favourite,...wrong},w.underdog),false);
});
test('zero sample has no numerical ROI',()=>{
 const c={completed:0,paired:0,unpriced:0,pickems:0,bettable:0,notCompleted:0};
 const s={wins:0,losses:0,stake:0,profit:0,roi:null};
 assert.ok(reconciles(c,s,s));assert.equal(reconciles(c,{...s,roi:0},s),false);
});
test('exact current ATP Finals alias only, never Challenger/qualifying/unknown edition',()=>{
 const f={tour:'ATP',event:'Finals',start:'2026-11-16T14:00:00Z',qualifying:false};
 assert.equal(familyForFixture(data,f)?.familyId,'atp-finals');
 for(const change of [{tour:'Challenger'},{qualifying:true},{event:'Unknown'},{start:'2027-11-16T14:00:00Z'},{event:'Metz'}])assert.equal(familyForFixture(data,{...f,...change}),null);
});
test('client payload contains bounded summaries, no raw fixture ledgers',()=>{
 const p=projectTournamentReturns(data,[]);assert.equal(p.examples.length,3);
 assert.ok(JSON.stringify(p).length<20000);assert.equal(p.examples[0].availability,'available');
 assert.equal(JSON.stringify(p).includes('winner_id'),false);
});

test('opening odds or unresolved identity in a later edition cannot silently reach the UI',()=>{
 for(const mode of ['opening','identity']){
  const f=structuredClone(family('queens'));
  if(mode==='opening')f.windows['3'].pool.priceMix['Pinnacle opening']=1;
  else f.editions[0].excluded.unresolvedIdentity=1;
  assert.equal(summaryForFamily(data,f).availability,'unavailable');
 }
});
