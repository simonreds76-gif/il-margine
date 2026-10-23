import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { gunzipSync } from 'node:zlib';
import { compressMatchupOutput } from '../compress-matchup-output.mjs';

test('all retained versions survive byte-identically, including prices and history', () => {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'matchup-storage-'));
  try {
    const originals = new Map();
    for (const version of ['20261021-0123456789ab', '20261023-abcdef012345']) {
      const dir = path.join(root, 'public/tennis-matchup/data', version);
      fs.mkdirSync(dir, { recursive: true });
      for (const name of ['index.json', '145.json']) {
        const bytes = Buffer.from(JSON.stringify({ version, name, player: 'Fàbregas', matches: [{ o1: 1.008, o2: 27.1, winner: 0 }], results: [{ o1: null }] }));
        const file = path.join(dir, name);
        originals.set(file, bytes);
        fs.writeFileSync(file, bytes);
      }
      fs.writeFileSync(path.join(dir, 'keep.txt'), 'untouched');
    }
    const report = compressMatchupOutput(root);
    assert.equal(report.files, 2);
    for (const [file, bytes] of originals) assert.deepEqual(fs.readFileSync(file), bytes);
    assert.equal(compressMatchupOutput(root, { write: true }).files, 2);
    for (const [file, bytes] of originals) {
      if (path.basename(file) === 'index.json') {
        assert.deepEqual(fs.readFileSync(file), bytes);
        assert.equal(fs.existsSync(`${file}.gz`), false);
        continue;
      }
      assert.equal(fs.existsSync(file), false);
      assert.deepEqual(gunzipSync(fs.readFileSync(`${file}.gz`)), bytes);
      assert.equal(fs.readFileSync(path.join(path.dirname(file), 'keep.txt'), 'utf8'), 'untouched');
    }
  } finally { fs.rmSync(root, { recursive: true, force: true }); }
});
