'use client';

import Image from 'next/image';
import ResearchIcon from '@/components/ResearchIcon';
import H2HRecord from '@/components/H2HRecord';
import FixturePhoto from '@/components/FixturePhoto';
import { priceBasisLabel } from '../football-core';
import Link from 'next/link';
import { useEffect, useId, useRef, useState, type ReactNode } from 'react';
import type { Club, EvidencePayload, EvidenceRow, FixtureBoard as Board, FixtureCard, RecordSummary, FixtureEvidence } from './types';
import { bothPositiveOutcomes, matchesHistoryFilter, type HistoryFilter, type OutcomeFilter } from './history-filter';

/* Football Matchday browser. The past return is the product, so it is on the
   surface twice: three-way ROI for clubs and for managers in every row, and
   the full ROI, profit and result count at the top of an opened fixture.
   The meetings behind each record are two separate lists that open and close
   on their own. Presentation only: every calculation, filter, expiry rule,
   deep link and evidence request below is the existing one. Recorded prices
   are historical and are never shown as current odds. */

const leagues: Record<string, string> = { 'premier-league': 'Premier League', 'serie-a': 'Serie A', 'la-liga': 'La Liga', bundesliga: 'Bundesliga', 'ligue-1': 'Ligue 1', championship: 'Championship' };
const leagueLogo = (key: string) => `/league-logos/${key === 'premier-league' ? 'epl' : key}.png`;
const number = (n: number, digits = 1) => `${n > 0 ? '+' : n < 0 ? '−' : ''}${Math.abs(n).toFixed(digits)}`;
const dayFormatter = new Intl.DateTimeFormat('en-CA', { timeZone: 'Europe/London', year: 'numeric', month: '2-digit', day: '2-digit' });
const dayKey = (value: string | number) => dayFormatter.format(new Date(value));
const dateFormatter = new Intl.DateTimeFormat('en-GB', { timeZone: 'Europe/London', day: 'numeric', month: 'short' });
const dateText = (value: string) => dateFormatter.format(new Date(value.length === 10 ? `${value}T12:00:00Z` : value));
const clockFormatter = new Intl.DateTimeFormat('en-GB', { timeZone: 'Europe/London', hour: '2-digit', minute: '2-digit', timeZoneName: 'short' });
const clockText = (value: string) => clockFormatter.format(new Date(value));
// Row times: same zone, without the repeated zone name. The status line says "UK time" once.
const timeFormatter = new Intl.DateTimeFormat('en-GB', { timeZone: 'Europe/London', hour: '2-digit', minute: '2-digit' });
const timeText = (value: string) => timeFormatter.format(new Date(value));
const offsetDay = (value: string, days: number) => new Date(Date.parse(`${value}T12:00:00Z`) + days * 86400000).toISOString().slice(0, 10);
const plural = (n: number, word: string) => `${n} ${word}${n === 1 ? '' : 's'}`;
const roiText = (roi: number | null) => roi === null ? '—' : `${number(roi)}%`;

function Icon({ name }: { name: 'calendar' | 'manager' | 'club' | 'link' | 'arrow' | 'search' | 'clock' | 'chevron' | 'filter' }) {
  if (name === 'manager' || name === 'club' || name === 'calendar') return <ResearchIcon name={name === 'manager' ? 'managers' : name === 'club' ? 'football' : 'matchday'} width={18} height={18}/>;
  const paths = { link: 'm10 14 4-4M9 16l-2 2a4 4 0 0 1-6-6l4-4a4 4 0 0 1 6 0m2 0 2-2a4 4 0 0 1 6 6l-4 4a4 4 0 0 1-6 0', arrow: 'M4 12h16m-6-6 6 6-6 6', search: 'M10 3a7 7 0 1 0 0 14 7 7 0 0 0 0-14m5 12 6 6', clock: 'M12 2a10 10 0 1 0 0 20 10 10 0 0 0 0-20m0 4v6l4 2', chevron: 'm6 9 6 6 6-6', filter: 'M4 7h16M7 12h10M10 17h4' };
  return <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d={paths[name]} /></svg>;
}

function Photo({ src, manager = false }: { src: string | null; manager?: boolean }) {
  return <FixturePhoto src={src} className={manager ? 'fm-face' : 'fm-crest'} size={48} fallback={<Icon name={manager ? 'manager' : 'club'} />} />;
}

