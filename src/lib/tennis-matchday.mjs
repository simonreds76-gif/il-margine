// Explicit feed variants of these archive identities; never fuzzy-match opponents.
const aliases = { 'jaume munar': 'vbt-10698', 'pedro martinez': 'vbt-12525', 'taylor fritz': 'vbt-9023', 'yunchaokete bu': 'vbt-25003' };
const normal = text => String(text ?? '').normalize('NFD').replace(/\p{M}/gu, '').toLowerCase().replace(/[^a-z0-9]+/g, ' ').trim();
const knownPlayer = name => name && !/\b(tba|tbd|winner|qualifier|bye)\b|[/&]/i.test(name);
const day = (time, zone) => new Intl.DateTimeFormat('en-CA', { timeZone: zone, year: 'numeric', month: '2-digit', day: '2-digit' }).format(time);

export function matchdayHref(a, b) {
  return '/tennis-matchup?' + new URLSearchParams({ player: a, compare: b, record: 'h2h', history: 'archive' });
}

export function buildTennisMatchday(rows, history, now = new Date()) {
  const names = new Map(), ids = new Map(history.players.map((p, i) => [p.id, i]));
  history.players.forEach((p, i) => names.set(normal(p.name), [...(names.get(normal(p.name)) ?? []), i]));
  const resolve = name => {
    const key = normal(name), direct = names.get(key);
    if (direct?.length === 1) return direct[0];
    return Object.hasOwn(aliases, key) ? ids.get(aliases[key]) : undefined;
  };
  const stamps = [...new Set(rows.map(r => r.captured_at).filter(Boolean))];
  const capturedAt = stamps.length === 1 && Number.isFinite(Date.parse(stamps[0])) ? stamps[0] : null;
  const stale = !capturedAt || now.getTime() - Date.parse(capturedAt) > 24 * 3600000 || Date.parse(capturedAt) > now.getTime() + 300000;
  const fixtures = [], excluded = { started: 0, invalid: 0, duplicate: 0 };
  const pairs = new Map();
  for (const row of rows) {
    const start = Date.parse(row.kickoff_iso);
    if (!['ATP', 'Challenger'].includes(row.league) || !knownPlayer(row.player1_name) || !knownPlayer(row.player2_name)
      || /doubles|women|\bwta\b/i.test(row.league_name) || !Number.isFinite(start)
      || normal(row.player1_name) === normal(row.player2_name) || (capturedAt && start <= Date.parse(capturedAt))) { excluded.invalid++; continue; }
    if (start <= now.getTime()) { excluded.started++; continue; }
    if (start > now.getTime() + 72 * 3600000) continue;
    const pairKey = [normal(row.player1_name), normal(row.player2_name)].sort().join('|');
    if (pairs.has(pairKey)) { pairs.get(pairKey).ambiguous = true; excluded.duplicate++; continue; }
    const a = resolve(row.player1_name), b = resolve(row.player2_name);
    const players = [a, b].map((i, side) => i === undefined ? { id: null, name: side ? row.player2_name : row.player1_name, portrait: null }
      : { id: history.players[i].id, name: history.players[i].name, portrait: history.players[i].portrait });
    const cutoff = [now.toISOString().slice(0, 10), new Date(start).toISOString().slice(0, 10), history.asOf].sort()[0];
    const meetings = a === undefined || b === undefined ? null : history.matches
      .filter(m => m[0] < cutoff && ((m[1] === a && m[2] === b) || (m[1] === b && m[2] === a)))
      .map(m => ({ date: m[0], winner: (m[3] === 0 ? m[1] : m[2]) === a ? 0 : 1,
        odds: m[1] === a ? [m[4], m[5]] : [m[5], m[4]], surface: m[6], score: m[7], event: m[8] }));
    const wins = meetings ? [meetings.filter(m => m.winner === 0).length, meetings.filter(m => m.winner === 1).length] : null;
    const priced = meetings?.filter(m => m.odds.every(p => Number.isFinite(p) && p > 1)) ?? [];
    const profit = [0, 1].map(side => priced.reduce((sum, m) => sum + (m.winner === side ? m.odds[side] - 1 : -1), 0));
    const fixture = { id: `${row.league}:${pairKey}`, start: new Date(start).toISOString(), tour: row.league,
      event: row.league_name.replace(/^ATP\s+Challenger\s+|^ATP\s+/i, ''), qualifying: /qualifying|qualification|\bqual\b/i.test(row.league_name),
      players, wins, meetings: meetings?.length ?? null, priced: priced.length,
      roi: profit.map(p => priced.length ? Math.round(1000 * p / priced.length) / 10 : null),
      profit: profit.map(p => Math.round(p * 100) / 100), recent: meetings?.slice(-3).reverse() ?? [],
      href: a !== undefined && b !== undefined ? matchdayHref(players[0].id, players[1].id) : null, ambiguous: false };
    pairs.set(pairKey, fixture); fixtures.push(fixture);
  }
  return { capturedAt, historyThrough: history.through, historyVersion: history.version, stale, excluded,
    fixtures: stale ? [] : fixtures.filter(f => !f.ambiguous).sort((a, b) => a.start.localeCompare(b.start) || a.event.localeCompare(b.event)) };
}

export function fixturesFor(fixtures, filter, tour, search, now, zone = 'Europe/London') {
  const today = day(now, zone);
  // Calendar tomorrow, including the 25-hour day when British Summer Time ends.
  const tomorrow = new Date(Date.parse(`${today}T12:00:00Z`) + 24 * 3600000).toISOString().slice(0, 10);
  return fixtures.filter(f => Date.parse(f.start) > now.getTime() && (tour === 'all' || f.tour === tour)
    && (filter === 'upcoming' || day(new Date(f.start), zone) === (filter === 'today' ? today : tomorrow))
    && normal(`${f.event} ${f.players.map(p => p.name).join(' ')}`).includes(normal(search)));
}
