'use client';

import Image from 'next/image';
import Link from 'next/link';
import { useEffect, useRef, useState } from 'react';
import type { Club, EvidencePayload, FixtureBoard as Board, FixtureCard, FixtureEvidence, RecordSummary } from './types';
import { bothPositiveOutcomes, matchesHistoryFilter, type HistoryFilter, type OutcomeFilter } from './history-filter';

const leagues: Record<string, string> = { 'premier-league': 'Premier League', 'serie-a': 'Serie A', 'la-liga': 'La Liga', bundesliga: 'Bundesliga', 'ligue-1': 'Ligue 1' };
const number = (n: number, digits = 1) => `${n > 0 ? '+' : n < 0 ? '−' : ''}${Math.abs(n).toFixed(digits)}`;
const dayFormatter = new Intl.DateTimeFormat('en-CA', { timeZone: 'Europe/London', year: 'numeric', month: '2-digit', day: '2-digit' });
const dayKey = (value: string | number) => dayFormatter.format(new Date(value));
const dateFormatter = new Intl.DateTimeFormat('en-GB', { timeZone: 'Europe/London', day: 'numeric', month: 'short' });
const dateText = (value: string) => dateFormatter.format(new Date(value.length === 10 ? `${value}T12:00:00Z` : value));
const clockFormatter = new Intl.DateTimeFormat('en-GB', { timeZone: 'Europe/London', hour: '2-digit', minute: '2-digit', timeZoneName: 'short' });
const clockText = (value: string) => clockFormatter.format(new Date(value));
const offsetDay = (value: string, days: number) => new Date(Date.parse(`${value}T12:00:00Z`) + days * 86400000).toISOString().slice(0, 10);

function Icon({ name }: { name: 'calendar' | 'manager' | 'club' | 'link' | 'arrow' | 'search' | 'clock' }) {
  const paths = { calendar: 'M7 2v4m10-4v4M3 9h18M4 4h16v17H4zM8 13h2m4 0h2m-8 4h2', manager: 'M8 7a4 4 0 1 0 8 0 4 4 0 1 0-8 0M4 22v-4l5-4 3 6 3-6 5 4v4M10 14h4', club: 'M12 2 3 6v6c0 5 5 8 9 10 4-2 9-5 9-10V6zM8 10h8m-4-4v10', link: 'm10 14 4-4M9 16l-2 2a4 4 0 0 1-6-6l4-4a4 4 0 0 1 6 0m2 0 2-2a4 4 0 0 1 6 6l-4 4a4 4 0 0 1-6 0', arrow: 'M4 12h16m-6-6 6 6-6 6', search: 'M10 3a7 7 0 1 0 0 14 7 7 0 0 0 0-14m5 12 6 6', clock: 'M12 2a10 10 0 1 0 0 20 10 10 0 0 0 0-20m0 4v6l4 2' };
  return <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d={paths[name]} /></svg>;
}

function Photo({ src, manager = false }: { src: string | null; manager?: boolean }) {
  const [failed, setFailed] = useState(false);
  return <span className={manager ? 'af-face' : 'af-crest'}>{src && !failed ? <Image src={src} alt="" width={manager ? 28 : 48} height={manager ? 28 : 48} unoptimized onError={() => setFailed(true)} /> : <Icon name={manager ? 'manager' : 'club'} />}</span>;
}

function Team({ club, away = false }: { club: Club; away?: boolean }) {
  return <div className={`af-team ${away ? 'af-away' : ''}`}><Photo src={club.crest} /><div><strong>{club.name}</strong><span className="af-coach"><Photo src={club.manager?.portrait ?? null} manager /><span>{club.manager?.name ?? 'Manager to be confirmed'}{club.manager?.status === 'unmatched' && <small>Archive identity pending</small>}</span></span></div></div>;
}

