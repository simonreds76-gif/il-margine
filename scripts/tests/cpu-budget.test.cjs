const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const vm=require('node:vm');
const root=process.env.CPU_TEST_ROOT || path.resolve(__dirname,'../..');
const ts=require(path.join(root,'node_modules/typescript'));
function compile(source, imports={}, globals={}) {
 const module={exports:{}};
 vm.runInNewContext(ts.transpileModule(source,{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022,esModuleInterop:true,jsx:ts.JsxEmit.ReactJSX}}).outputText,
 {module,exports:module.exports,URL,Response,Request,Date,setTimeout,clearTimeout,process:{env:{}},...globals,require:n=>imports[n]??require(n)});
 return module.exports;
}
const cache=compile(fs.readFileSync(path.join(root,'src/lib/bounded-async-cache.ts'),'utf8'));
test('tip preview PNGs have an explicit shared cache and missing tips avoid rendering',async()=>{
 let fixture=null, renders=0;
 const format=compile(fs.readFileSync(path.join(root,'src/lib/format.ts'),'utf8'));
 const share=compile(fs.readFileSync(path.join(root,'src/lib/tip-share.ts'),'utf8'),{'./format':format});
 const renderer=compile(fs.readFileSync(path.join(root,'src/lib/tip-share-image.tsx'),'utf8'),{
  'server-only':{}, './config':{BASE_URL:'https://ilmargine.bet'},
  'next/og':{ImageResponse:class extends Response {constructor(_jsx,options){super('png',options);renders++;}}},
  './site-brand-image':{SITE_BRAND_IMAGE:'test-logo'},
  './share-fonts':{SHARE_FONTS:[]},
  './tip-artwork':{getTipArtwork:()=>[]}, './format':format, './tip-share':share,
  'react/jsx-runtime':{jsx:()=>null,jsxs:()=>null},
 });
 const route=compile(fs.readFileSync(path.join(root,'src/app/betting-tips/[slugId]/opengraph-image.tsx'),'utf8'),{
  '@/lib/tip-seo-server':{fetchSeoTipFixture:async()=>fixture},
  '@/lib/tip-share-image':renderer,
 });
 const missing=await route.default({params:Promise.resolve({slugId:'missing'})});
 assert.equal(missing.status,404);assert.equal(renders,0);
 fixture={bets:[{id:1,event:'Home vs Away',market:'props',category:'pl',player:'Keeper',selection:'Over 2.5 saves',odds:1.73,stake:0.5,match_date:'2026-10-15'}]};
 const valid=await route.default({params:Promise.resolve({slugId:'known'})});
 assert.equal(valid.status,200);assert.equal(renders,1);
 assert.equal(route.revalidate,604800);
 assert.match(valid.headers.get('Cache-Control'),/s-maxage=604800/);
 assert.doesNotMatch(valid.headers.get('Cache-Control'),/immutable/);
 const details=share.tipShareDetails(fixture.bets);
 assert.match(details.title,/Keeper · Over 2.5 saves at 1.73/);
 assert.match(details.description,/stake 0.5u/);
 const multi=share.tipShareDetails([...fixture.bets,{...fixture.bets[0],id:2,player:'Striker',selection:'Over 1.5 shots',odds:2.2}]);
 assert.match(multi.title,/2 published selections/);
 assert.match(multi.description,/Striker · Over 1.5 shots at 2.20/);
 assert.throws(()=>share.tipShareDetails([]),/requires a published selection/);
});
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
 const query=new Proxy({}, {get:(_,key)=>key==='then' ? (resolve)=>resolve({data:[{id:1,market:'props',category:'pl',event:'Hull vs Everton',player:'Keane'}],error:fail?{message:'offline'}:null}) : ()=>query});
 const monthlyLoader=compile(fs.readFileSync(path.join(root,'src/lib/public-record.ts'),'utf8'),{
  'server-only':{},
  '@/lib/tip-artwork':{getTipArtwork:()=>[]},
  '@/lib/monthly-record':compile(fs.readFileSync(path.join(root,'src/lib/monthly-record.ts'),'utf8')),
  '@/lib/read-record-pages':compile(fs.readFileSync(path.join(root,'src/lib/read-record-pages.ts'),'utf8')),
  '@/lib/supabase-server':{getSupabaseAdmin:()=>({from:()=>{queries++;return query}}),hasSupabaseAdminConfig:()=>true},
  '@/lib/bet-category':{getDisplayBetCategory:()=>''},
 });
 const api=compile(fs.readFileSync(path.join(root,'src/app/api/public-record/route.ts'),'utf8'),{
  '@/lib/public-record':monthlyLoader,
  '@/lib/tip-artwork':{getTipArtwork:()=>[{name:'Michael Keane',src:'verified.png',kind:'player'}]},
  '@/lib/bounded-async-cache':cache,
  '@/lib/supabase-server':{getSupabaseAdmin:()=>({from:()=>{queries++;return query}})},
  '@/lib/bet-category':{getDisplayBetCategory:()=>''},
  'next/server':{NextResponse:{json:(p,o)=>Response.json(p,o)}}
 });
 const responses=await Promise.all(['home','home&ts=1','home&ts=2'].map(s=>api.GET(new Request('https://example.com/api/public-record?scope='+s))));
 assert.equal(queries,4);
 for(const r of responses){assert.equal(r.status,200);assert.match(r.headers.get('Cache-Control'),/s-maxage=30/);assert.doesNotMatch(r.headers.get('Cache-Control'),/stale-while/);const body=await r.json();assert.equal(body.pending[0].artwork[0].src,'verified.png');assert.equal(body.recent[0].artwork[0].src,'verified.png')}
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
  '@/lib/penalty-editorial-store': {readPenaltyOverrides: async () => ({})},
  '@/lib/penalty-editorial': {penaltyKey: (league, team) => `${league}|${team}`},
  'server-only':{},'react':{cache:f=>f},
  '@/lib/config':{BASE_URL:'https://ilmargine.bet'},
  '@/lib/player-name-matching':compile(fs.readFileSync(path.join(root,'src/lib/player-name-matching.ts'),'utf8')),
  '@/lib/football-club-names':compile(fs.readFileSync(path.join(root,'src/lib/football-club-names.ts'),'utf8')),
  '../../data/goalscorer/penalty-player-portraits.json':JSON.parse(fs.readFileSync(path.join(root,'data/goalscorer/penalty-player-portraits.json'),'utf8')),
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
