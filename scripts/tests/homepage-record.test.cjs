const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const ts = require('typescript');
function load(name) {
  const code = ts.transpileModule(fs.readFileSync(path.join(__dirname, '../../src/lib/', name + '.ts'), 'utf8'), {
    compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020 },
  }).outputText;
  const context = { exports: {}, require: (id) => load(id.replace('./', '')) };
  vm.runInNewContext(code, context);
  return context.exports;
}
const { buildCombinedStats } = load('homepage-record');
const { BASELINE_STATS, calculateROI } = load('baseline');
const record = [
  { market: 'tennis', total_bets: 418, wins: 195, losses: 222, total_profit: -3.3, total_stake: 298.5, avg_odds: 2.1 },
  { market: 'props', total_bets: 741, wins: 358, losses: 376, total_profit: 66.98, total_stake: 474.95, avg_odds: 2.7 },
];
test('headline excludes eight pending bets while retaining historical totals and monetary figures', () => {
  const stats = buildCombinedStats(record);
  assert.equal(stats.overall.total_bets, 2378);
  assert.equal(stats.props.total_bets, 1514);
  assert.equal(stats.tennis.total_bets, 864);
  assert.ok(Math.abs(stats.overall.total_profit - 297.122) < 1e-8);
  assert.equal(stats.overall.roi, calculateROI(297.122, 2000.45));
  assert.equal(stats.overall.avg_odds, (2.7 * 1521 + 2.1 * 865) / 2386);
});
test('additional pending or void entries cannot increase settled count or change recorded profit and ROI', () => {
  const before = buildCombinedStats(record);
  const after = buildCombinedStats(record.map(row => ({ ...row, total_bets: row.total_bets + 12 })));
  for (const market of ['props', 'tennis', 'overall']) {
    assert.equal(after[market].total_bets, before[market].total_bets);
    assert.equal(after[market].total_profit, before[market].total_profit);
    assert.equal(after[market].roi, before[market].roi);
  }
  assert.equal(buildCombinedStats([]).overall.total_bets, BASELINE_STATS.overall.total_bets);
});
