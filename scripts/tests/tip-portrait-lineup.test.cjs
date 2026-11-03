const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const ts = require('typescript');
const root = path.resolve(__dirname, '../..');
const evidence = require('./fixtures/tip-portrait-recent-lineups.json');
const now = Date.parse('2026-11-03T12:00:00Z');
const html = (team, id = team.details.id) => `<script id="__NEXT_DATA__">${JSON.stringify({props:{pageProps:{fallback:{['team-'+id]:team}}}})}</script>`;
function harness() {
  let fetches = 0;
  const modules = new Map(), cached = new Map();
  const load = file => {
    if (!path.extname(file)) file += '.ts';
    if (modules.has(file)) return modules.get(file).exports;
    const module = {exports:{}}; modules.set(file,module);
    const code = ts.transpileModule(fs.readFileSync(file,'utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022,esModuleInterop:true}}).outputText;
    const req = id => {
      if(id === 'server-only') return {};
      if(id === 'next/cache') return {unstable_cache:fn=>async(...args)=>{
        const key=JSON.stringify(args); if(!cached.has(key)) cached.set(key,fn(...args)); return cached.get(key);
      }};
      if(id.endsWith('team-logo-map.json')) return {leagues:{}};
      if(id.endsWith('europe.json')) return {teams:[{fotmob_team_id:9728,name:'Shakhtar Donetsk',aliases:[],logo_path:'/shakhtar.png'},{fotmob_team_id:9768,name:'Sporting',aliases:[],logo_path:'/sporting.png'}]};
      if(id === './team-logos') return {resolveTeamLogoPath:()=>null};
      return load(path.resolve(path.dirname(file),id));
    };
    const fetch = async url => {
      fetches++; const match=url.match(/^https:\/\/www\.fotmob\.com\/teams\/(9728|9768)\/overview$/);
      assert.ok(match); return new Response(html(evidence[match[1]]));
    };
    class FrozenDate extends Date {static now(){return now;}}
    vm.runInThisContext('(function(require,module,exports,fetch,Date){'+code+'\n})',{filename:file})(req,module,module.exports,fetch,FrozenDate);
    return module.exports;
  };
  return {r:load(path.join(root,'src/lib/tip-portrait-resolver.ts')),count:()=>fetches};
}

test('recent lineup restores a full-name portrait when the squad feed is null, with the same two cached requests',async()=>{
  const {r,count}=harness();
  const pick={market:'props',category:'ucl',event:'Shakhtar Donetsk vs Sporting ',player:'Vinicius Tobias'};
  for(const player of ['Vinicius Tobias','Vinícius Tobias']) {
    const result=await r.resolveTipPortrait({...pick,player});
    assert.equal(result.id,1314657); assert.equal(result.clubId,9728); assert.equal(result.evidence,'recent-lineup');
  }
  assert.equal(count(),2);
  assert.equal((await r.resolveTipPortrait({...pick,event:'Sporting vs Shakhtar Donetsk'})).id,1314657);
  assert.equal(count(),2);
});

test('partial lineup coverage never enables surname guesses or ambiguous full names',()=>{
  const {r}=harness();const home=r.parseSquad(html(evidence[9728]),9728,now),away=r.parseSquad(html(evidence[9768]),9768,now);
  assert.equal(r.uniquePlayer('Tobias',[home,away]),null);
  assert.equal(r.uniquePlayer('Vinicius Tobias',[home,[]]),null);
  assert.equal(r.uniquePlayer('Vinicius Tobias',[home,[...away,{id:99,name:'Vinicius Tobias',clubId:9768}]]),null);
  assert.equal(r.uniquePlayer('Vinicius Tobias',[home,away]).id,1314657);
  assert.equal(r.uniquePlayer('Unrelated Player',[home,away]),null);
});

test('recent lineup rejects stale, unfinished, malformed or mismatched evidence',()=>{
  const {r}=harness();
  const edits=[
    t=>t.overview.lastLineupStats.id=9768,
    t=>t.overview.lastLineupStats.lastMatch.matchId++,
    t=>t.overview.lastLineupStats.lastMatch.homeTeamId=9768,
    t=>t.overview.lastLineupStats.lastMatch.awayTeamId=9768,
    t=>t.overview.lastMatch.status.finished=false,
    t=>t.overview.lastMatch.status.cancelled=true,
    t=>t.overview.lastMatch.status.awarded=true,
    t=>t.overview.lastMatch.status.utcTime='2026-09-01T12:00:00Z',
    t=>t.overview.lastMatch.status.utcTime='2026-11-04T12:00:00Z',
    t=>t.overview.lastMatch.status.utcTime='invalid',
    t=>t.overview.lastLineupStats.starters.pop(),
    t=>t.overview.lastLineupStats.subs.push(t.overview.lastLineupStats.starters[0]),
    t=>t.overview.lastLineupStats.starters[0].name='',
    t=>t.overview.lastLineupStats.starters[0].id=0,
    t=>delete t.overview.lastLineupStats,
  ];
  for(const edit of edits){const team=structuredClone(evidence[9728]);edit(team);assert.deepEqual(r.parseSquad(html(team),9728,now),[],edit.toString());}
  assert.throws(()=>r.parseSquad(html(evidence[9728],9768),9768,now),/identity/);
});

test('full squads retain precedence and partial squads can use verified recent evidence',()=>{
  const {r}=harness();
  const team=structuredClone(evidence[9728]);team.squad.squad=[];
  assert.equal(r.parseSquad(html(team),9728,now).find(p=>p.id===1314657).evidence,'recent-lineup');
  const full=r.parseSquad(html(evidence[9768]),9768,now);
  assert.ok(full.length>=11);assert.equal(full.some(p=>p.evidence),false);
  const broken=structuredClone(evidence[9728]);broken.squad.squad={};
  assert.throws(()=>r.parseSquad(html(broken),9728,now),/Squad unavailable/);
});
