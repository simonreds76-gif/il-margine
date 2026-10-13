const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const ts = require('typescript');
const source = fs.readFileSync(path.join(__dirname, '../../src/components/TodaysEdge.tsx'), 'utf8');
const dateSource = source.slice(source.indexOf('const londonDate'), source.indexOf('function publishedTime'));
const context = { Intl, Date };
vm.runInNewContext(ts.transpileModule(dateSource, {
  compilerOptions: { target: ts.ScriptTarget.ES2020 },
}).outputText, context);

test('cached HTML and initial client render use an absolute date until the London day is known', () => {
  assert.equal(context.dateChip('2026-10-14', null), '14 Oct');
  assert.equal(context.dateChip('2026-10-14', '2026-10-13'), 'Tomorrow');
  assert.equal(context.dateChip('2026-10-14', '2026-10-14'), 'Today');
  assert.equal(context.dateChip('2026-10-13', '2026-10-14'), '13 Oct');
});

test('calendar comparisons work across daylight saving and year boundaries', () => {
  assert.equal(context.dateChip('2026-03-30', '2026-03-29'), 'Tomorrow');
  assert.equal(context.dateChip('2026-10-26', '2026-10-25'), 'Tomorrow');
  assert.equal(context.dateChip('2027-01-01', '2026-12-31'), 'Tomorrow');
  assert.equal(context.dateChip(null, '2026-10-14'), 'Date TBC');
  assert.equal(context.dateChip('invalid', '2026-10-14'), 'Date TBC');
});
