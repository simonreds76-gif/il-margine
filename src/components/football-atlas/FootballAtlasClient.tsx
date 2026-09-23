'use client';
import { useEffect, useMemo, useRef, useState } from 'react';
import Icon from './FootballAtlasIcon';
import Chart from './FootballProfitChart';
import FootballSeasonFilter from './FootballSeasonFilter';
import { FootballAtlasLegend } from './FootballAtlasGuide';
import { bands, defaults, eligible, seasonMatches, hasPrices, leagues, observations, summary, type Fixture, type Filters, type Side, type Role } from './football-core';
type Archive = {
    fixtures: Fixture[];
    teams: string[];
    crests: Record<string, string | null>;
    seasons: string[];
};
type Packed = {
    fixtures: [
        string,
        string,
        number,
        number,
        number,
        number,
        number,
        number,
        number | null,
        number | null,
        number | null,
        number
    ][];
    teams: string[];
    crests: Record<string, string | null>;
    seasons: string[];
    leagues: string[];
};
type Ranking = ReturnType<typeof summary> & {
    team: string;
    eligible: number;
    priced: number;
};
const signed = (n: number, d = 1) => (n > 0 ? '+' : '') + n.toFixed(d);
const cls = (n: number) => n < 0 ? 'fa-negative' : 'fa-positive';
const fmt = (n: number) => n.toLocaleString('en-GB');
const priceText = (n: number) => n.toLocaleString('en-GB', { minimumFractionDigits: 2, maximumFractionDigits: 6 });
const shortSeason = (s: string) => s.slice(0, 4) + '/' + s.slice(-2);
const sideLabel: Record<Side, string> = { team: 'Back team', draw: 'Back draw', opponent: 'Back opponent' };
function LeagueMark({id}:{id:string}) {
    // eslint-disable-next-line @next/next/no-img-element
    return <img src={`/league-logos/${id==='premier-league'?'epl':id}.png`} alt="" width="28" height="28" />;
}
function Crest({ team, crests }: {
    team: string;
    crests: Archive['crests'];
}) {
    const [failed, setFailed] = useState(false);
    return <span className="fa-crest">{crests[team] && !failed ?
            // Local, already optimised crest assets; avoid a runtime image transformation per historical club.
            // eslint-disable-next-line @next/next/no-img-element
            <img src={crests[team]!} alt="" width="36" height="36" loading="lazy" onError={() => setFailed(true)}/> : <svg viewBox="0 0 40 44" aria-hidden="true"><path d="M4 3h32v24c0 6-8 11-16 15C12 38 4 33 4 27Z" fill="#17382f" stroke="#57d196"/><text x="20" y="26" textAnchor="middle" fill="#fff" fontSize="14">{team.slice(0, 2).toUpperCase()}</text></svg>}</span>;
}
function Choices({ filters, onChange }: {
    filters: Filters;
    onChange: (next: Filters) => void;
}) {
    return <><p className="fa-control-label">Choose what you back</p><div className="fa-choices" role="group" aria-label="Bet selection">{(['team', 'draw', 'opponent'] as Side[]).map(side => <button key={side} className={'fa-choice ' + (filters.side === side ? 'selected' : '')} aria-pressed={filters.side === side} onClick={() => onChange({ ...filters, side })}><Icon name={side}/><span>{sideLabel[side]}<small>{side === 'team' ? 'Team wins · draw loses' : side === 'draw' ? 'Level after 90 minutes' : 'Opponent wins · draw loses'}</small></span><span className="fa-selection-check" aria-hidden="true">{filters.side === side ? '✓' : ''}</span></button>)}</div>
 <p className="fa-control-label">When the named club was…</p><div className="fa-role" role="group" aria-label="Named team market role">{(['all', 'favourite', 'underdog'] as Role[]).map(role => <button key={role} aria-label={role === 'all' ? 'All matches' : role === 'favourite' ? 'As favourite' : 'As underdog'} aria-pressed={filters.role === role} className={filters.role === role ? 'selected' : ''} onClick={() => onChange({ ...filters, role })}><Icon name={role}/><span>{role === 'all' ? 'All matches' : role === 'favourite' ? 'As favourite' : 'As underdog'}<small>{role === 'all' ? 'Any market position' : role === 'favourite' ? 'Shorter price than opponent' : 'Longer price than opponent'}</small></span></button>)}</div></>;
}
function OddsFilter({ filters, onChange }: {
    filters: Filters;
    onChange: (next: Filters) => void;
}) {
    const root = useRef<HTMLDetailsElement>(null);
    const [min, setMin] = useState(''), [max, setMax] = useState(''), [error, setError] = useState('');
    const preset = bands.find(b => b.min === filters.min && b.max === filters.max && filters.upperExclusive);
    const label = preset?.label ?? (filters.min === 1 && filters.max === Infinity ? 'Any odds' : `${filters.min === 1 ? 'Any' : filters.min} – ${filters.max === Infinity ? 'Any' : filters.max}`);
    return <details className="fa-odds" ref={root}><summary><span>Named team odds</span><strong>{label}</strong><span aria-hidden="true">⌄</span></summary><div className="fa-odds-pop"><p>Filter by the named team’s win price, whichever bet you select.</p><div className="fa-band-grid"><button aria-pressed={filters.min === 1 && filters.max === Infinity && !filters.upperExclusive} onClick={() => { onChange({ ...filters, min: 1, max: Infinity, upperExclusive: false }); root.current!.open = false; }}>Any odds</button>{bands.map(b => <button key={b.min} aria-pressed={preset === b} onClick={() => { onChange({ ...filters, min: b.min, max: b.max, upperExclusive: true }); root.current!.open = false; }}>{b.label}</button>)}</div><form onSubmit={e => { e.preventDefault(); const lo = min === '' ? 1 : Number(min), hi = max === '' ? Infinity : Number(max); if (!Number.isFinite(lo) || lo < 1 || (min !== '' && lo <= 1) || Number.isNaN(hi) || (max !== '' && !Number.isFinite(hi)) || hi <= 1 || hi < lo) {
        setError('Enter decimal odds above 1.00, with maximum at least the minimum.');
        return;
    } setError(''); onChange({ ...filters, min: lo, max: hi, upperExclusive: false }); root.current!.open = false; }}><label>From<input value={min} onChange={e => setMin(e.target.value)} type="number" min="1.01" step="any" placeholder="Any"/></label><label>To<input value={max} onChange={e => setMax(e.target.value)} type="number" min="1.01" step="any" placeholder="Any"/></label><button>Apply</button></form>{error && <p role="alert">{error}</p>}<small>Preset upper limits belong to the next band. Custom limits are inclusive.</small></div></details>;
}
function Stat({ label, value, note, number }: {
    label: string;
    value: string;
    note?: string;
    number?: number;
}) { return <div className="fa-stat"><span>{label}</span><strong className={number === undefined ? '' : cls(number)}>{value}</strong>{note && <small>{note}</small>}</div>; }
function TeamDetail({ team, data, initial, onClose }: {
    team: string;
    data: Archive;
    initial: Filters;
    onClose: () => void;
}) {
    const dialog = useRef<HTMLDialogElement>(null);
    const [filters, setFilters] = useState(initial), [limit, setLimit] = useState(25);
    const rows = observations(data.fixtures, team, filters), stats = summary(rows);
    const base = eligible(data.fixtures, team, filters), priced = base.filter(hasPrices).length;
    useEffect(() => { const d = dialog.current!; d.showModal(); const old = document.body.style.overflow; document.body.style.overflow = 'hidden'; return () => { document.body.style.overflow = old; }; }, []);
    const update = (f: Filters) => { setFilters(f); setLimit(25); };
    return <dialog aria-label={`${team} club record`} className="fa-dialog" ref={dialog} onCancel={onClose} onClick={e => { if (e.target === e.currentTarget)
        onClose(); }}><div className="fa-dialog-inner"><header className="fa-detail-heading"><div className="fa-club"><Crest team={team} crests={data.crests}/><div><p className="fa-eyebrow">Club record</p><h2>{team}</h2></div></div><button className="fa-close" onClick={onClose} aria-label="Close club record">Close ×</button></header>
 <Choices filters={filters} onChange={update}/><div className="fa-filters"><FootballSeasonFilter seasons={data.seasons} filters={filters} onChange={update}/><label>Venue<select aria-label="Venue" value={filters.venue} onChange={e => update({ ...filters, venue: e.target.value })}><option value="all">Home & away</option><option value="home">Home</option><option value="away">Away</option></select></label><OddsFilter filters={filters} onChange={update}/></div>
 <p className="fa-filter-note">{sideLabel[filters.side]} · Role and odds range describe {team}. {priced} of {base.length} archived matches have usable prices before role and odds filters.{filters.year !== 'all' ? ` Calendar year ${filters.year}.` : ''}</p>
 <div className="fa-stats"><Stat label="Return on stakes" value={stats.bets ? `${signed(stats.roi)}%` : '—'} number={stats.roi}/><Stat label="Net profit" value={`${signed(stats.profit)}u`} number={stats.profit} note={`${stats.bets} bets at 1u`}/><Stat label="Bets won / lost" value={`${stats.wins} / ${stats.losses}`} note={`Team results: ${stats.results.W}W ${stats.results.D}D ${stats.results.L}L`}/><Stat label="Largest drawdown" value={`${stats.drawdown.toFixed(1)}u`} note="Peak to subsequent low"/></div>
 <FootballAtlasLegend/><Chart rows={rows}/><div className="fa-breakdowns"><section><h3>By season</h3><div className="fa-table-wrap"><table><thead><tr><th>Season</th><th>Bets</th><th>Profit</th><th>ROI</th></tr></thead><tbody>{[...new Set(rows.map(r => r.season))].reverse().map(s => { const a = summary(rows.filter(r => r.season === s)); return <tr key={s}><td><button onClick={() => update({ ...filters, season: s })}>{shortSeason(s)}</button></td><td>{a.bets}</td><td className={cls(a.profit)}>{signed(a.profit)}u</td><td className={cls(a.roi)}>{signed(a.roi)}%</td></tr>; })}</tbody></table></div></section><section><h3>Compare named team odds</h3><p className="fa-filter-note">Same season, venue and role. Select a band to inspect it.</p><div className="fa-table-wrap"><table><thead><tr><th>Odds</th><th>Bets</th><th>Profit</th><th>ROI</th></tr></thead><tbody>{bands.map(b => { const a = summary(observations(data.fixtures, team, { ...filters, min: b.min, max: b.max, upperExclusive: true })); return <tr key={b.min}><td><button onClick={() => update({ ...filters, min: b.min, max: b.max, upperExclusive: true })}>{b.label}</button></td><td>{a.bets}</td><td className={cls(a.profit)}>{a.bets ? `${signed(a.profit)}u` : '—'}</td><td className={cls(a.roi)}>{a.bets ? `${signed(a.roi)}%` : '—'}</td></tr>; })}</tbody></table></div></section></div>
 <section className="fa-ledger"><h3>The matches behind the return</h3><p className="fa-filter-note">90-minute results. {sideLabel[filters.side]}. Largest winning bet: {signed(stats.largestWin)}u.</p><div className="fa-table-wrap"><table className="fa-match-table"><thead><tr><th>Date / fixture</th><th>Team role</th><th>Team odds</th><th>Selection backed</th><th>Price</th><th>Profit</th></tr></thead><tbody>{rows.slice().reverse().slice(0, limit).map(r => <tr key={r.id}><td className="fa-match-fixture"><small>{r.date} · {shortSeason(r.season)}</small><strong>{r.home} {r.hg}–{r.ag} {r.away}</strong></td><td className="fa-match-role"><span className="fa-cell-label">Team role</span><span className="fa-role-badge">{r.role === 'level' ? 'Equal prices' : r.role}</span></td><td className="fa-match-team-price"><span className="fa-cell-label">Team odds</span>{priceText(r.teamOdds)}</td><td className="fa-match-selection"><span className="fa-cell-label">Selection backed</span>{filters.side === 'draw' ? 'Draw' : filters.side === 'opponent' ? r.opponent : team}</td><td className="fa-match-price"><span className="fa-cell-label">Backed price</span>{priceText(r.price)}<small>{r.basis === 'closing' ? 'Closing' : 'Last pre-match'}</small></td><td className={`fa-match-profit ${cls(r.profit)}`}><span className="fa-cell-label">Net profit</span>{signed(r.profit, 2)}u<small>{r.won ? 'Won' : 'Lost'}</small></td></tr>)}</tbody></table></div>{rows.length > limit && <button className="fa-more" onClick={() => setLimit(limit + 25)}>Show 25 more matches ({rows.length - limit} remaining)</button>}</section>
 <p className="fa-filter-note">Historical results, not a forecast. Draw returns for this club overlap with its opponents’ records; team rows are not independent portfolios.</p></div></dialog>;
}
export default function FootballAtlasClient({ indexUrl }: {
    indexUrl: string;
}) {
    const [data, setData] = useState<Archive | null>(null), [error, setError] = useState(''), [attempt, setAttempt] = useState(0), [filters, setFilters] = useState(defaults), [search, setSearch] = useState(''), [minimum, setMinimum] = useState(30), [sort, setSort] = useState('roi'), [selected, setSelected] = useState<string | null>(null), [limit, setLimit] = useState(30);
    useEffect(() => { const controller = new AbortController(); const timer = setTimeout(() => controller.abort(), 20000); fetch(indexUrl, { signal: controller.signal }).then(r => { if (!r.ok)
        throw Error('Archive unavailable'); return r.json(); }).then((p: Packed) => { const fixtures: Fixture[] = p.fixtures.map(r => ({ id: r[0], date: r[1], league: p.leagues[r[2]], season: p.seasons[r[3]], home: p.teams[r[4]], away: p.teams[r[5]], hg: r[6], ag: r[7], odds: r[8] === null ? null : [r[8], r[9]!, r[10]!], basis: r[11] === 1 ? 'closing' : r[11] === 2 ? 'last-pre-match' : null })); setData({ fixtures, teams: p.teams, crests: p.crests, seasons: p.seasons }); setError(''); }).catch(() => { if (!controller.signal.aborted)
        setError('The archive could not be loaded. Please retry.');
    else
        setError('The archive took too long to load. Please retry.'); }).finally(() => clearTimeout(timer)); return () => { clearTimeout(timer); controller.abort(); }; }, [indexUrl, attempt]);
    const ranks = useMemo(() => { if (!data)
        return []; return data.teams.map(team => { const base = eligible(data.fixtures, team, filters); return { team, ...summary(observations(data.fixtures, team, filters)), eligible: base.length, priced: base.filter(hasPrices).length }; }).filter(r => r.bets >= Math.max(1, minimum)); }, [data, filters, minimum]);
    const visible = useMemo(() => ranks.filter(r => r.team.normalize('NFKD').replace(/\p{M}/gu, '').toLowerCase().includes(search.normalize('NFKD').replace(/\p{M}/gu, '').toLowerCase())).sort((a, b) => sort === 'name' ? a.team.localeCompare(b.team) : sort === 'profit' ? b.profit - a.profit || b.bets - a.bets : sort === 'bets' ? b.bets - a.bets : sort === 'worst' ? a.roi - b.roi : b.roi - a.roi || b.bets - a.bets), [ranks, search, sort]);
    const leaders = useMemo(() => { if (!data)
        return []; return (['all', 'favourite', 'underdog'] as Role[]).map(role => { const active = new Set(data.fixtures.filter(m => m.season === data.seasons.at(-1)).flatMap(m => [m.home, m.away])); const records = data.teams.filter(team => active.has(team)).map(team => ({ team, ...summary(observations(data.fixtures, team, { ...filters, role })) })).filter(r => r.bets >= Math.max(30, minimum)); records.sort((a, b) => b.roi - a.roi || b.bets - a.bets); return { role, best: records[0] }; }); }, [data, filters, minimum]);
    const update = (next: Filters) => { setFilters(next); setLimit(30); };
    if (!data)
        return <section className="fa-panel fa-loading" aria-live="polite">{error ? <><p>{error}</p><button onClick={() => { setError(''); setAttempt(attempt + 1); }}>Retry archive</button></> : <p>Loading the football archive…</p>}</section>;
    const seasonFixtures = data.fixtures.filter(m => (filters.league === 'all' || m.league === filters.league) && seasonMatches(m.season, filters.season, data.seasons.at(-1)!) && (filters.year === 'all' || m.date.startsWith(filters.year)));
    const seasonPriced = seasonFixtures.filter(hasPrices).length;
    return <><section className="fa-panel" aria-label="Explore football returns"><div className="fa-leagues" role="group" aria-label="League"><button className={filters.league === 'all' ? 'selected' : ''} aria-pressed={filters.league === 'all'} onClick={() => update({ ...filters, league: 'all' })}><Icon name="all"/><span>All five leagues</span></button>{Object.entries(leagues).map(([id, name]) => <button key={id} className={filters.league === id ? 'selected' : ''} aria-pressed={filters.league === id} onClick={() => update({ ...filters, league: id })}><LeagueMark id={id}/><span>{name}</span></button>)}</div>
 <Choices filters={filters} onChange={update}/><div className="fa-filters"><FootballSeasonFilter seasons={data.seasons} filters={filters} onChange={update}/><label>Venue<select aria-label="Venue" value={filters.venue} onChange={e => update({ ...filters, venue: e.target.value })}><option value="all">Home & away</option><option value="home">Home</option><option value="away">Away</option></select></label><OddsFilter filters={filters} onChange={update}/><label>Minimum matches<select aria-label="Minimum matches" value={minimum} onChange={e => { setMinimum(Number(e.target.value)); setLimit(30); }}>{[1, 10, 30, 50, 100, 200].map(n => <option key={n} value={n}>{n}+ matches</option>)}</select></label></div>
 <button className="fa-reset" onClick={() => { update(defaults); setSearch(''); setMinimum(30); setSort('roi'); }}>Reset filters</button><p className="fa-filter-note">Favourite / underdog and odds ranges always describe the named team. {filters.side === 'draw' ? 'Backing the draw wins only when the score is level.' : 'A draw loses a team-win bet.'}</p>
 <details className="fa-calendar"><summary>Filter by calendar year instead</summary><label>Calendar year<select aria-label="Calendar year" value={filters.year} onChange={e => update({ ...filters, year: e.target.value, season: 'all' })}><option value="all">All years</option>{[...new Set(data.fixtures.map(m => m.date.slice(0, 4)))].reverse().map(y => <option key={y}>{y}</option>)}</select></label></details></section>
 <section className="fa-highlights" aria-label="Historical return leaders">{leaders.filter(item => !!item.best).map(({ role, best }) => <button key={role} className="fa-leader" disabled={!best} onClick={() => { if (best) {
        update({ ...filters, role });
        setSelected(best.team);
    } }}><span className="fa-eyebrow">{role === 'all' ? 'All matches' : role === 'favourite' ? 'As favourite' : 'As underdog'} · {sideLabel[filters.side]}</span>{best ? <><span className="fa-club"><Crest team={best.team} crests={data.crests}/><strong>{best.team}</strong><span aria-hidden="true">↗</span></span><span className={'fa-leader-roi ' + cls(best.roi)}>{signed(best.roi)}% <small>ROI</small></span><span>{fmt(best.bets)} bets · {signed(best.profit)}u</span></> : <span>No clubs reach {Math.max(30, minimum)} matches</span>}</button>)}</section>
 <section className="fa-records"><header><div><p className="fa-eyebrow">Find the record behind the reputation</p><h2>Explore club returns</h2></div><p>{fmt(seasonPriced)} / {fmt(seasonFixtures.length)} archived fixtures with prices<br /><small>Before venue, role and odds filters · unique fixtures</small></p></header><div className="fa-search-row"><label>Find a club<input type="search" placeholder="Search Arsenal, Napoli, Marseille…" value={search} onChange={e => { setSearch(e.target.value); setLimit(30); }}/></label><label>Sort by<select aria-label="Sort by" value={sort} onChange={e => { setSort(e.target.value); setLimit(30); }}><option value="roi">Highest ROI</option><option value="worst">Lowest ROI</option><option value="profit">Highest profit</option><option value="bets">Most matches</option><option value="name">Club name</option></select></label></div>
 <p className="fa-filter-note" aria-live="polite">{visible.length} clubs · {sideLabel[filters.side]} · {filters.role === 'all' ? 'All roles' : filters.role} · {minimum}+ matches. Highlights feature current top-flight clubs with at least {Math.max(30, minimum)} matches.</p>
 <FootballAtlasLegend/><div className="fa-table-wrap fa-ranking-wrap"><table className="fa-ranking" aria-label="Club betting returns"><thead><tr><th><button onClick={() => setSort('name')}>Club ↕</button></th><th><button onClick={() => setSort(sort === 'roi' ? 'worst' : 'roi')}>ROI {sort === 'worst' ? '↑' : '↓'}</button></th><th><button onClick={() => setSort('profit')}>Net profit ↓</button></th><th><button onClick={() => setSort('bets')}>Bets ↓</button></th><th>Record & coverage</th></tr></thead><tbody>{visible.slice(0, limit).map((r: Ranking, rank) => <tr key={r.team}>
  <td className="fa-rank-club"><button className="fa-club" onClick={() => setSelected(r.team)}><span className="fa-rank">{rank + 1}</span><Crest team={r.team} crests={data.crests}/><span className="fa-club-name"><strong>{r.team}</strong><small>Open club record <span aria-hidden="true">↗</span></small></span></button></td>
  <td className={`fa-rank-roi ${cls(r.roi)}`}><span className="fa-cell-label">ROI</span><strong>{signed(r.roi)}%</strong></td>
  <td className={`fa-rank-profit ${cls(r.profit)}`}><span className="fa-cell-label">Net profit</span><strong>{signed(r.profit)}u</strong></td>
  <td className="fa-rank-bets"><span className="fa-cell-label">Bets · 1u each</span><strong>{fmt(r.bets)}</strong></td>
  <td className="fa-rank-record"><details><summary>Record breakdown <span aria-hidden="true">＋</span></summary><dl><div><dt>Bets won / lost</dt><dd>{r.wins} / {r.losses}</dd></div><div><dt>Team W / D / L</dt><dd>{r.results.W} / {r.results.D} / {r.results.L}</dd></div><div><dt>Price coverage</dt><dd>{r.priced} / {r.eligible}</dd></div></dl><small>Coverage before role / odds filters</small></details></td>
 </tr>)}</tbody></table></div>{!visible.length && <p className="fa-empty">No clubs match these filters. Try a wider odds range or fewer minimum matches.</p>}{visible.length > limit && <button className="fa-more" onClick={() => setLimit(limit + 30)}>Show 30 more clubs</button>}
 <p className="fa-filter-note">Club histories overlap. Do not add their profits together as a betting portfolio. Missing prices can change rankings. These are historical returns, not recommended bets.</p></section>
 {selected && <TeamDetail key={selected} team={selected} data={data} initial={filters} onClose={() => setSelected(null)}/>}</>;
}
