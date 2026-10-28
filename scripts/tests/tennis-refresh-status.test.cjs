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
const { tennisRefreshIsActive, tennisRefreshStatusMessage, refreshTime } = compiled.exports;

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