// Crest, club and manager names, and the manager's portrait. Same order on every row.
function Team({ club, side }: { club: Club; side: 'home' | 'away' }) {
  return <span className={`fm-team fm-${side}`}>
    <Photo src={club.crest} />
    <span className="fm-names">
      <strong><span className="sr-only">{side === 'home' ? 'Home: ' : 'Away: '}</span>{club.name}</strong>
      <span><span className="sr-only">Manager: </span>{club.manager?.name ?? 'Manager to be confirmed'}{club.manager?.status === 'unmatched' && <small>Archive identity pending</small>}</span>
    </span>
    <Photo src={club.manager?.portrait ?? null} manager />
  </span>;
}

/* Row summary of one record: all three past returns, never only the best one,
   with the number of priced meetings they come from. Results (wins, draws,
   wins) are a separate, labelled figure so they cannot be read as returns. */
function Brief({ label, record, unavailable, stale, names, manager = false }: { label: string; record: RecordSummary; unavailable: boolean; stale: boolean; names: string[]; manager?: boolean }) {
  const meetings = record.meetings ?? record.count, results = record.results;
  if (unavailable) return <span className="fm-brief fm-brief-none"><span className="fm-brief-head"><em>{manager ? 'Manager ROI' : 'Club ROI'}</em></span><small>Identity pending</small></span>;
  if (!meetings) return <span className="fm-brief fm-brief-none"><span className="fm-brief-head"><em>{manager ? 'Manager ROI' : 'Club ROI'}</em></span><small>No meetings</small></span>;
  const priced = record.count > 0, short = priced && record.count < 3;
  const heads = manager ? ['Home mgr', 'Draw', 'Away mgr'] : ['Home', 'Draw', 'Away'];
  const spoken = manager ? [`${names[0]}’s team`, 'the draw', `${names[1]}’s team`] : [names[0], 'the draw', names[1]];
  return <span className="fm-brief">
    <span className="fm-brief-head">
      <em>{manager ? 'Manager ROI' : 'Club ROI'}</em>
      <small data-short={short}>{priced ? `${record.count} priced` : 'No prices'}{short ? ' · short' : ''}</small>
      {results && results.length === 3 && <small className="fm-wdw" aria-hidden="true">W–D–W {results.join('–')}</small>}
    </span>
    <span className="fm-roi3" aria-hidden="true">{record.outcomes.slice(0, 3).map((outcome, i) => <span key={i} data-positive={priced && outcome.positive && !stale}><i>{heads[i]}</i><b>{priced ? roiText(outcome.roi) : '—'}</b></span>)}</span>
    <span className="sr-only">
      {label} past returns{priced ? ` from ${plural(record.count, 'priced meeting')}: ${record.outcomes.slice(0, 3).map((outcome, i) => `1 unit on ${spoken[i]} ${roiText(outcome.roi)}`).join(', ')}.` : ': no recorded prices.'}
      {results && results.length === 3 ? ` Results in ${plural(meetings, 'meeting')}: ${names[0]} ${plural(results[0], 'win')}, ${plural(results[1], 'draw')}, ${names[1]} ${plural(results[2], 'win')}. ` : ' '}
    </span>
  </span>;
}

