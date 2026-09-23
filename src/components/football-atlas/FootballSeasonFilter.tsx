'use client';
import { seasonMatches, type Filters } from './football-core';
const short = (s: string) => `${s.slice(0, 4)}/${s.slice(-2)}`;
export default function FootballSeasonFilter({ seasons, filters, onChange }: {
    seasons: string[]; filters: Filters; onChange: (filters: Filters) => void;
}) {
    const ordered = seasons.slice().sort(), latest = ordered.at(-1)!;
    const custom = filters.season.startsWith('range:');
    const [, from, to] = filters.season.split(':');
    const included = ordered.filter(s => seasonMatches(s, filters.season, latest));
    const set = (season: string) => onChange({ ...filters, season, year: 'all' });
    return <div className="fa-season-control"><label>Season<select aria-label="Season" value={custom ? 'custom' : filters.season} onChange={e => set(e.target.value === 'custom' ? `range:${ordered.at(-3) ?? ordered[0]}:${latest}` : e.target.value)}>
        <option value="all">All seasons</option><optgroup label="Recent seasons combined">{[2, 3, 5].map(n => <option key={n} value={`latest:${n}`}>Latest {n} seasons</option>)}<option value="custom">Custom season range</option></optgroup>
        <optgroup label="Individual season">{ordered.slice().reverse().map(s => <option key={s} value={s}>{short(s)}</option>)}</optgroup>
    </select></label>
        {custom && <div className="fa-season-range"><label>From<select aria-label="From season" value={from} onChange={e => set(`range:${e.target.value}:${e.target.value > to ? e.target.value : to}`)}>{ordered.map(s => <option key={s} value={s}>{short(s)}</option>)}</select></label><label>To<select aria-label="To season" value={to} onChange={e => set(`range:${e.target.value < from ? e.target.value : from}:${e.target.value}`)}>{ordered.map(s => <option key={s} value={s}>{short(s)}</option>)}</select></label></div>}
        {(custom || filters.season.startsWith('latest:')) && <p className="fa-period-caption">{included.length ? `${short(included[0])}–${short(included.at(-1)!)}` : 'No seasons in this archive'}{included.includes(latest) ? ' · latest season to date' : ''}</p>}
    </div>;
}
