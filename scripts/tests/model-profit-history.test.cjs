const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const ts = require('typescript');
const cache = {};
function load(name) {
  if (cache[name]) return cache[name].exports;
  const module = cache[name] = { exports: {} };
  const code = ts.transpileModule(fs.readFileSync(`src/lib/${name}.ts`, 'utf8'), { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 } }).outputText;
  new Function('module', 'exports', 'require', code)(module, module.exports, dep => load(dep.replace('./', '')));
  return module.exports;
}
const { profitHistory, reconciledHistory, profitWindow } = load('model-profit-history');
const row = (date, pnl, extra = {}) => ({ date, pnl, result: pnl < 0 ? 'loss' : 'win', settlement_status: 'settled', market: 'aces', ...extra });

test('sorts match dates and groups same-day settlements without mutating ledger', () => {
  const rows = [row('2026-10-03', -1), row('2026-10-01', 2), row('2026-10-01', -.5)];
  const r = profitHistory(rows, 'props-record', 'props');
  assert.deepEqual(r.days.map(d => [d.date, d.cumulative, d.settled]), [['2026-10-01', 1.5, 2], ['2026-10-03', .5, 1]]);
  assert.equal(rows[0].date, '2026-10-03');
});
test('pending, void, quarantined and other markets never affect props graph', () => {
  const r = profitHistory([row('2026-10-01', 2), row('2026-10-02', 99, { result: '', settlement_status: 'pending' }), row('2026-10-02', 10, { result: 'void' }), row('2026-10-02', 5, { quarantine_reason: 'duplicate' }), row('2026-10-02', 4, { market: 'breaks' })], 'props-record', 'props');
  assert.equal(r.profit, 2); assert.equal(r.settled, 1);
});
test('missing dates or profit and duplicate IDs fail closed, no guessed stakes', () => {
  const r = profitHistory([row('', -1), row('2026-02-30', 2), row('2026-10-01', '', { selected_odds: 2 }), row('2026-10-03', 1, { signal_id: 'same' }), row('2026-10-03', 1, { signal_id: 'same' })], 'props-record', 'props');
  assert.equal(r.omitted, 4); assert.equal(r.settled, 1);
});
test('match date takes precedence over later batch settlement time', () => {
  assert.equal(profitHistory([row('2026-10-04', 1, { match_date: '2026-10-05', settled_at_utc: '2026-11-02T22:00:00Z' })], 'props-record').days[0].date, '2026-10-05');
});
test('reconciles count and profit with the same snapshot, refuses partial/different cohort', () => {
  const csv = 'date,pnl,result,settlement_status,market\n2026-10-01,2,win,settled,aces\n2026-10-02,-1,loss,settled,double_faults\n';
  assert.equal(reconciledHistory(csv, 'props-record', { settled: 2, profit: 1 }).days.length, 2);
  assert.ok(reconciledHistory(csv, 'props-record', { settled: 3, profit: 1 }).message);
  assert.ok(reconciledHistory(csv, 'props-record', { settled: 2, profit: 2 }).message);
  assert.equal(reconciledHistory(csv, 'props-record', { settled: 1, profit: 2 }, 'aces').days.length, 1);
});
test('recent window retains opening balance and measures daily drawdown from it', () => {
  const r = profitHistory([row('2026-08-01', 4), row('2026-10-01', -1), row('2026-10-04', 2)], 'props-record');
  const window = profitWindow(r, 30);
  assert.equal(window.opening, 4); assert.equal(window.change, 1); assert.equal(window.drawdown, 1);
  assert.equal(window.days.at(-1).cumulative, 5);
});
test('empty and all losing histories preserve zero origin', () => {
  assert.equal(profitWindow(profitHistory([], 'props-record'), null).change, 0);
  const r = profitWindow(profitHistory([row('2026-10-01', -1), row('2026-10-02', -1)], 'props-record'), null);
  assert.equal(r.opening, 0); assert.equal(r.drawdown, 2);
});
test('unresolved status overrides stale outcome and profit fields', () => {
  assert.equal(profitHistory([row('2026-10-01', 50, { settlement_status: 'pending' }), row('2026-10-01', 20, { settlement_status: 'void' })], 'props-record').settled, 0);
});
test('saved current private props ledger reconciles without modifying it', { skip: !process.env.MONITOR_SNAPSHOT_TEST }, () => {
  const d = JSON.parse(fs.readFileSync(process.env.MONITOR_SNAPSHOT_TEST, 'utf8'));
  const s = d.sections.tennis_props_shadow_decision;
  const r = reconciledHistory(d.admin_files['props-record'], 'props-record', { settled: s.settled, profit: s.pnl_units });
  assert.equal(r.message, undefined); assert.equal(r.settled, s.settled);
  for (const market of s.by_market) {
    assert.equal(reconciledHistory(d.admin_files['props-record'], 'props-record', { settled: market.settled, profit: market.pnl_units }, market.market).message, undefined);
  }
  for (const key of ['tennis_hardcourt_scout', 'tennis_astrissimo', 'tennis_indoor_paper']) {
    const section = d.sections[key];
    assert.equal(reconciledHistory(section.selections, key, { settled: section.settled, profit: section.pnl_units }).message, undefined, key);
  }
  console.log(JSON.stringify({ settled: r.settled, profit: r.profit, latest: r.days.at(-1), recent30: profitWindow(r, 30).change }));
});
