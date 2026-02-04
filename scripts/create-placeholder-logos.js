const fs = require('fs');
const path = require('path');

const outputDir = path.join(__dirname, '..', 'public', 'bookmakers');

// Create directory if it doesn't exist
if (!fs.existsSync(outputDir)) {
  fs.mkdirSync(outputDir, { recursive: true });
}

// Bookmaker placeholders with colors
const bookmakers = [
  { name: 'bet365', color: '#00A859', text: '365' },
  { name: 'betfair', color: '#FFB800', text: 'BF' },
  { name: 'paddypower', color: '#00A859', text: 'PP' },
  { name: 'williamhill', color: '#003366', text: 'WH' },
  { name: 'ladbrokes', color: '#E60012', text: 'LB' },
  { name: 'coral', color: '#E60012', text: 'CR' },
  { name: 'skybet', color: '#003087', text: 'SB' },
  { name: 'unibet', color: '#FF6B00', text: 'UB' },
  { name: 'betway', color: '#00A859', text: 'BW' },
  { name: '888sport', color: '#FF6B00', text: '888' },
  { name: 'betvictor', color: '#003366', text: 'BV' },
  { name: 'betfred', color: '#E60012', text: 'BF' },
  { name: 'pinnacle', color: '#1A1A1A', text: 'PN' },
  { name: 'betmgm', color: '#FFB800', text: 'MGM' },
];

function createSVGLogo({ name, color, text }) {
  return `<svg width="64" height="64" viewBox="0 0 64 64" fill="none" xmlns="http://www.w3.org/2000/svg">
  <rect width="64" height="64" rx="8" fill="${color}"/>
  <text x="32" y="42" font-family="Arial, sans-serif" font-size="${text.length > 2 ? '14' : '18'}" font-weight="bold" fill="white" text-anchor="middle">${text}</text>
</svg>`;
}

console.log('Creating placeholder logos...\n');

bookmakers.forEach((bookmaker) => {
  const svg = createSVGLogo(bookmaker);
  const filepath = path.join(outputDir, `${bookmaker.name}.svg`);
  fs.writeFileSync(filepath, svg);
  console.log(`✓ Created: ${bookmaker.name}.svg`);
});

console.log('\n✓ All placeholder logos created!');
console.log('\nNote: These are temporary placeholders. Replace with actual PNG logos when available.');
console.log('You can find official logos from:');
console.log('- Bookmaker affiliate portals (they provide marketing assets)');
console.log('- Official bookmaker websites (press/media sections)');
console.log('- Logo databases (logos-world.net, brandfetch.com)');
