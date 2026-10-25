const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const ts = require('typescript');
const code = ts.transpileModule(fs.readFileSync(path.join(__dirname, '../../src/lib/aerial-height-display.ts'), 'utf8'), {
  compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020 },
}).outputText;
const context = { exports: {} }; vm.runInNewContext(code, context);
const { summarizeKnownHeights } = context.exports;
const lineup = values => [{ id: 'keeper', name: 'Keeper', role: 'GK', height_cm: 210 },
  ...values.map((height_cm, i) => ({ id: String(i), name: `Player ${i}`, role: 'DEF', height_cm }))];

test('one missing starter preserves the known average without imputing a tenth height', () => {
 const players = lineup([170,175,180,180,180,185,190,195,200,null]);
 const before = JSON.stringify(players); const h = summarizeKnownHeights(players);
 assert.equal(h.known,9); assert.equal(h.complete,false);
 assert.equal(h.mean,1655/9); assert.equal(h.tallestThreeMean,195);
 assert.equal(h.atLeast185,4); assert.equal(h.missing.join(','),'Player 9');
 assert.equal(JSON.stringify(players),before);
});
test('complete lineup excludes the goalkeeper and matches full-XI calculations', () => {
 const h = summarizeKnownHeights(lineup(Array(10).fill(180)));
 assert.equal(h.complete,true); assert.equal(h.known,10); assert.equal(h.mean,180);
 assert.equal(h.tallestThreeMean,180); assert.equal(h.atLeast185,0);
});
test('no heights and fewer than three heights retain unavailable metrics honestly', () => {
 const none = summarizeKnownHeights(lineup(Array(10).fill(null)));
 assert.equal(none.mean,null); assert.equal(none.atLeast185,null); assert.equal(none.tallestThreeMean,null);
 const sparse = summarizeKnownHeights(lineup([180,190,null,0,NaN,Infinity,300,129,null,null]));
 assert.equal(sparse.known,2); assert.equal(sparse.mean,185); assert.equal(sparse.tallestThreeMean,null);
 assert.equal(sparse.atLeast185,1); assert.equal(sparse.complete,false);
});