function RecordRow({ kind, record, unavailable, stale, paired }: { kind: 'Managers' | 'Clubs'; record: RecordSummary; unavailable: boolean; stale: boolean; paired: number[] }) {
  return <div className="af-record"><div className="af-record-label"><Icon name={kind === 'Managers' ? 'manager' : 'club'} /><strong>{kind}</strong><span>{unavailable ? 'Identity pending' : `${record.count} meeting${record.count === 1 ? '' : 's'}`}</span>{!unavailable && record.firstDate && record.lastDate && <span className="af-record-years">{record.firstDate.slice(0, 4) === record.lastDate.slice(0, 4) ? record.firstDate.slice(0, 4) : `${record.firstDate.slice(0, 4)} to ${record.lastDate.slice(0, 4)}`}</span>}{record.count > 0 && record.count < 6 && <small>{record.count < 3 ? 'Short history' : 'Few meetings'}</small>}</div><div className="af-cells">{record.outcomes.map((outcome, i) => <div className={`af-return ${outcome.positive && !stale && !unavailable ? 'af-positive' : ''} ${paired.includes(i) ? 'af-paired' : ''} ${record.count < 3 ? 'af-short' : ''} ${Math.abs(outcome.roi ?? 0) >= 1000 ? 'af-long' : ''}`} key={i}><strong>{unavailable || outcome.roi === null ? '—' : `${number(outcome.roi)}%`}</strong><span>{unavailable ? 'Not matched' : !record.count ? 'No meetings' : `${number(outcome.profit, 2)}u`}</span></div>)}</div></div>;
}

