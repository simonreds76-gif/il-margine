const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const ts = require('typescript');
const root = path.resolve(__dirname, '../..');
const europa = require('./fixtures/tip-portrait-europa-squads.json');
const squads = require('./fixtures/tip-portrait-squads.json');
const independent = require('./fixtures/tip-portrait-independent.json');
const source = (club) => `<script id="__NEXT_DATA__" type="application/json">${JSON.stringify({props:{pageProps:{fallback:{['team-'+squads[club].details.id]:squads[club]}}}})}</script>`;

function harness({ fail = false, empty = false, noSquad = false, updateError = false, unauthorized = false, allowPost = false, responses = {} } = {}) {
  const cache = new Map();
  const cachedValues = new Map(), invalidations = [], paths = [];
  let fetches = 0, queries = 0;
  const cached = (fn, parts = [], options = {}) => {
    return async (...args) => {
      const key = JSON.stringify([fn.toString(),parts,args]);
      if (!cachedValues.has(key)) cachedValues.set(key, {tags:options.tags || [],value:Promise.resolve().then(() => fn(...args)).catch((e) => { cachedValues.delete(key); throw e; })});
      return cachedValues.get(key).value;
    };
  };
  const pick = {id:123, market:'props',category:'ligue1',event:'Rennes vs Auxerre',player:'Cresswell'};
  const load = (file) => {
    if (!path.extname(file)) file += '.ts';
    if (file.endsWith('.json')) return JSON.parse(fs.readFileSync(file, 'utf8'));
    if (cache.has(file)) return cache.get(file).exports;
    const module = {exports:{}}; cache.set(file,module);
    const code = ts.transpileModule(fs.readFileSync(file,'utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022,esModuleInterop:true}}).outputText;
    const req = (id) => {
      if(id === 'server-only') return {};
      if(id === 'node:crypto' || id === 'crypto') return require(id);
      if(id === 'next/cache') return {unstable_cache:cached,revalidatePath:p=>paths.push(p),revalidateTag:(tag,profile)=>{
        invalidations.push({tag,profile});
        for(const [k,v] of cachedValues) if(v.tags.includes(tag)) cachedValues.delete(k);
      }};
      if(id === 'next/server') return {NextResponse:{json:(body,opts)=>Response.json(body,opts)}};
      if(id === 'next/headers') return {cookies:async()=>({get:()=>({value:unauthorized?'invalid':require('node:crypto').createHmac('sha256','portrait-test-only').update('admin_session').digest('base64url')})})};
      if(id === '@/lib/player-props-telegram') return {postPlayerPropTipToTelegram:()=>{if(allowPost)return {status:'posted'};throw new Error('Editing must not send Telegram');}};
      if(id === '@/lib/supabase-server') return {getSupabaseAdmin:()=>({from:()=>({
        select:()=>({eq:()=>({maybeSingle:async()=>{queries++;return {data:empty?null:{...pick},error:null};},single:async()=>({data:{...pick},error:null})})}),
        update:updates=>({eq:()=>({select:()=>({single:async()=>{if(updateError)return {data:null,error:{message:'Update rejected'}};Object.assign(pick,updates);return {data:{...pick},error:null};}})})}),
        insert:rows=>({select:()=>({single:async()=>({data:{...pick,...rows[0]},error:null})})}),
        delete:()=>({eq:async()=>({error:null})}),
      })})};
      return load(id.startsWith('@/')?path.join(root,'src',id.slice(2)):path.resolve(path.dirname(file),id));
    };
    const mockedFetch = async (url) => {
      fetches++;
      if(fail) throw new Error('timeout');
      if (url in responses) {
        const body = responses[url];
        if (body instanceof Error) throw body;
        return new Response('<script id="__NEXT_DATA__">'+JSON.stringify({props:{pageProps:body}})+'</script>');
      }
      if (url === 'https://www.fotmob.com/players/1186444/charlie-cresswell') {
        return new Response('<script id="__NEXT_DATA__">'+JSON.stringify({props:{pageProps:{data:{id:1186444,name:'Charlie Cresswell',isCoach:false,primaryTeam:{teamId:9851}}}}})+'</script>');
      }
      assert.match(url,/^https:\/\/www\.fotmob\.com\/teams\/\d+\/overview$/);
      const teamId = url.match(/teams\/(\d+)/)[1];
      if (noSquad && teamId === '8583') return new Response('<script id="__NEXT_DATA__">'+JSON.stringify({props:{pageProps:{fallback:{['team-'+teamId]:{details:{id:8583},squad:{squad:null}}}}}})+'</script>');
      if (europa[teamId]) return new Response('<script id="__NEXT_DATA__">'+JSON.stringify({props:{pageProps:{fallback:{['team-'+teamId]:europa[teamId]}}}})+'</script>');
      const club = url.includes('/9851/')?'rennes':'auxerre';
      return new Response(source(club));
    };
    vm.runInThisContext('(function(require,module,exports,fetch,process){'+code+'\n})',{filename:file})(req,module,module.exports,mockedFetch,{env:{ADMIN_PASSWORD:'portrait-test-only'}});
    return module.exports;
  };
  return {load,pick,invalidations,paths,counts:()=>({fetches,queries})};
}

test('new players resolve automatically despite missing opponent data, without a curated player entry',async()=>{
  const responses={};
  for(const [id,team] of Object.entries(independent.teams)) responses[`https://www.fotmob.com/teams/${id}/overview`]={fallback:{['team-'+id]:team}};
  for(const [id,profile] of Object.entries(independent.profiles)) responses[`https://www.fotmob.com/players/${id}/${profile.name.toLowerCase().replaceAll(' ','-')}`]={data:profile};
  const h=harness({responses});
  Object.assign(h.pick,{id:1301,category:'ucl',event:'Viking vs Sabah',player:'Botheim'});
  const artwork=h.load(path.join(root,'src/lib/tip-artwork.ts')).getTipArtwork;
  const photo='https://images.fotmob.com/image_resources/playerimages/741561.png';
  for(const player of ['Botheim','Erik Botheim']) for(const event of ['Viking vs Sabah','Sabah vs Viking FK']) {
    const result=artwork({...h.pick,player,event});
    assert.match(result[0].src,/^\/api\/tip-portrait\/1301\?v=/,'must exercise automatic lookup, not a manual override');
    assert.equal((await h.load(path.join(root,'src/lib/tip-portrait-resolver.ts')).resolveTipPortrait({...h.pick,player,event})).id,741561);
  }
  const {GET}=h.load(path.join(root,'src/app/api/tip-portrait/[id]/route.ts'));
  const response=await GET(new Request('https://example.test/api/tip-portrait/1301?v=8bcf8b9ed6e0&thumb=96'),{params:Promise.resolve({id:'1301'})});
  assert.equal(response.status,307);
  assert.equal(response.headers.get('location'),`/_next/image?url=${encodeURIComponent(photo)}&w=96&q=75`);
  assert.deepEqual(h.counts(),{fetches:3,queries:1},'two squads and one cached identity check');
  const r=h.load(path.join(root,'src/lib/tip-portrait-resolver.ts'));
  assert.equal((await r.resolveTipPortrait({...h.pick,player:'Bell'})).id,848345,'a second new player also resolves automatically');
  assert.deepEqual(h.counts(),{fetches:4,queries:1});
  assert.notEqual(artwork({...h.pick,event:'Rennes vs Auxerre'})[0].src,photo,'club identity must remain scoped');
  assert.notEqual(artwork({...h.pick,player:'Anders Botheim'})[0].src,photo,'another full name must not match');
});

test('opponent timeouts, invalid payloads and unknown club mappings do not discard a verified player',async()=>{
  const opponentUrl='https://www.fotmob.com/teams/8583/overview';
  for(const bad of [new Error('timeout'),{}, {fallback:{'team-8583':{details:{id:999},squad:{squad:[]}}}}]) {
    const h=harness({responses:{[opponentUrl]:bad}});
    const r=h.load(path.join(root,'src/lib/tip-portrait-resolver.ts'));
    for(const player of ['Cresswell','Charlie Cresswell','C. Cresswell']) {
      assert.equal((await r.resolveTipPortrait({...h.pick,player})).id,1186444);
    }
    assert.equal((await r.resolveTipPortrait({...h.pick,event:'Unknown Club vs Rennes'})).id,1186444);
  }
});

test('profile disagreement, transfers and service errors never become verified portraits',async()=>{
  const url='https://www.fotmob.com/players/1186444/charlie-cresswell';
  const original={id:1186444,name:'Charlie Cresswell',isCoach:false,primaryTeam:{teamId:9851}};
  for(const change of [{id:2},{name:'Aaron Cresswell'},{isCoach:true},{primaryTeam:{teamId:8583}},{primaryTeam:null}]) {
    const h=harness({noSquad:true,responses:{[url]:{data:{...original,...change}}}});
    const r=h.load(path.join(root,'src/lib/tip-portrait-resolver.ts'));
    assert.equal(await r.resolveTipPortrait(h.pick),null);
  }
  const h=harness({noSquad:true,responses:{[url]:new Error('profile temporarily unavailable')}});
  const {GET}=h.load(path.join(root,'src/app/api/tip-portrait/[id]/route.ts'));
  for(let i=0;i<2;i++) {
    const response=await GET(new Request('https://example.test'),{params:Promise.resolve({id:'123'})});
    assert.equal(response.status,503);assert.equal(response.headers.get('cache-control'),'no-store');
  }
  assert.deepEqual(h.counts(),{fetches:4,queries:1},'failed profile reads retry rather than storing a permanent miss');
});

test('ambiguity in the available roster is rejected before any profile lookup',async()=>{
  const team=structuredClone(squads.rennes);
  const group=team.squad.squad.find(g=>!/coach/i.test(g.title));
  group.members.push({id:9999,name:'Aaron Cresswell'});
  const h=harness({noSquad:true,responses:{'https://www.fotmob.com/teams/9851/overview':{fallback:{'team-9851':team}}}});
  const r=h.load(path.join(root,'src/lib/tip-portrait-resolver.ts'));
  assert.equal(await r.resolveTipPortrait(h.pick),null);
  assert.equal(h.counts().fetches,2);
  assert.equal((await r.resolveTipPortrait({...h.pick,player:'C. Cresswell'})).id,1186444);
  assert.equal(await r.resolveTipPortrait({...h.pick,player:'B. Cresswell'}),null);
});

test('partial lineup candidates need a full name or explicit initial and independent profile',async()=>{
  const team=structuredClone(require('./fixtures/tip-portrait-recent-lineups.json')['9728']);
  team.overview.lastMatch.status.utcTime=new Date(Date.now()-86400000).toISOString();
  const h=harness({responses:{
    'https://www.fotmob.com/teams/9728/overview':{fallback:{'team-9728':team}},
    'https://www.fotmob.com/teams/951893/overview':{fallback:{'team-951893':independent.teams['951893']}},
    'https://www.fotmob.com/players/1314657/vinicius-tobias':{data:{id:1314657,name:'Vinicius Tobias',isCoach:false,primaryTeam:{teamId:9728}}},
  }});
  const r=h.load(path.join(root,'src/lib/tip-portrait-resolver.ts'));
  const pick={...h.pick,event:'Shakhtar vs Sabah',category:'ucl'};
  assert.equal(await r.resolveTipPortrait({...pick,player:'Tobias'}),null);
  assert.equal((await r.resolveTipPortrait({...pick,player:'Vinicius Tobias'})).id,1314657);
  assert.equal((await r.resolveTipPortrait({...pick,player:'V. Tobias'})).id,1314657);
  assert.equal(h.counts().fetches,3);
});

test('current ATP Berrettini shorthand resolves to the verified Matteo portrait',()=>{
  const h=harness(); const artwork=h.load(path.join(root,'src/lib/tip-artwork.ts')).getTipArtwork;
  const pick={id:1255,market:'tennis',category:'atp',event:'Cobolli vs Berrettini',player:'Berrettini',match_date:'2026-10-29'};
  assert.equal(artwork(pick)[1].name,'Matteo Berrettini');
  assert.equal(artwork(pick)[1].src,'https://a.espncdn.com/i/headshots/tennis/players/full/2622.png');
  assert.equal(artwork({...pick,event:'Berrettini vs Cobolli'})[0].name,'Matteo Berrettini');
  assert.equal(pick.event,'Cobolli vs Berrettini','artwork must not change the saved pick');
});

test('Berrettini shorthand never overrides Jacopo, Challenger ambiguity or historical ATP records',()=>{
  const h=harness(); const artwork=h.load(path.join(root,'src/lib/tip-artwork.ts')).getTipArtwork;
  const pick={market:'tennis',category:'atp',event:'Matteo Berrettini vs Jacopo Berrettini',player:null,match_date:'2026-10-29'};
  assert.deepEqual(artwork(pick).map(p=>p.name),['Matteo Berrettini','Jacopo Berrettini']);
  assert.equal(artwork(pick)[1].src,null);
  for(const edit of [{category:'challenger'},{category:'wta'},{match_date:'2023-12-31'}]) {
    assert.equal(artwork({...pick,event:'Cobolli vs Berrettini',...edit})[1].src,null);
  }
  assert.equal(artwork({...pick,category:'challenger'})[0].name,'Matteo Berrettini');
  assert.equal(artwork({...pick,event:'Cobolli vs Zverev'})[1].name,'Alexander Zverev');
  assert.equal(artwork({...pick,event:'Cobolli vs Mischa Zverev'})[1].name,'Mischa Zverev');
});

test('a new surname-only pick gets a real club-scoped portrait without a curated player entry',async()=>{
  const h=harness();
  const artwork=h.load(path.join(root,'src/lib/tip-artwork.ts')).getTipArtwork(h.pick);
  assert.match(artwork[0].src,/^\/api\/tip-portrait\/123\?v=[a-f0-9]{12}$/);
  const {GET}=h.load(path.join(root,'src/app/api/tip-portrait/[id]/route.ts'));
  for(let n=0;n<2;n++) {
    const response=await GET(new Request('https://example.test/api/tip-portrait/123'),{params:Promise.resolve({id:'123'})});
    assert.equal(response.status,307);
    assert.equal(response.headers.get('location'),'https://images.fotmob.com/image_resources/playerimages/1186444.png');
  }
  assert.deepEqual(h.counts(),{fetches:2,queries:1});
});

test('ambiguous surnames, missing clubs, coaches and wrong team payloads do not get guessed',()=>{
  const h=harness(); const r=h.load(path.join(root,'src/lib/tip-portrait-resolver.ts'));
  const a=[{id:1,name:'Charlie Cresswell',clubId:1}],b=[{id:2,name:'Aaron Cresswell',clubId:2}];
  assert.equal(r.uniquePlayer('Cresswell',[a,b]),null);
  assert.equal(r.uniquePlayer('Charlie Cresswell',[a,b]).id,1);
  assert.equal(r.uniquePlayer('Cresswell',[a,[]]),null);
  assert.equal(r.uniquePlayer('Cress',[a,b]),null);
  assert.equal(r.clubsForPick({...h.pick,event:'Unknown vs Rennes'}).length,1);
  assert.equal(r.clubsForPick({...h.pick,event:'Rennes vs Rennes'}).length,0);
  assert.throws(()=>r.parseSquad(source('rennes'),8583),/identity/);
  const squad=r.parseSquad(source('rennes'),9851);
  const coaches=squads.rennes.squad.squad.filter(g=>/coach/i.test(g.title)).flatMap(g=>g.members);
  assert.equal(squad.some(p=>coaches.some(c=>c.id===p.id)),false);
});

test('small portraits resolve the same verified player before redirecting to the shared image cache',async()=>{
  const h=harness(),{GET}=h.load(path.join(root,'src/app/api/tip-portrait/[id]/route.ts'));
  for(const width of ['64','96','256']) {
    const response=await GET(new Request(`https://example.test/api/tip-portrait/123?v=123abc&thumb=${width}`),{params:Promise.resolve({id:'123'})});
    const location=new URL(response.headers.get('location'),'https://example.test');
    assert.equal(location.pathname,'/_next/image');
    assert.equal(location.searchParams.get('url'),'https://images.fotmob.com/image_resources/playerimages/1186444.png');
    assert.equal(location.searchParams.get('w'),width);
    assert.equal(location.searchParams.get('q'),'75');
  }
  for(const width of ['100000','https://attacker.test','0']) {
    const response=await GET(new Request(`https://example.test/api/tip-portrait/123?thumb=${encodeURIComponent(width)}`),{params:Promise.resolve({id:'123'})});
    assert.equal(response.headers.get('location'),'https://images.fotmob.com/image_resources/playerimages/1186444.png');
  }
  assert.deepEqual(h.counts(),{fetches:2,queries:1});
});

test('source outage, unknown tip and malformed IDs fail safely without arbitrary requests',async()=>{
  for(const config of [{fail:true},{empty:true}]){
    const h=harness(config),{GET}=h.load(path.join(root,'src/app/api/tip-portrait/[id]/route.ts'));
    const invalid=await GET(new Request('https://example.test'),{params:Promise.resolve({id:'../123'})});
    assert.equal(invalid.status,400); assert.deepEqual(h.counts(),{fetches:0,queries:0});
    const response=await GET(new Request('https://example.test'),{params:Promise.resolve({id:'123'})});
    assert.equal(response.status,config.fail?503:404);
    assert.equal(response.headers.get('cache-control'),'no-store');
    assert.equal(response.headers.get('location'),null);
    if(config.empty) assert.equal(h.counts().fetches,0);
  }
});

test('SV 07 Elversberg resolves to its existing club identity for new player tips',()=>{
  const h=harness();
  const r=h.load(path.join(root,'src/lib/tip-portrait-resolver.ts'));
  const logos=h.load(path.join(root,'src/lib/team-logos.ts'));
  const pick={...h.pick,category:'bundesliga',event:'RB Leipzig vs SV 07 Elversberg',player:'Vandevoordt'};
  assert.equal(logos.resolveTeamLogoPath('SV 07 Elversberg','bundesliga'),'/team-logos/bundesliga/sv-elversberg.png');
  assert.deepEqual(r.clubsForPick(pick).map(c=>c.id),[178475,8232]);
});

test('unavailable opponent squad uses independent current-club identity verification', async()=>{
  const h=harness({noSquad:true});
  const {GET}=h.load(path.join(root,'src/app/api/tip-portrait/[id]/route.ts'));
  const response=await GET(new Request('https://example.test'),{params:Promise.resolve({id:'123'})});
  assert.equal(response.status,307);
  assert.equal(response.headers.get('location'),'https://images.fotmob.com/image_resources/playerimages/1186444.png');
  assert.deepEqual(h.counts(),{fetches:3,queries:1});
});

test('verified Zima portrait also repairs old API URLs without depending on either squad source',async()=>{
  const h=harness({fail:true});
  Object.assign(h.pick,{id:1133,category:'ucl',event:'Sabah vs Slavia Prague',player:'Zima'});
  const {GET}=h.load(path.join(root,'src/app/api/tip-portrait/[id]/route.ts'));
  const response=await GET(new Request('https://example.test'),{params:Promise.resolve({id:'1133'})});
  assert.equal(response.status,307);
  assert.equal(response.headers.get('location'),'https://images.fotmob.com/image_resources/playerimages/1085401.png');
  assert.deepEqual(h.counts(),{fetches:0,queries:1});
  const artwork=h.load(path.join(root,'src/lib/tip-artwork.ts')).getTipArtwork({...h.pick,event:'Rennes vs Auxerre'});
  assert.match(artwork[0].src,/^\/api\/tip-portrait\/1133\?v=[a-f0-9]{12}$/);
});

test('correcting a club on the same bet immediately retries a failed portrait without waiting for cached lookup expiry',async()=>{
  const h=harness();h.pick.event='Rennnes vs Auxerre';
  const artwork=h.load(path.join(root,'src/lib/tip-artwork.ts')).getTipArtwork;
  const {GET}=h.load(path.join(root,'src/app/api/tip-portrait/[id]/route.ts'));
  const {PATCH}=h.load(path.join(root,'src/app/api/admin/bets/route.ts'));
  const before=artwork(h.pick)[0].src;
  const request=()=>GET(new Request('https://example.test'+artwork(h.pick)[0].src),{params:Promise.resolve({id:'123'})});
  assert.equal((await request()).status,404);
  assert.equal(h.counts().queries,1);
  const saved=await PATCH(new Request('https://example.test/api/admin/bets',{method:'PATCH',body:JSON.stringify({id:123,event:'Rennes vs Auxerre'})}));
  assert.equal(saved.status,200);
  assert.notEqual(artwork(h.pick)[0].src,before,'browser and React failed-image key must change');
  assert.deepEqual(h.invalidations,[{tag:'tip-portrait:123',profile:{expire:0}}]);
  assert.ok(h.paths.includes('/api/tip-portrait/123'));
  const fixed=await request();
  assert.equal(fixed.status,307);
  assert.match(fixed.headers.get('location'),/1186444\.png$/);
  assert.equal(h.counts().queries,2,'saved identity must replace stale cached miss');
});

test('player, club and category edits change the lookup URL; price edits do not; failed writes do not invalidate',async()=>{
  const h=harness({updateError:true});const art=h.load(path.join(root,'src/lib/tip-artwork.ts')).getTipArtwork;
  const original=art(h.pick)[0].src;
  for(const edit of [{player:'Charlie Cresswell'},{event:'Auxerre vs Rennes'},{category:'other'}]) assert.notEqual(art({...h.pick,...edit})[0].src,original);
  assert.equal(art({...h.pick,odds:3.5})[0].src,original);
  const {PATCH}=h.load(path.join(root,'src/app/api/admin/bets/route.ts'));
  const response=await PATCH(new Request('https://example.test/api/admin/bets',{method:'PATCH',body:JSON.stringify({id:123,event:'Rennnes vs Auxerre'})}));
  assert.equal(response.status,400);assert.deepEqual(h.invalidations,[]);assert.equal(h.pick.event,'Rennes vs Auxerre');
});

test('new Europa picks resolve both squads and the correct player including accents and verified short names', async () => {
  const examples = [
    ['Sparta Praha vs Lillestrom', 'Suchomel', 1310253],
    ['Benfica vs Celtic', 'Lukebakio', 688876],
    ['Torreense vs Sunderland', 'Adriel', 1248662],
    ['Az Alkmaar vs Hapoel Beer Sheva', 'Diop ', 1316534],
    ['Hoffenheim vs Besiktas', 'Murillo', 643635],
    ['Torreense vs Sunderland', 'Javi Vasquez ', 886809],
  ];
  const h=harness(); const r=h.load(path.join(root,'src/lib/tip-portrait-resolver.ts'));
  for (const [event,player,id] of examples) {
    const pick={market:'props',category:'other',event,player};
    assert.equal(r.clubsForPick(pick).length,2,event);
    assert.equal((await r.resolveTipPortrait(pick))?.id,id,event+' '+player);
  }
  assert.equal(r.uniquePlayer('Adriel',[[{id:9,name:'Adriel Other',clubId:1}],[{id:10,name:'Other Player',clubId:2}]]),null);
});

test('settlements refresh the exact pages and portraits without evicting unchanged social images', async()=>{
  for (const status of ['won','lost','void','pending']) {
    const h=harness(); Object.assign(h.pick,{match_date:'2026-10-28',odds:2,stake:.5});
    const {PATCH}=h.load(path.join(root,'src/app/api/admin/bets/route.ts'));
    const result=await PATCH(new Request('https://example.test/api/admin/bets',{method:'PATCH',body:JSON.stringify({id:123,status,profit_loss:status==='won'?.5:status==='lost'?-.5:0,settled_at:'2026-10-28T12:00:00Z'})}));
    assert.equal(result.status,200);assert.equal(h.pick.status,status);
    assert.ok(h.paths.includes('/player-props'));
    assert.ok(h.paths.includes('/track-record'));
    assert.ok(h.paths.includes('/api/tip-portrait/123'));
    assert.ok(h.paths.some(p=>p.startsWith('/tips/')));
    assert.ok(h.paths.some(p=>p.startsWith('/betting-tips/')));
    assert.equal(h.paths.some(p=>p.endsWith('/opengraph-image')),false,status);
  }
});

test('content edits, moved fixtures and unknown fields still invalidate old and new images', async()=>{
  for (const updates of [{odds:2.5,status:'won',profit_loss:.75},{player:'Charlie Cresswell'},
    {event:'Auxerre vs Rennes',match_date:'2026-10-29'},{notes:'Updated analysis'},{future_field:'unknown'},{}]) {
    const h=harness();Object.assign(h.pick,{match_date:'2026-10-28',odds:2,stake:.5});
    const before={...h.pick};
    const {PATCH}=h.load(path.join(root,'src/app/api/admin/bets/route.ts'));
    assert.equal((await PATCH(new Request('https://example.test/api/admin/bets',{method:'PATCH',body:JSON.stringify({id:123,...updates})}))).status,200);
    const {slugifyTip}=h.load(path.join(root,'src/lib/slugify.ts'));
    const {tipPreviewPath}=h.load(path.join(root,'src/lib/tip-seo.ts'));
    for(const pick of [before,h.pick]){
      assert.ok(h.paths.includes(`/tips/${slugifyTip(pick.event,pick.id)}/opengraph-image`));
      assert.ok(h.paths.includes(`${tipPreviewPath(pick)}/opengraph-image`));
    }
  }
});

test('adding or removing a selection invalidates its grouped fixture image', async()=>{
  for(const method of ['POST','DELETE']){
    const h=harness({allowPost:true}); Object.assign(h.pick,{match_date:'2026-10-28',odds:2,stake:.5});
    const route=h.load(path.join(root,'src/app/api/admin/bets/route.ts'));
    const request=new Request('https://example.test/api/admin/bets?id=123',method==='POST'?{method,body:JSON.stringify(h.pick)}:{method});
    assert.equal((await route[method](request)).status,200);
    assert.ok(h.paths.some(p=>p.startsWith('/betting-tips/')&&p.endsWith('/opengraph-image')));
    assert.ok(h.paths.some(p=>p.startsWith('/tips/')&&p.endsWith('/opengraph-image')));
  }
});

test('failed or unauthorised settlements do not invalidate pages or images', async()=>{
  for(const opts of [{unauthorized:true},{updateError:true}]){
    const h=harness(opts);const {PATCH}=h.load(path.join(root,'src/app/api/admin/bets/route.ts'));
    assert.equal((await PATCH(new Request('https://example.test/api/admin/bets',{method:'PATCH',body:JSON.stringify({id:123,status:'won'})}))).status,opts.unauthorized?401:400);
    assert.deepEqual(h.paths,[]);assert.deepEqual(h.invalidations,[]);assert.equal(h.pick.status,undefined);
  }
});

require('./tip-portrait-lineup.test.cjs');

