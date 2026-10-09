import fs from 'node:fs';
import path from 'node:path';

// Compact, server-only projection of the existing public Matchup Lab archive.
// Rebuilt with each site build; no odds downloads or new historical sources.
const root = process.cwd();
const release = JSON.parse(fs.readFileSync(path.join(root, 'src/data/tennis-matchup-release.json'), 'utf8'));
const dir = path.dirname(path.join(root, 'public', release.indexUrl));
const index = JSON.parse(fs.readFileSync(path.join(dir, 'index.json'), 'utf8'));
const matches = new Map();
const results = new Map();
for (let player = 0; player < index.players.length; player++) {
  if (index.players[player].index !== player) throw Error('Matchday player index mismatch');
  const shard = JSON.parse(fs.readFileSync(path.join(dir, `${player}.json`), 'utf8'));
  if (shard.version !== index.version || shard.player !== player) throw Error('Matchday history snapshot mismatch');
  for (const m of [...shard.matches,...(shard.results ?? [])]) {
    const store = m.competition ? results : matches;
    const row = [m.date, m.p1, m.p2, m.winner, m.o1, m.o2, m.surface, m.score, m.event, m.competition ?? null, m.priceBasis ?? null];
    if (store.has(m.id) && JSON.stringify(store.get(m.id)) !== JSON.stringify(row)) throw Error('Conflicting match records');
    store.set(m.id, row);
  }
}
if (matches.size !== release.matches) throw Error('Incomplete Matchday history projection');
if (results.size !== (index.additionalResults ?? 0)) throw Error('Incomplete H2H projection');
const output = { version: index.version, through: index.through, asOf: index.asOf,
  players: index.players.map(p => ({ ...p, portrait: index.portraits?.[p.id]?.url ?? null })),
  results: [...results.values()],
  matches: [...matches.values()].sort((a, b) => a[0].localeCompare(b[0])) };
fs.writeFileSync(path.join(root, 'src/data/tennis-matchday-history.json'), JSON.stringify(output) + '\n');
console.log(`Tennis Matchday history: ${matches.size} matches, ${index.players.length} identities, through ${index.through}`);
