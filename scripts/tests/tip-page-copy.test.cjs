const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const ts = require('typescript');
const file = path.resolve(__dirname, '../../src/lib/tip-page-copy.ts');
const mod = { exports: {} };
vm.runInNewContext(ts.transpileModule(fs.readFileSync(file, 'utf8'), {
  compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 },
}).outputText, { exports: mod.exports, module: mod });
const { buildTipPageCopy, priceContext, serializeTipSchema } = mod.exports;
const bet = { event: 'Genoa vs Frosinone', market: 'props', category: 'seriea', match_date: '2026-09-12', player: 'Masini', selection: 'Over 1.5 Fouls', odds: 1.85, status: 'won' };

test('copy identifies the actual match, market, date and completed record', () => {
  const copy = buildTipPageCopy(bet, [bet], '12 September 2026');
  for (const text of ['Genoa vs Frosinone', 'Serie A', '12 September 2026', 'Masini - Over 1.5 Fouls']) assert.ok(copy.introduction.includes(text));
  assert.match(copy.statusCopy, /Completed betting record/);
  assert.match(copy.metaDescription, /results/);
  assert.doesNotMatch(copy.introduction, /guaranteed|proven|before the match|positive EV/);
});
test('mixed ledger counts pending accurately without implying prices remain available', () => {
  const copy = buildTipPageCopy(bet, [bet, { ...bet, status: 'pending' }], '12 September 2026');
  assert.match(copy.statusCopy, /^1 selection is awaiting/);
  assert.match(copy.statusCopy, /does not mean the original odds are still available/);
});
test('tennis expands shorthand and long descriptions stay bounded', () => {
  const tennis = { ...bet, market: 'tennis', category: 'usopen', event: 'Sinner vs Alcaraz', selection: 'ML', player: 'Sinner' };
  const copy = buildTipPageCopy(tennis, [tennis], '13 September 2026');
  assert.match(copy.introduction, /US Open/);
  assert.match(copy.introduction, /Sinner - Match winner/);
  assert.ok(buildTipPageCopy({ ...bet, event: 'Very long team name '.repeat(20) }, [bet], '12 September 2026').metaDescription.length <= 170);
});
test('break-even math is not presented as predicted probability; invalid prices are omitted', () => {
  assert.match(priceContext(2.5), /40.0%/);
  assert.match(priceContext(1.85), /54.1%/);
  assert.match(priceContext(2), /not our predicted chance/);
  for (const value of [0, 1, -3, NaN, Infinity]) assert.equal(priceContext(value), null);
});
test('structured data cannot be terminated by a name containing script markup', () => {
  const input = { name: '</script><script>alert(1)</script>' };
  const serialized = serializeTipSchema(input);
  assert.ok(!serialized.includes('<'));
  assert.deepEqual(JSON.parse(serialized), input);
});
