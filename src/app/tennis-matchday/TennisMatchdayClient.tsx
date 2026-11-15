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
    <summary><span>All {f.history.length} {f.history.length === 1 ? 'meeting' : 'meetings'} & odds</span><Icon name="arrow" /></summary>
    <p className={styles.historyKey}>Recorded odds for each match. Profit or loss assumes a fixed 1u stake on each player separately. Scores show the winner first.</p>
    <ol className={styles.historyList}>{f.history.map(m => {
      const priced = m.odds.every(p => p !== null && Number.isFinite(p) && p > 1);
      return <li className={styles.historyMatch} key={`${m.date}:${m.event}`}>
        <div className={styles.historyHeading}><time dateTime={m.date}>{format(`${m.date}T12:00:00Z`, { day: 'numeric', month: 'short', year: 'numeric' })}</time><span>{m.surface.replace('-', ' ')}</span></div>
        <p className={styles.historyEvent}>{m.event}{m.competition ? ` · ${m.competition}` : ''}</p>
        <p className={styles.historyResult}><strong>{surname(f.players[m.winner].name)} won</strong><span>{m.score || 'Score unavailable'}</span></p>
        <dl className={styles.historyPrices}>{f.players.map((p, i) => <div key={p.name}><dt>{surname(p.name)} odds</dt><dd><strong>{price(m.odds[i])}</strong><span>{priced ? units(m.winner === i ? (m.odds[i] as number) - 1 : -1) : 'Excluded from ROI'}</span></dd></div>)}</dl>
        {m.priceBasis && <p className={styles.historyKey}>{m.priceBasis}</p>}
      </li>;
    })}</ol>
    <div className={styles.historyTotal}><p>{f.priced} priced {f.priced === 1 ? 'meeting' : 'meetings'} · {f.priced}u staked on each player</p><dl>{f.players.map((p, i) => <div key={p.name}><dt>{surname(p.name)}</dt><dd>{f.priced ? units(f.profit[i]) : 'Not available'}<small>{percent(f.roi[i])} ROI</small></dd></div>)}</dl></div>
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

