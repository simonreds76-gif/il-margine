const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const cp=require('node:child_process');
const ts=require('typescript');
function moduleAt(path){const m={exports:{}};new Function('module','exports',ts.transpileModule(fs.readFileSync(path,'utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS}}).outputText)(m,m.exports);return m.exports;}
const b=moduleAt('src/lib/baseline.ts');
const count=moduleAt('src/lib/settled-record-count.ts').settledRecordCount;
function statsFunction(source,name,rows){
 const start=source.indexOf('const '+name+' =');
 const end=source.indexOf('const getArchive',start);
 assert.ok(start>0&&end>start);
 const expression=ts.transpileModule(source.slice(start,end),{compilerOptions:{module:ts.ModuleKind.CommonJS}}).outputText;
 return new Function('stats','BASELINE_STATS','calculateROI','calculateWinRate','normalizeBetCategory','settledRecordCount',expression+'; return '+name)(rows,b.BASELINE_STATS,b.calculateROI,b.calculateWinRate,x=>x,count);
}
for(const [path,market,name] of [['src/app/player-props/PlayerPropsClient.tsx','props','getStatsForLeague'],['src/app/tennis-tips/TennisTipsClient.tsx','tennis','getStatsForCategory']]){
 test(market+': all, baseline category and new category exclude pending/void without changing other figures',()=>{
  const category=Object.keys(b.BASELINE_STATS.categoryBaselines[market])[0];
  const rows=[{market,category,total_bets:6,wins:2,losses:1,total_profit:1.2,total_stake:2.5,avg_odds:2.2},
   {market,category:'new-competition',total_bets:5,wins:1,losses:1,total_profit:-0.1,total_stake:1,avg_odds:1.9}];
  const after=statsFunction(fs.readFileSync(path,'utf8'),name,rows);
  const before=statsFunction(cp.execFileSync('git',['show','ad576ef326f9ebcd003d9f95d8647df2702cb3a1:'+path],{encoding:'utf8'}),name,rows);
  const expected={all:b.BASELINE_STATS[market].total_bets+5,[category]:b.BASELINE_STATS.categoryBaselines[market][category].total_bets+3,'new-competition':2};
  for(const key of Object.keys(expected)){
   const current=after(key),old=before(key);
   assert.equal(current.total_bets,expected[key]);
   const {total_bets:oldCount,...oldOther}=old;const {total_bets:newCount,...newOther}=current;
   assert.deepEqual(newOther,oldOther);
  }
 });
}
