const {test}=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm'),ts=require('typescript');
function load(file,imports={}){const module={exports:{}};vm.runInNewContext(ts.transpileModule(fs.readFileSync(file,'utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022,esModuleInterop:true}}).outputText,{module,exports:module.exports,require:n=>imports[n]??require(n),URL,Response,AbortSignal});return module.exports;}
const parser=load('src/lib/admin-signal-format.ts');
test('CSV preserves quoted commas, newlines, escaped quotes and zero values',()=>{const rows=parser.signalCsv('\ufeffplayer,result,stake\r\n"A, B",pending,0\r\n"C\n""D""",loss,0.5');assert.equal(rows.length,2);assert.equal(rows[0].player,'A, B');assert.equal(rows[0].stake,'0');assert.equal(rows[1].player,'C\n"D"');assert.throws(()=>parser.signalCsv('a\n"unfinished'));});
test('Only explicit results are classified, with bet outcome taking priority over match result',()=>{assert.equal(parser.resultGroup({bet_outcome:'loss',result:'2-1'}),'settled');assert.equal(parser.resultGroup({status:'pending'}),'pending');assert.equal(parser.resultGroup({status:'candidate'}),'other');assert.equal(parser.resultGroup({}),'other');assert.equal(parser.resultGroup({result:'void'}),'settled');});
test('Private API denies anonymous and unknown views before reading and returns errors without fake empty results',async()=>{let auth=false,reads=0,fail=false;const route=load('src/app/api/admin/model-signals/route.ts',{'next/server':{NextResponse:{json:(b,o)=>Response.json(b,o)}},'@/lib/admin-auth':{isAdminSession:async()=>auth},'@/lib/admin-signals-reader':{catalog:[{id:'known'}],readAdminSignalFile:async()=>{reads++;if(fail)throw Error('unavailable');return {content:'saved',manifest:[]};}}});const request=id=>({url:'https://site.test/api/admin/model-signals?view='+id});assert.equal((await route.GET(request('known'))).status,401);auth=true;assert.equal((await route.GET(request('unknown'))).status,400);assert.equal(reads,0);const response=await route.GET(request('known'));assert.equal(response.status,200);assert.equal(response.headers.get('cache-control'),'private, no-store');fail=true;assert.equal((await route.GET(request('known'))).status,503);});
test('Football views prefer newer scheduled files, retain newer local files and disclose cloud failures',async()=>{let auth=true,cloudMtime='2026-10-14T10:00:00Z',cloudFails=false;const catalog=[{id:'football-candidates',file:'data/candidates.csv'}];const q=()=>{let key='';return {select(){return this;},eq(_,v){key=v;return this;},abortSignal(){return this;},async single(){return key==='corners_state'?(cloudFails?{data:null,error:true}:{data:{generated_at:'cloud upload',file:{content:'cloud rows',mtime:cloudMtime}}}):{data:{generated_at:'local upload',manifest:[{id:'football-candidates',modified_at:'2026-10-13T10:00:00Z'}],content:'local rows'}};}}};const reader=load('src/lib/admin-signals-reader.ts',{'server-only':{},'@/lib/admin-auth':{isAdminSession:async()=>auth},'@/lib/supabase-server':{getSupabaseAdmin:()=>({from:q})},'@/lib/team-shots-live-files':{},'../../config/admin-monitor-catalog.json':catalog});assert.equal((await reader.readAdminSignalFile('football-candidates')).content,'cloud rows');cloudMtime='2026-10-12T10:00:00Z';assert.equal((await reader.readAdminSignalFile('football-candidates')).content,'local rows');cloudFails=true;assert.match((await reader.readAdminSignalFile('football-candidates')).warning,/could not be checked/);auth=false;await assert.rejects(reader.readAdminSignalFile('football-candidates'),/Unauthorized/);});
const display=load('src/lib/admin-monitor-display.ts');
test('Selected tennis player is first with that player’s price and fair odds',()=>{const r=display.selectionCard({player1:'Opponent',player2:'Selection',side:'P2',pin_odds1:'1.5',pin_odds2:'2.9',our_odds1:'1.7',our_odds2:'2.4',value_p2:'20.83'},'tennis-strict-archive');assert.equal(r.selection,'Selection to win');assert.equal(r.opponent,'Opponent');assert.equal(r.odds,2.9);assert.equal(r.fair,2.4);assert.equal(r.ev,20.83);});
test('Handicaps never substitute match winner fair odds',()=>{const r=display.selectionCard({player1:'A',player2:'B',side:'P2',bet_type:'spread',spread_line:'3.5',spread_odds:'1.91',our_odds2:'4.1'},'tennis-spreadv1-archive');assert.equal(r.selection,'B +3.5 games');assert.equal(r.odds,1.91);assert.equal(r.fair,null);});
test('EV scales remain correct and losing or excluded selections are explicit',()=>{assert.equal(display.selectionCard({edge:0.106},'gk-record').ev,10.6);assert.equal(display.selectionCard({value_pct:'10.6'},'props-record').ev,10.6);assert.equal(display.selectionCard({status:'settled',won:false},'hardcourt-scout-v1').outcome,'Lost');assert.equal(display.selectionCard({result:'win',quarantine_reason:'ambiguous'},'props-record').outcome,'Excluded');});
test('Reciprocal forecasts pair only within identical fixture context without losing rows',()=>{const rows=[{player:'A',opponent:'B',date:'2026-10-15',tournament:'One'},{player:'B',opponent:'A',date:'2026-10-15',tournament:'One'},{player:'B',opponent:'A',date:'2026-10-16',tournament:'One'},{player:'B',opponent:'A',date:'2026-10-15',tournament:'Two'}];const groups=display.forecastGroups(rows);assert.equal(groups.length,3);assert.equal(groups[0].rows.length,2);assert.equal(groups.reduce((n,g)=>n+g.rows.length,0),4);});
test('V4 observations and football scans are not mislabelled as another model’s selections',()=>{assert.equal(display.visibleRows([{v4_signal:'false'},{v4_signal:'true'}],'aces-v4','aces4').length,1);const rows=[{model:'team_shots_v4'},{model:'corners_v3'}];assert.equal(display.visibleRows(rows,'football-candidates','shots')[0].model,'team_shots_v4');assert.equal(display.visibleRows(rows,'football-candidates','corners')[0].model,'corners_v3');});
test('Most aces uses the three-way market, including ties, rather than match winner prices',()=>{let r=display.selectionCard({player1:'A',player2:'B',recommended_side:'P2',selected_odds:'2.5',fair_player2:'2.2',value_player2_pct:'13.64'},'most-aces-record');assert.equal(r.selection,'B · Most aces');assert.equal(r.fair,2.2);assert.equal(r.ev,13.64);r=display.selectionCard({player1:'A',player2:'B',recommended_side:'DRAW',open_draw_odds:'15',fair_draw:'12',value_draw_pct:'25'},'most-aces-record');assert.equal(r.selection,'Tie for most aces');assert.equal(r.odds,15);assert.equal(r.fair,12);});
test('Every curated model view exists in the approved upload catalog',()=>{const catalog=JSON.parse(fs.readFileSync('config/admin-monitor-catalog.json','utf8'));for(const m of display.monitorModels)for(const [id]of m.views)assert.ok(catalog.some(v=>v.id===id),id);assert.ok(!display.monitorModels.some(m=>m.views.some(([id])=>id==='full-refresh')));});
test('Display profit requires explicit outcome, stake and odds and never supplies a fictional stake',()=>{const won=display.selectionCard({player:'A',odds:'2.02',stake_units:'0.5',result:'win'},'tennis-strict-archive');assert.equal(won.profit,0.51);assert.equal(won.calculatedProfit,true);assert.equal(display.selectionCard({odds:'2.02',result:'win'},'tennis-strict-archive').profit,null);assert.equal(display.selectionCard({odds:'2.02',stake_units:'1',status:'pending'},'tennis-strict-archive').profit,null);assert.equal(display.selectionCard({odds:'2.02',stake_units:'1',result:'win',pnl_units:'0.8'},'tennis-strict-archive').profit,0.8);});
test('Aces/DF record excludes service-break research while retaining the full source in diagnostics',()=>{const rows=[{market:'aces'},{market:'double_faults'},{market:'player_breaks',decision_mode:'breaks_calibration_unfiltered'}];assert.equal(display.visibleRows(rows,'props-record','props').length,2);assert.equal(display.visibleRows(rows,'props-record','reference').length,3);});


test('Awaiting settlement includes failed result lookups without classifying them as new selections or settling them',()=>{
 const rows=[{settlement_status:'no_match',settlement_note:'No exact result',player:'A'}, {settlement_status:'ambiguous'}, {settlement_status:'pending'}, {result:'win'}, {result:'void'}, {status:'duplicate'}];
 const before=JSON.stringify(rows);
 const shown=rows.filter(r=>display.matchesOutcomeFilter(display.selectionCard(r,'tennis-strict-archive').outcome,'pending'));
 assert.equal(shown.length,3);
 assert.equal(display.selectionCard(shown[0],'tennis-strict-archive').outcome,'Not settled');
 assert.equal(display.selectionCard(shown[0],'tennis-strict-archive').profit,null);
 assert.equal(JSON.stringify(rows),before);
});


test('Match ace totals require reciprocal forecasts for exactly the same fixture',()=>{
 const a={player:'A',opponent:'B',date:'2026-10-29',tournament:'Vienna',projected_aces:'6.927'};
 const b={player:'B',opponent:'A',date:'2026-10-29',tournament:'Vienna',projected_aces:'4.441'};
 assert.ok(Math.abs(display.pairedAceTotal([a,b])-11.368)<1e-9);
 assert.equal(display.pairedAceTotal([a,{...b,tournament:'Basel'}]),null);
 assert.equal(display.pairedAceTotal([a,{...b,projected_aces:''}]),null);
 assert.equal(display.pairedAceTotal([a,a]),null);
});
test('Current tournament totals retain zeros, disclose missing values and exclude future dates',()=>{
 const row={date:'2026-10-29',same_tournament_matches:'3',tournament_round_log:JSON.stringify([
  {date:'2026-10-27',opponent:'A',aces:'6',dfs:'3'},
  {date:'2026-10-28',opponent:'B',aces:'0',dfs:''},
  {date:'2026-10-30',opponent:'Future',aces:'99',dfs:'99'}])};
 const h=display.tournamentHistory(row);
 assert.equal(h.logs.length,2);assert.equal(h.aces.value,6);assert.equal(h.aces.covered,2);
 assert.equal(h.dfs.value,3);assert.equal(h.dfs.covered,1);assert.equal(h.incomplete,true);
 assert.equal(display.tournamentHistory({tournament_round_log:'broken'}).aces.value,null);
 assert.equal(display.tournamentHistory({tournament_round_log:'[]'}).aces.value,null);
});

test('Most Aces current display selects the refreshed Direct cohort without borrowing old results',()=>{
 const old='most_aces_direct_1x2_v1',fresh=old+'_oncourt_20261029',count='v3_aces_gaussian_copula_nb2_evidence_tiers_v3';
 const matches=[{model:count},{model:fresh}],records=[{model:old,wins:0,losses:4},{model:fresh,wins:0,losses:0}];
 const selected=display.currentMostAcesModel(matches,records,'direct');
 assert.equal(selected,fresh);assert.equal(records.find(r=>r.model===selected).losses,0);
 assert.equal(display.currentMostAcesModel(matches,records,'count'),count);
 assert.equal(display.currentMostAcesModel([],[{model:old}],'direct'),old);
 assert.equal(display.currentMostAcesModel([],records,'direct'),fresh);
});
