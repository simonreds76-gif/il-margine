import test from 'node:test';
import assert from 'node:assert/strict';
import {scheduleSummary,contextPanel} from '../../src/app/tennis-matchup/runtime/context.mjs';
const meta={asOf:'2026-10-24',from:'2026-04-27',through:'2026-10-23',mapped:{0:true,1:false},scope:'Recorded singles'};
const schedule=[
  {date:'2026-10-09',sets:2,games:20},
  {date:'2026-10-10',sets:3,games:30},
  {date:'2026-10-17',sets:2,games:21},
  {date:'2026-10-23',sets:1,games:12,retired:true,event:'Test'},
  {date:'2026-10-24',sets:3,games:35},
  {date:'2026-10-25',sets:3,games:36},
];
test('strict pre-date windows include qualifying/other opponents and retain retirements',()=>{
  const result=scheduleSummary(schedule,'2026-10-24',meta);
  assert.equal(result.week.matches,2); assert.equal(result.week.sets,3);
  assert.equal(result.week.games,33); assert.equal(result.week.retirements,1);
  assert.equal(result.fortnight.matches,3); assert.equal(result.gap,1);
});
test('unmapped or out-of-coverage players are unavailable, not rested',()=>{
  assert.equal(scheduleSummary(schedule,'2026-10-25',meta),null);
  assert.equal(scheduleSummary(schedule,'2026-01-01',meta),null);
  assert.equal(scheduleSummary(schedule,'2026-10-24',meta,false),null);
  assert.equal(scheduleSummary([],'2026-10-24',meta).week.matches,0);
  const html=contextPanel([{name:'A'},{name:'B'}],[0,1],{0:schedule},meta,'2026-10-24');
  assert.match(html,/Unavailable/);assert.match(html,/All opponents and surfaces/);
});