// Opened fixture: result count and past return side by side for each outcome, nothing hidden.
function RecordBlock({ kind, record, unavailable, stale, paired, names, covered }: { kind: 'Managers' | 'Clubs'; record: RecordSummary; unavailable: boolean; stale: boolean; paired: number[]; names: string[]; covered: boolean }) {
  const meetings = record.meetings ?? record.count;
  const returns = record.outcomes.map((outcome, i) => <span className="fm-return" data-positive={outcome.positive && !stale && !unavailable} data-short={record.count < 3} key={i}>
    <strong>{unavailable || outcome.roi === null ? '—' : `${number(outcome.roi)}%`}<small> past ROI</small></strong>
    <span>{unavailable ? 'Not matched' : !record.count ? 'No prices' : `${number(outcome.profit, 2)}u`}</span>
    {paired.includes(i) && <span className="fm-return-both">Both positive</span>}
  </span>);
  return <section className="fm-record" aria-label={`${kind} head to head`}>
    <div className="fm-record-head"><Icon name={kind === 'Managers' ? 'manager' : 'club'} /><h3>{kind === 'Managers' ? 'Manager' : 'Club'} head to head</h3>
      {!unavailable && record.count > 0 && record.count < 6 && <small>{record.count < 3 ? 'Short history' : 'Few meetings'}</small>}
    </div>
    <p className="fm-record-scope">{kind === 'Clubs' ? 'These two clubs · home & away, both venues' : 'These two managers · across clubs, home & away'}</p>
    <H2HRecord compact showCoverage={false} coverageLabel={covered && kind === 'Clubs' ? 'covered leagues only' : 'top-five leagues only'} results={unavailable ? null : record.results ?? null} meetings={unavailable ? null : meetings} names={names} details={returns} />
    <p className="fm-record-coverage">
      {!unavailable && meetings > 0 && <strong>{plural(meetings, 'meeting')} · {record.count} with odds{record.firstDate && record.lastDate && <> · {record.firstDate.slice(0, 4)}{record.firstDate.slice(0, 4) === record.lastDate.slice(0, 4) ? '' : ` to ${record.lastDate.slice(0, 4)}`}</>}</strong>}
      <span>{covered ? (kind === 'Managers' ? 'Top-five leagues only · since 2012/13' : 'Top five + Championship · since 2012/13') : 'Top-five leagues only · since 2012/13'}</span>
    </p>
  </section>;
}

/* One optional evidence list. Club meetings and manager meetings are separate
   lists: each opens and closes on its own, and both can be open at once. */
