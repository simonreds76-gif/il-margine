const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const ts=require('typescript');
const cache={};
function load(name){if(cache[name])return cache[name].exports;const m=cache[name]={exports:{}};const code=ts.transpileModule(fs.readFileSync(`src/lib/${name}.ts`,'utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022}}).outputText;new Function('module','exports','require',code)(m,m.exports,dep=>load(dep.replace('./','')));return m.exports;}
const {propsBreakdowns,footballModel}=load('monitor-breakdowns');
const {row}=load('admin-model-summary');
const header='date,signal_id,market,tour,settlement_status,result,pnl,quarantine_reason\n';
const csv=header+'2026-11-01,a,aces,ATP,settled,win,2,\n2026-11-02,b,double_faults,WTA,settled,loss,-1,\n2026-11-03,c,aces,WTA,pending,,99,\n2026-11-03,d,aces,ATP,void,void,0,\n2026-11-03,e,double_faults,WTA,quarantined,win,40,disputed\n';
const expected=row('props','Props','','',{settled:2,pnl_units:1},'2026-11-03');
test('market and tour charts partition the same canonical results without double counting pending/void/quarantine',()=>{
 const result=propsBreakdowns(csv,expected),find=id=>result.rows.find(r=>r.id===id);
 assert.equal(find('props-men').profit,2);assert.equal(find('props-women').profit,-1);assert.equal(find('props-women').pending,1);
 assert.equal(find('props-aces').profit,2);assert.equal(find('props-double_faults').profit,-1);
 for(const r of result.rows){assert.equal(result.histories[r.id].message,undefined);assert.equal(r.stake,r.settled);}
});
test('unknown tour is never silently assigned to men and stale parent totals never produce split charts',()=>{
 const unknown=propsBreakdowns(csv.replace(',ATP,',',UNKNOWN,'),expected);
 assert.equal(unknown.rows.find(r=>r.id==='props-men').profit,null);assert.ok(unknown.histories['props-women'].message);
 assert.equal(unknown.histories['props-aces'].message,undefined);
 const stale=propsBreakdowns(csv,{...expected,settled:3});assert.ok(stale.rows.every(r=>r.profit===null));
});
test('missing data and duplicate records fail closed',()=>{
 for(const content of [null,'broken"',csv+'2026-11-01,a,aces,ATP,settled,win,2,\n']){
  assert.ok(propsBreakdowns(content,expected).rows.every(r=>r.profit===null));
 }
});
test('current football headline and curve exclude warmup and refuse mismatched dated evidence',()=>{
 const ledger='match_date,pick_id,pnl_units,result,signal_status,confidence_guard_applied,blocked_reason\n2026-11-01,a,-1,lost,eligible,false,\n2026-11-01,b,30,won,warmup_tracking,false,\n';
 const result=footballModel('shots','Shots',{settled:1,pnl_units:-1,roi:-1},'2026-11-01',ledger,'');
 assert.equal(result.history.message,undefined);assert.equal(result.row.losses,1);assert.equal(result.row.stake,null);
 assert.ok(footballModel('shots','Shots',{settled:2,pnl_units:29},'2026-11-01',ledger,'').history.message);
});
test('actual private props and latest cloud football records reconcile exactly', {skip:!process.env.MONITOR_SEGMENT_FIXTURES},()=>{
 const root=process.env.MONITOR_SEGMENT_FIXTURES;
 const read=fn=>JSON.parse(fs.readFileSync(root+'/'+fn,'utf8'));
 const d=read('tennis_evidence_v1.json'),p=d.sections.tennis_props_shadow_decision;
 const before=JSON.stringify(d),r=propsBreakdowns(d.props_ledger,row('props','Props','','',p,p.generated_at));
 for(const x of r.rows){assert.equal(r.histories[x.id].message,undefined,x.id);console.log(JSON.stringify({id:x.id,settled:x.settled,profit:x.profit,roi:x.roi,pending:x.pending}));}
 for(const pair of [['aces','double_faults'],['men','women']]){const xs=r.rows.filter(x=>pair.includes(x.id.slice(6)));assert.equal(xs.reduce((sum,x)=>sum+x.settled,0),p.settled);assert.ok(Math.abs(xs.reduce((sum,x)=>sum+x.profit,0)-p.pnl_units)<.00001);}
 assert.equal(JSON.stringify(d),before);
 const shots=read('shots-canonical.json'),corners=read('corners-canonical.json');
 const content=(bundle,path)=>bundle.files['data/football-form/'+path].content;
 const gate=JSON.parse(content(shots,'football-counts-vnext-gate.json')),opp=JSON.parse(content(shots,'team-shots-opponent-status.json'));
 for(const [id,raw,ledger] of [['team_shots_v4',gate.team_shots_v4.prospective,content(shots,'team-shots-v4-shadow-clv.csv')],['corners_v3',gate.corners_v3.prospective,content(corners,'corners-v3-shadow-clv.csv')],['team_shots_opponent',opp.prospective,content(shots,'team-shots-opponent-shadow.csv')]]){
  const r=footballModel(id,id,raw,gate.generated_at,ledger,'');assert.equal(r.history.message,undefined,id);console.log(JSON.stringify(r.row));
 }
});

test('paired comparison accepts future input revisions with the same verified schema, not unrelated or incomplete payloads',()=>{
 const {validShotsComparison}=load('monitor-breakdowns');
 const data={version:'paired-market-offset-20270101-v5',generated_at:'2027-01-01T12:00:00Z',contracts:10,paired_fixtures:5,models:Object.fromEntries(['shots_market_offset_v1','opponent','v4','ema20_v3'].map(id=>[id,{hypothetical_selections:{settled:0,pnl_units:0}}]))};
 assert.equal(validShotsComparison(data),true);
 for(const bad of [{...data,version:'different-model'}, {...data,models:{}}, {...data,generated_at:'unknown'}])assert.equal(validShotsComparison(bad),false);
});
