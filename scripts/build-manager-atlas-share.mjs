import fs from 'node:fs';
import { pathToFileURL } from 'node:url';
import sharp from 'sharp';
import { brandMark } from '../research/manager-atlas/identity.mjs';

// Explicit colour is essential: standalone SVG currentColor defaults to black.
export async function buildManagerAtlasShare(directory = 'public/manager-atlas') {
  const mark = brandMark()
    .replace(/\s(?:width|height)="[^"]*"/g, '')
    .replaceAll('currentColor', '#a1f0d0')
    .replace('<svg ', '<svg x="76" y="134" width="228" height="228" ');
  const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="630" viewBox="0 0 1200 630">
    <defs><linearGradient id="background" x2="1" y2="1"><stop stop-color="#132b26"/><stop offset="1" stop-color="#0b131b"/></linearGradient></defs>
    <rect width="1200" height="630" fill="url(#background)"/>
    <rect x="24" y="24" width="1152" height="582" rx="28" fill="none" stroke="#36564f"/>
    <rect x="78" y="73" width="44" height="5" rx="2.5" fill="#9ae7c6"/>
    <text x="139" y="85" fill="#b2c9c0" font-family="Arial" font-size="23" letter-spacing="3">IL MARGINE</text>
    <rect x="65" y="127" width="248" height="248" rx="44" fill="#152f29" stroke="#41675b"/>
    ${mark}
    <text x="350" y="241" fill="#f2f7f4" font-family="Arial" font-size="76" font-weight="bold">Return Atlas</text>
    <text x="355" y="308" fill="#a1f0d0" font-family="Arial" font-size="38" letter-spacing="8">MANAGERS</text>
    <text x="80" y="460" fill="#f2f7f4" font-family="Arial" font-size="38" font-weight="bold">Compare managers head to head.</text>
    <text x="80" y="513" fill="#c0d3cb" font-family="Arial" font-size="29">Explore past results and betting returns.</text>
    <text x="80" y="566" fill="#a1f0d0" font-family="Arial" font-size="21" letter-spacing="2">FOOTBALL RESEARCH</text>
    <text x="1120" y="566" text-anchor="end" fill="#b2c9c0" font-family="Arial" font-size="23">ilmargine.bet</text>
  </svg>`;
  fs.mkdirSync(directory, { recursive: true });
  await sharp(Buffer.from(svg)).png().toFile(`${directory}/share-v2.png`);
}

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  await buildManagerAtlasShare();
}
