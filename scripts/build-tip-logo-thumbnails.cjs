// Offline copies for small UI badges. Original artwork remains untouched.
const fs = require('node:fs');
const path = require('node:path');
const { execFileSync } = require('node:child_process');
const sharp = require('sharp');
(async () => {
  const files = execFileSync('git', ['ls-files', 'public/team-logos'], {encoding:'utf8'}).trim().split(/\r?\n/).filter(p=>p.endsWith('.png'));
  const manifest = {};
  let before=0,after=0;
  for (const file of files) {
    const output = file.replace('public/team-logos/', 'public/team-logos/thumbs-v1/').replace(/\.png$/, '.webp');
    fs.mkdirSync(path.dirname(output),{recursive:true});
    await sharp(file).resize(144,144,{fit:'inside',withoutEnlargement:true}).webp({quality:90,alphaQuality:100}).toFile(output);
    manifest['/'+file.slice(7)]='/'+output.slice(7);
    before+=fs.statSync(file).size; after+=fs.statSync(output).size;
  }
  fs.writeFileSync('src/lib/team-logo-thumbnails.json', JSON.stringify(manifest,null,2)+'\n');
  await sharp('public/icons/markets/atp-logo.png').resize(240,240,{fit:'inside',withoutEnlargement:true}).webp({quality:90,alphaQuality:100}).toFile('public/icons/markets/atp-logo-small-v1.webp');
  console.log(JSON.stringify({crests:files.length,originalBytes:before,thumbnailBytes:after,atpBytes:fs.statSync('public/icons/markets/atp-logo-small-v1.webp').size}));
})();
