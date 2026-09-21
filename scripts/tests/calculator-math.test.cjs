const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const ts=require('typescript');
const m={exports:{}};
new Function('module','exports',ts.transpileModule(fs.readFileSync('src/lib/calculator/math.ts','utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS}}).outputText)(m,m.exports);
const math=m.exports;
test('de-vig probabilities sum to one including high margin and underround',()=>{
 for(const prices of [[1.9,1.9],[1.28,3.75],[2.3,3.4,3.1],[1.1,1.1,1.1],[2.5,2.5]]){
  for(const method of ['proportional','shin','oddsRatio']){
   const p=math.devig(prices,method).probabilities;
   assert.ok(p.every(v=>v>0&&v<1));
   assert.ok(Math.abs(p.reduce((a,b)=>a+b,0)-1)<1e-8,`${method} ${prices}`);
  }
 }
 const p=math.devig([1.28,3.75],'shin').probabilities[0];
 assert.ok(Math.abs(p-(1/1.28-(1/1.28+1/3.75-1)/2))<1e-8);
});
test('CLV removes margin and rejects incomplete closing markets',()=>{
 const r=math.closingLineValue(2.1,1.95,1.95);
 assert.ok(Math.abs(r.expectedValuePct-5)<1e-8);
 assert.ok(Math.abs(r.probabilityClvPct-5)<1e-8);
 assert.ok(r.priceClvPct>7);
 assert.equal(math.closingLineValue(2.1,1.95,0).fairClosingProbability,0);
});
test('flat simulation is seeded, has variance and stops when unfunded',()=>{
 const input={bets:100,stake:10,winRate:.5,roi:.05,startBankroll:1000};
 const a=math.simulateFlatStake(input);
 assert.deepEqual(a,math.simulateFlatStake(input));
 assert.ok(a.terminal.p05<a.terminal.p95);
 const broke=math.simulateFlatStake({...input,startBankroll:5});
 assert.equal(broke.terminal.p95,5);
 assert.equal(broke.bustProbability,1);
 assert.ok(math.simulateFlatStake({...input,startBankroll:10}).terminal.p05>=0);
});
test('Kelly growth peaks at the true Kelly share and estimate error matters',()=>{
 const f=math.kellyFraction(2,.6);
 assert.ok(Math.abs(f-.2)<1e-12);
 assert.ok(math.growthRate(2,.6,f)>math.growthRate(2,.6,f/2));
 const input={bankroll:1000,odds:2,estimatedProbability:.6,trueProbability:.5,fraction:1,bets:100};
 const a=math.simulateKelly(input);
 assert.ok(a.growthPerBet<0);
 assert.ok(a.severeDrawdownPct>0);
 assert.deepEqual(a,math.simulateKelly(input));
});