function Meetings({ kind, fixture: f, rows, loading, error, retry, unavailable, open, onToggle }: {
  kind: 'clubs' | 'managers'; fixture: FixtureCard; rows: EvidenceRow[] | null; loading: boolean; error: string; retry: () => void; unavailable: boolean; open: boolean; onToggle: (open: boolean) => void;
}) {
  const [mode, setMode] = useState<'returns' | 'results'>('returns');
  const [outcome, setOutcome] = useState(0);
  const [limit, setLimit] = useState(10);
  const summary = f[kind], selected = summary.outcomes[outcome];
  const labels = [f.home.name, 'The draw', f.away.name];
  const sides = kind === 'clubs' ? [f.home.name, f.away.name] : [f.home.manager?.name ?? 'the home manager', f.away.manager?.name ?? 'the away manager'];
  const noun = kind === 'managers' ? 'manager meetings' : 'club meetings';
  return <details className="fm-meetings" open={open} onToggle={e => onToggle(e.currentTarget.open)}>
    <summary><Icon name={kind === 'managers' ? 'manager' : 'club'} /><span><span className="fm-show">Show</span><span className="fm-hide">Hide</span> {noun}</span><small>{summary.meetings ?? summary.count}</small><span className="fm-chev"><Icon name="chevron" /></span></summary>
    <div className="fm-meetings-body">
      <p className="fm-orientation">{kind === 'managers' ? `The ${f.home.name} column follows ${f.home.manager?.name ?? 'the home manager'} across clubs and venues. The ${f.away.name} column follows ${f.away.manager?.name ?? 'the away manager'}.` : `The ${f.home.name} column follows ${f.home.name} in every meeting, including when they played away.`} The list shows each match’s actual home and away teams.</p>
      <div className="fm-meetings-bar">
        <div className="fm-seg" role="group" aria-label={`Detail shown for ${noun}`}>
          <button type="button" aria-pressed={mode === 'returns'} onClick={() => setMode('returns')}>Prices &amp; returns</button>
          <button type="button" aria-pressed={mode === 'results'} onClick={() => setMode('results')}>Results only</button>
        </div>
        {mode === 'returns' && <label className="fm-select">1u on<select value={outcome} onChange={e => setOutcome(Number(e.target.value))}>{labels.map((label, i) => <option key={i} value={i}>{label}{i !== 1 && kind === 'managers' ? ' manager’s team' : ''}</option>)}</select></label>}
      </div>

      {mode === 'returns' && summary.count > 0 && <>
        <p className="fm-detail-profit">{labels[outcome]}{outcome !== 1 && kind === 'managers' ? ' manager’s team' : ''}: <strong>{number(selected.roi ?? 0)}% ROI · {number(selected.profit, 2)}u</strong> from {summary.count} priced meetings.</p>
        <div className="fm-stats"><div><span>Result frequency</span><strong>{summary.results?.[outcome] ?? selected.wins} of {summary.meetings ?? summary.count}</strong></div><div><span>Expected by the odds</span><strong>{selected.expectedWins.toFixed(1)} of {summary.count}</strong></div><div><span>Without biggest win</span><strong>{selected.withoutBest === null ? 'No winning bet' : `${number(selected.withoutBest, 2)}u`}</strong></div></div>
        <p className="fm-small">{dateText(summary.firstDate!)} {summary.firstDate!.slice(0, 4)} to {dateText(summary.lastDate!)} {summary.lastDate!.slice(0, 4)}. The odds-based figure adds the chances implied by each match’s prices after removing the margin. These are prices recorded before past matches, not current odds.</p>
      </>}

      {loading && <p className="fm-note" role="status">Loading the match history…</p>}
      {error && <p className="fm-note" role="alert">{error} <button type="button" onClick={retry}>Retry</button></p>}
      {rows && (rows.length ? <>
        <p className="fm-ledger-key" aria-hidden="true"><span><i data-side="0" />{sides[0]} won</span><span><i data-side="1" />Draw</span><span><i data-side="2" />{sides[1]} won</span></p>
        {mode === 'returns' && <div className="fm-ledger-heading" aria-hidden="true"><span>Meeting</span><span>Price</span><span>Return</span></div>}
        <ol className="fm-ledger" data-mode={mode}>{rows.slice(0, limit).map(r => {
          // Read from the recorded score: which of today's two sides won that meeting.
          const won = r.score[0] === r.score[1] ? 1 : (r.score[0] > r.score[1]) === r.firstWasHome ? 0 : 2;
          return <li key={r.id}>
            <i className="fm-dot" data-side={won} aria-hidden="true" />
            <div>
              <small>{dateText(r.date)} {r.date.slice(0, 4)} · {r.league === 'championship' ? 'Championship' : leagues[r.league]}</small>
              <strong><span data-won={r.score[0] > r.score[1]}>{r.home}</span> <b>{r.score[0]} : {r.score[1]}</b> <span data-won={r.score[1] > r.score[0]}>{r.away}</span></strong>
              <span className="sr-only">{won === 1 ? 'Draw.' : `${sides[won === 0 ? 0 : 1]} won.`} </span>
              {mode === 'returns' && <small>{outcome === 1 ? 'Back draw' : `Back ${outcome === 0 ? (r.firstWasHome ? r.home : r.away) : (r.firstWasHome ? r.away : r.home)}`} · {!r.odds ? 'No recorded odds' : priceBasisLabel(r.basis)}</small>}
            </div>
            {mode === 'returns' && <>
              <span>{r.odds ? r.odds[outcome].toFixed(2) : 'Unavailable'}</span>
              <span className={(r.profits?.[outcome] ?? 0) > 0 ? 'fm-mint' : ''}>{r.profits ? `${number(r.profits[outcome], 2)}u` : 'Excluded from ROI'}</span>
            </>}
          </li>;
        })}</ol>
        {rows.length > limit && <button type="button" className="fm-more" onClick={() => setLimit(limit + 20)}>Show more {noun}</button>}
      </> : <p className="fm-note">{kind === 'managers' && unavailable ? 'We are checking the manager identity before calculating this record. Club history is available separately.' : 'No verified meetings in the covered league archive.'}</p>)}
    </div>
  </details>;
}

