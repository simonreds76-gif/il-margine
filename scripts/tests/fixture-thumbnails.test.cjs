const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const os = require('node:os');
const { createHash } = require('node:crypto');
const sharp = require('sharp');
const { build } = require('../build-fixture-thumbnails.cjs');
const root = path.resolve(__dirname, '../..');

test('all portrait copies exist, retain proportions and use the current original', async () => {
  const manifest = require('../../src/lib/fixture-portrait-thumbnails.json');
  assert.equal(Object.keys(manifest).length, fs.readdirSync(path.join(root, 'public/manager-atlas/portraits')).filter(f => f.endsWith('.webp')).length);
  for (const [original, thumbnail] of Object.entries(manifest)) {
    const input = fs.readFileSync(path.join(root, 'public', original));
    assert.ok(thumbnail.includes(createHash('sha256').update(input).digest('hex').slice(0, 12)));
    const a = await sharp(input).metadata();
    const b = await sharp(path.join(root, 'public', thumbnail)).metadata();
    assert.equal(b.format, 'webp');
    assert.ok(b.width <= 144 && b.height <= 144);
    assert.ok(Math.abs(a.width / a.height - b.width / b.height) < 0.025, original);
  }
});

test('a later portrait correction gets a new URL without overwriting its original', async () => {
  const temp = fs.mkdtempSync(path.join(os.tmpdir(), 'fixture-thumbnails-test-'));
  try {
    fs.mkdirSync(path.join(temp, 'public/manager-atlas/portraits'), { recursive: true });
    fs.mkdirSync(path.join(temp, 'src/lib'), { recursive: true });
    const input = path.join(temp, 'public/manager-atlas/portraits/manager.webp');
    const output = path.join(temp, 'src/lib/fixture-portrait-thumbnails.json');
    await sharp({ create: { width: 192, height: 192, channels: 4, background: '#123456' } }).webp().toFile(input);
    const before = fs.readFileSync(input);
    await build(temp);
    const first = JSON.parse(fs.readFileSync(output));
    assert.deepEqual(fs.readFileSync(input), before);
    await sharp({ create: { width: 192, height: 192, channels: 4, background: '#abcdef' } }).webp().toFile(input);
    await build(temp);
    const next = JSON.parse(fs.readFileSync(output));
    assert.notDeepEqual(next, first);
    assert.ok(fs.existsSync(path.join(temp, 'public', Object.values(next)[0])));
  } finally { fs.rmSync(temp, { recursive: true, force: true }); }
});
