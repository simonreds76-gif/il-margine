const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs'), path = require('node:path'), vm = require('node:vm'), ts = require('typescript');
const root = path.resolve(__dirname, '../..');
const fixture = require('./fixtures/penalty-portrait-elversberg.json');

function harness({ archived = false, fail = false } = {}) {
  const modules = new Map(); let fetches = 0;
  const cached = fn => { const entries = new Map(); return (...args) => {
    const key = JSON.stringify(args);
    if (!entries.has(key)) entries.set(key, Promise.resolve().then(() => fn(...args)).catch(e => { entries.delete(key); throw e; }));
    return entries.get(key);
  }; };
  function load(file) {
    if (!path.extname(file)) file += '.ts';
    if (file.endsWith('.json')) return JSON.parse(fs.readFileSync(file, 'utf8'));
    if (modules.has(file)) return modules.get(file).exports;
    const module = { exports: {} }; modules.set(file, module);
    const req = id => {
      if (id === 'server-only') return {};
      if (id === 'next/cache') return { unstable_cache: cached };
      if (id === '@/lib/club-penalty-takers') return { getClubPenaltyTeam: async (league, club) => league === 'bundesliga' && club === 'sv-elversberg' ? { team: 'SV Elversberg', isArchived: archived, verifiedNames: ['Noel Futkeu', 'Lukas Petkov'] } : undefined };
      return load(id.startsWith('@/') ? path.join(root, 'src', id.slice(2)) : path.resolve(path.dirname(file), id));
    };
    const fetch = async url => {
      fetches++; assert.equal(url, 'https://www.fotmob.com/teams/8232/overview');
      if (fail) throw new Error('upstream timeout');
      return new Response('<script id="__NEXT_DATA__">' + JSON.stringify({ props: { pageProps: { fallback: { 'team-8232': fixture } } } }) + '</script>');
    };
    const code = ts.transpileModule(fs.readFileSync(file, 'utf8'), { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022, esModuleInterop: true } }).outputText;
    vm.runInThisContext('(function(require,module,exports,fetch){'+code+'\n})', { filename: file })(req, module, module.exports, fetch);
    return module.exports;
  }
  const route = load(path.join(root, 'src/app/api/penalty-portrait/[league]/[club]/[player]/route.ts'));
  return { load, fetches: () => fetches, get: (params = {}) => route.GET(new Request('https://example.test'), { params: Promise.resolve({ league: 'bundesliga', club: 'sv-elversberg', player: 'noelfutkeu', ...params }) }) };
}

test('new editorial takers resolve from their actual club and share one cached squad fetch', async () => {
  const h = harness();
  for (const player of ['noelfutkeu', 'lukaspetkov', 'noelfutkeu']) {
    const response = await h.get({ player });
    assert.equal(response.status, 307);
    if (player === 'noelfutkeu') assert.equal(response.headers.get('location'), 'https://images.fotmob.com/image_resources/playerimages/1138725.png');
    assert.match(response.headers.get('cache-control'), /s-maxage=21600/);
  }
  assert.equal(h.fetches(), 1);
});
test('unknown or archived takers cannot trigger external lookups', async () => {
  const h = harness();
  for (const params of [{ player: 'unknown' }, { club: 'unknown' }, { league: 'unknown' }]) assert.equal((await h.get(params)).status, 404);
  assert.equal((await h.get({ player: '../noelfutkeu' })).status, 400);
  assert.equal(h.fetches(), 0);
  const old = harness({ archived: true }); assert.equal((await old.get()).status, 404); assert.equal(old.fetches(), 0);
});
test('outages retry and ambiguous or surname-only identities are not guessed', async () => {
  const outage = harness({ fail: true });
  assert.equal((await outage.get()).status, 503);
  assert.equal((await outage.get()).headers.get('retry-after'), '300');
  assert.equal(outage.fetches(), 2);
  const h = harness(); const resolver = h.load(path.join(root, 'src/lib/tip-portrait-resolver.ts'));
  assert.equal(await resolver.resolveClubPlayerPortrait('SV Elversberg', 'bundesliga', 'Futkeu'), null);
  assert.equal(await resolver.resolveClubPlayerPortrait('Unknown', 'bundesliga', 'Noel Futkeu'), null);
  assert.equal(h.fetches(), 1);
});
test('curated portraits include the newly saved names with exact club scope', () => {
  const portraits = require('../../data/goalscorer/penalty-player-portraits.json');
  assert.equal(portraits['bundesliga|svelversberg|noelfutkeu'], '1138725');
  assert.equal(portraits['epl|coventrycity|jackrudoni'], '1030830');
  assert.equal(portraits['ligue-1|toulouse|caspertengstedt'], '1102240');
});
