const courts = new Set(['all', 'outdoor-hard', 'indoor-hard', 'clay', 'grass']);

// Use archive identities, never array positions or display-name matching.
export function atlasResearchHref(player, companion, surface = 'all') {
  const params = new URLSearchParams({ player });
  if (companion && companion !== player) params.set('compare', companion);
  if (courts.has(surface) && surface !== 'all') params.set('surface', surface);
  return `/return-atlas?${params}`;
}

export function readAtlasResearch(search, players) {
  const params = new URLSearchParams(search);
  const requested = [params.get('player'), params.get('compare')].filter(Boolean);
  const known = new Set(players.map(player => player.id));
  const ids = [...new Set(requested.filter(id => known.has(id)))];
  return {
    ids,
    surface: courts.has(params.get('surface')) ? params.get('surface') : 'all',
    missing: requested.some(id => !known.has(id)),
  };
}

export function readMatchupResearch(search, players) {
  const params = new URLSearchParams(search);
  const result = readAtlasResearch(search, players);
  return { ...result, ready: result.ids.length === 2 && !result.missing,
    mode: params.get('record') === 'h2h' ? 'h2h' : 'profiles',
    months: params.get('history') === 'archive' ? 'archive' : '24' };
}