function FixtureCard({ fixture: f, now }: { fixture: TennisFixture; now: Date }) {
  const limited = f.meetings !== null && f.meetings > 0 && f.meetings < 10;
  const quote = matchdayQuote(f, now);
  const bothPositive = f.roi.every(p => p !== null && p > 0);
  const oneWin = bothPositive && f.priced === f.meetings ? f.players.findIndex((_, i) => f.wins?.[i] === 1) : -1;
  const winningPrice = oneWin >= 0 ? f.history.find(m => m.winner === oneWin)?.odds[oneWin] : null;
  return <article className={styles.card} aria-label={`${f.players[0].name} versus ${f.players[1].name}`}>
    <div className={styles.cardTop}><span className={styles.event}><span className={styles.tour}>{f.tour}</span>{f.event}{f.qualifying && <span>Qualifying</span>}</span><time dateTime={f.start}><Icon name="clock" />{format(f.start, { hour: '2-digit', minute: '2-digit' })}</time></div>
    <div className={styles.match}><div><Portrait player={f.players[0]} /><h4>{f.players[0].name}</h4></div><span className={styles.versus}>VS</span><div><Portrait player={f.players[1]} /><h4>{f.players[1].name}</h4></div></div>
    <div className={styles.quote}>
      <div className={styles.quoteHeading}><span>UPCOMING MATCH ODDS</span><span className={styles.quoteBookmaker}><Image src="/bookmakers/pinnacle.png" alt="Pinnacle" width={104} height={43} unoptimized /></span></div>
      {quote ? <><dl>{f.players.map((p, i) => <div key={p.name}><dt>{surname(p.name)}</dt><dd>{price(quote.odds[i])}</dd></div>)}</dl><p>Recorded <time dateTime={quote.capturedAt}>{stamp(quote.capturedAt)}</time>. Prices may have moved.</p></>
        : <p>{f.quote ? 'Price too old to display. Waiting for a fresh capture.' : 'No paired price captured for this match yet.'}</p>}
    </div>
    <div className={styles.record}>
      <div className={styles.recordLabel}><span>PLAYER H2H</span><small>{f.meetings === null ? 'Player coverage missing' : f.meetings === 0 ? 'No recorded meetings' : 'All surfaces'}</small></div>
      {f.resultsOnly && <p className={styles.h2hScope}>Results only · no priced player profile. Archive checked {format(`${f.coverageThrough}T12:00:00Z`, { day: 'numeric', month: 'short' })}.</p>}
      {f.meetings !== null && f.meetings > 0 && <p className={styles.h2hScope}>Completed meetings across recorded tournaments</p>}
      {f.wins && f.meetings ? <><H2HRecord compact results={f.wins} meetings={f.meetings} names={f.players.map(p => p.name)} />
        <div className={styles.returns}><span><Icon name="record" />Past H2H ROI<small>Odds for {f.priced} of {f.meetings} {f.meetings === 1 ? 'meeting' : 'meetings'}</small></span>{f.roi.map((value, i) => <strong key={i} className={value !== null && value > 0 ? styles.positive : styles.neutral}>{percent(value)}<small>{surname(f.players[i].name)}</small></strong>)}</div>
        {f.priced < f.meetings && <p className={styles.explanation}><strong>Odds missing for {f.meetings - f.priced} {f.meetings - f.priced === 1 ? 'meeting' : 'meetings'}.</strong> {f.priced ? `ROI uses only the ${f.priced} with recorded odds.` : 'ROI is unavailable.'} The H2H score includes every recorded meeting.</p>}
        <p className={styles.roiKey}>1u on each player separately at recorded odds. Past returns, not a forecast.</p>
        {bothPositive && <p className={styles.explanation}>{oneWin >= 0 && winningPrice ? `${surname(f.players[oneWin].name)}’s win at ${price(winningPrice)} covered ${f.priced - 1} losing ${f.priced - 1 === 1 ? 'bet' : 'bets'}.` : 'A win at long odds can cover several losses.'} Both historical returns can be positive.</p>}
        {limited && <p className={styles.sample}>Only {f.meetings} {f.meetings === 1 ? 'meeting' : 'meetings'}. One result can change the ROI sharply.</p>}</> : <p className={styles.noHistory}>{f.meetings === null ? 'We do not yet have a profile for both players in this pairing. Explore other players in Matchup Lab.' : f.resultsOnly ? 'No completed meetings found for these players in our available competitive archive.' : 'No completed meetings found in our available competitive archive. You can still compare the players’ wider profiles.'}</p>}
    </div>
    {f.history.length > 0 && <MeetingHistory fixture={f} />}
    <div className={styles.actions}>{f.href ? <Link href={f.href} prefetch={false}><Image src="/tennis-matchup/court-v1.webp" alt="" width={27} height={27} unoptimized /><span>Explore this H2H</span><Icon name="arrow" /></Link> : <Link href="/tennis-matchup" prefetch={false}><span>Search Matchup Lab</span><Icon name="arrow" /></Link>}
      {f.players.every(p => p.id) && <Link href={atlasResearchHref(f.players[0].id, f.players[1].id)} prefetch={false} title="Open both players’ records against all opponents"><Icon name="record" /><span>Player returns</span></Link>}
    </div>
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
      {f.players.map((p, i) => <span key={i} className={styles.rowPlayer}><span className={styles.rowName}>{p.name}</span><DecimalPrice value={quote?.odds[i]} /></span>)}
      {showEvent && <span className={styles.rowEvent} data-surface={event.surface}><CourtMark surface={event.surface} />{event.displayName}{event.round ? ` · ${event.round}` : ''}<span className="sr-only"> · {surfaceNames[event.surface]}</span></span>}
      <span className={`${styles.rowH2h} ${!f.meetings ? styles.noCompactH2h : ''}`}>{f.meetings !== null && f.meetings > 0 ? <><strong>{f.wins?.[0]}–{f.wins?.[1]}</strong><small>{f.meetings} {f.meetings === 1 ? 'meeting' : 'meetings'}</small></> : <small>{f.meetings === 0 ? 'No meetings found' : 'History unavailable'}</small>}</span>
      <span className={styles.rowArrow} aria-hidden="true">{open ? '−' : '+'}</span>
      <span className="sr-only">{open ? 'Close' : 'Open'} H2H and match details. {quote ? `Pinnacle prices captured ${stamp(quote.capturedAt)}` : 'Paired prices unavailable or expired.'}</span>
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
    <p className={styles.listKey}>H2H includes recorded meetings on <strong>all surfaces</strong>. Open a match for results, returns and player profiles.</p>
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
