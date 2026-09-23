import test from 'node:test';
import assert from 'node:assert/strict';
import {underwater,unitScale} from '../../src/components/football-atlas/chart-math.ts';
import {defaults,observations,summary,eligible,bands,uniqueDrawPortfolio,seasonMatches} from '../../src/components/football-atlas/football-core.ts';
const match=(patch={})=>({id:'one',league:'premier-league',season:'2025-2026',date:'2026-01-01',home:'A',away:'B',hg:1,ag:1,odds:[2.3,3.2,3.4],basis:'closing',...patch});
test('underwater chart measures from running peak, including initial losses and recovery',()=>{
 assert.deepEqual(underwater([0,-1,-2,3,2,0,4]),[0,-1,-2,0,-1,-3,0]);
 assert.deepEqual(underwater([0,1,2]),[0,0,0]);
 assert.deepEqual(underwater([0,-1,-2]),[0,-1,-2]);
});
test('unit axes include zero and all points with distinct round ticks, including flat and tiny samples',()=>{
 for(const curve of [[0],[0,0],[0,.001],[0,-.001],[0,113.8,-7.2],[0,-37.1]]){
  const s=unitScale(curve);assert.ok(s.max>s.min);assert.ok(s.min<=Math.min(...curve));assert.ok(s.max>=Math.max(...curve));assert.ok(s.ticks.includes(0));assert.equal(new Set(s.ticks).size,s.ticks.length);
 }
 assert.deepEqual(unitScale([0,113.8,-7.2]).ticks,[-50,0,50,100,150]);
});
test('draw loses either team win; backing draw uses actual draw price',()=>{
 for(const team of ['A','B']){assert.equal(observations([match()],team,defaults)[0].profit,-1);assert.equal(observations([match()],team,{...defaults,side:'opponent'})[0].profit,-1);assert.equal(observations([match()],team,{...defaults,side:'draw'})[0].profit,2.2);}
});
test('favourite is relative; role and range belong to named team on every side',()=>{
 for(const side of ['team','draw','opponent']){const row=observations([match()],'A',{...defaults,side,role:'favourite',min:2.2,max:2.5})[0];assert.equal(row.role,'favourite');assert.equal(row.teamOdds,2.3);assert.equal(observations([match()],'B',{...defaults,side,role:'favourite'}).length,0);}
});
test('bands include lower boundary and exclude upper; custom includes both',()=>{
 assert.equal(observations([match({odds:[2.5,3.2,2.8]})],'A',{...defaults,min:2.2,max:2.5,upperExclusive:true}).length,0);
 assert.equal(observations([match({odds:[2.5,3.2,2.8]})],'A',{...defaults,min:2.5,max:3,upperExclusive:true}).length,1);
 assert.equal(observations([match({odds:[2.5,3.2,2.8]})],'A',{...defaults,min:2.2,max:2.5}).length,1);
 assert.equal(bands.at(-1).max,Infinity);
});
test('missing prices count in coverage, never ROI; duplicates never count twice',()=>{
 const a=match(),b=match({id:'two',odds:null});assert.equal(eligible([a,a,b],'A',defaults).length,2);assert.equal(observations([a,a,b],'A',defaults).length,1);
});
test('tied win prices excluded from role splits',()=>{const m=match({odds:[2.8,3,2.8]});assert.equal(observations([m],'A',defaults).length,1);for(const role of ['favourite','underdog'])assert.equal(observations([m],'A',{...defaults,role}).length,0);});
test('profit, drawdown and team WDL separate from bet WL',()=>{
 const rows=observations([match({hg:2,ag:0}),match({id:'two',date:'2026-01-02'})],'A',defaults);const s=summary(rows);assert.ok(Math.abs(s.profit-.3)<1e-10);assert.ok(Math.abs(s.roi-15)<1e-10);assert.equal(s.drawdown,1);assert.deepEqual(s.results,{W:1,D:1,L:0});assert.equal(s.losses,1);
});
test('draw fixture portfolio dedupes opposing team rows',()=>{const a=observations([match()],'A',{...defaults,side:'draw'}),b=observations([match()],'B',{...defaults,side:'draw'});assert.equal(summary(uniqueDrawPortfolio([...a,...b])).bets,1);});
test('venue, season, calendar year, league filters apply before prices',()=>{for(const f of [{venue:'away'},{season:'2024-2025'},{year:'2025'},{league:'ligue-1'}])assert.equal(observations([match()],'A',{...defaults,...f}).length,0);});

test('latest seasons share an archive anchor; absent clubs never pull older matches into it',()=>{
 const fixtures=[match({id:'old',season:'2023-2024'}),match({id:'a',season:'2024-2025',hg:2,ag:0}),match({id:'b',season:'2025-2026'}),match({id:'current',season:'2026-2027',home:'C',away:'D'})];
 const rows=observations(fixtures,'A',{...defaults,season:'latest:3'});
 assert.deepEqual(rows.map(r=>r.id).sort(),['a','b']);assert.equal(summary(rows).bets,2);
 assert.equal(observations(fixtures,'A',{...defaults,season:'latest:2'}).length,1);
 assert.equal(observations(fixtures,'A',{...defaults,season:'latest:5'}).length,3);
});
test('custom season bounds are inclusive and combine profit, not average season ROIs',()=>{
 const fixtures=[match({id:'old',season:'2022-2023'}),match({id:'a',season:'2023-2024',hg:2,ag:0,odds:[3,3.2,2.1]}),match({id:'b',season:'2024-2025'}),match({id:'c',season:'2024-2025'}),match({id:'missing',season:'2024-2025',odds:null})];
 const f={...defaults,season:'range:2023-2024:2024-2025'};
 assert.equal(eligible(fixtures,'A',f).length,4);const s=summary(observations(fixtures,'A',f));assert.equal(s.bets,3);assert.equal(s.profit,0);assert.equal(s.roi,0);
 assert.equal(seasonMatches('2025-2026',f.season,'2026-2027'),false);
});
