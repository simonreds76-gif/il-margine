import { readFile, writeFile } from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import sharp from 'sharp';

// Static brand art. No runtime image generation or external assets.
const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const directory = path.join(root, 'public/football-atlas/matchday');
const mark = await readFile(path.join(directory, 'mark-v1.svg'), 'utf8');
const markBody = mark.slice(mark.indexOf('>') + 1, mark.lastIndexOf('</svg>'));
const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="630" viewBox="0 0 1200 630">
  <defs><linearGradient id="background" x2="1" y2="1"><stop stop-color="#142b25"/><stop offset="1" stop-color="#0d141c"/></linearGradient></defs>
  <rect width="1200" height="630" fill="url(#background)"/>
  <rect x="28" y="28" width="1144" height="574" rx="26" fill="none" stroke="#426858"/>
  <g stroke="#88dfb9" opacity=".11" fill="none" stroke-width="2">
    <rect x="864" y="68" width="370" height="490" rx="12"/>
    <path d="M864 313h370M970 68v77h165V68m-165 490v-77h165v77"/>
    <circle cx="1052" cy="313" r="78"/>
  </g>
  <svg x="64" y="74" width="112" height="112" viewBox="0 0 72 72">${markBody}</svg>
  <g font-family="Arial, Helvetica, sans-serif">
    <text x="192" y="112" font-size="20" font-weight="700" letter-spacing="4" fill="#a3cab8">RETURN ATLAS</text>
    <text x="188" y="183" font-size="76" font-weight="700" letter-spacing="-3" fill="#f3f8f5">Matchday<tspan fill="#8ce8bd">.</tspan></text>
    <text x="72" y="300" font-size="48" font-weight="700" letter-spacing="-1.3" fill="#f3f8f5">The record before kickoff.</text>
    <text x="74" y="349" font-size="25" fill="#b9cfca">Upcoming football fixtures. Manager and club history.</text>
    <g font-size="18" font-weight="700" fill="#a5eac9">
      <rect x="74" y="399" width="190" height="52" rx="12" fill="#1b372c" stroke="#426858"/>
      <text x="96" y="432">Manager H2H</text>
      <rect x="277" y="399" width="185" height="52" rx="12" fill="#1b372c" stroke="#426858"/>
      <text x="301" y="432">Club history</text>
      <rect x="475" y="399" width="220" height="52" rx="12" fill="#1b372c" stroke="#426858"/>
      <text x="496" y="432">Historical returns</text>
    </g>
    <g text-anchor="middle" font-size="43" font-weight="700" fill="#a5eac9">
      <text x="923" y="280">1</text><text x="1001" y="280">×</text><text x="1079" y="280">2</text>
    </g>
    <g text-anchor="middle" font-size="11" font-weight="700" letter-spacing="1.8" fill="#bad0c6">
      <text x="923" y="307">HOME</text><text x="1001" y="307">DRAW</text><text x="1079" y="307">AWAY</text>
    </g>
    <text x="74" y="544" font-size="20" font-weight="700" letter-spacing="1.3" fill="#c2d8cd">IL MARGINE</text>
    <text x="1126" y="544" text-anchor="end" font-size="19" fill="#9ebcae">ilmargine.bet</text>
  </g>
</svg>`;
await writeFile(path.join(directory, 'share-v1.svg'), svg);
await sharp(Buffer.from(svg)).png().toFile(path.join(directory, 'share-v1.png'));
console.log('Created Matchday social card, 1200 × 630.');
