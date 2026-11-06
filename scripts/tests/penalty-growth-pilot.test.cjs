const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const ts = require('typescript');
const React = require('react');
const { renderToStaticMarkup } = require('react-dom/server');
const root = path.resolve(__dirname, '../..');
function load(file, imports = {}) {
  const module = { exports: {} };
  vm.runInNewContext(ts.transpileModule(fs.readFileSync(path.join(root, file), 'utf8'), {
    compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022, jsx: ts.JsxEmit.ReactJSX, esModuleInterop: true },
  }).outputText, { module, exports: module.exports, Date, Intl, console,
    require: name => Object.hasOwn(imports, name) ? imports[name] : require(name) });
  return module.exports;
}
const helpers = load('src/lib/penalty-growth-pilot.ts');
const newsHelpers = load('src/lib/penalty-news.ts');
const news = require('../../src/data/penalty-news.json');
const board = require('../../src/data/atlas-fixtures.json');

test('preview is confined to ten named club pages and leaves controls outside', () => {
  assert.equal(new Set(helpers.PENALTY_GROWTH_PAGES).size, 10);
  assert.equal(helpers.isPenaltyGrowthPage('epl', 'everton'), false);
  assert.equal(helpers.isPenaltyGrowthPage('epl', 'chelsea'), true);
});
test('deduplicate events, retain different incidents and latest correction without mutating records', () => {
  const a = news.articles[0], corrected = { ...a, updatedAt: '2099-01-01', outcome: 'saved' };
  const second = { ...a, eventId: 'separate', id: 'separate' };
  const input = [a, second, corrected], before = JSON.stringify(input);
  const rows = helpers.recordedClubPenalties(input, a.clubUrl, news.coverageStart);
  assert.equal(rows.length, 2);
  assert.equal(rows.find(r => r.eventId === a.eventId).outcome, 'saved');
  assert.equal(JSON.stringify(input), before);
  assert.equal(helpers.recordedClubPenalties(input, '/wrong-club', news.coverageStart).length, 0);
  assert.equal(helpers.recordedClubPenalties([{ ...a, kickoff: 'invalid' }, { ...a, date: '1900-01-01' }], a.clubUrl, news.coverageStart).length, 0);
});
test('all real pilot rows retain the exact report URLs, outcomes, timestamps and partial-coverage label', () => {
  const Component = load('src/components/ClubPenaltyLog.tsx', {
    'next/link': ({ children, prefetch, ...props }) => React.createElement('a', props, children),
    './ToolEmblem': () => null, './FixturePhoto': () => null,
    '@/lib/penalty-news-data': { penaltyNews: news }, '@/lib/penalty-news': newsHelpers,
    '@/lib/penalty-growth-pilot': helpers, './ClubPenaltyLog.module.css': {},
  }).default;
  for (const page of helpers.PENALTY_GROWTH_PAGES) {
    const clubUrl = `/penalty-takers/${page}`;
    const rows = helpers.recordedClubPenalties(news.articles, clubUrl, news.coverageStart);
    assert.ok(rows.length > 0, page);
    const html = renderToStaticMarkup(React.createElement(Component, { clubUrl, club: page }));
    assert.ok(html.includes('not a complete season total'));
    for (const row of rows) {
      assert.ok(html.includes(`/penalty-news/${row.slug}`));
      assert.ok(html.includes(`dateTime="${row.date}"`));
      assert.ok(html.includes(newsHelpers.outcomeLabel[row.outcome]));
    }
  }
  const empty = renderToStaticMarkup(React.createElement(Component, { clubUrl: '/no-reports', club: 'Example' }));
  assert.ok(empty.includes('does not mean the club has taken no penalties'));
});
test('fixture joins require the exact existing league and crest and carry only compact public fields', () => {
  const f = board.fixtures.find(f => f.league === 'premier-league');
  const links = helpers.clubFixtureLinks(board, 'epl', f.home.crest);
  assert.ok(links.some(r => r.id === f.id));
  assert.equal(helpers.clubFixtureLinks(board, 'serie-a', f.home.crest).length, 0);
  assert.equal(helpers.clubFixtureLinks(board, 'epl', '').length, 0);
  assert.ok(links.every(r => !('managers' in r) && !('outcomes' in r)));
});
test('next fixture disappears after kickoff, on stale evidence and on invalid/future observations', () => {
  const rows = [{ id: 'a', kickoff: '2026-11-07T15:00:00Z' }, { id: 'b', kickoff: '2026-11-08T15:00:00Z' }];
  const checked = '2026-11-06T00:00:00Z', expires = '2026-11-09T00:00:00Z';
  assert.equal(helpers.nextClubFixture(rows, checked, expires, Date.parse('2026-11-07T14:59:00Z')).id, 'a');
  assert.equal(helpers.nextClubFixture(rows, checked, expires, Date.parse(rows[0].kickoff)).id, 'b');
  assert.equal(helpers.nextClubFixture(rows, checked, expires, Date.parse(expires)), null);
  assert.equal(helpers.nextClubFixture(rows, 'invalid', expires, Date.parse(checked)), null);
  assert.equal(helpers.nextClubFixture(rows, checked, expires, Date.parse('2026-11-05')), null);
});
test('only identical full evidence is collapsed, not distinct hierarchy evidence', () => {
  assert.equal(helpers.sameEvidenceText('Same  note\n here', 'Same note here'), true);
  assert.equal(helpers.sameEvidenceText('Same note here', 'Different evidence'), false);
  assert.equal(helpers.sameEvidenceText('', ''), false);
});