function MatchRow({ fixture: f, stale, load, initialKind, covered, additional, onExpand }: { fixture: FixtureCard; stale: boolean; load: () => Promise<EvidencePayload>; initialKind?: 'managers' | 'clubs'; covered: boolean; additional: number; onExpand: () => void }) {
  const [evidence, setEvidence] = useState<FixtureEvidence | null>(null);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  // Open states live here, set once from the deep link. After that only the visitor changes them,
  // so a list they close stays closed through every later re-render.
  const [open, setOpen] = useState(Boolean(initialKind));
  const [clubsOpen, setClubsOpen] = useState(initialKind === 'clubs');
  const [managersOpen, setManagersOpen] = useState(initialKind === 'managers');
  const unavailable = !f.home.manager?.id || !f.away.manager?.id;
  const paired = bothPositiveOutcomes(f, stale);
  const clubNames = [f.home.name, f.away.name];
  const managerNames = [f.home.manager?.name ?? 'Manager unconfirmed', f.away.manager?.name ?? 'Manager unconfirmed'];
  async function openEvidence() {
    if (evidence || loading) return;
    setLoading(true); setError('');
    try { const data = await load(); if (!data.fixtures[f.id]) throw new Error(); setEvidence(data.fixtures[f.id]); }
    catch { setError('The match list could not load. Please try again.'); }
    finally { setLoading(false); }
  }
  // The shared evidence file is requested only when a meetings list is opened.
  const toggleList = (set: (value: boolean) => void) => (next: boolean) => { set(next); if (next) void openEvidence(); };
  return <article className="fm-row" style={{ scrollMarginTop: 100 }} id={f.id} aria-label={`${f.home.name} versus ${f.away.name}`}>
    <details open={open} onToggle={e => setOpen(e.currentTarget.open)}>
      <summary>
        <span className="fm-rowgrid">
          <span className="fm-when">
            <time dateTime={f.kickoff}>{timeText(f.kickoff)}</time>
            <span className="fm-comp" title={`${leagues[f.league]} · Round ${f.round}`}><Image src={leagueLogo(f.league)} alt="" width={16} height={16} unoptimized /><span aria-hidden="true">R{f.round}</span><span className="sr-only">{leagues[f.league]}, round {f.round}. </span></span>
          </span>
          <Team club={f.home} side="home" />
          <Team club={f.away} side="away" />
          <Brief label="Clubs" record={f.clubs} unavailable={false} stale={stale} names={clubNames} />
          <Brief label="Managers" record={f.managers} unavailable={unavailable} stale={stale} names={managerNames} manager />
          <span className="fm-chev"><Icon name="chevron" /></span>
          <span className="sr-only">Open or close the full club and manager returns.</span>
        </span>
      </summary>

      <div className="fm-panel">
        <div className="fm-records">
          <RecordBlock covered={covered && additional > 0} kind="Clubs" record={f.clubs} unavailable={false} stale={stale} paired={paired} names={clubNames} />
          <RecordBlock covered={covered} kind="Managers" record={f.managers} unavailable={unavailable} stale={stale} paired={paired} names={managerNames} />
        </div>
        <p className="fm-method">Past ROI: 1u on the named side or the draw in every meeting with odds, at the price recorded before that match. Past prices, not current odds, and not a prediction. <a href="#fixture-guide">How to read it ↗</a></p>
        <p className="fm-context">
          <span><Icon name="link" />{unavailable ? 'Manager comparison pending' : f.shared ? `${f.shared} priced meeting${f.shared === 1 ? '' : 's'} in both records` : 'No shared meetings'}</span>
          {paired.length > 0 && <span className="fm-aligned">Both positive: {paired.map(i => [`${f.home.name} win`, 'draw', `${f.away.name} win`][i]).join(', ')}</span>}
          {paired.length > 0 && <span>{f.managers.count - f.shared} manager only · {f.clubs.count - f.shared} club only</span>}
          {!covered && additional > 0 && <button type="button" className="fm-expand" onClick={onExpand}>+{additional} Championship meetings · Include them ↗</button>}
        </p>

        <div className="fm-evidence">
          <Meetings kind="clubs" fixture={f} rows={evidence ? evidence.clubs : null} loading={loading} error={error} retry={() => void openEvidence()} unavailable={unavailable} open={clubsOpen} onToggle={toggleList(setClubsOpen)} />
          <Meetings kind="managers" fixture={f} rows={evidence ? evidence.managers : null} loading={loading} error={error} retry={() => void openEvidence()} unavailable={unavailable} open={managersOpen} onToggle={toggleList(setManagersOpen)} />
        </div>

        <div className="fm-links"><Link href="/manager-atlas" prefetch={false}>Explore Manager Atlas ↗</Link><Link href={covered ? '/football-atlas?scope=covered' : '/football-atlas'} prefetch={false}>Explore club returns ↗</Link></div>
      </div>
    </details>
  </article>;
}

