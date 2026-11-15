import test from 'node:test';
import assert from 'node:assert/strict';
import {chooseContext,validContext} from '../../src/lib/tennis-matchday-context.mjs';
import {buildTennisMatchday} from '../../src/lib/tennis-matchday.mjs';
const now=new Date('2026-11-15T12:00:00Z');
const context=()=>({schema:1,version:'a'.repeat(24),asOf:'2026-11-15',sourceUpdatedAt:'2026-11-15T10:00:00Z',recent:{players:{}},supplement:{pairs:{}},pairHistory:{},results:{from:'2026-11-08',before:'2026-11-15',matches:[]}});
test('invalid/older remote cannot replace the dated validated fallback',()=>{let c=context();assert.equal(chooseContext({},c,now),c);assert.equal(chooseContext({...c,asOf:'2026-11-14',sourceUpdatedAt:'2026-11-14T10:00:00Z',results:{...c.results,before:'2026-11-14'}},c,now),c);assert.equal(chooseContext({}, {},now),null)});
test('future and same-day result contamination rejected',()=>{let c=context();assert.equal(validContext({...c,sourceUpdatedAt:'2026-11-16T10:00:00Z'},now),false);c.results.matches=[{id:'x',date:'2026-11-15',tour:'ATP',players:['A','B'],winner:0,status:'completed'}];assert.equal(validContext(c,now),false)});
test('fresh pair history reaches a preview built on an older archive; reversed feed preserves orientation',()=>{
 const h={asOf:'2026-11-13',through:'2026-11-12',version:'old',players:[{id:'a',name:'Alice A'},{id:'b',name:'Betty B'}],matches:[],matchdayPairs:{'alice a|betty b':{names:['alice a','betty b'],checkedThrough:'2026-11-15',matches:[{date:'2026-11-14',winner:0,odds:[2,1.8],event:'Metz',score:'6-4 6-4',surface:'indoor-hard'}]}}};
 const b=buildTennisMatchday([{captured_at:'2026-11-15T11:00:00Z',kickoff_iso:'2026-11-15T15:00:00Z',league:'Challenger',league_name:'Metz',player1_name:'Betty B',player2_name:'Alice A',odds1:2,odds2:2}],h,now);
 assert.deepEqual(b.fixtures[0].wins,[0,1]);assert.deepEqual(b.fixtures[0].history[0].odds,[1.8,2]);assert.equal(b.fixtures[0].coverageThrough,'2026-11-15');assert.deepEqual(h.matches,[]);
});
