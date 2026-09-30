const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const ts = require('typescript');
const source = fs.readFileSync(path.resolve(__dirname, '../../src/lib/tennis-monitor-overview.ts'), 'utf8');
const compiled = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 } });
const moduleUnderTest = { exports: {} };
vm.runInNewContext(compiled.outputText, { module: moduleUnderTest, exports: moduleUnderTest.exports });
const { tennisOverviewRows } = moduleUnderTest.exports;
const find = (snapshot, id) => tennisOverviewRows(snapshot).find(row => row.id === id);

test('missing evidence stays unavailable and valid zero is preserved', () => {
  const empty = find({}, 'challenger');
  assert.equal(empty.settled, null);
  assert.equal(empty.roi, null);
  const zero = find({ sections: { tennis_model_evidence: { lanes: { challenger: { settled: 10, roi_pct: 0, pnl_units: 0, clv: { rows: 0 } } } } } }, 'challenger');
  assert.equal(zero.roi, 0);
  assert.equal(zero.pnl, 0);
  assert.equal(zero.closes, 0);
});
test('unsettled research cannot show a zero ROI as performance', () => {
  const row = find({ sections: { tennis_props_v3: { evidence: { settled: 0, roi_pct: 0 } } } }, 'props_v3');
  assert.equal(row.roi, null);
});
test('report cutoff, generation date and cohort remain separate', () => {
  const row = find({ sections: { tennis_model_evidence: { lanes: { strict: { as_of_date: '2026-08-22', generated_at: '2026-09-29T09:00:00Z', evidence_period: 'clean' } } } } }, 'strict');
  assert.equal(row.date, '2026-08-22');
  assert.equal(row.reportDate, '2026-09-29T09:00:00Z');
  assert.equal(row.cohort, 'clean');
});
test('paired experiment distinguishes selected bets from independent fixtures', () => {
  const row = find({ sections: { tennis_rate_trend: { markets: { aces: { settled: 57, independent_fixtures: 28, candidate: { bets: 34, pnl_units: -3.38, roi_pct: -9.94 }, control: { roi_pct: -10.79 } } } } } }, 'aces');
  assert.equal(row.settled, 34);
  assert.equal(row.fixtures, 28);
  assert.equal(row.roi, -9.94);
  assert.match(row.note, /-10.79%/);
});
test('forecast outcomes and pre-fit closes are not passed off as betting results', () => {
  const snapshot = { sections: { tennis_most_aces_forecast: { rows_settled: 100, accuracy_pct: 61 }, tennis_props_v4: { rows_settled: 124, signals_settled: 0, clv_coverage: 90, roi_pct: null } } };
  assert.equal(find(snapshot, 'most_aces').settled, null);
  assert.equal(find(snapshot, 'most_aces').roi, null);
  assert.equal(find(snapshot, 'props_v4').closes, null);
  assert.equal(find(snapshot, 'props_v4').roi, null);
});
