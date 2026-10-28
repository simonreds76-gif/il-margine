const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs'),vm=require('node:vm'),ts=require('typescript');
const source=fs.readFileSync('src/lib/admin-signals-reader.ts','utf8');
function reader(auth=true,missing=false){
 const module={exports:{}};let cloudReads=0;
 const mocks={
  'server-only':{},
  '@/lib/admin-auth':{isAdminSession:async()=>auth},
  '@/lib/supabase-server':{getSupabaseAdmin:()=>{cloudReads++;throw Error('Wrong PC snapshot read');}},
  '../../config/admin-monitor-catalog.json':[{id:'gk-record',file:'data/goalkeeper-saves/gk-saves-v1-shadow-signals.csv'}],
  '@/lib/team-shots-live-files':{
   readTeamShotsLiveFile:async()=>missing?'':'canonical,current,ledger',
   inspectTeamShotsLiveSource:async()=>({source:missing?'missing':'hosted',hostedGeneratedAt:'2026-10-28T16:40:00Z',hostedFileMtime:'2026-10-28T16:39:00Z'}),
  },
 };
 vm.runInNewContext(ts.transpileModule(source,{compilerOptions:{module:ts.ModuleKind.CommonJS,esModuleInterop:true}}).outputText,{module,exports:module.exports,require:n=>mocks[n],AbortSignal});
 return {read:module.exports.readAdminSignalFile,reads:()=>cloudReads};
}
test('GK Admin records use the same canonical snapshot as the dedicated monitor',async()=>{
 const r=reader(),v=await r.read('gk-record');
 assert.equal(v.content,'canonical,current,ledger');assert.equal(v.source,'Scheduled football snapshot');
 assert.equal(v.generated_at,'2026-10-28T16:40:00Z');assert.equal(r.reads(),0);
});
test('private authentication and missing-source failures are retained',async()=>{
 await assert.rejects(reader(false).read('gk-record'),/Unauthorized/);
 await assert.rejects(reader(true,true).read('gk-record'),/snapshot unavailable/);
 await assert.rejects(reader().read('unknown'),/Unknown model view/);
});
