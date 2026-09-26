import test from 'node:test';
import assert from 'node:assert/strict';
import { managerRows } from '../../research/manager-atlas/core.mjs';
import { defaults, summary } from '../../src/components/football-atlas/football-core.ts';
const fixture=(patch={})=>({id:'1',date:'2024-01-01',league:'premier-league',season:'2023-2024',home:'A',away:'B',homeManager:'x',awayManager:'y',hg:1,ag:1,odds:[2,3,4],basis:'closing',...patch});
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