function MatchCard({ fixture: f, stale, load }: { fixture: FixtureCard; stale: boolean; load: () => Promise<EvidencePayload> }) {
  const [evidence, setEvidence] = useState<FixtureEvidence | null>(null);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const [kind, setKind] = useState<'managers' | 'clubs'>(f.managers.count ? 'managers' : 'clubs');
  const [outcome, setOutcome] = useState(0);
  const [limit, setLimit] = useState(10);
  const unavailable = !f.home.manager?.id || !f.away.manager?.id;
  const paired = bothPositiveOutcomes(f, stale);
  const summary = f[kind], selected = summary.outcomes[outcome];
  const labels = [f.home.name, 'The draw', f.away.name];
  async function openEvidence() {
    if (evidence || loading) return;
    setLoading(true); setError('');
    try { const data = await load(); if (!data.fixtures[f.id]) throw new Error(); setEvidence(data.fixtures[f.id]); }
    catch { setError('The match list could not load. Please try again.'); }
    finally { setLoading(false); }
  }
  return <article className="af-card" id={f.id} aria-label={`${f.home.name} versus ${f.away.name}`}>
    <header className="af-card-top"><span><Image src={`/league-logos/${f.league === 'premier-league' ? 'epl' : f.league}.png`} alt="" width={18} height={18} unoptimized />{leagues[f.league]}<span className="af-round"> · Round {f.round}</span></span><time dateTime={f.kickoff}>{clockText(f.kickoff)}</time></header>
    <div className="af-match"><Team club={f.home} /><span className="af-versus">v</span><Team club={f.away} away /></div>
    <div className="af-grid-heading"><span>Past returns</span><div>{['Home win', 'Draw', 'Away win'].map((label, i) => <span key={label} className={paired.includes(i) ? 'af-paired-heading' : undefined} title={paired.includes(i) ? 'Positive in both histories' : undefined}>{label}{paired.includes(i) && <span className="af-paired-dot" aria-hidden="true" />}</span>)}</div></div>
    <RecordRow kind="Managers" record={f.managers} unavailable={unavailable} stale={stale} paired={paired} />
    <RecordRow kind="Clubs" record={f.clubs} unavailable={false} stale={stale} paired={paired} />
    <div className="af-card-context"><span><Icon name="link" />{unavailable ? 'Manager comparison pending' : f.shared ? `${f.shared} meeting${f.shared === 1 ? '' : 's'} in both records` : 'No shared meetings'}<span className="af-context-more"> · Shared history</span></span>{paired.length > 0 && <span className="af-alignment">Both positive: {paired.map(i => ['home win', 'draw', 'away win'][i]).join(', ')}</span>}{paired.length > 0 && <span className="af-overlap-detail">{f.managers.count - f.shared} manager only · {f.clubs.count - f.shared} club only</span>}</div>
    <details className="af-evidence" onToggle={e => { if (e.currentTarget.open) void openEvidence(); }}><summary>Explore the meetings <span aria-hidden="true">+</span></summary>
      <div className="af-evidence-body"><div className="af-evidence-controls"><div className="af-toggle" aria-label="History type">{(['managers', 'clubs'] as const).map(k => <button key={k} aria-pressed={kind === k} onClick={() => { setKind(k); setLimit(10); }}>{k === 'managers' ? 'Manager meetings' : 'Club meetings'} ({f[k].count})</button>)}</div><label>Selection shown<select value={outcome} onChange={e => setOutcome(Number(e.target.value))}>{labels.map((label, i) => <option key={i} value={i}>{label}{i !== 1 && kind === 'managers' ? ' manager’s team' : ''}</option>)}</select></label></div>
      <p className="af-orientation">{kind === 'managers' ? `Home win follows ${f.home.manager?.name ?? 'the home manager'} across clubs and venues. Away win follows ${f.away.manager?.name ?? 'the away manager'}.` : `Home win follows ${f.home.name} in every meeting, including when they played away.`} The list shows each match’s actual home and away teams.</p>
      {summary.count > 0 && <><div className="af-evidence-stats"><div><span>Result frequency</span><strong>{selected.wins} of {summary.count}</strong></div><div><span>Odds suggested</span><strong>{selected.expectedWins.toFixed(1)} of {summary.count}</strong></div><div><span>Without biggest win</span><strong>{selected.withoutBest === null ? 'No winning bet' : `${number(selected.withoutBest, 2)}u`}</strong></div></div><p className="af-small">{dateText(summary.firstDate!)} {summary.firstDate!.slice(0, 4)} to {dateText(summary.lastDate!)} {summary.lastDate!.slice(0, 4)}. The odds-based figure adds the chances implied by each match’s prices after removing the margin.</p></>}
      {loading && <p role="status">Loading the match history…</p>}{error && <p role="alert">{error} <button onClick={() => void openEvidence()}>Retry</button></p>}
      {evidence && (evidence[kind].length ? <><div className="af-ledger-heading"><span>Meeting</span><span>Price</span><span>Return</span></div><ol className="af-ledger">{evidence[kind].slice(0, limit).map(r => <li key={r.id}><div><small>{dateText(r.date)} {r.date.slice(0, 4)} · {leagues[r.league]}</small><strong>{r.home} <b>{r.score[0]} : {r.score[1]}</b> {r.away}</strong><small>{outcome === 1 ? 'Back draw' : `Back ${outcome === 0 ? (r.firstWasHome ? r.home : r.away) : (r.firstWasHome ? r.away : r.home)}`} · {r.basis === 'closing' ? 'Closing price' : 'Last prematch price'}</small></div><span>{r.odds[outcome].toFixed(2)}</span><span className={r.profits[outcome] > 0 ? 'af-mint' : ''}>{number(r.profits[outcome], 2)}u</span></li>)}</ol>{evidence[kind].length > limit && <button className="af-more" onClick={() => setLimit(limit + 20)}>Show more meetings</button>}</> : <p className="af-no-history">{kind === 'managers' && unavailable ? 'We are checking the manager identity before calculating this record. Club history is available separately.' : 'No priced meetings in the covered league archive.'}</p>)}
      <div className="af-explore-links"><Link href="/manager-atlas" prefetch={false}>Explore Manager Atlas ↗</Link><Link href="/football-atlas" prefetch={false}>Explore club returns ↗</Link></div></div>
    </details>
  </article>;
}

