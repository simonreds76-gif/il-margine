// Build small UI copies once; keep the original portraits and their provenance intact.
const fs = require('node:fs');
const path = require('node:path');
const { createHash } = require('node:crypto');
const sharp = require('sharp');

async function build(root = path.resolve(__dirname, '..')) {
  const sourceDir = path.join(root, 'public/manager-atlas/portraits');
  const outputDir = path.join(root, 'public/manager-atlas/portrait-thumbs-v1');
  fs.mkdirSync(outputDir, { recursive: true });
  const manifest = {};
  let originalBytes = 0, thumbnailBytes = 0;
  for (const file of fs.readdirSync(sourceDir).filter(file => file.endsWith('.webp')).sort()) {
    const input = fs.readFileSync(path.join(sourceDir, file));
    const hash = createHash('sha256').update(input).digest('hex').slice(0, 12);
    const name = `${path.parse(file).name}-${hash}.webp`;
    const output = path.join(outputDir, name);
    if (!fs.existsSync(output)) {
      await sharp(input).resize(144, 144, { fit: 'inside', withoutEnlargement: true })
        .webp({ quality: 88, alphaQuality: 100 }).toFile(output);
    }
    manifest[`/manager-atlas/portraits/${file}`] = `/manager-atlas/portrait-thumbs-v1/${name}`;
    originalBytes += input.length;
    thumbnailBytes += fs.statSync(output).size;
  }
  fs.writeFileSync(path.join(root, 'src/lib/fixture-portrait-thumbnails.json'), JSON.stringify(manifest, null, 2) + '\n');
  const crestManifest = {};
  const logoManifestPath = path.join(root, 'src/lib/team-logo-thumbnails.json');
  if (fs.existsSync(logoManifestPath)) {
    const crestDir = path.join(root, 'public/team-logos/fixture-thumbs-v2');
    fs.mkdirSync(crestDir, { recursive: true });
    for (const original of Object.keys(JSON.parse(fs.readFileSync(logoManifestPath, 'utf8'))).sort()) {
      const input = fs.readFileSync(path.join(root, 'public', original));
      const hash = createHash('sha256').update(input).digest('hex').slice(0, 12);
      const name = `${original.slice('/team-logos/'.length).replaceAll('/', '-')}-${hash}.webp`;
      const output = path.join(crestDir, name);
      if (!fs.existsSync(output)) await sharp(input).resize(96, 96, { fit: 'inside', withoutEnlargement: true })
        .webp({ quality: 82, alphaQuality: 100 }).toFile(output);
      crestManifest[original] = `/team-logos/fixture-thumbs-v2/${name}`;
    }
  }
  fs.writeFileSync(path.join(root, 'src/lib/fixture-crest-thumbnails.json'), JSON.stringify(crestManifest, null, 2) + '\n');
  console.log(JSON.stringify({ portraits: Object.keys(manifest).length, originalBytes, thumbnailBytes }));
}

module.exports = { build };
if (require.main === module) build().catch(error => { console.error(error); process.exitCode = 1; });
