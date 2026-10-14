const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const ts = require('typescript');
function load(file, dependencies = {}) {
  const exports = {};
  const code = ts.transpileModule(fs.readFileSync(file, 'utf8'), {compilerOptions: {module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2021}}).outputText;
  vm.runInNewContext(code, {exports, require: id => {if (id in dependencies) return dependencies[id]; throw new Error(id);}, AbortSignal, Date, Error});
  return exports;
}
const summary = load('src/lib/admin-model-summary.ts');
test('Volume 200 uses the published lane key', () => {
  const r = summary.modelRows({tennis_model_evidence: {lanes: {volume_200: {settled: 125, roi_pct: -1.0252}}}}, {}).find(r => r.id === 'volume_200');
  assert.equal(r.settled, 125); assert.equal(r.roi, -1.0252);
});
test('missing reports stay unavailable; no fabricated zeros', () => {
  const rows = summary.modelRows(null, null);
  for (const r of rows) for (const k of ['roi', 'profit', 'settled', 'pending']) assert.equal(r[k], null, `${r.id}.${k}`);
});
test('football ratios convert once and exclude warm up evidence', () => {
  const rows = summary.modelRows({}, {football_counts_vnext: {team_shots_v4: {prospective: {settled: 3, pending: 0, roi: -1, pnl_units: -3}, warmup_tracking: {roi: .8, settled: 100}}}, goalkeeper_saves_v1: {settled: 60, roi: .531767}});
  assert.equal(rows.find(r => r.id === 'team_shots_v4').roi, -100);
  assert.equal(rows.find(r => r.id === 'team_shots_v4').settled, 3);
  assert.equal(rows.find(r => r.id === 'gk').roi, 53.1767);
  assert.equal(rows.find(r => r.id === 'gk').profit, null);
});
test('Astra uses corrected forward selections, not all fixtures or replay', () => {
  const r = summary.modelRows({tennis_context_forward: {settled: 39, candidate: {settled: 2, roi_pct: -100, pending: 1}, historical_replay_bets: 69}}, {}).find(r => r.id === 'astra');
  assert.equal(r.settled, 2); assert.equal(r.pending, 1); assert.equal(r.roi, -100);
});
test('v4 observations are not bets and empty ROI stays unavailable', () => {
  const r = summary.modelRows({tennis_props_v4: {rows_settled: 301, rows_pending: 10, signals_settled: 0, roi_pct: 0}}, {}).find(r => r.id === 'aces-v4');
  assert.equal(r.settled, 0); assert.equal(r.pending, null); assert.equal(r.roi, null);
});
test('freshness flags stale, missing and future dates', () => {
  const now = Date.parse('2026-10-14T12:00:00Z');
  assert.equal(summary.snapshotAge('2026-10-13T12:00:00Z', now), 'Recent');
  assert.equal(summary.snapshotAge('2026-05-18T12:00:00Z', now), 'Stale');
  assert.equal(summary.snapshotAge(null, now), 'Date unavailable');
  assert.equal(summary.snapshotAge('2026-10-16', now), 'Date unavailable');
});
test('reader checks authentication before creating a database client', async () => {
  let dbCalls = 0;
  const reader = load('src/lib/admin-model-reader.ts', {'server-only': {}, '@/lib/admin-auth': {isAdminSession: async () => false}, '@/lib/supabase-server': {getSupabaseAdmin: () => {dbCalls++;}}, '@/lib/admin-model-summary': summary});
  await assert.rejects(reader.readAdminModels(), /Unauthorized/); assert.equal(dbCalls, 0);
});
test('one failed source does not hide the other source', async () => {
  const reader = load('src/lib/admin-model-reader.ts', {'server-only': {}, '@/lib/admin-auth': {isAdminSession: async () => true}, '@/lib/admin-model-summary': summary,
    '@/lib/supabase-server': {getSupabaseAdmin: () => ({from: () => ({select: () => ({eq: (_, key) => ({abortSignal: () => ({maybeSingle: async () => key === 'tennis_evidence_v1' ? {error: {message: 'unavailable'}} : {data: {report: {content: JSON.stringify({generated_at: '2026-10-14', goalkeeper_saves_v1: {settled: 60, roi: .5}})}}}})})})})})}});
  const result = await reader.readAdminModels();
  assert.equal(result.sources[0].available, false); assert.equal(result.sources[1].available, true);
  assert.equal(result.rows.find(r => r.id === 'gk').roi, 50);
});
