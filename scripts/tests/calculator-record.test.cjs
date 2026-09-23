const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const ts=require('typescript');
function load(path, dependencies={}) {
 const m={exports:{}};
 new Function('module','exports','require',ts.transpileModule(fs.readFileSync(path,'utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS}}).outputText)(m,m.exports,name=>{
  if(name in dependencies)return dependencies[name];
  throw Error('Unexpected dependency '+name);
 });
 return m.exports;
}
const baseline=load('src/lib/baseline.ts');
const {summarizeCalculatorRecord}=load('src/lib/calculator/record.ts',{'@/lib/baseline':baseline});
test('current record uses stake-weighted returns and excludes other markets',()=>{
 const b=baseline.BASELINE_STATS.overall;
 const r=summarizeCalculatorRecord([
  {market:'tennis',total_bets:2,wins:1,losses:1,total_profit:1,total_stake:3},
  {market:'props',total_bets:3,wins:2,losses:1,total_profit:-.5,total_stake:1.5},
  {market:'other',total_bets:1000,wins:1000,losses:0,total_profit:1000,total_stake:1000},
 ]);
 assert.equal(r.totalBets,b.total_bets+5);
 assert.equal(r.totalStake,b.total_stake+4.5);
 assert.equal(r.wins,b.wins+3);
 assert.equal(r.losses,b.losses+2);
 assert.equal(r.roi,(b.total_profit+.5)/(b.total_stake+4.5)*100);
 assert.equal(r.source,'live');
});
test('missing configuration is labelled as baseline; zero stake is not invented',()=>{
 assert.equal(summarizeCalculatorRecord(null).source,'fallback');
 const r=summarizeCalculatorRecord([{market:'tennis',total_bets:1,wins:0,losses:0,total_profit:0,total_stake:0}]);
 assert.equal(r.totalStake,baseline.BASELINE_STATS.overall.total_stake);
});
