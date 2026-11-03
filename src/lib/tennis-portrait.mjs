import catalogue from '../data/tip-tennis-portraits.json' with { type: 'json' };

const words = value => String(value ?? '').normalize('NFD').replace(/\p{M}/gu, '').toLowerCase().replace(/[^a-z0-9]+/g, ' ').trim();

// Resolve identity before considering whether a picture exists. A missing photo
// must never make us choose another player with the same surname.
export function resolveTennisPortrait(name, rows = catalogue) {
  const query = words(name);
  if (!query) return null;
  const exact = rows.filter(row => words(row.name) === query);
  if (exact.length) return exact.length === 1 ? exact[0] : null;
  const suffix = rows.filter(row => words(row.name).endsWith(` ${query}`));
  if (suffix.length) return suffix.length === 1 ? suffix[0] : null;
  const parts = query.split(' ');
  if (parts.length < 2) return null;
  const queries = [parts];
  // Editors and feeds also use surname-first notation: Tsitsipas S.,
  // Cerundolo F. and Cerundolo J.M. Preserve both orientations safely.
  for (let split = 1; split < parts.length; split++) {
    const tail = parts.slice(split);
    if (tail.every(token => token.length === 1) || (tail.length === 1 && tail[0].length <= 3)) queries.push([...tail, ...parts.slice(0, split)]);
  }
  const candidates = rows.filter(row => queries.some(parts => {
    const full = words(row.name).split(' ');
    // Match the entire surname; expand given-name initials only. Reject partial
    // names that could belong to either sibling, even if only one has artwork.
    for (let split = 1; split < parts.length; split++) {
      const surname = parts.slice(split), given = parts.slice(0, split);
      if (full.length <= surname.length || full.slice(-surname.length).join(' ') !== surname.join(' ')) continue;
      const first = full.slice(0, -surname.length);
      const initials = given.length === 1 && given[0].length <= first.length && first.length > 1
        ? given[0].split('') : given;
      if (initials.length > first.length) continue;
      if (initials.every((token, i) => token.length === 1 ? first[i].startsWith(token) : first[i] === token)) return true;
    }
    return false;
  }));
  return candidates.length === 1 ? candidates[0] : null;
}
