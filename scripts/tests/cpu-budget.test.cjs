const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const vm=require('node:vm');
const root=process.env.CPU_TEST_ROOT || path.resolve(__dirname,'../..');
const ts=require(path.join(root,'node_modules/typescript'));
function compile(source, imports={}, globals={}) {
 const module={exports:{}};
 vm.runInNewContext(ts.transpileModule(source,{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022,esModuleInterop:true}}).outputText,
 {module,exports:module.exports,URL,Response,Request,Date,setTimeout,clearTimeout,process:{env:{}},...globals,require:n=>imports[n]??require(n)});
 return module.exports;
}
const cache=compile(fs.readFileSync(path.join(root,'src/lib/bounded-async-cache.ts'),'utf8'));
test('concurrent callers share one load, expiry reloads, capacity is bounded',async()=>{
 let now=0,calls=0,resolve;
 const c=cache.createBoundedAsyncCache(2,()=>now);
 const load=()=>{calls++;return new Promise(r=>resolve=r)};
 const a=c.get('a',100,load), b=c.get('a',100,load);
 await Promise.resolve(); assert.equal(calls,1); assert.equal(a,b);
 resolve(42); assert.equal(await a,42);
 assert.equal(await c.get('a',100,()=>Promise.resolve(99)),42);
 now=101;assert.equal(await c.get('a',100,()=>Promise.resolve(99)),99);
 await c.get('b',100,()=>Promise.resolve(1));await c.get('c',100,()=>Promise.resolve(2));
 assert.equal(await c.get('a',100,()=>Promise.resolve(100)),100);
});
test('failed and slow loads cannot leave stale successful entries',async()=>{
 let now=0;
 const c=cache.createBoundedAsyncCache(1,()=>now);
 await assert.rejects(c.get('a',10,async()=>{throw Error('database unavailable')}));
 assert.equal(await c.get('a',10,async()=>{now=20;return 1}),1);
 assert.equal(await c.get('a',10,async()=>2),2);
});
test('scope keys coalesce queries; live responses cache briefly; errors are not cached',async()=>{
 let queries=0,fail=false;
 const query=new Proxy({}, {get:(_,key)=>key==='then' ? (resolve)=>resolve({data:[],error:fail?{message:'offline'}:null}) : ()=>query});
 const api=compile(fs.readFileSync(path.join(root,'src/app/api/public-record/route.ts'),'utf8'),{
  '@/lib/bounded-async-cache':cache,
  '@/lib/supabase-server':{getSupabaseAdmin:()=>({from:()=>{queries++;return query}})},
  '@/lib/bet-category':{getDisplayBetCategory:()=>''},
  'next/server':{NextResponse:{json:(p,o)=>Response.json(p,o)}}
 });
 const responses=await Promise.all(['home','home&ts=1','home&ts=2'].map(s=>api.GET(new Request('https://example.com/api/public-record?scope='+s))));
 assert.equal(queries,4);
 for(const r of responses){assert.equal(r.status,200);assert.match(r.headers.get('Cache-Control'),/s-maxage=30/);assert.doesNotMatch(r.headers.get('Cache-Control'),/stale-while/)}
 fail=true;const error=await api.GET(new Request('https://example.com/api/public-record?scope=tennis'));
 assert.equal(error.status,500);assert.equal(error.headers.get('Cache-Control'),'no-store');
 fail=false;assert.equal((await api.GET(new Request('https://example.com/api/public-record?scope=tennis'))).status,200);
});
function fairApi(hosted, run) {
 const source=fs.readFileSync(path.join(root,'src/app/api/fair-odds/route.ts'),'utf8');
 return compile(source.slice(source.indexOf('const hostedResponseCache =')),{},
 {createBoundedAsyncCache:cache.createBoundedAsyncCache,NextResponse:{json:(p,o)=>Response.json(p,o)},API_TIMEOUT_MS:1000,run,process:{env:hosted?{VERCEL:'1'}:{}}});
}
test('hosted fair odds coalesces, clones independently, and local refresh stays direct',async()=>{
 let calls=0;const run=async()=>Response.json({version:++calls});
 const hosted=fairApi(true,run);
 const [a,b]=await Promise.all([hosted.GET(),hosted.GET()]);
 assert.deepEqual(await a.json(),{version:1});assert.deepEqual(await b.json(),{version:1});assert.equal(calls,1);
 assert.match(a.headers.get('Cache-Control'),/s-maxage=30/);
 const local=fairApi(false,run);await local.GET();await local.GET();assert.equal(calls,3);
});
test('hosted fair odds retries failures without caching a false healthy response',async()=>{
 let calls=0;
 const api=fairApi(true,async()=>++calls===1?Response.json({error:'upstream'},{status:503}):Response.json({ok:true}));
 assert.equal((await api.GET()).status,503);assert.equal((await api.GET()).status,200);assert.equal(calls,2);
});
test('homepage proxy executes only for the query that needs canonicalization',()=>{
 const {unstable_doesMiddlewareMatch}=require(path.join(root,'node_modules/next/experimental/testing/server'));
 const {config}=compile(fs.readFileSync(path.join(root,'src/proxy.ts'),'utf8'),{'next/server':{}});
 assert.equal(unstable_doesMiddlewareMatch({config,url:'https://example.com/'}),false);
 assert.equal(unstable_doesMiddlewareMatch({config,url:'https://example.com/?utm_source=test'}),false);
 assert.equal(unstable_doesMiddlewareMatch({config,url:'https://example.com/?q=arsenal'}),true);
 assert.equal(unstable_doesMiddlewareMatch({config,url:'https://example.com/penalty-takers/epl/arsenal'}),false);
});
test('penalty data reuses its date formatter and preserves date output',async()=>{
 let constructions=0;
 const NativeFormat=Intl.DateTimeFormat;
 const api=compile(fs.readFileSync(path.join(root,'src/lib/club-penalty-takers.ts'),'utf8'),{
  'server-only':{},'react':{cache:f=>f},
  '@/lib/config':{BASE_URL:'https://ilmargine.bet'},
  '@/lib/project-file-paths':{getKnownProjectFilePath:p=>path.join(root,p)},
  '../../data/goalscorer/club-penalty-season.json':JSON.parse(fs.readFileSync(path.join(root,'data/goalscorer/club-penalty-season.json'),'utf8')),
 },{Intl:{DateTimeFormat:function(...args){constructions++;return new NativeFormat(...args)}}});
 const data=await api.readClubPenaltyData();
 assert.ok(data.length>=5);
 assert.equal(constructions,1);
 for(const date of ['2026-01-02','2026-07-01','2026-10-25']){
  assert.equal(api.formatClubPenaltyDate(date),new NativeFormat('en-GB',{timeZone:'Europe/London',day:'numeric',month:'short',year:'numeric'}).format(new Date(date+'T12:00:00Z')));
 }
 assert.equal(api.formatClubPenaltyDate('invalid'),'invalid');
});