export default function FixtureBoard({ board, renderedAt, historyControls, covered = false, additions = {}, onExpand = () => {} }: { board: Board; renderedAt: number; historyControls?: ReactNode; covered?: boolean; additions?: Record<string, number>; onExpand?: () => void }) {
  const activeLeagues = Object.entries(leagues).filter(([key]) => key !== 'championship');
  const allLeaguesLabel = 'All leagues';
  const [league, setLeague] = useState('all'), [period, setPeriod] = useState('next'), [query, setQuery] = useState('');
  const [history, setHistory] = useState<HistoryFilter>('all'), [limit, setLimit] = useState(16);
  const [outcomeFilter, setOutcomeFilter] = useState<OutcomeFilter>('all');
  const [now, setNow] = useState(renderedAt);
  const [from, setFrom] = useState(''), [to, setTo] = useState('');
  const [focus, setFocus] = useState<{ id: string; kind: 'clubs' | 'managers' } | null>(null);
  // Presentation state only: phone disclosures for search and secondary filters.
  const [searchOpen, setSearchOpen] = useState(false), [filtersOpen, setFiltersOpen] = useState(false);
  const searchId = useId();
  useEffect(() => { const params = new URLSearchParams(window.location.search); const id = params.get('fixture'); if (!id || !board.fixtures.some(f => f.id === id)) return; const timer = setTimeout(() => setFocus({ id, kind: params.get('history') === 'clubs' ? 'clubs' : 'managers' }), 0); return () => clearTimeout(timer); }, [board.fixtures]);
  useEffect(() => { if (!focus) return; const frame = requestAnimationFrame(() => document.getElementById(focus.id)?.scrollIntoView({ block: 'start' })); return () => cancelAnimationFrame(frame); }, [focus]);
  const request = useRef<{ version: string; promise: Promise<EvidencePayload> } | null>(null);
  useEffect(() => { const initial = setTimeout(() => setNow(Date.now()), 0); const tick = setInterval(() => setNow(Date.now()), 60000); return () => { clearTimeout(initial); clearInterval(tick); }; }, []);
  function load() {
    if (!request.current || request.current.version !== board.version) {
      const version = board.version;
      const promise = fetch(board.evidenceUrl).then(async response => {
        if (!response.ok) throw new Error();
        const data = await response.json() as EvidencePayload;
        if (data.version !== version) throw new Error();
        return data;
      }).catch(error => { if (request.current?.version === version) request.current = null; throw error; });
      request.current = { version, promise };
    }
    return request.current.promise;
  }
  const stale = now >= Date.parse(board.expiresAt), upcoming = board.fixtures.filter(f => Date.parse(f.kickoff) > now).sort((a, b) => Date.parse(a.kickoff) - Date.parse(b.kickoff) || a.id.localeCompare(b.id));
  const first = upcoming.length ? dayKey(upcoming[0].kickoff) : dayKey(now);
  const today = dayKey(now), weekday = new Date(`${today}T12:00:00Z`).getUTCDay();
  const monday = offsetDay(today, -(weekday === 0 ? 6 : weekday - 1));
  const start = period === 'week' ? today : period === 'following' ? offsetDay(monday, 7) : period === 'custom' ? from || today : first;
  const end = period === 'week' ? offsetDay(monday, 6) : period === 'following' ? offsetDay(monday, 13) : period === 'custom' ? to || board.windowEnd : period === 'all' ? board.windowEnd : offsetDay(first, 6);
  const term = query.trim().toLocaleLowerCase();
  const dated = upcoming.filter(f => dayKey(f.kickoff) >= start && dayKey(f.kickoff) <= end);
  const leagueCounts = Object.fromEntries(activeLeagues.map(([key]) => [key, dated.filter(f => f.league === key).length]));
  const candidates = focus ? board.fixtures.filter(f => f.id === focus.id) : dated.filter(f => (league === 'all' || f.league === league) && (!term || [f.home.name, f.away.name, f.home.manager?.name, f.away.manager?.name].join(' ').toLocaleLowerCase().includes(term)));
  const visible = candidates.filter(f => matchesHistoryFilter(f, history, outcomeFilter, stale));
  const groups = new Map<string, FixtureCard[]>();
  for (const f of visible.slice(0, limit)) { const key = dayKey(f.kickoff); groups.set(key, [...(groups.get(key) ?? []), f]); }
  const reset = () => { setFocus(null); setLeague('all'); setQuery(''); setHistory('all'); setOutcomeFilter('all'); setPeriod('next'); setLimit(16); };
  const showSearch = searchOpen || !!query;
  const narrowed = league !== 'all' || !!query || history !== 'all' || outcomeFilter !== 'all' || period !== 'next';
  const held = board.footballHeld ?? 0;

  return <section className="fm-board" id="fixture-board" data-version={board.version}>
    <div className="fm-controls" onChangeCapture={() => setFocus(null)} onClickCapture={e => { if ((e.target as HTMLElement).closest('button')) setFocus(null); }}>
      {focus && <p className="fm-focus-note">Showing your selected matchup. <button type="button" onClick={reset}>Show all fixtures →</button></p>}

      {/* All five leagues are always on screen: names beside the logos on wide screens, logos alone on phones. */}
      <div className="fm-leagues" role="group" aria-label="Filter upcoming fixtures by league">
        {[['all', allLeaguesLabel], ...activeLeagues].map(([key, name]) => {
          const count = key === 'all' ? dated.length : leagueCounts[key];
          return <button type="button" className="fm-league" key={key} title={name} aria-pressed={league === key} data-empty={count === 0} onClick={() => { setLeague(key); setLimit(16); }}>
            <span className={`fm-league-logo${key === 'all' ? ' fm-league-all' : ''}`}>{key === 'all' ? <span aria-hidden="true">All</span> : <Image src={leagueLogo(key)} width={28} height={28} alt="" unoptimized />}</span>
            <span className="fm-league-name">{name}</span>
            <span className="fm-league-count">{count}<span className="sr-only"> {count === 1 ? 'match' : 'matches'} in selected dates</span></span>
          </button>;
        })}
      </div>

      <div className="fm-bar">
        <div className="fm-days" role="group" aria-label="Fixture dates">{[['next', 'Next fixtures'], ['week', 'This week'], ['following', 'Next week'], ['all', 'All scheduled'], ['custom', 'Choose dates']].map(([value, label]) => <button type="button" key={value} aria-pressed={period === value} onClick={() => { setPeriod(value); setLimit(16); }}>{label}</button>)}</div>
        <button type="button" className="fm-search-toggle" aria-expanded={showSearch} aria-controls={searchId} onClick={() => setSearchOpen(!showSearch)}><Icon name="search" /><span className="sr-only">Find a club or manager</span></button>
        <label id={searchId} className="fm-search" data-open={showSearch}><Icon name="search" /><span className="sr-only">Find a club or manager</span><input type="search" placeholder="Club or manager" value={query} onChange={e => { setQuery(e.target.value); setLimit(16); }} /></label>
      </div>
      {period === 'custom' && <div className="fm-custom"><label>From<input type="date" value={from} onChange={e => { setFrom(e.target.value); setLimit(16); }} /></label><label>To<input type="date" value={to} min={from} onChange={e => { setTo(e.target.value); setLimit(16); }} /></label></div>}

      <div className="fm-options" data-open={filtersOpen}>
        <button type="button" className="fm-filter-toggle" aria-expanded={filtersOpen} onClick={() => setFiltersOpen(!filtersOpen)}><Icon name="filter" />Filters{history !== 'all' ? ' · 1' : ''}</button>
        <div className="fm-optionset">
          <div className="fm-past" role="group" aria-label="Past ROI"><span>Past ROI</span>{([['all', 'All fixtures'], ['any', 'Positive in either'], ['both', 'Positive in both']] as const).map(([value, label]) => <button type="button" className="fm-opt" key={value} aria-pressed={history === value} disabled={stale && value !== 'all'} onClick={() => { setHistory(value); setLimit(16); }}>{label}</button>)}</div>
          {history !== 'all' && <label className="fm-select">Upcoming match outcome<select value={outcomeFilter} disabled={stale} onChange={e => { setOutcomeFilter(e.target.value as OutcomeFilter); setLimit(16); }}><option value="all">Any outcome</option><option value="home">Home team to win</option><option value="draw">Draw</option><option value="away">Away team to win</option></select></label>}
          {narrowed && <button type="button" className="fm-clear" onClick={reset}>Clear filters</button>}
          {historyControls}
        </div>
        <p className="fm-count" aria-live="polite">{league !== 'all' && !focus && <>{leagues[league]} · </>}<strong>{visible.length}</strong>{history !== 'all' && <> of {candidates.length}</>} fixture{visible.length === 1 ? '' : 's'} <span>{focus ? '· selected matchup' : `· ${dateText(start)} to ${dateText(end)}`}</span></p>
      </div>
      {history !== 'all' && <p className="fm-filter-note"><strong>{history === 'both' ? 'Positive past ROI in both records, on the same outcome.' : 'Positive past ROI in at least one record.'}</strong> {history === 'both' ? 'At least 3 meetings with odds in each. Shared matches can appear in both.' : 'At least 3 meetings with odds in the qualifying record.'} Club or manager history. Small samples can swing sharply; this is not a forecast.</p>}
    </div>

    <p className="fm-status">
      <span>{held > 0 ? 'Latest recorded club fixture' : 'Club history through'} <b>{dateText(board.footballThrough)} {board.footballThrough.slice(0, 4)}</b>{held > 0 && <> · <b>{held} club match{held === 1 ? '' : 'es'} under review</b></>}</span>
      <span>Latest verified manager fixture <b>{dateText(board.managerThrough)} {board.managerThrough.slice(0, 4)}</b></span>
      <span>Fixtures checked {dateText(board.checkedAt)} at {clockText(board.checkedAt)}</span>
      <span>UK time · home side first</span>
    </p>
    <p className="fm-scope-key"><b>Past ROI</b>: 1u on today’s home side, the draw or the away side in every earlier meeting with odds, at both venues. Manager ROI follows each manager across clubs. Past prices, not current odds.</p>
    {stale && <p className="fm-warning" role="status"><Icon name="clock" />Schedule snapshot needs refreshing. Kickoffs and appointments may have changed; historical highlights are paused.</p>}

    {!visible.length ? <div className="fm-empty"><Icon name="calendar" /><h2>{upcoming.length ? 'No fixtures in this view' : 'The next fixtures are being prepared'}</h2><p>{upcoming.length ? history === 'both' ? `No fixture has both histories positive ${outcomeFilter === 'all' ? 'on the same outcome' : `on ${outcomeFilter === 'draw' ? 'the draw' : `${outcomeFilter} win`}`} in this view. Try another outcome or date window, or show all fixtures.` : `The next covered fixture is on ${dateText(first)}. Try another date window or clear your filters.` : 'The published schedule has no remaining fixtures. Previous meetings remain available in Return Atlas.'}</p><button type="button" onClick={reset}>Show next fixtures <Icon name="arrow" /></button></div>
      : [...groups].map(([date, fixtures]) => <section className="fm-day" key={date}>
        <h2><span>{new Intl.DateTimeFormat('en-GB', { weekday: 'long', timeZone: 'UTC' }).format(new Date(`${date}T12:00:00Z`))}</span>{dateText(date)}<small>{fixtures.length} shown</small></h2>
        <div className="fm-group">
          <div className="fm-colhead" aria-hidden="true"><span>Kick-off</span><span className="fm-col-home">Home<span className="fm-col-then">, then away</span></span><span className="fm-col-away">Away</span><span>Club past ROI<small>these two clubs · both venues</small></span><span>Manager past ROI<small>these two managers · across clubs</small></span><span /></div>
          {fixtures.map(f => <MatchRow key={`${board.version}-${f.id}-${focus?.kind ?? 'default'}`} fixture={f} stale={stale} load={load} covered={covered} additional={additions[f.id] ?? 0} onExpand={onExpand} initialKind={focus?.id === f.id ? focus.kind : undefined} />)}
        </div>
      </section>)}
    {visible.length > limit && <button type="button" className="fm-load-more" onClick={() => setLimit(limit + 16)}>Show next {Math.min(16, visible.length - limit)} fixtures <span>{visible.length - limit} remaining</span></button>}

    <details className="fm-about"><summary>About this board</summary>
      <p><strong>Club past ROI</strong> follows these two teams, home and away, whoever was in charge. <strong>Manager past ROI</strong> follows these two coaches across clubs and venues, not their current clubs’ history. Each row shows all three returns: 1u on today’s home side (or the home manager’s team), on the draw, and on the away side, with the number of priced meetings behind them. “W–D–W” is the separate result count: wins, draws, wins. Open a fixture for profit in units, coverage and the meetings themselves.</p>
      <p>Returns use a fixed 1u stake at recorded prematch prices. Pinnacle is the primary benchmark; reviewed bet365 fallbacks are labelled in the match list. Team columns follow the named club or its manager across all historical venues. Results without odds remain in the meeting list and are excluded from ROI. A green figure marks a positive past ROI from at least three priced meetings. Past returns are not a prediction, and no current match odds are shown on this board. <a href="#fixture-guide">How to read the board ↗</a></p>
    </details>
  </section>;
}
