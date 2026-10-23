import fs from 'node:fs';
import path from 'node:path';
import { gzipSync, gunzipSync } from 'node:zlib';
import { fileURLToPath } from 'node:url';

// Build-output optimisation only. Source snapshots stay readable in Git and
// locally. Run after Next has generated the Matchday projection and traces.
// The CDN rewrites the existing JSON URLs to these losslessly encoded files.
export function compressMatchupOutput(root, { write = false } = {}) {
  const base = path.resolve(root, 'public/tennis-matchup/data');
  let rawBytes = 0, compressedBytes = 0, files = 0;
  for (const version of fs.readdirSync(base, { withFileTypes: true })) {
    if (!version.isDirectory() || !/^\d{8}-[a-f0-9]{12}$/.test(version.name)) continue;
    const dir = path.join(base, version.name);
    for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
      // Keep the tiny index in plain JSON: existing daily publishing tools use
      // curl/urllib without content decoding to validate it before promotion.
      if (!entry.isFile() || !/^\d+\.json$/.test(entry.name)) continue;
      const source = path.join(dir, entry.name);
      const original = fs.readFileSync(source);
      const compressed = gzipSync(original, { level: 9 });
      if (!gunzipSync(compressed).equals(original)) throw Error(`Round-trip failed: ${source}`);
      rawBytes += original.length;
      compressedBytes += compressed.length;
      files++;
      if (write) {
        fs.writeFileSync(`${source}.gz`, compressed);
        // Only the exact JSON file verified above; never directories or archives.
        fs.unlinkSync(source);
      }
    }
  }
  if (!files) throw Error('No Matchup snapshots found to compress');
  const size = dir => fs.readdirSync(dir, { withFileTypes: true }).reduce((sum, entry) => {
    const file = path.join(dir, entry.name);
    return sum + (entry.isDirectory() ? size(file) : fs.statSync(file).size);
  }, 0);
  const publicBytes = size(path.join(root, 'public')) - (write ? 0 : rawBytes - compressedBytes);
  // Current public output is ~91 MB. Stop accidental archive duplication from
  // silently returning on future daily publications; investigate before raising.
  const maxPublicBytes = 150_000_000;
  if (publicBytes > maxPublicBytes) throw Error(`Static output ${publicBytes} exceeds ${maxPublicBytes} byte budget`);
  return { files, rawBytes, compressedBytes, savedBytes: rawBytes - compressedBytes, publicBytes, maxPublicBytes, write };
}

if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  // Do not mutate a developer checkout. Vercel builds use disposable source trees.
  const write = process.env.VERCEL === '1';
  console.log('[matchup-storage]', JSON.stringify(compressMatchupOutput(process.cwd(), { write })));
}
