const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const ts = require('typescript');
const moduleUnderTest = { exports: {} };
const code = ts.transpileModule(fs.readFileSync('src/components/ProfitProgressionPanel.tsx', 'utf8'), {
  compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020, jsx: ts.JsxEmit.ReactJSX },
}).outputText;
new Function('module', 'exports', 'require', code)(moduleUnderTest, moduleUnderTest.exports, name => {
  if (name === 'next/dynamic') return { default: () => null };
  if (['react', 'react/jsx-runtime', '@/lib/baseline'].includes(name)) return {};
  throw new Error(`Unexpected dependency: ${name}`);
});
const { buildProgressionPoints } = moduleUnderTest.exports;

test('aggregate history contributes one balance; subsequent movement is actual sorted profit', () => {
  const rows = [
    { id: 2, date: '2026-09-02', profit_loss: -2 },
    { id: 1, date: '2026-09-01', profit_loss: 1.5 },
  ];
  const points = buildProgressionPoints(rows, { total_bets: 780, total_profit: 195 });
  assert.equal(points.length, 3);
  assert.deepEqual(points.map(p => p.cumulative), [195, 196.5, 194.5]);
  assert.equal(points.filter(p => p.isArchiveReconstruction).length, 1);
  assert.equal(points[0].date, null);
  assert.equal(rows[0].id, 2, 'input order is not mutated');
});

test('negative aggregate and empty history do not manufacture a curve', () => {
  const negative = buildProgressionPoints([], { total_bets: 50, total_profit: -10 });
  assert.equal(negative.length, 1);
  assert.equal(negative[0].cumulative, -10);
  const empty = buildProgressionPoints([]);
  assert.equal(empty.length, 1);
  assert.equal(empty[0].cumulative, 0);
  assert.equal(empty[0].isOriginPoint, true);
});
