const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs'),path=require('node:path'),vm=require('node:vm'),ts=require('typescript');
function load(file,imports={}){const module={exports:{}};vm.runInNewContext(ts.transpileModule(fs.readFileSync(path.resolve(file),'utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022,esModuleInterop:true}}).outputText,{module,exports:module.exports,require:n=>imports[n]??require(n),structuredClone,URL,Date,process:{env:{}}});return module.exports;}
test('saved current-season hierarchy supplies latest public evidence; old record and archive are retained',async()=>{
 const entry={primary:'',secondary:'',tertiary:'',evidence_log:[{id:'old-review',date:'2026-09-19',type:'current_season_board_review',affects_hierarchy:true,context:'Order remains open',review:{status:'approved'}}]};
 const season={label:'2026/27',previous_label:'2025/26',published_at:'2026-07-10',league_start_dates:{}};
 const model=load('src/lib/penalty-editorial.ts');let overrides={};
 const api=load('src/lib/club-penalty-takers.ts',{'server-only':{},react:{cache:f=>f},'node:fs':{promises:{readFile:async p=>JSON.stringify(p.includes('team-logo-map')?{}:{_meta:{season:{label:p.includes('archive/')?'2025/26':'2026/27'}},'SV Elversberg':entry})}},'@/lib/config':{BASE_URL:'https://ilmargine.bet'},'@/lib/project-file-paths':{getKnownProjectFilePath:p=>p},'@/lib/penalty-editorial':model,'@/lib/penalty-editorial-store':{readPenaltyOverrides:async()=>overrides},'@/lib/player-name-matching':load('src/lib/player-name-matching.ts'),'@/lib/football-club-names':load('src/lib/football-club-names.ts'),'../../data/goalscorer/penalty-player-portraits.json':{},'../../data/goalscorer/club-penalty-season.json':season});
 const original=await api.readClubPenaltyData();
 overrides['bundesliga|svelversberg']={order:{primary:'Lukas Petkov',secondary:'Noel Futkeu',tertiary:'Francis Onyeka'},season:'2026/27',at:'2026-10-18T12:00:00Z',reason:'Both took penalties on 17 October; third candidate provisional.',source:'https://www.bundesliga.com/example'};
 const updated=await api.readClubPenaltyData();const team=updated.find(l=>l.key==='bundesliga').teams[0];
 assert.equal(team.evidenceUpdates[0].date,'2026-10-18');
 assert.equal(team.evidenceUpdates[0].type,'editorial_hierarchy_review');
 assert.equal(team.evidenceUpdates[0].fullSummary,overrides['bundesliga|svelversberg'].reason);
 assert.equal(team.evidenceUpdates[1].id,'old-review');
 assert.equal(team.primary,'Lukas Petkov');
 assert.equal(JSON.stringify(updated.map(l=>l.archivedTeams)),JSON.stringify(original.map(l=>l.archivedTeams)));
 overrides['bundesliga|svelversberg'].season='2025/26';
 assert.equal((await api.readClubPenaltyData()).find(l=>l.key==='bundesliga').teams[0].evidenceUpdates[0].id,'old-review');
});
