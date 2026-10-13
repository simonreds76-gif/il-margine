const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const ts = require('typescript');
function load(file) {
  const exports = {};
  vm.runInNewContext(ts.transpileModule(fs.readFileSync(file, 'utf8'), {compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022}}).outputText, {exports, Error, Map});
  return exports;
}
const {readRecordPages} = load('src/lib/read-record-pages.ts');
const {buildMonthlyRows} = load('src/lib/monthly-record.ts');
test('retains older results beyond the API 1000-row cap, with reconciled sport totals', async () => {
  const data = Array.from({length:1067}, (_, i) => ({match_date:i < 67 ? '2026-02-12' : '2026-03-12', settled_at:null, status:i % 2 ? 'lost' : 'won', stake: i % 2 ? .5 : 2, profit_loss:i % 2 ? -.5 : 1.4}));
  const calls = [];
  const rows = await readRecordPages(async (from,to) => {calls.push([from,to]); return data.slice(from,to+1);});
  assert.equal(rows.length,1067);
  assert.deepEqual(calls,[[0,499],[500,999],[1000,1499]]);
  const months = buildMonthlyRows(rows);
  assert.equal(months.reduce((sum,row)=>sum+row.total_bets,0),1067);
  assert.equal(months.find(row=>row.month==='2026-02').total_bets,67);
  const profit = months.reduce((sum,row)=>sum+row.total_profit,0);
  const stake = months.reduce((sum,row)=>sum+row.total_stake,0);
  const split = [buildMonthlyRows(rows.slice(0,666)),buildMonthlyRows(rows.slice(666))].flat();
  assert.ok(Math.abs(profit-split.reduce((sum,row)=>sum+row.total_profit,0))<1e-8);
  assert.ok(Math.abs(stake-split.reduce((sum,row)=>sum+row.total_stake,0))<1e-8);
});
test('an exact full page requires a final empty read', async () => {
  let calls=0;
  const rows=await readRecordPages(async from=>{calls++;return from===0?[1,2]:[];},2);
  assert.equal(rows.length,2); assert.equal(calls,2);
});
test('fails instead of returning partial totals on read failure or bounded limit', async () => {
  await assert.rejects(readRecordPages(async from=>{if(from)throw Error('read failed');return [1,2];},2),/read failed/);
  await assert.rejects(readRecordPages(async()=>[1,2],2,2),/refusing a partial total/);
});
