const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const ts = require('typescript');
const root = path.resolve(__dirname, '../..');
const europa = require('./fixtures/tip-portrait-europa-squads.json');
const squads = require('./fixtures/tip-portrait-squads.json');
const source = (club) => `<script id="__NEXT_DATA__" type="application/json">${JSON.stringify({props:{pageProps:{fallback:{['team-'+squads[club].details.id]:squads[club]}}}})}</script>`;

function harness({ fail = false, empty = false, noSquad = false } = {}) {
  const cache = new Map();
  let fetches = 0, queries = 0;
  const cached = (fn) => {
    const values = new Map();
    return async (...args) => {
      const key = JSON.stringify(args);
      if (!values.has(key)) values.set(key, Promise.resolve().then(() => fn(...args)).catch((e) => { values.delete(key); throw e; }));
      return values.get(key);
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
      if(id === 'next/cache') return {unstable_cache:cached};
      if(id === '@/lib/supabase-server') return {getSupabaseAdmin:()=>({from:()=>({select:()=>({eq:()=>({maybeSingle:async()=>{queries++;return {data:empty?null:pick,error:null};}})})})})};
      return load(id.startsWith('@/')?path.join(root,'src',id.slice(2)):path.resolve(path.dirname(file),id));
    };
    const mockedFetch = async (url) => {
      fetches++;
      if(fail) throw new Error('timeout');
      assert.match(url,/^https:\/\/www\.fotmob\.com\/teams\/\d+\/overview$/);
      const teamId = url.match(/teams\/(\d+)/)[1];
      if (noSquad && teamId === '8583') return new Response('<script id="__NEXT_DATA__">'+JSON.stringify({props:{pageProps:{fallback:{['team-'+teamId]:{details:{id:8583},squad:{squad:null}}}}}})+'</script>');
      if (europa[teamId]) return new Response('<script id="__NEXT_DATA__">'+JSON.stringify({props:{pageProps:{fallback:{['team-'+teamId]:europa[teamId]}}}})+'</script>');
      const club = url.includes('/9851/')?'rennes':'auxerre';
      return new Response(source(club));
    };
    vm.runInThisContext('(function(require,module,exports,fetch){'+code+'\n})',{filename:file})(req,module,module.exports,mockedFetch);
    return module.exports;
  };
  return {load,pick,counts:()=>({fetches,queries})};
}

test('a new surname-only pick gets a real club-scoped portrait without a curated player entry',async()=>{
  const h=harness();
  const artwork=h.load(path.join(root,'src/lib/tip-artwork.ts')).getTipArtwork(h.pick);
  assert.equal(artwork[0].src,'/api/tip-portrait/123');
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
  assert.equal(r.clubsForPick({...h.pick,event:'Unknown vs Rennes'}).length,0);
  assert.equal(r.clubsForPick({...h.pick,event:'Rennes vs Rennes'}).length,0);
  assert.throws(()=>r.parseSquad(source('rennes'),8583),/identity/);
  const squad=r.parseSquad(source('rennes'),9851);
  const coaches=squads.rennes.squad.squad.filter(g=>/coach/i.test(g.title)).flatMap(g=>g.members);
  assert.equal(squad.some(p=>coaches.some(c=>c.id===p.id)),false);
});

test('source outage, unknown tip and malformed IDs fail safely without arbitrary requests',async()=>{
  for(const config of [{fail:true},{empty:true}]){
    const h=harness(config),{GET}=h.load(path.join(root,'src/app/api/tip-portrait/[id]/route.ts'));
    const invalid=await GET(new Request('https://example.test'),{params:Promise.resolve({id:'../123'})});
    assert.equal(invalid.status,400); assert.deepEqual(h.counts(),{fetches:0,queries:0});
    const response=await GET(new Request('https://example.test'),{params:Promise.resolve({id:'123'})});
    assert.equal(response.status,config.fail?503:404);
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

test('explicitly unavailable opponent squad is missing coverage, never a 503 or a guessed surname', async()=>{
  const h=harness({noSquad:true});
  const {GET}=h.load(path.join(root,'src/app/api/tip-portrait/[id]/route.ts'));
  const response=await GET(new Request('https://example.test'),{params:Promise.resolve({id:'123'})});
  assert.equal(response.status,404);
  assert.equal(response.headers.get('location'),null);
  assert.deepEqual(h.counts(),{fetches:2,queries:1});
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
  assert.equal(artwork[0].src,'/api/tip-portrait/1133');
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
