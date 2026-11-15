'use client';
import { useEffect, useId, useState } from 'react';
import Link from 'next/link';
import Image from 'next/image';
import { fixturesFor, matchdayQuote, type TennisBoard, type TennisFixture, type FixturePlayer } from '@/lib/tennis-matchday.mjs';
import { atlasResearchHref } from '@/components/return-atlas/research-links.mjs';
import styles from './matchday.module.css';
import { tournamentOf, isQualifying, surfaceNames, readBrowseState, browseQuery, displayDay, type BrowseState } from '@/lib/tennis-matchday-browse.mjs';
import H2HRecord from '@/components/H2HRecord';
import { resolveTennisPortrait } from '@/lib/tennis-portrait.mjs';

const zone = 'Europe/London';
const format = (date: string, options: Intl.DateTimeFormatOptions) => new Intl.DateTimeFormat('en-GB', { timeZone: zone, ...options }).format(new Date(date));
const stamp = (date: string) => format(date, { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit', timeZoneName: 'short' });
const percent = (n: number | null) => n === null ? 'Not available' : `${n > 0 ? '+' : ''}${n.toFixed(1)}%`;
const surname = (name: string) => name.split(' ').slice(-1).join(' ');
const price = (n: number | null) => n !== null && Number.isFinite(n) && n > 1 ? n.toFixed(3).replace(/0$/, '') : 'Unavailable';
const units = (n: number) => `${n < 0 ? '−' : '+'}${Math.abs(n).toFixed(2)}u`;


const tours = [{ value: 'all', label: 'All singles', logo: null }, { value: 'ATP', label: 'ATP', logo: '/icons/markets/atp-logo.png' }, { value: 'Challenger', label: 'Challenger', logo: '/icons/markets/challenger-tour.png' }];

function MeetingHistory({ fixture: f }: { fixture: TennisFixture }) {
  return <details className={styles.meetings}>
    <summary><span>Previous {f.history.length === 1 ? 'meeting' : `${f.history.length} meetings`}</span><Icon name="arrow" /></summary>
    <p className={styles.historyKey}>Scores show the winner first. Recorded match odds are shown where available; these are historical prices.</p>
    <ol className={styles.historyList}>{f.history.map(m => {
      return <li className={styles.historyMatch} key={`${m.date}:${m.event}`}>
        <div className={styles.historyHeading}><time dateTime={m.date}>{format(`${m.date}T12:00:00Z`, { day: 'numeric', month: 'short', year: 'numeric' })}</time><span>{m.surface.replace('-', ' ')}</span></div>
        <p className={styles.historyEvent}>{m.event}{m.competition ? ` · ${m.competition}` : ''}</p>
        <p className={styles.historyResult}><strong>{surname(f.players[m.winner].name)} won</strong><span>{m.score || 'Score unavailable'}</span></p>
        {m.odds.some(p => p !== null) && <dl className={styles.historyPrices}>{f.players.map((p, i) => <div key={p.name}><dt>{surname(p.name)} odds</dt><dd><strong>{price(m.odds[i])}</strong></dd></div>)}</dl>}
        {m.priceBasis && <p className={styles.historyKey}>{m.priceBasis}</p>}
      </li>;
    })}</ol>

  </details>;
}

function Icon({ name }: { name: 'clock' | 'arrow' | 'person' | 'record' | 'search' }) {
  return <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
    {name === 'clock' ? <><circle cx="12" cy="12" r="8.5" /><path d="M12 7v5l3 2" /></> : name === 'arrow' ? <path d="M5 12h14m-6-6 6 6-6 6" /> : name === 'person' ? <><circle cx="12" cy="8" r="3.5" /><path d="M4 21v-2a8 8 0 0 1 16 0v2" /></> : name === 'record' ? <><path d="M4 19h16M6 15V9m6 6V5m6 10v-7" /><path d="m4 7 5-3 5 2 6-4" /></> : <><circle cx="10" cy="10" r="6" /><path d="m15 15 5 5" /></>}
  </svg>;
}

function Portrait({ player }: { player: FixturePlayer }) {
  const [failedSrc, setFailedSrc] = useState<string | null>(null);
  const crop = resolveTennisPortrait(player.name);
  return <span className={styles.portrait}>
    {player.portrait && failedSrc !== player.portrait
      ? <Image src={player.portrait} width={72} height={72} unoptimized alt="" loading="lazy"
          style={crop?.scale ? { objectFit: 'cover', objectPosition: crop.position, transform: `scale(${crop.scale})`, transformOrigin: '50% 0%' } : undefined}
          onError={() => setFailedSrc(player.portrait)} />
      : <Icon name="person" />}
  </span>;
}

function FormStrip({ player, compact = false }: { player: FixturePlayer; compact?: boolean }) {
  const form = player.recent?.matches.filter(m => m.status !== 'walkover' && Date.parse(`${player.recent?.through}T00:00:00Z`) - Date.parse(`${m.date}T00:00:00Z`) <= 366 * 86400000).slice(0, 5) ?? [];
  if (!form.length) return null;
  return <span className={styles.formStrip} aria-hidden={compact || undefined} aria-label={`${player.name}: recent results, newest first`}>{form.map(m => <span key={m.id} data-outcome={m.winner ? 'win' : 'loss'} title={`${m.date}: ${m.winner ? 'beat' : 'lost to'} ${m.opponent}, ${m.score}`}><span aria-hidden="true">{m.winner ? 'W' : 'L'}{m.status === 'retired' ? '*' : ''}</span><span className="sr-only">{m.winner ? 'Win' : 'Loss'} against {m.opponent}, {m.date}{m.status === 'retired' ? ', retirement' : ''}. </span></span>)}</span>;
}

function RecentResults({ player }: { player: FixturePlayer }) {
  const [more, setMore] = useState(false);
  const recent = player.recent;
  const dayLabel = (day: string) => format(`${day}T12:00:00Z`, { day: 'numeric', month: 'short', year: '2-digit' });
  return <section className={styles.recentPlayer} aria-label={`${player.name} recent results`}>
    <header><h5>{player.name}</h5><FormStrip player={player} /></header>{recent?.matches[0] && Date.parse(`${recent.through}T00:00:00Z`) - Date.parse(`${recent.matches[0].date}T00:00:00Z`) > 365 * 86400000 && <p className={styles.resultEmpty}>Last recorded appearance: {dayLabel(recent.matches[0].date)}. This is older history.</p>}
    {!!recent?.omitted && <p className={styles.resultEmpty}>{recent.omitted} {recent.omitted === 1 ? 'result with an unrecognised score omitted' : 'results with unrecognised scores omitted'} from this date window.</p>}
    {!recent ? <p className={styles.resultEmpty}>Results not linked for this player yet. The other player’s record is independent.</p> : !recent.matches.length ? <p className={styles.resultEmpty}>No results found in the last three years of our archive.</p> : <>
      <ol className={styles.recentList}>{recent.matches.slice(0, more ? 10 : 5).map(m => <li key={m.id}>
        <span className={styles.resultBadge} data-outcome={m.status === 'walkover' ? 'walkover' : m.winner ? 'win' : 'loss'}>{m.status === 'walkover' ? 'W/O' : m.winner ? 'W' : 'L'}</span>
        <div className={styles.resultBody}><div className={styles.resultOpponent}><strong>{m.opponent}</strong><span>{m.status === 'walkover' ? 'Not played' : m.score}</span></div><p><time dateTime={m.date}>{dayLabel(m.date)}</time><span>{m.event} · {m.round}</span></p><p><span data-surface={m.surface} className={styles.resultSurface}>{surfaceNames[m.surface as keyof typeof surfaceNames] || m.surface}</span><span>{m.competition}{m.status === 'retired' ? ' · Retirement' : ''}</span></p></div>
      </li>)}</ol>
      {recent.matches.length > 5 && <button className={styles.moreResults} type="button" onClick={() => setMore(!more)}>{more ? 'Show five' : `Show ${Math.min(recent.matches.length, 10)} results`}</button>}
    </>}
  </section>;
}

function FixtureCard({ fixture: f, now }: { fixture: TennisFixture; now: Date }) {
  const quote = matchdayQuote(f, now);
  const through = f.players.map(p => p.recent?.through).filter(Boolean).sort()[0];
  const staleResults = through && Date.parse(`${through}T00:00:00Z`) < Date.parse(`${now.toISOString().slice(0,10)}T00:00:00Z`) - 86400000;
  return <article className={styles.card} aria-label={`${f.players[0].name} versus ${f.players[1].name}`}>
    <div className={styles.match}><div><Portrait player={f.players[0]} /><h4>{f.players[0].name}</h4></div><span className={styles.versus}>VS</span><div><Portrait player={f.players[1]} /><h4>{f.players[1].name}</h4></div></div>
    <div className={styles.recentHeading}><h4>Recent results</h4><p className={staleResults ? styles.oldResults : ''}>{through ? `Archive through ${format(`${through}T12:00:00Z`, { day: 'numeric', month: 'short', year: 'numeric' })}${staleResults ? ' · Update overdue' : ''}` : 'Results coverage unavailable'}</p></div>
    <p className={styles.recentKey}>By date, newest first · all surfaces · qualifying included. Scores shown winner first. W/O is not played; * marks a retirement.</p>
    <div className={styles.recentGrid}>{f.players.map(p => <RecentResults key={p.name} player={p} />)}</div>
    <section className={styles.h2hBlock} aria-label="Head-to-head">
      <div className={styles.recordLabel}><h4>Head-to-head</h4><small>All recorded surfaces</small></div>
      {f.wins && f.meetings ? <><H2HRecord compact results={f.wins} meetings={f.meetings} names={f.players.map(p => p.name)} /><p className={styles.h2hScope}>{f.meetings} completed {f.meetings === 1 ? 'meeting' : 'meetings'}. Retirements and walkovers excluded.</p></> : <p className={styles.h2hScope}>{f.meetings === 0 ? `No completed meetings found in our archive. Checked ${format(`${f.coverageThrough}T12:00:00Z`, { day: 'numeric', month: 'short' })}.` : f.h2hStatus === 'unchecked' ? 'H2H not checked yet. Both players’ recent results are available above.' : 'H2H awaits a verified player link. Available recent results are shown above.'}</p>}
      {f.history.length > 0 && <MeetingHistory fixture={f} />}
    </section>
    <div className={styles.actions}>{f.href && <Link href={f.href} prefetch={false}><Image src="/tennis-matchup/court-v1.webp" alt="" width={27} height={27} unoptimized /><span>Explore this H2H</span><Icon name="arrow" /></Link>}{f.players.every(p => p.id) && <Link href={atlasResearchHref(f.players[0].id, f.players[1].id)} prefetch={false}><Icon name="record" /><span>Player returns</span></Link>}</div>
    {f.priced >= 5 && <details className={styles.pastReturns}><summary>Hypothetical past returns · {f.priced} priced meetings</summary><p>What a 1u bet on each player would have returned in these meetings. Two separate strategies, not a forecast.</p><dl>{f.players.map((p,i) => <div key={p.name}><dt>{p.name}</dt><dd><strong>{units(f.profit[i])}</strong><span>{percent(f.roi[i])} ROI · {f.priced}u staked</span></dd></div>)}</dl><p>Recorded odds for {f.priced} of {f.meetings} meetings. Missing prices are excluded.</p></details>}
    <p className={styles.cardQuote}>{quote ? `Pinnacle prices captured ${stamp(quote.capturedAt)}. They may have moved.` : 'No fresh paired prices available for this fixture.'}</p>
  </article>;
}


function CourtMark({ surface }: { surface: string }) {
  return <svg className={styles.courtMark} data-surface={surface} viewBox="0 0 28 28" fill="none" stroke="currentColor" strokeWidth="1.3" aria-hidden="true"><rect x="5" y="8" width="18" height="16" rx="1" strokeDasharray={surface === 'unknown' ? '2 2' : undefined} /><path d="M8 8v16m12-16v16M5 16h18m-9-8v16" />{surface === 'indoor-hard' && <path d="m3 6 11-4 11 4" />}</svg>;
}

function DecimalPrice({ value }: { value: number | undefined }) {
  if (value === undefined) return <span className={styles.compactPrice}><span aria-hidden="true">—</span><span className="sr-only">Price unavailable</span></span>;
  const [whole, fraction = '00'] = price(value).split('.');
  return <span className={styles.compactPrice}><span>{whole}.</span><span>{fraction.padEnd(2, '0')}</span></span>;
}

function FixtureRow({ fixture: f, now, showEvent }: { fixture: TennisFixture; now: Date; showEvent: boolean }) {
  const [open, setOpen] = useState(false);
  const detailId = useId();
  const quote = matchdayQuote(f, now), event = tournamentOf(f);
  return <div className={styles.fixtureRow} data-fixture={f.id}>
    <button className={styles.rowToggle} type="button" aria-expanded={open} aria-controls={detailId} onClick={() => setOpen(!open)}>
      <span className={styles.rowTime}><time dateTime={f.start}>{format(f.start, { hour: '2-digit', minute: '2-digit' })}</time>{!showEvent && <small>{event.round || (isQualifying(f) ? 'Qualifying' : '')}</small>}</span>
      {f.players.map((p, i) => <span key={i} className={styles.rowPlayer}><span className={styles.rowPlayerText}><span className={styles.rowName}>{p.name}</span><FormStrip player={p} compact /></span><DecimalPrice value={quote?.odds[i]} /></span>)}
      {showEvent && <span className={styles.rowEvent} data-surface={event.surface}><CourtMark surface={event.surface} />{event.displayName}{event.round ? ` · ${event.round}` : ''}<span className="sr-only"> · {surfaceNames[event.surface]}</span></span>}
      <span className={`${styles.rowH2h} ${!f.meetings ? styles.noCompactH2h : ''}`}>{f.meetings !== null && f.meetings > 0 ? <><strong>{f.wins?.[0]}–{f.wins?.[1]}</strong><small>{f.meetings} {f.meetings === 1 ? 'meeting' : 'meetings'}</small></> : <span aria-hidden="true">—</span>}</span>
      <span className={styles.rowArrow} aria-hidden="true">{open ? '−' : '+'}</span>
      <span className="sr-only">{open ? 'Close' : 'Open'} recent results and H2H. {quote ? `Pinnacle prices captured ${stamp(quote.capturedAt)}` : 'Paired prices unavailable or expired.'}</span>
    </button>
    <div id={detailId} hidden={!open} className={styles.expandedMatch}>{open && <FixtureCard fixture={f} now={now} />}</div>
  </div>;
}

const defaults = readBrowseState('');
export default function TennisMatchdayClient({ board, renderedAt }: { board: TennisBoard; renderedAt: string }) {
  const [state, setState] = useState<BrowseState>(defaults);
  const [now, setNow] = useState(() => new Date(renderedAt));
  useEffect(() => {
    const sync = () => setState(readBrowseState(window.location.search));
    sync(); window.addEventListener('popstate', sync);
    return () => window.removeEventListener('popstate', sync);
  }, []);
  useEffect(() => { const tick = () => setNow(new Date()); tick(); const id = setInterval(tick, 60000); return () => clearInterval(id); }, []);
  const update = (patch: Partial<BrowseState>) => {
    const next = { ...state, ...patch };
    const query = browseQuery(next, window.location.search);
    setState(next);
    try { window.history.replaceState(window.history.state, '', `${window.location.pathname}${query ? `?${query}` : ''}${window.location.hash}`); } catch { /* Keep controls usable if a browser throttles URL writes. */ }
  };
  const { tour, tournament, search, qualifying, order } = state;
  const stale = board.stale || !board.capturedAt || now.getTime() - Date.parse(board.capturedAt) > 86400000;
  const upcoming = stale ? [] : fixturesFor(board.fixtures, 'upcoming', 'all', '', now);
  const filter = displayDay(state.filter, upcoming, now);
  const dated = fixturesFor(upcoming, filter, 'all', search, now).filter(f => qualifying || !isQualifying(f));
  const candidates = dated.filter(f => tour === 'all' || f.tour === tour);
  const options = new Map<string, ReturnType<typeof tournamentOf> & { count: number }>();
  // Keep event choices across date/search changes; an empty filter never silently switches the event.
  for (const f of upcoming.filter(f => tour === 'all' || f.tour === tour)) {
    const event = tournamentOf(f);
    if (!options.has(event.key)) options.set(event.key, { ...event, count: 0 });
  }
  for (const f of candidates) { const item = options.get(tournamentOf(f).key); if (item) item.count++; }
  const selectedEvent = options.get(tournament);
  const shown = candidates.filter(f => tournament === 'all' || tournamentOf(f).key === tournament);
  const reset = (widen = false) => update({ ...defaults, filter: widen ? 'upcoming' : filter });
  const groups = new Map<string, { label: string; event: ReturnType<typeof tournamentOf> | null; fixtures: TennisFixture[] }>();
  for (const fixture of shown) {
    const date = format(fixture.start, { weekday: 'long', day: 'numeric', month: 'long' });
    const event = tournamentOf(fixture), key = `${date}:${order === 'time' ? 'time' : event.key}`;
    if (!groups.has(key)) groups.set(key, { label: date, event: order === 'time' ? null : event, fixtures: [] });
    groups.get(key)!.fixtures.push(fixture);
  }
  const priced = shown.filter(f => matchdayQuote(f, now)).length;
  return <section className={`${styles.board} ${styles.compactBoard}`} aria-labelledby="upcoming-tennis">
    <div className={styles.boardHeader}><h2 id="upcoming-tennis">Find your next match</h2><span className={styles.matchCount}>{shown.length} {shown.length === 1 ? 'match' : 'matches'}</span></div>
    <div className={styles.browseToolbar}>
      <div className={styles.browseTop}>
        <div className={styles.tabs} role="group" aria-label="Match date">{[['today', 'Today'], ['tomorrow', 'Tomorrow'], ['upcoming', 'Next 3 days']].map(([value, label]) => <button key={value} type="button" aria-pressed={filter === value} onClick={() => update({ filter: value })}>{label}<span>{fixturesFor(upcoming, value, tour, search, now).filter(f => qualifying || !isQualifying(f)).length}</span></button>)}</div>
        <label className={styles.browseSearch}><Icon name="search" /><span className="sr-only">Search player or tournament</span><input type="search" placeholder="Player or tournament" value={search} onChange={e => update({ search: e.target.value })} /></label>
      </div>
      <div className={styles.browseControls}>
        <div className={styles.miniTours} role="group" aria-label="Filter upcoming matches by tour">{tours.map(({ value, label, logo }) => <button key={value} type="button" aria-pressed={tour === value} onClick={() => update({ tour: value, tournament: 'all' })}>{logo && <Image src={logo} alt="" width={23} height={23} unoptimized />}<span>{label}</span><small>{dated.filter(f => value === 'all' || f.tour === value).length}</small></button>)}</div>
        <label className={styles.qualifyingToggle}><input type="checkbox" checked={qualifying} onChange={e => update({ qualifying: e.target.checked })} /> Include qualifying</label>
      </div>
      <div className={styles.eventStrip} role="group" aria-label="Filter upcoming matches by tournament">
        <button type="button" aria-pressed={tournament === 'all'} onClick={() => update({ tournament: 'all' })}><span>All tournaments<small>All surfaces</small></span><b>{candidates.length}</b></button>
        {[...options.values()].map(event => <button key={event.key} type="button" data-surface={event.surface} aria-pressed={tournament === event.key} onClick={() => update({ tournament: event.key })}><CourtMark surface={event.surface} /><span>{event.displayName}<small>{surfaceNames[event.surface]}</small></span><b>{event.count}<span className="sr-only"> matches</span></b></button>)}
      </div>
    </div>
    <div className={styles.listMeta}><p><strong>UK time</strong> · Provisional starts</p><div role="group" aria-label="Group fixtures"><button type="button" aria-pressed={order === 'tournament'} onClick={() => update({ order: 'tournament' })}>By tournament</button><button type="button" aria-pressed={order === 'time'} onClick={() => update({ order: 'time' })}>By time</button></div></div>
    <div className={styles.priceMeta}><Image src="/bookmakers/pinnacle.png" alt="Pinnacle" width={72} height={30} unoptimized /><p>{board.capturedAt ? <>Captured <time dateTime={board.capturedAt}>{stamp(board.capturedAt)}</time> · {priced} of {shown.length} matches with fresh paired prices.</> : 'Schedule unavailable.'} {priced ? 'Prices may have moved.' : board.capturedAt && now.getTime() - Date.parse(board.capturedAt) >= 7200000 ? 'Prices withheld: last capture over two hours old.' : 'No fresh paired prices available in this view.'} <span>— = no fresh paired price.</span></p></div>
    {board.resultsThrough && <p className={`${styles.resultFreshness} ${Date.parse(`${board.resultsThrough}T00:00:00Z`) < Date.parse(`${now.toISOString().slice(0,10)}T00:00:00Z`) - 86400000 ? styles.oldResults : ''}`}>Results archive through <strong>{format(`${board.resultsThrough}T12:00:00Z`, { day: 'numeric', month: 'short', year: 'numeric' })}</strong>. {board.resultsUpdatedAt ? `Refreshed ${stamp(board.resultsUpdatedAt)}.` : ''} Results by date, not live scores.</p>}
    <p className={styles.listKey}>Form: <strong>five latest recorded results, newest first</strong> · all surfaces · * retirement. H2H counts completed meetings. Open a match for each player’s recent results, previous meetings and deeper research.</p>
    {(tour !== 'all' || tournament !== 'all' || search || !qualifying) && <div className={styles.activeFilters}><span>{selectedEvent?.displayName || (tournament !== 'all' ? 'Selected tournament' : tour === 'all' ? 'All tours' : tour)}{search ? ` · “${search}”` : ''}{!qualifying ? ' · Main draw only' : ''}</span><button type="button" onClick={() => reset()}>Clear filters</button></div>}
    <p className="sr-only" aria-live="polite">{shown.length} upcoming {shown.length === 1 ? 'match' : 'matches'} shown</p>
    {shown.length ? [...groups].map(([key, group]) => <section className={styles.fixtureGroup} key={key} aria-label={`${group.event?.label || 'Matches'} ${group.label}`}>
      <header className={styles.groupHeading} data-surface={group.event?.surface || 'unknown'}>{group.event && <CourtMark surface={group.event.surface} />}<div><h3>{group.event?.displayName || group.label}</h3><p>{group.event ? `${group.event.tour} · ${surfaceNames[group.event.surface]} · ${group.label}` : 'All tournaments · chronological order'}</p></div><span>{group.fixtures.length}</span></header>
      <div className={styles.columnHead} aria-hidden="true"><span>START / ROUND</span><span>PLAYER 1 <b>ODDS</b></span><span>PLAYER 2 <b>ODDS</b></span><span>H2H</span><span /></div>
      {group.fixtures.map(f => <FixtureRow fixture={f} now={now} showEvent={order === 'time'} key={f.id} />)}
    </section>) : <div className={styles.empty}><h3>{stale ? 'Waiting for a fresh schedule' : 'No upcoming matches in this view'}</h3><p>{stale ? 'The schedule is unavailable or more than 24 hours old. Player research remains available below.' : `${selectedEvent ? `${selectedEvent.label}: ` : ''}try another date or clear the filters. We show captured fixtures, not a complete tennis calendar.`}</p>{!stale && <button type="button" onClick={() => reset(true)}>Show all captured fixtures</button>}</div>}
    <details className={styles.coverageDetails}><summary>Coverage &amp; update times <span aria-hidden="true">+</span></summary><p>Men’s ATP and Challenger singles, including qualifying when captured. No WTA or doubles. Paired quotes expire after two hours; schedules after 24 hours. Started matches leave the list automatically. Surface colours describe the verified edition’s court type, not its speed. Unverified editions stay neutral.</p><p>H2H through {format(`${board.historyThrough}T12:00:00Z`, { day: 'numeric', month: 'short', year: 'numeric' })}. Available completed competitive singles across ATP, Challenger, ITF, qualifying and team events. Retirements, unfinished matches, exhibitions and juniors are excluded. Coverage can be incomplete. <a href="#tennis-matchday-faq">Full explanation</a></p></details>
  </section>;
}
