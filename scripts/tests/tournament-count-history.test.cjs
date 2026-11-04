const {test}=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),ts=require('typescript');
const mod={exports:{}};
new Function('module','exports',ts.transpileModule(fs.readFileSync('src/lib/admin-monitor-display.ts','utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022}}).outputText)(mod,mod.exports);
const {tournamentHistory}=mod.exports;
const result=(extra={})=>({date:'2026-11-03',opponent:'Opponent',round_id:'4',result:'6-4 6-4',status:'completed',aces:17,dfs:1,...extra});
const row=(logs)=>({tour:'ATP',tour_id:'21362',player_id:'29812',date:'2026-11-04',generation_date:'2026-11-03',same_tournament_matches:'0',tournament_round_log:'[]',tournament_count_history:JSON.stringify({version:'tournament-count-history-v1',tour:'ATP',tour_id:'21362',player_id:'29812',before_date:'2026-11-04',source_observed_epoch:1793786800,logs})});
test('fresh edition results override empty forecast-era display log, never change forecast inputs',()=>{
 const input=row([result()]);const original=JSON.stringify(input);const h=tournamentHistory(input);
 assert.equal(h.logs.length,1);assert.equal(h.aces.value,17);assert.equal(h.dfs.value,1);assert.equal(h.logs[0].round,'R1');assert.equal(JSON.stringify(input),original);
});
test('retirement counts remain visible and are separate from completed totals',()=>{
 const h=tournamentHistory(row([result(),result({status:'retired',aces:7,dfs:1})]));
 assert.equal(h.logs.length,2);assert.equal(h.partial,1);assert.equal(h.completed,1);assert.equal(h.aces.value,17);
});
test('missing counts stay null, real zero remains zero and same-day future rows are excluded',()=>{
 const h=tournamentHistory(row([result({aces:null,dfs:0}),result({date:'2026-11-04',aces:50})]));
 assert.equal(h.logs.length,1);assert.equal(h.aces.value,null);assert.equal(h.aces.covered,0);assert.equal(h.dfs.value,0);
});
test('wrong player, edition, tour and cutoff do not borrow a different history',()=>{
 for(const change of [{player_id:'other'},{tour_id:'old'},{tour:'WTA'},{date:'2026-11-05'}]) assert.equal(tournamentHistory({...row([result()]),...change}).logs.length,0);
});
test('legacy saved forecasts still render their original history',()=>{
 const h=tournamentHistory({date:'2026-11-04',same_tournament_matches:'1',tournament_round_log:JSON.stringify([result()])});
 assert.equal(h.aces.value,17);assert.equal(h.observedAt,null);
});
