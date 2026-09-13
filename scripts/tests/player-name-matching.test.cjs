const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const { foldNameText } = require('../../src/lib/player-name-matching.ts');

test('web matching agrees with Python on special Latin letters', () => {
  const cases = JSON.parse(fs.readFileSync(path.join(__dirname, 'name-folding-cases.json'), 'utf8'));
  for (const [raw, expected] of cases) {
    assert.equal(foldNameText(raw), expected);
    assert.equal(foldNameText(foldNameText(raw)), expected);
  }
  assert.equal(foldNameText(null), '');
  assert.equal(foldNameText('张帅'), '张帅');
  assert.notEqual(foldNameText('Martin Ødegaard'), foldNameText('Markus Odegaard'));
});
