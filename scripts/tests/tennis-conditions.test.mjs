import test from 'node:test';
import assert from 'node:assert/strict';
import {conditionsFor,renderConditions,latestSharedConditions} from '../../src/lib/tennis-conditions.mjs';
import {renderTennisContext} from '../../src/lib/tennis-context-html.mjs';
const input={event:'Paris',tour:'ATP',date:'2026-11-02'};
test('measurement and prior-edition estimate keep distinct units and years',()=>{
 const c=conditionsFor(input),html=renderConditions(c);
 assert.equal(c.edition.measurement.value,50);assert.equal(c.estimate.year,2025);
 assert.match(html,/2025 edition · historical reference/);assert.match(html,/50<small>CPI/);assert.match(html,/0\.99<small>ace index/);assert.match(html,/Sample size not supplied/);
});
test('2025 never inherits the 2026 ball or reading',()=>{
 const c=conditionsFor({...input,date:'2025-11-01'}),html=renderConditions(c);
 assert.equal(c.edition.measurement.value,35.1);assert.equal(c.edition.ball,null);
 assert.doesNotMatch(html,/New Dunlop|50<small/);assert.match(html,/Moved from Bercy/);
});
test('2027 measurement remains missing, without a last-reading fallback',()=>{
 const c=conditionsFor({...input,date:'2027-11-01'});
 assert.equal(c.edition,null);assert.match(renderConditions(c),/No reviewed measurement for this edition/);
});
test('Challenger, WTA and ambiguous names do not inherit an ATP city match',()=>{
 for(const x of [{...input,tour:'Challenger'},{...input,tour:'WTA'},{...input,event:'Paris ITF'}]){
  const c=conditionsFor(x);assert.equal(c.family,null);assert.equal(c.estimate,null);
 }
});
test('Finals is a separate edition with a historical estimate, not an unreviewed CPI',()=>{
 const c=conditionsFor({...input,event:'Finals'});assert.equal(c.edition.measurement,null);assert.equal(c.estimate.value,1.4);assert.equal(c.estimate.year,2025);
});
test('unknown events remain missing and text is escaped',()=>{
 const c=conditionsFor({...input,event:'<img src=x onerror=alert(1)>'});
 assert.doesNotMatch(renderConditions(c),/<img src=x/);assert.match(renderConditions(c),/Court conditions not yet reviewed/);
 assert.equal(conditionsFor({...input,date:'invalid'}),null);
});
test('all public evidence links are HTTPS and measurement limitations visible',()=>{
 const html=renderConditions(conditionsFor(input));assert.match(html,/Original measurement and publication times are not supplied/);
 for(const x of html.matchAll(/href="([^"]+)"/g))assert.ok(x[1].startsWith('https://'));
});
test('H2H conditions require a common full-title event before cutoff',()=>{
 const row={date:'2026-11-08',event:'Rolex Paris Masters - Paris'};
 assert.equal(latestSharedConditions([[row],[row]],'2026-11-09')?.year,2026);
 assert.equal(latestSharedConditions([[row],[row]],'2026-11-08'),null);
 assert.equal(latestSharedConditions([[row],[]],'2026-11-09'),null);
 assert.equal(latestSharedConditions([[{...row,event:'Paris'}],[{...row,event:'Paris'}]],'2026-11-09'),null);
});
test('saved player context does not attach Paris to unknown or mixed-edition players',()=>{
 const data={players:{A:{edition:'Paris 2026'},B:{edition:'Finals 2026'}},notes:[],generatedAt:'2026-11-06',notesCoverage:'Limited',notesObservedAt:'2026-11-06'};
 assert.doesNotMatch(renderTennisContext(['A','B'],data,{history:false}),/data-conditions/);
 assert.doesNotMatch(renderTennisContext(['A','Unknown'],data,{history:false}),/data-conditions/);
});

test('a later shared unreviewed tournament suppresses the older Paris card',()=>{
 const paris={date:'2026-11-08',event:'Rolex Paris Masters - Paris'};
 const later={date:'2026-11-15',event:'Another event'};
 assert.equal(latestSharedConditions([[paris,later],[paris,later]],'2026-11-16'),null);
});
test('unsupported editions have no misleading review date or expanded evidence panel',()=>{
 const html=renderConditions(conditionsFor({event:'Helsinki',tour:'Challenger',date:'2026-11-16'}),{compact:true});
 assert.doesNotMatch(html,/Evidence reviewed|details|16 Nov/);
 assert.match(html,/not yet reviewed/);
});
test('prior estimates expire after one edition and changes qualify their relevance',()=>{
 assert.equal(conditionsFor({...input,date:'2027-11-01'}).estimate,null);
 assert.match(renderConditions(conditionsFor(input)),/before the verified ball change/);
 assert.equal(conditionsFor({...input,surface:'clay'}).family,null);
});
test('retained Paris history links each measurement and estimate, with exact precision',()=>{
 const html=renderConditions(conditionsFor(input));
 assert.match(html,/e0e1de515382/);assert.match(html,/year=2024/);assert.doesNotMatch(html,/>50\.0/);
 assert.match(html,/<h3>Paris Masters/);
});
test('real Matchday and public archive aliases identify the same ATP family',()=>{
 assert.equal(conditionsFor({...input,event:'Rolex Paris Masters - Paris'}).family,'paris');
 assert.equal(conditionsFor({...input,event:'Finals'}).family,'finals');
});
test('registry has numeric edition years and unique exact aliases within each tour',async()=>{
 const {default:d}=await import('../../src/data/tennis-conditions-evidence.json',{with:{type:'json'}});
 const seen=new Set();for(const f of d.families){for(const a of f.aliases){const k=f.tour+':'+a;assert.ok(!seen.has(k));seen.add(k);}for(const e of f.editions)assert.ok(Number.isInteger(e.year));}
});
