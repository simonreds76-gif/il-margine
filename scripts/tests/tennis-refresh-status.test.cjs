const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const ts = require('typescript');
const file = path.resolve(__dirname, '../../src/lib/tennis-refresh-status.ts');
const code = ts.transpileModule(fs.readFileSync(file, 'utf8'), {
  compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020 },
}).outputText;
const compiled = { exports: {} };
new Function('module', 'exports', code)(compiled, compiled.exports);
const { tennisRefreshIsActive, tennisRefreshStatusMessage, tennisRefreshStatusType, reconcileMonitorUpload, refreshTime } = compiled.exports;

test('restored waiting and running requests remain active; completed/failed never do', () => {
  for (const state of ['pending', 'waiting', 'dispatching', 'started']) assert.equal(tennisRefreshIsActive({ state }), true);
  for (const state of ['completed', 'failed', undefined]) assert.equal(tennisRefreshIsActive({ state }), false);
  assert.equal(tennisRefreshIsActive(null), false);
});

test('old daily alert IDs must not be described as current selections', () => {
  const message = tennisRefreshStatusMessage({ state: 'completed', signal_count: 19, telegram_status: 'relay_queued' });
  assert.doesNotMatch(message, /19|current tennis signal|delivered successfully/);
  assert.match(message, /not confirmation of delivery/);
});

test('a receipt without relay evidence does not claim a Telegram send', () => {
  assert.doesNotMatch(tennisRefreshStatusMessage({ state: 'completed' }), /queued|delivered/);
});

test('failed work stays a failure, retaining its specific reason', () => {
  assert.equal(tennisRefreshStatusMessage({ state: 'failed', error: 'OnCourt changed during extraction' }), 'OnCourt changed during extraction');
});

test('missing and invalid input timestamps are not presented as fresh', () => {
  for (const value of [undefined, '', 'not-a-date']) assert.equal(refreshTime(value), 'Not recorded');
});

test('evening run timestamps show London time including summer time', () => {
  assert.match(refreshTime('2026-10-28T21:49:23.4682053Z'), /21:49/);
  assert.match(refreshTime('2026-09-26T21:13:32Z'), /22:13/);
});

test('current pipeline progress is shown without declaring completion', () => {
  const message = tennisRefreshStatusMessage({ state: 'started', phase: 'props', progress_message: 'Capturing fresh aces and double-fault prices.' });
  assert.equal(message, 'Capturing fresh aces and double-fault prices.');
  assert.equal(tennisRefreshIsActive({ state: 'started' }), true);
});

test('successful zero-new check does not imply Telegram delivery', () => {
  const message = tennisRefreshStatusMessage({ state: 'completed', telegram_status: 'checked_no_new', telegram_new_signals: 0 });
  assert.match(message, /No new qualifying selections/);
  assert.match(message, /earlier alerts were not repeated/);
  assert.doesNotMatch(message, /relay queued|30 minutes/);
});

const failure = Object.freeze({
  request_id: 'original-request', state: 'failed', error: 'Private Monitor upload failed.',
  completed_at: '2026-11-03T21:21:24Z', telegram_status: 'relay_queued',
});
const snapshot = Object.freeze({
  source: 'windows_local_tennis_pipeline', schema_version: 3, file_count: 34,
  payload_hash: 'a'.repeat(64), generated_at: '2026-11-04T10:31:22Z', updated_at: '2026-11-04T10:31:22Z',
});
const now = Date.parse('2026-11-04T11:00:00Z');

test('later hosted snapshot recovers upload display without rewriting failed request or claiming delivery', () => {
  const result = reconcileMonitorUpload(failure, snapshot, now);
  assert.equal(result.monitor_upload_recovered_at, snapshot.generated_at);
  assert.equal(result.state, 'failed');
  assert.equal(result.error, failure.error);
  assert.equal(result.request_id, failure.request_id);
  assert.equal(failure.monitor_upload_recovered_at, undefined);
  assert.equal(tennisRefreshIsActive(result), false);
  assert.equal(tennisRefreshStatusType(result), 'info');
  assert.match(tennisRefreshStatusMessage(result), /upload recovered/);
  assert.match(tennisRefreshStatusMessage(result), /not fresh prices or Telegram delivery/);
});

test('old, future, incomplete and invalid snapshot evidence never hides the failure', () => {
  const invalidSnapshots = [null, {},
    { ...snapshot, source: 'other' }, { ...snapshot, schema_version: 2 },
    { ...snapshot, payload_hash: 'invalid' }, { ...snapshot, file_count: 0 },
    { ...snapshot, generated_at: '2026-11-03T21:00:00Z', updated_at: '2026-11-03T21:00:00Z' },
    { ...snapshot, generated_at: failure.completed_at, updated_at: failure.completed_at },
    { ...snapshot, updated_at: '2026-11-04T10:30:00Z' },
    { ...snapshot, generated_at: '2026-11-05T10:31:22Z', updated_at: '2026-11-05T10:31:22Z' },
    { ...snapshot, generated_at: 'invalid' },
  ];
  for (const invalid of invalidSnapshots) {
    const result = reconcileMonitorUpload(failure, invalid, now);
    assert.deepEqual(result, failure);
    assert.equal(tennisRefreshStatusType(result), 'error');
    assert.equal(tennisRefreshStatusMessage(result), failure.error);
  }
});

test('a new run or unrelated failure cannot inherit upload recovery', () => {
  for (const changed of [
    { state: 'started' }, { state: 'pending' }, { state: 'completed' },
    { error: 'OnCourt extraction failed.' }, { completed_at: '' }, { request_id: '' },
    { completed_at: '2026-11-04T10:45:00Z' },
  ]) {
    const result = reconcileMonitorUpload({ ...failure, ...changed, monitor_upload_recovered_at: snapshot.generated_at }, snapshot, now);
    assert.equal(result.monitor_upload_recovered_at, undefined);
  }
});
