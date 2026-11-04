const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const ts = require('typescript');
const root = path.resolve(__dirname, '../..');
function load(file, imports = {}) {
  const module = { exports: {} };
  const code = ts.transpileModule(fs.readFileSync(path.join(root, file), 'utf8'), {
    compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022, esModuleInterop: true },
  }).outputText;
  vm.runInNewContext(code, { module, exports: module.exports, Date, Intl, URL, process: { env: {} },
    require: name => Object.hasOwn(imports, name) ? imports[name] : require(name) });
  return module.exports;
}
const api = load('src/lib/club-penalty-takers.ts', {
  'server-only': {}, react: { cache: f => f },
  '@/lib/config': { BASE_URL: 'https://ilmargine.bet' },
  '@/lib/project-file-paths': { getKnownProjectFilePath: p => path.join(root, p) },
  '@/lib/penalty-editorial-store': { readPenaltyOverrides: async () => ({}) },
  '@/lib/penalty-editorial': load('src/lib/penalty-editorial.ts'),
  '@/lib/player-name-matching': load('src/lib/player-name-matching.ts'),
  '@/lib/football-club-names': load('src/lib/football-club-names.ts'),
  '../../data/goalscorer/penalty-player-portraits.json': require('../../data/goalscorer/penalty-player-portraits.json'),
  '../../data/goalscorer/club-penalty-season.json': require('../../data/goalscorer/club-penalty-season.json'),
});
const news = load('src/lib/penalty-news.ts');
const articles = require('../../src/data/penalty-news.json').articles;

test('every current club has the same confidence in metadata, lead, first FAQ and directory labels', async () => {
  const leagues = await api.readClubPenaltyData();
  assert.equal(leagues.length, 5);
  let clubs = 0;
  for (const league of leagues) for (const team of league.teams) {
    const before = JSON.stringify(team);
    const status = api.clubPenaltyOrderStatus(team);
    const lead = api.buildClubPenaltyLead(team);
    assert.equal(api.buildClubPenaltyDescription(team), lead);
    assert.equal(api.buildClubPenaltyFaq(team)[0].answer, lead);
    assert.equal(api.buildClubPenaltyCardSummary(team), lead);
    if (status !== 'confirmed') {
      assert.match(lead, /provisional|conditional|disputed|unconfirmed/);
      assert.ok(api.clubPenaltyRankLabels(team).every(s => !/choice/.test(s)));
      assert.doesNotMatch(api.buildClubPenaltyHierarchyNote(team), /^If .* is unavailable/);
    }
    const directory = api.buildPenaltyDirectory([league])[0].teams.find(t => t.url === team.relativeUrl);
    assert.equal(directory.status, status);
    assert.equal(JSON.stringify(directory.rankLabels), JSON.stringify(api.clubPenaltyRankLabels(team)));
    assert.equal(JSON.stringify(team), before, 'copy must not mutate any saved hierarchy or date');
    clubs++;
  }
  assert.ok(clubs >= 90);
});

test('missing, weak and carried-over evidence cannot become confirmed by default', () => {
  const team = { team: 'Example', primary: 'Player A', secondary: 'Player B', tertiary: 'Player C', hierarchyDepth: 3 };
  assert.equal(api.clubPenaltyOrderStatus(team), 'provisional');
  for (const flags of [{ weakEvidence: true }, { isCarryover: true }, { primaryConfidence: 'low' }]) {
    assert.equal(api.clubPenaltyOrderStatus({ ...team, hierarchyStatus: 'confirmed', ...flags }), 'provisional');
  }
  for (const status of ['disputed', 'conditional']) {
    const t = { ...team, hierarchyStatus: status };
    assert.match(api.buildClubPenaltyFaq(t)[1].answer, new RegExp(status));
    assert.doesNotMatch(api.buildClubPenaltyFaq(t)[1].answer, /is second choice/);
  }
});

test('archived orders remain explicitly historical', async () => {
  for (const league of await api.readClubPenaltyData()) for (const team of league.archivedTeams) {
    assert.match(api.buildClubPenaltyDescription(team), /^Archived/);
    assert.match(api.buildClubPenaltyLead(team), /archived/);
    assert.match(api.buildClubPenaltyFaq(team)[1].answer, /not presented as the current/);
  }
});

test('all saved news titles preserve players, clubs, outcome semantics and immutable article bodies', () => {
  for (const a of articles) {
    const before = JSON.stringify(a);
    const title = news.newsSeoTitle(a);
    assert.ok(title.includes(a.player));
    assert.ok(title.includes(a.club));
    assert.match(title, /penalty/);
    const outcome = { scored: /scores/, missed: /misses/, saved: /saved/, woodwork: /woodwork/ };
    assert.match(title, outcome[a.outcome] || /report/);
    assert.ok(!title.includes('| Penalty News'));
    assert.equal(JSON.stringify(a), before);
  }
});

test('saved, missed, woodwork, repeated and retaken incidents remain distinct without inventing a keeper', () => {
  const base = { ...articles[0], player: 'Player', club: 'Club', keeper: null };
  for (const outcome of ['saved', 'missed', 'woodwork']) {
    assert.match(news.newsSeoTitle({ ...base, outcome }), new RegExp(outcome === 'missed' ? 'misses' : outcome));
  }
  const repeated = [
    { ...base, id: 'a', eventId: '1', minute: '19', title: 'Player scores' },
    { ...base, id: 'b', eventId: '2', minute: '81', title: 'Player scores' },
  ];
  const titles = repeated.map(a => news.newsSeoTitle({ ...a, title: news.distinctNewsTitle(a, repeated) }));
  assert.equal(new Set(titles).size, 2);
  assert.match(titles[0], /19′/);
  assert.match(news.newsSeoTitle({ ...base, title: 'Player scores retaken penalty' }), /retake/);
  const long = { ...base, player: 'A deliberately very long complete player name', club: 'A long club name', outcome: 'saved' };
  assert.equal(news.newsSeoTitle(long), `${long.player}'s ${long.club} penalty saved`);
});

test('latest recorded penalty is selected by the club URL and event time, without mutating the archive', () => {
  const base = articles[0];
  const rows = [
    { ...base, id: 'old', kickoff: '2026-10-01T12:00:00Z', eventId: '9' },
    { ...base, id: 'new', kickoff: '2026-10-31T12:00:00Z', eventId: '11' },
    { ...base, id: 'another', kickoff: '2026-11-01T12:00:00Z', clubUrl: '/another-club' },
  ];
  const before = JSON.stringify(rows);
  assert.equal(news.latestClubPenaltyReport(rows, base.clubUrl).id, 'new');
  assert.equal(news.latestClubPenaltyReport(rows, '/missing'), undefined);
  assert.equal(JSON.stringify(rows), before);
});
