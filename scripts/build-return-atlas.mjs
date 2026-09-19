// Offline release exporter. No provider requests, database calls or Vercel functions.
import fs from 'node:fs';
import path from 'node:path';
import { pathToFileURL, fileURLToPath } from 'node:url';
import { createHash } from 'node:crypto';
import { gzipSync } from 'node:zlib';

const root = process.env.RETURN_ATLAS_OUTPUT_ROOT || path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const input = process.argv[2];
if (!input) throw new Error('Usage: node scripts/build-return-atlas.mjs <audited-preview-directory>');
const checkedAt = process.argv[3];
if (!/^\d{4}-\d{2}-\d{2}$/.test(checkedAt || '')) throw new Error('Pass the actual archive-check date as YYYY-MM-DD after the source directory');
const source = path.resolve(input);
const { players, matches, metadata, eligibleRecords } = await import(pathToFileURL(path.join(source, 'real-data.mjs')));
const { portraits } = await import(pathToFileURL(path.join(source, 'portraits.mjs')));
const surfaces = ['outdoor-hard', 'clay', 'grass', 'indoor-hard'];
const sources = ['Valuebetennis', 'Tennis-Data', 'Il Margine capture'];
const playerIndex = new Map(players.map((p, i) => [p.id, i]));
const seen = new Set();
for (const m of matches) {
  if (seen.has(m.id) || !playerIndex.has(m.p1) || !playerIndex.has(m.p2) ||
    ![m.p1, m.p2].includes(m.winner) || ![m.o1,m.o2].every(n=>Number.isFinite(n)&&n>1) ||
    !surfaces.includes(m.surface) || !sources.includes(m.source) || m.status !== 'completed' || m.level !== 'ATP-main' || m.date > checkedAt) {
    throw new Error(`Invalid or duplicate accepted record: ${m.id}`);
  }
  seen.add(m.id);
}
if (matches.length !== metadata.matches || players.length !== metadata.players) throw new Error('Release metadata mismatch');
const index = {
  schema: 1, metadata, players,
  portraits: Object.fromEntries(Object.entries(portraits).map(([id,p])=>[id,{url:p.url}])),
  surfaces, sources,
  matches: matches.map(m=>[m.id,m.date,playerIndex.get(m.p1),playerIndex.get(m.p2),m.o1,m.o2,m.winner===m.p1?0:1,surfaces.indexOf(m.surface),sources.indexOf(m.source)]),
  eligible: eligibleRecords.map(([p,date,surface])=>[playerIndex.get(p),date,surfaces.indexOf(surface)]),
};
if (index.eligible.some(([p,,s])=>p===undefined||s<0)) throw new Error('Invalid eligible-record identity');
const content = JSON.stringify(index);
const hash = createHash('sha256').update(content).update(JSON.stringify(matches.map(m=>[m.id,m.event,m.score]))).digest('hex').slice(0,12);
const version = metadata.through.replaceAll('-','')+'-'+hash;
const publicPath = `/return-atlas/data/${version}`;
const out = path.join(root,'public',publicPath);
fs.mkdirSync(path.join(out,'players'),{recursive:true});
fs.writeFileSync(path.join(out,'index.json'),content);
for (const p of players) {
  const details = matches.filter(m=>m.p1===p.id||m.p2===p.id).map(m=>[m.id,m.event,m.score]);
  fs.writeFileSync(path.join(out,'players',`${p.id}.json`),JSON.stringify({schema:1,version,playerId:p.id,matches:details}));
}
const logo = fs.readFileSync(path.join(source,'return-atlas-wordmark.png'));
const logoName = 'wordmark-'+createHash('sha256').update(logo).digest('hex').slice(0,12)+'.png';
fs.mkdirSync(path.join(root,'public/return-atlas/assets'),{recursive:true});
fs.writeFileSync(path.join(root,'public/return-atlas/assets',logoName),logo);
const credits = fs.readFileSync(path.join(source,'portrait-credits.html'),'utf8');
const creditBody = credits.match(/<section>([\s\S]+)<\/main>/)?.[0].replace(/<\/main>$/,'');
if (!creditBody || !creditBody.includes('creativecommons.org/licenses/by/4.0/')) throw new Error('Missing credits');
const manifest = {version,indexUrl:publicPath+'/index.json',detailsBase:publicPath+'/players',logoUrl:'/return-atlas/assets/'+logoName,checkedAt,through:metadata.through,matches:matches.length,players:players.length,photoCount:Object.keys(portraits).length,years:metadata.years,coverage:metadata.coverage,creditsHtml:creditBody,indexBytes:Buffer.byteLength(content),indexGzipBytes:gzipSync(content).length};
fs.mkdirSync(path.join(root,'src/data'),{recursive:true});
fs.writeFileSync(path.join(root,'src/data/return-atlas-release.json'),JSON.stringify(manifest,null,2)+'\n');
console.log(JSON.stringify({version,players:players.length,matches:matches.length,indexBytes:manifest.indexBytes,indexGzipBytes:manifest.indexGzipBytes,detailsFiles:players.length}));
