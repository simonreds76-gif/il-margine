const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const ts = require('typescript');
function load(file, deps = {}) {
  const module = { exports: {} };
  new Function('module', 'exports', 'require', ts.transpileModule(fs.readFileSync(file, 'utf8'), { compilerOptions: { module: ts.ModuleKind.CommonJS } }).outputText)(module, module.exports, name => deps[name] ?? require(name));
  return module.exports;
}
const math = load('src/lib/calculator/math.ts');
const { footballFairPrices, footballExpectedValue } = load('src/lib/calculator/football.ts', { './math': math });
const near = (actual, expected) => assert.ok(Math.abs(actual - expected) < 1e-8, `${actual} != ${expected}`);

test('equal three-way probabilities yield DC 1.5 and DNB 2.0', () => {
  for (const method of ['proportional', 'shin', 'oddsRatio']) {
    const { markets } = footballFairPrices([2.8, 2.8, 2.8], method);
    for (const key of ['homeDraw', 'homeAway', 'drawAway']) near(markets[key].fairOdds, 1.5);
    for (const key of ['homeDnb', 'awayDnb']) near(markets[key].fairOdds, 2);
  }
});
test('worked example refunds draws and measures EV on the original stake', () => {
  const result = footballFairPrices([2, 1 / .3, 5]);
  near(result.markets.homeDraw.fairOdds, 1.25);
  near(result.markets.homeDnb.fairOdds, 1.4);
  near(result.markets.homeDnb.refund, .3);
  near(footballExpectedValue(result.markets.homeDnb, 1.5), .05);
  near(footballExpectedValue(result.markets.homeDnb, 1.3), -.05);
  near(footballExpectedValue(result.markets.homeDraw, 1.3), .04);
});
test('settlement probabilities sum to one and every fair price has zero EV', () => {
  for (const prices of [[1.15, 8, 18], [2.1, 3.4, 3.6], [4, 4, 4], [1000, 1.01, 500]]) {
    for (const method of ['proportional', 'shin', 'oddsRatio']) {
      const result = footballFairPrices(prices, method);
      assert.ok(result);
      for (const market of Object.values(result.markets)) {
        near(market.win + market.refund + market.lose, 1);
        near(footballExpectedValue(market, market.fairOdds), 0);
        assert.ok(market.fairOdds > 1 && Number.isFinite(market.fairOdds));
      }
    }
  }
});
test('home-away swap preserves the corresponding market prices', () => {
  const a = footballFairPrices([1.7, 4, 5]);
  const b = footballFairPrices([5, 4, 1.7]);
  near(a.markets.homeDnb.fairOdds, b.markets.awayDnb.fairOdds);
  near(a.markets.homeDraw.fairOdds, b.markets.drawAway.fairOdds);
});
test('incomplete, impossible and non-finite inputs cannot create a result', () => {
  for (const prices of [[], [2, 3], [2, 3, 4, 5], [1, 3, 4], [0, 3, 4], [-2, 3, 4], [NaN, 3, 4], [Infinity, 3, 4], [1001, 3, 4]]) assert.equal(footballFairPrices(prices), null);
});
