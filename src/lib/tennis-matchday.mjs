import { resolveTennisPortrait, safeTennisPortraitSource } from './tennis-portrait.mjs';
import { davisCupProgramme } from './davis-cup-programme.mjs';
// Explicit feed variants of these archive identities; never fuzzy-match opponents.
const aliases = { 'jaume munar': 'vbt-10698', 'pedro martinez': 'vbt-12525', 'taylor fritz': 'vbt-9023', 'yunchaokete bu': 'vbt-25003', 'igor marcondes': 'vbt-5490', 'felipe meligeni rodrigues alves': 'vbt-16420' };
const normal = text => String(text ?? '').normalize('NFD').replace(/\p{M}/gu, '').toLowerCase().replace(/[^a-z0-9]+/g, ' ').trim();
// Verify the event itself as older price captures can carry an incorrect men's tour tag.
function mensSinglesEvent(name) {
  const label = normal(name);
  if (/\b(?:wta|women(?:s)?|ladies|girls|billie jean king|bjkc?|fed(?:eration)? cup|doubles|mixed|itf|futures|juniors?|boys|[mw]\d{2,3})\b/.test(label)) return false;
  return /\b(?:atp|men(?:s)?|davis cup|laver cup)\b|^challenger\b/.test(label);
}

const identityAliases = { 'tai leonard sach': 'tai sach', 'abdullah shelbayh': 'abedallah shelbayh', 'jason kubler': 'jason murray kubler',
  'soonwoo kwon': 'soon woo kwon', 'jisung nam': 'ji sung nam' };
const identityKey = text => identityAliases[normal(text)] ?? normal(text);
const searchNames = name => [normal(name), ...Object.entries(identityAliases).filter(([, canonical]) => canonical === identityKey(name)).map(([alias]) => alias)].join(' ');

const knownPlayer = name => name && !/\b(tba|tbd|winner|qualifier|bye)\b|[/&]/i.test(name);
const teamCompetition = /\b(?:davis cup|laver cup|atp cup|united cup)\b/;
const nationKey = name => ({ 'czech republic':'czechia', 'south korea':'korea', 'republic of korea':'korea', 'korea rep':'korea', 'great britain':'britain', 'united kingdom':'britain' })[normal(name)] ?? normal(name);
const tieMarket = /\b(?:tie|team|nation|country|overall) (?:winner|result|moneyline)|\b(?:winner of (?:the )?tie|to win (?:the )?tie|to advance|outrights?)\b/;
const day = (time, zone) => new Intl.DateTimeFormat('en-CA', { timeZone: zone, year: 'numeric', month: '2-digit', day: '2-digit' }).format(time);

// A schedule can remain useful for a day; an old quote must not look current.
export const QUOTE_MAX_AGE_MS = 2 * 3600000;
export function matchdayQuote(fixture, now = new Date()) {
  const quote = fixture.quote, captured = Date.parse(quote?.capturedAt);
  if (!quote || !Number.isFinite(captured) || captured > now.getTime() + 300000
    || now.getTime() - captured >= QUOTE_MAX_AGE_MS || Date.parse(fixture.start) <= now.getTime()
    || quote.odds.length !== 2 || !quote.odds.every(p => Number.isFinite(p) && p > 1)) return null;
  return quote;
}

export function matchdayHref(a, b) {
  return '/tennis-matchup?' + new URLSearchParams({ player: a, compare: b, record: 'h2h', history: 'archive' });
}