export default function FixtureBoard({ board }: { board: Board }) {
  const [league, setLeague] = useState('all'), [period, setPeriod] = useState('next'), [query, setQuery] = useState('');
  const [history, setHistory] = useState<HistoryFilter>('all'), [limit, setLimit] = useState(16);
  const [outcomeFilter, setOutcomeFilter] = useState<OutcomeFilter>('all');
  const [now, setNow] = useState(Date.parse(board.checkedAt));
  const [from, setFrom] = useState(''), [to, setTo] = useState('');
  const request = useRef<Promise<EvidencePayload> | null>(null);
  useEffect(() => { const initial = setTimeout(() => setNow(Date.now()), 0); const tick = setInterval(() => setNow(Date.now()), 60000); return () => { clearTimeout(initial); clearInterval(tick); }; }, []);
  function load() {
    if (!request.current) request.current = fetch(board.evidenceUrl).then(async response => { if (!response.ok) throw new Error(); const data = await response.json() as EvidencePayload; if (data.version !== board.version) throw new Error(); return data; }).catch(error => { request.current = null; throw error; });
    return request.current;
  }
  const stale = now >= Date.parse(board.expiresAt), upcoming = board.fixtures.filter(f => Date.parse(f.kickoff) > now);
  const first = upcoming.length ? dayKey(upcoming[0].kickoff) : dayKey(now);
  const today = dayKey(now), weekday = new Date(`${today}T12:00:00Z`).getUTCDay();
  const monday = offsetDay(today, -(weekday === 0 ? 6 : weekday - 1));
  const start = period === 'week' ? today : period === 'following' ? offsetDay(monday, 7) : period === 'custom' ? from || today : first;
  const end = period === 'week' ? offsetDay(monday, 6) : period === 'following' ? offsetDay(monday, 13) : period === 'custom' ? to || board.windowEnd : period === 'all' ? board.windowEnd : offsetDay(first, 6);
  const term = query.trim().toLocaleLowerCase();
  const candidates = upcoming.filter(f => (league === 'all' || f.league === league) && dayKey(f.kickoff) >= start && dayKey(f.kickoff) <= end && (!term || [f.home.name, f.away.name, f.home.manager?.name, f.away.manager?.name].join(' ').toLocaleLowerCase().includes(term)));
  const visible = candidates.filter(f => matchesHistoryFilter(f, history, outcomeFilter, stale));
  const groups = new Map<string, FixtureCard[]>();
  for (const f of visible.slice(0, limit)) { const key = dayKey(f.kickoff); groups.set(key, [...(groups.get(key) ?? []), f]); }
  const reset = () => { setLeague('all'); setQuery(''); setHistory('all'); setOutcomeFilter('all'); setPeriod('next'); setLimit(16); };
  return <section className="af-board" id="fixture-board" data-version={board.version}>
    <div className="af-toolbar"><div className="af-date-tabs" aria-label="Fixture dates">{[['next', 'Next fixtures'], ['week', 'This week'], ['following', 'Next week'], ['all', 'All scheduled'], ['custom', 'Choose dates']].map(([value, label]) => <button key={value} aria-pressed={period === value} onClick={() => { setPeriod(value); setLimit(16); }}>{value === 'next' && <Icon name="calendar" />}{label}</button>)}</div><div className="af-filters"><label>Competition<select value={league} onChange={e => { setLeague(e.target.value); setLimit(16); }}><option value="all">All five leagues</option>{Object.entries(leagues).map(([key, name]) => <option key={key} value={key}>{name}</option>)}</select></label><label className="af-search">Find a club or manager<span><Icon name="search" /><input type="search" placeholder="Arsenal, Arteta…" value={query} onChange={e => { setQuery(e.target.value); setLimit(16); }} /></span></label><fieldset className="af-history-filter"><legend>History</legend><div>{([['all', 'All fixtures'], ['any', 'Any positive'], ['both', 'Both positive']] as const).map(([value, label]) => <button key={value} aria-pressed={history === value} disabled={stale && value !== 'all'} onClick={() => { setHistory(value); setLimit(16); }}>{label}</button>)}</div></fieldset></div>{history !== 'all' && <div className="af-positive-options"><div><strong>{history === 'both' ? 'Manager and club history positive on the same outcome.' : 'Positive in at least one history.'}</strong><small>{history === 'both' ? 'At least 3 meetings in each record. Shared matches can appear in both.' : 'At least 3 meetings in the qualifying record.'}</small></div><label>Outcome<select value={outcomeFilter} disabled={stale} onChange={e => { setOutcomeFilter(e.target.value as OutcomeFilter); setLimit(16); }}><option value="all">Any outcome</option><option value="home">Home win</option><option value="draw">Draw</option><option value="away">Away win</option></select></label></div>}{period === 'custom'  && <div className="af-custom"><label>From<input type="date" value={from} onChange={e => { setFrom(e.target.value); setLimit(16); }} /></label><label>To<input type="date" value={to} min={from} onChange={e => { setTo(e.target.value); setLimit(16); }} /></label></div>}</div>
    <div className="af-board-status"><p aria-live="polite"><strong>{visible.length}</strong>{history !== 'all' && <> of {candidates.length}</>} fixture{visible.length === 1 ? '' : 's'} <span>· {dateText(start)} to {dateText(end)}</span></p><span className="af-legend"><i />Positive ROI with 3+ meetings</span></div>
    {stale && <p className="af-warning" role="status"><Icon name="clock" />Schedule snapshot needs refreshing. Kickoffs and appointments may have changed; historical highlights are paused.</p>}
    <p className="af-board-note">Returns use recorded Pinnacle closing or last prematch prices and a fixed 1u stake. Home and away follow the upcoming fixture. <a href="#fixture-guide">How to read the board ↗</a></p><p className="af-coverage-note">Club history through {dateText(board.footballThrough)} {board.footballThrough.slice(0, 4)} · Manager history through {dateText(board.managerThrough)} {board.managerThrough.slice(0, 4)}. Past returns, not a forecast.</p>
    {!visible.length ? <div className="af-empty"><Icon name="calendar" /><h2>{upcoming.length ? 'No fixtures in this view' : 'The next fixtures are being prepared'}</h2><p>{upcoming.length ? history === 'both' ? `No fixture has both histories positive ${outcomeFilter === 'all' ? 'on the same outcome' : `on ${outcomeFilter === 'draw' ? 'the draw' : `${outcomeFilter} win`}`} in this view. Try another outcome or date window, or show all fixtures.` : `The next covered fixture is on ${dateText(first)}. Try another date window or clear your filters.` : 'The published schedule has no remaining fixtures. Previous meetings remain available in Return Atlas.'}</p><button onClick={reset}>Show next fixtures <Icon name="arrow" /></button></div> : [...groups].map(([date, fixtures]) => <section className="af-day" key={date}><h2><span>{new Intl.DateTimeFormat('en-GB', { weekday: 'long', timeZone: 'UTC' }).format(new Date(`${date}T12:00:00Z`))}</span>{dateText(date)}<small>{fixtures.length} shown</small></h2><div className="af-card-grid">{fixtures.map(f => <MatchCard key={f.id} fixture={f} stale={stale} load={load} />)}</div></section>)}
    {visible.length > limit && <button className="af-load-more" onClick={() => setLimit(limit + 16)}>Show next {Math.min(16, visible.length - limit)} fixtures <span>{visible.length - limit} remaining</span></button>}
    <p className="af-snapshot"><Icon name="clock" />Fixtures and managers checked {dateText(board.checkedAt)} at {clockText(board.checkedAt)}. Club history through {dateText(board.footballThrough)} {board.footballThrough.slice(0, 4)}; manager history through {dateText(board.managerThrough)} {board.managerThrough.slice(0, 4)}.</p>
  </section>;
}
