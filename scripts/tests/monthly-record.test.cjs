const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const ts = require('typescript');
const code = ts.transpileModule(fs.readFileSync(path.join(__dirname, '../../src/lib/monthly-record.ts'), 'utf8'), {
  compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020 },
}).outputText;
const context = { exports: {} };
vm.runInNewContext(code, context);
const { buildMonthlyRows } = context.exports;
test('monthly record retains losses and uses total stake as ROI denominator', () => {
  const rows = buildMonthlyRows([
    { match_date: '2026-09-01', status: 'won', stake: 2, profit_loss: 3 },
    { match_date: '2026-09-02', status: 'lost', stake: 1, profit_loss: -1 },
    { match_date: '2026-08-01', status: 'lost', stake: 2, profit_loss: -2 },
    { match_date: '2026-09-03', status: 'void', stake: 10, profit_loss: 0 },
    { match_date: '2026-09-04', status: 'pending', stake: 10, profit_loss: null },
  ]);
  assert.equal(rows.length, 2);
  assert.equal(rows[0].month, '2026-09');
  assert.equal(rows[0].total_bets, 2);
  assert.equal(rows[0].total_stake, 3);
  assert.equal(rows[0].total_profit, 2);
  assert.equal(rows[0].roi, 66.6667);
  assert.equal(rows[1].total_profit, -2);
  assert.equal(rows[1].roi, -100);
});
test('settlement date is the fallback and missing dates do not create fake months', () => {
  const rows = buildMonthlyRows([
    { settled_at: '2026-07-10', status: 'won', stake: '0.5', profit_loss: '0.75' },
    { status: 'lost', stake: 1, profit_loss: -1 },
  ]);
  assert.equal(rows.length, 1);
  assert.equal(rows[0].month, '2026-07');
  assert.equal(rows[0].roi, 150);
});

test('full record adds earlier summary exactly once and weights ROI by stakes', () => {
  const monthly = [{ total_profit: -10, total_stake: 50, total_bets: 20 }];
  const earlier = { total_profit: 40, total_stake: 200, total_bets: 200 };
  const full = context.exports.summarizeMonthlyRecord(monthly, earlier);
  assert.equal(full.profit, 30);
  assert.equal(full.stake, 250);
  assert.equal(full.bets, 220);
  assert.equal(full.roi, 12);
  const recent = context.exports.summarizeMonthlyRecord(monthly);
  assert.equal(recent.profit, -10);
  assert.equal(recent.roi, -20);
  assert.equal(monthly[0].total_profit, -10);
  assert.equal(context.exports.summarizeMonthlyRecord([]).roi, null);
});

test('full monthly record retains more than 24 months without truncating totals', () => {
  const rows = buildMonthlyRows(Array.from({ length: 30 }, (_, i) => ({
    match_date: new Date(Date.UTC(2023, i, 10)).toISOString(),
    status: 'lost', stake: 1, profit_loss: -1,
  })));
  assert.equal(rows.length, 30);
  assert.equal(context.exports.summarizeMonthlyRecord(rows).profit, -30);
});
