const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const { createRequire } = require('node:module');
const ts = require('typescript');
const root = path.resolve(__dirname, '../..');
const source = path.join(root, 'src/lib/team-logos.ts');
const moduleResult = { exports: {} };
vm.runInNewContext(ts.transpileModule(fs.readFileSync(source, 'utf8'), {
  compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022, esModuleInterop: true },
}).outputText, { module: moduleResult, exports: moduleResult.exports, require: createRequire(source) });
const { resolveTeamLogoPath } = moduleResult.exports;
const europe = require('../../data/team-logos/europe.json');

function checkFile(team, category) {
  const logo = resolveTeamLogoPath(team, category);
  assert.ok(logo, `No crest for ${team}`);
  const bytes = fs.readFileSync(path.join(root, 'public', logo));
  assert.equal(bytes.subarray(0, 8).toString('hex'), '89504e470d0a1a0a', `${team}: not PNG`);
  assert.ok(bytes.readUInt32BE(16) >= 32 && bytes.readUInt32BE(20) >= 32, `${team}: too small`);
  return logo;
}

test('every 2026/27 Champions League club resolves to a real local crest', () => {
  assert.equal(europe.champions_league_2026_27.length, 36);
  for (const club of europe.champions_league_2026_27) checkFile(club, 'ucl');
});

test('today’s published fixtures resolve both badges regardless of competition category', () => {
  for (const category of ['ucl', 'championsleague', 'all']) {
    for (const team of ['Barcelona', 'Feyenoord', 'Stuttgart', 'Viking', 'Sporting', 'Galatasaray']) checkFile(team, category);
  }
});

test('European aliases and historical qualifiers retain their own identities', () => {
  for (const club of europe.teams) {
    for (const alias of club.aliases) assert.equal(checkFile(alias, 'all'), club.logo_path);
  }
  assert.notEqual(resolveTeamLogoPath('Sporting Braga', 'ucl'), resolveTeamLogoPath('Sporting', 'ucl'));
  assert.equal(resolveTeamLogoPath('Unknown Club', 'ucl'), null);
  assert.equal(resolveTeamLogoPath(null, 'ucl'), null);
});

test('existing domestic and World Cup crests continue to resolve', () => {
  for (const [team, category] of [['Arsenal', 'pl'], ['Inter', 'seriea'], ['Barcelona', 'laliga'], ['PSG', 'ligue1'], ['Stuttgart', 'bundesliga'], ['England', 'worldcup']]) checkFile(team, category);
});