export function buildTennisMatchday(rows, history, now = new Date(), confirmedProgramme = null) {
  const names = new Map(), ids = new Map(history.players.map((p, i) => [p.id, i]));
  history.players.forEach((p, i) => names.set(identityKey(p.name), [...(names.get(identityKey(p.name)) ?? []), i]));
  const resolve = name => {
    const key = identityKey(name), direct = names.get(key);
    if (direct?.length === 1) return direct[0];
    return Object.hasOwn(aliases, key) ? ids.get(aliases[key]) : undefined;
  };
  const stamps = [...new Set(rows.map(r => r.captured_at).filter(Boolean))];
  const capturedAt = stamps.length === 1 && Number.isFinite(Date.parse(stamps[0])) ? stamps[0] : null;
  const stale = !capturedAt || now.getTime() - Date.parse(capturedAt) > 24 * 3600000 || Date.parse(capturedAt) > now.getTime() + 300000;
  const fixtures = [], excluded = { started: 0, invalid: 0, duplicate: 0 };
  const pairs = new Map(), teamTies = new Map();
  const programme = davisCupProgramme(now, confirmedProgramme);
  for (const row of [...rows, ...programme]) {
    const start = Date.parse(row.kickoff_iso);
    if (!['ATP', 'Challenger'].includes(row.league) || !knownPlayer(row.player1_name) || !knownPlayer(row.player2_name)
      || !mensSinglesEvent(row.league_name) || !Number.isFinite(start)
      || identityKey(row.player1_name) === identityKey(row.player2_name) || (!row.programme && capturedAt && start <= Date.parse(capturedAt))) { excluded.invalid++; continue; }
    if (!row.programme && start <= now.getTime()) { excluded.started++; continue; }
    if (start > now.getTime() + 72 * 3600000) continue;
    const pairKey = [identityKey(row.player1_name), identityKey(row.player2_name)].sort().join('|');
    const eventLabel = normal(row.league_name);
    if (tieMarket.test(eventLabel)) {
      const competition = eventLabel.match(teamCompetition)?.[0];
      if (competition && /\btie\b/.test(eventLabel)) {
        const event = competition.replace(/\b\w/g, c => c.toUpperCase()).replace(/^Atp /, 'ATP ');
        const id = [competition, pairKey, start].join('|');
        const covered = programme.some(r => event === 'Davis Cup' && r.programme.day === row.kickoff_iso.slice(0,10)
          && r.programme.teams.map(nationKey).sort().join('|') === [row.player1_name,row.player2_name].map(nationKey).sort().join('|'));
        if (!covered) teamTies.set(id, { id, event, start: new Date(start).toISOString(), teams: [row.player1_name, row.player2_name] });
      }
      continue;
    }
    // Some team markets omit "Tie Winner". Only named individuals from the player archive
    // or recent singles results can form a player H2H in a team competition.
    if (!row.programme && teamCompetition.test(eventLabel) && ![row.player1_name, row.player2_name].every(name => {
      const key = identityKey(name), recent = history.matchdayRecent;
      return resolve(name) !== undefined || Boolean(recent?.players?.[recent?.aliases?.[key] ?? key]);
    })) { excluded.invalid++; continue; }
    if (!row.programme && /\bdavis cup\b/.test(eventLabel)) {
      const sides = [row.player1_name,row.player2_name].map(identityKey);
      const sameDay = programme.filter(r => r.programme.day === row.kickoff_iso.slice(0,10));
      const overlaps = r => [identityKey(r.player1_name), identityKey(r.player2_name)].filter(n => sides.includes(n)).length;
      if (sameDay.some(r => overlaps(r) === 1) && !sameDay.some(r => overlaps(r) === 2)) continue;
    }
    const prior = pairs.get(pairKey);
    if (row.programme && prior && !prior.ambiguous && !stale && /\bdavis cup\b/.test(normal(prior.event))
        && prior.start.slice(0,10) === row.programme.day) {
      prior.programme = row.programme;
      prior.event = row.league_name;
      continue;
    }
    if (prior && !row.programme) { prior.ambiguous = true; excluded.duplicate++; continue; }
    const a = resolve(row.player1_name), b = resolve(row.player2_name);
    const players = [a, b].map((i, side) => i === undefined ? { id: null, name: side ? row.player2_name : row.player1_name, portrait: null }
      : { id: history.players[i].id, name: history.players[i].name, portrait: history.players[i].portrait });
    for (const [side, player] of players.entries()) {
      const feedName = side ? row.player2_name : row.player1_name;
      player.portrait = resolveTennisPortrait(player.name)?.src ?? resolveTennisPortrait(feedName)?.src ?? safeTennisPortraitSource(player.portrait);
      const recent = history.matchdayRecent;
      const key = identityKey(player.name), profile = recent?.players?.[recent?.aliases?.[key] ?? key];
      const limit = [now.toISOString().slice(0,10), new Date(start).toISOString().slice(0,10), recent?.asOf ?? '0000-00-00'].sort()[0];
      player.recent = profile ? { through: recent.through, matches: profile.matches.filter(m => m.date < limit), name: profile.name, omitted: profile.omitted ?? 0 } : null;
    }
    const cutoff = [now.toISOString().slice(0, 10), new Date(start).toISOString().slice(0, 10), history.asOf].sort()[0];
    const resultOnly = a === undefined || b === undefined;
    const extra = resultOnly ? history.matchdaySupplement?.pairs?.[players.map(p => identityKey(p.name)).sort().join('|')] : null;
    const extraSide = extra?.players?.findIndex(p => identityKey(p.name) === identityKey(players[0].name));
    const extraValid = extra && !extra.quarantined && extra.players.length === 2 && extraSide >= 0
      && identityKey(extra.players[1 - extraSide].name) === identityKey(players[1].name)
      && typeof extra.checkedThrough === 'string' && extra.checkedThrough <= now.toISOString().slice(0, 10);
    const extraCutoff = extraValid ? [now.toISOString().slice(0,10), new Date(start).toISOString().slice(0,10), extra.checkedThrough].sort()[0] : cutoff;
    let meetings = resultOnly ? (extraValid ? extra.matches.filter(m => m.date < extraCutoff)
      .map(m => ({ ...m, winner: extraSide === 0 ? m.winner : 1 - m.winner, odds: [null, null] })) : null) : [...history.matches,...(history.results ?? [])]
      .filter(m => m[0] < cutoff && ((m[1] === a && m[2] === b) || (m[1] === b && m[2] === a)))
      .map(m => ({ date: m[0], winner: (m[3] === 0 ? m[1] : m[2]) === a ? 0 : 1,
        odds: m[1] === a ? [m[4], m[5]] : [m[5], m[4]], surface: m[6], score: m[7], event: m[8], competition: m[9] ?? null, priceBasis: m[10] ?? null }))
      .sort((x, y) => x.date.localeCompare(y.date) || String(x.event).localeCompare(String(y.event)));
    if (resultOnly && meetings) meetings.sort((x, y) => x.date.localeCompare(y.date) || String(x.event).localeCompare(String(y.event)));
    const currentPair = history.matchdayPairs?.[players.map(p=>identityKey(p.name)).sort().join('|')];
    const currentSide = currentPair?.names.indexOf(identityKey(players[0].name));
    const currentValid = currentPair && currentSide >= 0 && currentPair.names[1-currentSide] === identityKey(players[1].name)
      && currentPair.checkedThrough <= now.toISOString().slice(0,10);
    if (currentValid) meetings = currentPair.matches.filter(m=>m.date < [now.toISOString().slice(0,10),new Date(start).toISOString().slice(0,10),currentPair.checkedThrough].sort()[0])
      .map(m=>({...m,winner:currentSide===0?m.winner:1-m.winner,odds:currentSide===0?m.odds:[...m.odds].reverse()}))
      .sort((a,b)=>a.date.localeCompare(b.date)||String(a.event).localeCompare(String(b.event)));
    const wins = meetings ? [meetings.filter(m => m.winner === 0).length, meetings.filter(m => m.winner === 1).length] : null;
    const priced = meetings?.filter(m => m.odds.every(p => Number.isFinite(p) && p > 1)) ?? [];
    const profit = [0, 1].map(side => priced.reduce((sum, m) => sum + (m.winner === side ? m.odds[side] - 1 : -1), 0));
    const fixture = { id: `${row.league}:${pairKey}`, start: new Date(start).toISOString(), tour: row.league,
      event: row.league_name.replace(/^ATP\s+Challenger\s+|^ATP\s+/i, ''), qualifying: /qualifying|qualification|\bqual\b/i.test(row.league_name),
      resultsOnly: Boolean(resultOnly && extraValid), coverageThrough: currentValid ? currentPair.checkedThrough : extraValid ? extra.checkedThrough : history.asOf,
      h2hStatus: meetings ? (meetings.length ? 'meetings' : 'none') : players.every(p => p.recent) ? 'unchecked' : 'unlinked',
      players, wins, meetings: meetings?.length ?? null, priced: priced.length,
      roi: profit.map(p => priced.length ? Math.round(1000 * p / priced.length) / 10 : null),
      profit: profit.map(p => Math.round(p * 1000) / 1000), history: meetings?.slice().reverse() ?? [],
      quote: capturedAt && [row.odds1, row.odds2].every(p => p !== null && p !== '' && Number.isFinite(Number(p)) && Number(p) > 1)
        ? { capturedAt, bookmaker: 'Pinnacle', odds: [Number(row.odds1), Number(row.odds2)] } : null,
      href: a !== undefined && b !== undefined ? matchdayHref(players[0].id, players[1].id) : null, ambiguous: false };
    if (row.programme) {
      fixture.programme = row.programme;
      fixture.id = 'programme:' + row.programme.day + ':' + pairKey;
    }
    pairs.set(pairKey, fixture); fixtures.push(fixture);
  }
  return { capturedAt, results: history.matchdayResults ?? null, contextVersion: history.contextVersion ?? null, resultsThrough: history.matchdayRecent?.through ?? null, resultsUpdatedAt: history.resultsUpdatedAt ?? null, historyThrough: history.through, historyVersion: history.version, stale, excluded,
    teamTies: stale ? [] : [...teamTies.values()].sort((a, b) => a.start.localeCompare(b.start)),
    fixtures: fixtures.filter(f => !f.ambiguous && (!stale || f.programme)).sort((a, b) => a.start.localeCompare(b.start) || (a.programme?.order ?? 0) - (b.programme?.order ?? 0) || a.event.localeCompare(b.event)) };
}

