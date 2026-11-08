import test from 'node:test';
import assert from 'node:assert/strict';
import { buildTennisMatchday } from '../../src/lib/tennis-matchday.mjs';
const now = new Date('2026-11-08T12:00:00Z');
const row = {captured_at:'2026-11-08T11:00:00Z',league:'Challenger',league_name:'Challenger Test',
  player1_name:'Ozan Baris',player2_name:'Quinn Vandecasteele',kickoff_iso:'2026-11-09T12:00:00Z',odds1:1.8,odds2:2.1};
const pair = {players:[{name:'Ozan Baris',nativeId:'82492'},{name:'Quinn Vandecasteele',nativeId:'71628'}],
  checkedThrough:'2026-11-08',matches:[{id:'one',date:'2023-07-29',winner:1,odds:[null,null],score:'6-1 6-3',event:'M25 Edwardsville',surface:'outdoor-hard',competition:'ITF'}]};
const h = {players:[],matches:[],asOf:'2026-11-08',through:'2026-11-07',version:'x',matchdaySupplement:{pairs:{'ozan baris|quinn vandecasteele':pair}}};
test('results-only recovery shows real result, no invented odds or priced profiles',()=>{
 const f=buildTennisMatchday([row],h,now).fixtures[0];
 assert.equal(f.meetings,1);assert.deepEqual(f.wins,[0,1]);assert.equal(f.priced,0);assert.equal(f.href,null);
 assert.deepEqual(f.roi,[null,null]);assert.equal(f.resultsOnly,true);assert.ok(f.players.every(p=>p.id===null));
});
test('reversed source order preserves winner and current price orientation',()=>{
 const f=buildTennisMatchday([{...row,player1_name:row.player2_name,player2_name:row.player1_name}],h,now).fixtures[0];
 assert.deepEqual(f.wins,[1,0]);assert.equal(f.history[0].winner,0);assert.deepEqual(f.quote.odds,[1.8,2.1]);
});
test('individual known names never imply an unscanned pair has zero meetings',()=>{
 assert.equal(buildTennisMatchday([{...row,player2_name:'Another Player'}],h,now).fixtures[0].meetings,null);
 const scanned={...h,matchdaySupplement:{pairs:{'ozan baris|quinn vandecasteele':{...pair,matches:[]}}}};
 assert.equal(buildTennisMatchday([row],scanned,now).fixtures[0].meetings,0);
});
test('quarantine, future and same-day records are withheld without removing fixtures',()=>{
 for(const patch of [{quarantined:'identity_changed'},{checkedThrough:'2026-11-10'}]){
  const q={...h,matchdaySupplement:{pairs:{'ozan baris|quinn vandecasteele':{...pair,...patch}}}};
  const f=buildTennisMatchday([row],q,now).fixtures[0];assert.equal(f.meetings,null);
 }
 const q={...h,matchdaySupplement:{pairs:{'ozan baris|quinn vandecasteele':{...pair,matches:[...pair.matches,{...pair.matches[0],id:'later',date:'2026-11-08'}]}}}};
 assert.equal(buildTennisMatchday([row],q,now).fixtures[0].meetings,1);
});
test('supplement cannot change any already-covered H2H, ROI or history',()=>{
 const base={...h,players:[{id:'a',name:row.player1_name},{id:'b',name:row.player2_name}],
 matches:[['2026-01-01',0,1,0,2,1.8,'clay','6-4 6-4','Test']]};
 const withExtra=buildTennisMatchday([row],base,now).fixtures[0];
 const without=buildTennisMatchday([row],{...base,matchdaySupplement:null},now).fixtures[0];
 assert.deepEqual(withExtra,without);
});
test('reviewed Brazilian feed variants retain existing public IDs',()=>{
 const base={...h,players:[{id:'vbt-5490',name:'Igor Ribeiro Marcondes'},{id:'vbt-16420',name:'Felipe Meligeni Alves'}]};
 const f=buildTennisMatchday([{...row,player1_name:'Igor Marcondes',player2_name:'Felipe Meligeni Rodrigues Alves'}],base,now).fixtures[0];
 assert.deepEqual(f.players.map(p=>p.id),['vbt-5490','vbt-16420']);assert.ok(f.href);assert.equal(f.resultsOnly,false);
});

test('reviewed Tai Leonard Sach name uses the same results-only identity',()=>{
 const history={...h,matchdaySupplement:{pairs:{'tai sach|thomas fancutt':{
   ...pair,players:[{name:'Tai Sach',nativeId:'68624'},{name:'Thomas Fancutt',nativeId:'30211'}]}}}};
 const f=buildTennisMatchday([{...row,player1_name:'Thomas Fancutt',player2_name:'Tai Leonard Sach'}],history,now).fixtures[0];
 assert.equal(f.meetings,1);assert.deepEqual(f.wins,[1,0]);assert.equal(f.players[1].name,'Tai Leonard Sach');
 assert.deepEqual(f.roi,[null,null]);assert.equal(f.href,null);
});

