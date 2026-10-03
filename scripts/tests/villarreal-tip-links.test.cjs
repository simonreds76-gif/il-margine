const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const ts = require('typescript');

function load(name) {
  const mod = { exports: {} };
  const source = path.resolve(__dirname, '../../src/lib', `${name}.ts`);
  vm.runInNewContext(ts.transpileModule(fs.readFileSync(source, 'utf8'), {
    compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 },
  }).outputText, {
    exports: mod.exports, module: mod,
    require: (dependency) => load(dependency.replace('@/lib/', '')),
  });
  return mod.exports;
}

const { correctFootballClubNames } = load('football-club-names');
const { tipFixtureHash, matchesTipFixtureHash, tipPreviewPath, parseTipPreviewSlug } = load('tip-seo');

test('old fixture URLs still find corrected records without matching another match', () => {
  for (const event of ['Villareal vs Sevilla', 'Atletico Madrid vs Villareal']) {
    const original = { market: 'props', event, match_date: '2026-08-23' };
    const corrected = { ...original, event: correctFootballClubNames(event) };
    const oldSlug = tipPreviewPath(original).split('/').at(-1);
    const hash = parseTipPreviewSlug(oldSlug).fixtureHash;
    assert.notEqual(tipFixtureHash(corrected), hash);
    assert.equal(matchesTipFixtureHash(corrected, hash), true);
    assert.equal(matchesTipFixtureHash(corrected, tipFixtureHash(corrected)), true);
    assert.equal(matchesTipFixtureHash({ ...corrected, match_date: '2026-08-24' }, hash), false);
    assert.equal(matchesTipFixtureHash({ ...corrected, event: 'Villarreal vs Barcelona' }, hash), false);
    assert.match(tipPreviewPath(corrected), /villarreal/);
  }
});

test('club migration does not alias a tennis player surname', () => {
  const tennis = { market: 'tennis', event: 'Villarreal vs Smith', match_date: '2026-08-23' };
  assert.equal(matchesTipFixtureHash(tennis, tipFixtureHash({ ...tennis, event: 'Villareal vs Smith' })), false);
});