export function teamTiesFor(ties, filter, tour, search, now, zone = 'Europe/London') {
  if (tour !== 'all' && tour !== 'ATP') return [];
  const today = day(now, zone);
  const tomorrow = new Date(Date.parse(today + 'T12:00:00Z') + 86400000).toISOString().slice(0,10);
  return ties.filter(t => Date.parse(t.start) > now.getTime()
    && (filter === 'upcoming' || day(new Date(t.start), zone) === (filter === 'today' ? today : tomorrow))
    && normal([t.event, ...t.teams].join(' ')).includes(normal(search)));
}

export function fixturesFor(fixtures, filter, tour, search, now, zone = 'Europe/London') {
  const today = day(now, zone);
  // Calendar tomorrow, including the 25-hour day when British Summer Time ends.
  const tomorrow = new Date(Date.parse(`${today}T12:00:00Z`) + 24 * 3600000).toISOString().slice(0, 10);
  return fixtures.filter(f => (f.programme ? f.programme.day >= today : Date.parse(f.start) > now.getTime()) && (tour === 'all' || f.tour === tour)
    && (filter === 'upcoming' || day(new Date(f.start), zone) === (filter === 'today' ? today : tomorrow))
    && `${[normal(f.event), normal(f.programme?.tie), ...f.players.map(p => searchNames(p.name))].filter(Boolean).join(' ')}`.includes(normal(search)));
}
