export type Side = 'team' | 'draw' | 'opponent';
export type Role = 'all' | 'favourite' | 'underdog';
export type Fixture = {
    id: string;
    league: string;
    season: string;
    date: string;
    home: string;
    away: string;
    hg: number;
    ag: number;
    odds: [
        number,
        number,
        number
    ] | null;
    basis: string | null;
};
export type Filters = {
    league: string;
    season: string;
    year: string;
    venue: string;
    role: Role;
    side: Side;
    min: number;
    max: number;
    upperExclusive: boolean;
};
export type Observation = Fixture & {
    team: string;
    opponent: string;
    venue: string;
    role: string;
    teamOdds: number;
    price: number;
    won: boolean;
    profit: number;
    result: 'W' | 'D' | 'L';
};
export const defaults: Filters = { league: 'all', season: 'all', year: 'all', venue: 'all', role: 'all', side: 'team', min: 1, max: Infinity, upperExclusive: false };
export const leagues: Record<string, string> = { 'premier-league': 'Premier League', 'serie-a': 'Serie A', 'la-liga': 'La Liga', bundesliga: 'Bundesliga', 'ligue-1': 'Ligue 1' };
export const bands = [1, 1.2, 1.5, 1.8, 2, 2.2, 2.5, 3, 3.5, 4, 5, 6, 8, 10, Infinity].slice(0, -1).map((min, i, values) => ({ min, max: values[i + 1] ?? Infinity, label: i === 0 ? 'Below 1.20' : min === 10 ? '10.00+' : `${min.toFixed(2)}–${values[i + 1].toFixed(2)}` }));
const indexes = new WeakMap<Fixture[], Map<string, Fixture[]>>();
const latestSeasons = new WeakMap<Fixture[], string>();
/** Recent windows share the archive's season anchor, never each club's last appearance. */
export function latestSeason(fixtures: Fixture[]) {
    if (!latestSeasons.has(fixtures)) latestSeasons.set(fixtures, fixtures.reduce((latest, m) => m.season > latest ? m.season : latest, ''));
    return latestSeasons.get(fixtures)!;
}
export function seasonMatches(season: string, selection: string, latest: string): boolean {
    if (selection === 'all') return true;
    if (selection.startsWith('latest:')) {
        const count = Number(selection.slice(7)), year = Number(season.slice(0, 4)), end = Number(latest.slice(0, 4));
        return Number.isInteger(count) && count > 0 && year <= end && year > end - count;
    }
    if (selection.startsWith('range:')) {
        const [, from, to] = selection.split(':');
        return !!from && !!to && season >= from && season <= to;
    }
    return season === selection;
}
export function teamFixtures(fixtures: Fixture[], team: string) {
    if (!indexes.has(fixtures)) {
        const index = new Map<string, Fixture[]>();
        for (const match of fixtures)
            for (const name of new Set([match.home, match.away])) {
                if (!index.has(name))
                    index.set(name, []);
                index.get(name)!.push(match);
            }
        indexes.set(fixtures, index);
    }
    return indexes.get(fixtures)!.get(team) ?? [];
}
export function eligible(fixtures: Fixture[], team: string, f: Filters): Fixture[] {
    const seen = new Set<string>();
    const latest = latestSeason(fixtures);
    return teamFixtures(fixtures, team).filter(m => {
        if (seen.has(m.id))
            return false;
        seen.add(m.id);
        return Number.isInteger(m.hg) && Number.isInteger(m.ag) && m.hg >= 0 && m.ag >= 0 &&
            (f.league === 'all' || m.league === f.league) && seasonMatches(m.season, f.season, latest) &&
            (f.year === 'all' || m.date.startsWith(f.year)) && (f.venue === 'all' || (m.home === team ? 'home' : 'away') === f.venue);
    });
}
export function hasPrices(m: Fixture): boolean { return !!m.odds && m.odds.length === 3 && m.odds.every(p => Number.isFinite(p) && p > 1); }
export function observations(fixtures: Fixture[], team: string, f: Filters): Observation[] {
    if (!Number.isFinite(f.min) || f.min < 1 || Number.isNaN(f.max) || f.max < f.min)
        return [];
    return eligible(fixtures, team, f).filter(hasPrices).map(m => {
        const home = m.home === team, [h, d, a] = m.odds!;
        const teamOdds = home ? h : a, other = home ? a : h, role = teamOdds < other ? 'favourite' : teamOdds > other ? 'underdog' : 'level';
        const result: Observation['result'] = m.hg === m.ag ? 'D' : (home ? m.hg > m.ag : m.ag > m.hg) ? 'W' : 'L';
        const price = f.side === 'draw' ? d : f.side === 'opponent' ? other : teamOdds;
        const won = result === (f.side === 'draw' ? 'D' : f.side === 'opponent' ? 'L' : 'W');
        return { ...m, team, opponent: home ? m.away : m.home, venue: home ? 'home' : 'away', role, teamOdds, price, won, profit: won ? price - 1 : -1, result };
    }).filter(m => (f.role === 'all' || m.role === f.role) && m.teamOdds >= f.min && (f.upperExclusive ? m.teamOdds < f.max : m.teamOdds <= f.max))
        .sort((a, b) => a.date.localeCompare(b.date) || a.id.localeCompare(b.id));
}
export function summary(rows: Observation[]) {
    let profit = 0, peak = 0, drawdown = 0, wins = 0, largestWin = 0;
    const results = { W: 0, D: 0, L: 0 };
    const curve = [0];
    for (const row of rows) {
        profit += row.profit;
        peak = Math.max(peak, profit);
        drawdown = Math.max(drawdown, peak - profit);
        if (row.won)
            wins++;
        largestWin = Math.max(largestWin, row.profit);
        results[row.result]++;
        curve.push(profit);
    }
    return { bets: rows.length, profit, roi: rows.length ? 100 * profit / rows.length : 0, wins, losses: rows.length - wins, drawdown, largestWin, results, curve };
}
/** Team leaderboard rows overlap: only use this to aggregate a fixture portfolio. */
export function uniqueDrawPortfolio(rows: Observation[]) { const seen = new Set<string>(); return rows.filter(r => { if (seen.has(r.id))
    return false; seen.add(r.id); return true; }); }
