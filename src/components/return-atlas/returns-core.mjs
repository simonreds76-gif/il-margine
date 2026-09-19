// Pure historical-return calculations shared by all three previews.
export function normalise(value) {
  return String(value).normalize('NFKD').replace(/\p{M}/gu, '').replace(/ø/gi, 'o').toLowerCase();
}

// Highlights describe today's player pool, even when viewing an older season.
// This activity rule does not rewrite or remove anyone's historical results.
export function recentlyActivePlayers(matches, players, asOf) {
  const cutoff = new Date(asOf + 'T12:00:00Z');
  cutoff.setUTCFullYear(cutoff.getUTCFullYear() - 1);
  const from = cutoff.toISOString().slice(0, 10);
  const active = new Set(matches.filter(m => m.date >= from && m.date <= asOf).flatMap(m => [m.p1, m.p2]));
  // ATP confirmed Thiem's retirement in October 2024. Never feature exhibition returns.
  const retired = new Set(['dominic thiem']);
  return players.filter(p => active.has(p.id) && !retired.has(normalise(p.name)));
}

const playerIndexes=new WeakMap();
function playerMatches(matches,id){
 if(!playerIndexes.has(matches)){const index=new Map();for(const m of matches)for(const p of new Set([m.p1,m.p2])){if(!index.has(p))index.set(p,[]);index.get(p).push(m);}playerIndexes.set(matches,index);}
 return playerIndexes.get(matches).get(id)||[];
}
export function observations(matches, playerId, filters = {}) {
  const { year = 'all', surface = 'all', role = 'all', side = 'player', priceSeries = 'all' } = filters;
  const seen = new Set();
  return playerMatches(matches,playerId).filter(match => {
    if (seen.has(match.id)) return false;
    seen.add(match.id);
    return (priceSeries!=='last-pre-match'||match.source==='Valuebetennis') && match.status === 'completed' && match.level === 'ATP-main' &&
      [match.p1, match.p2].includes(playerId) && [match.p1, match.p2].includes(match.winner) &&
      [match.o1, match.o2].every(price => Number.isFinite(price) && price > 1) &&
      (year === 'all' || match.date.startsWith(String(year))) &&
      (surface === 'all' || match.surface === surface);
  }).map(match => {
    const isFirst = match.p1 === playerId;
    const playerOdds = isFirst ? match.o1 : match.o2;
    const opponentOdds = isFirst ? match.o2 : match.o1;
    const opponent = isFirst ? match.p2 : match.p1;
    const playerRole = playerOdds < opponentOdds ? 'favourite' : playerOdds > opponentOdds ? 'underdog' : 'level';
    const backedId = side === 'opponent' ? opponent : playerId;
    const odds = side === 'opponent' ? opponentOdds : playerOdds;
    const won = match.winner === backedId;
    return { ...match, playerId, opponent, playerRole, odds, won, profit: won ? odds - 1 : -1 };
  }).filter(row => role === 'all' || row.playerRole === role)
    .sort((a, b) => a.date.localeCompare(b.date) || a.id.localeCompare(b.id));
}

export function summarise(rows) {
  const bets = rows.length;
  const wins = rows.filter(row => row.won).length;
  const profit = rows.reduce((sum, row) => sum + row.profit, 0);
  const prices = rows.map(row => row.odds).sort((a, b) => a - b);
  let running = 0, peak = 0, drawdown = 0;
  const curve = [0, ...rows.map(row => {
    running += row.profit; peak = Math.max(peak, running);
    drawdown = Math.max(drawdown, peak - running); return running;
  })];
  const median = !bets ? null : bets % 2 ? prices[(bets - 1) / 2] : (prices[bets / 2 - 1] + prices[bets / 2]) / 2;
  return { bets, wins, losses: bets - wins, profit, roi: bets ? profit / bets * 100 : null,
    winRate: bets ? wins / bets * 100 : null, median, drawdown, curve };
}

export function leaderboard(matches, players, filters = {}) {
  const query = normalise(filters.search || '');
  const result = players.filter(player => normalise(player.name).includes(query)).map(player => {
    const rows = observations(matches, player.id, filters);
    return { ...player, rows, ...summarise(rows) };
  }).filter(row => row.bets > 0 && row.bets >= Number(filters.minimum ?? 30));
  const sort = filters.sort || 'roi', direction = filters.direction === 'asc' ? 1 : -1;
  return result.sort((a, b) => {
    const primary = sort === 'name' ? a.name.localeCompare(b.name) : a[sort] - b[sort];
    return primary * direction || b.bets - a.bets || a.name.localeCompare(b.name);
  });
}
