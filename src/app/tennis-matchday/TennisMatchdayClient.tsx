'use client';
import TournamentReturns from './TournamentReturns';
import type { ReturnProjection } from '@/lib/tennis-tournament-returns.mjs';
import { useEffect, useId, useState } from 'react';
import Link from 'next/link';
import Image from 'next/image';
import { fixturesFor, teamTiesFor, matchdayQuote, type TennisBoard, type TennisFixture, type FixturePlayer } from '@/lib/tennis-matchday.mjs';
import { atlasResearchHref } from '@/components/return-atlas/research-links.mjs';
import { tournamentOf, isQualifying, readBrowseState, browseQuery, displayDay, type BrowseState } from '@/lib/tennis-matchday-browse.mjs';
import { countryForTournament } from '@/lib/tennis-tournament-country.mjs';
import H2HRecord from '@/components/H2HRecord';
import { resolveTennisPortrait, safeTennisPortraitSource } from '@/lib/tennis-portrait.mjs';
import MatchdayResults from './MatchdayResults';
import { Flag, Surface, TournamentRail, OptionsBar, Icon, surfaceLabel, type Country, type RailItem } from './parts';
import styles from './matchday.module.css';

const zone = 'Europe/London';
const format = (date: string, options: Intl.DateTimeFormatOptions) => new Intl.DateTimeFormat('en-GB', { timeZone: zone, ...options }).format(new Date(date));
const stamp = (date: string) => format(date, { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit', timeZoneName: 'short' });
const isDay = (day: unknown): day is string => typeof day === 'string' && /^\d{4}-\d{2}-\d{2}$/.test(day);
const dayLabel = (day: string, year: 'numeric' | '2-digit' = '2-digit') => format(`${day}T12:00:00Z`, { day: 'numeric', month: 'short', year });
const percent = (n: number | null) => n === null ? 'Not available' : `${n > 0 ? '+' : ''}${n.toFixed(1)}%`;
const surname = (name: string) => name.split(' ').slice(-1).join(' ');
const price = (n: number | null) => n !== null && Number.isFinite(n) && n > 1 ? n.toFixed(3).replace(/0$/, '') : 'Unavailable';
const units = (n: number) => `${n < 0 ? '−' : '+'}${Math.abs(n).toFixed(2)}u`;
const countryOf = (f: TennisFixture): Country => f.programme?.country ?? countryForTournament(tournamentOf(f).label, f.tour, f.start.slice(0, 10)) as Country;

// Played matches from the last 366 days only; a walkover is not form.
function recentForm(player: FixturePlayer) {
  const recent = player.recent;
  if (!recent) return [];
  return recent.matches.filter(m => m.status !== 'walkover' && Date.parse(`${recent.through}T00:00:00Z`) - Date.parse(`${m.date}T00:00:00Z`) <= 366 * 86400000).slice(0, 5);
}

function FormDots({ player }: { player: FixturePlayer }) {
  const form = recentForm(player);
  return <span className={styles.form} aria-hidden="true" title="Latest recorded results, newest first">{form.map(m => <i key={m.id} data-w={m.winner} />)}</span>;
}

function DecimalPrice({ value }: { value: number | undefined }) {
  if (value === undefined) return <span className={styles.price} data-none="true" aria-label="Pinnacle match-winner odds unavailable"><span aria-hidden="true">—</span><span className="sr-only">Price unavailable</span></span>;
  // Keep the quoted precision while giving every row the same numeric width.
  const [whole, fraction] = value.toFixed(3).split('.');
  return <span className={styles.price} aria-label={`Pinnacle match-winner decimal odds ${price(value)}`}><span className={styles.priceWhole}>{whole}.</span><span className={styles.priceFraction}>{fraction}</span></span>;
}

function OddsColumns() {
  return <div className={styles.rowColumns} aria-label="Pinnacle match-winner odds, decimal format">
    <span className={styles.columnWhen}>UK time</span>
    <span className={styles.playerColumns}><span>Player</span><span className={styles.oddsColumnTitle}>
      <span className={styles.bookieMark}><Image src="/bookmakers/pinnacle.png" alt="Pinnacle" width={132} height={55} unoptimized /></span>
      <span>Odds <span className="sr-only">in decimal format</span></span>
    </span></span>
    <span className={styles.columnH2H}>H2H</span><span aria-hidden="true" />
  </div>;
}

function Portrait({ player }: { player: FixturePlayer }) {
  const [failedSrc, setFailedSrc] = useState<string | null>(null);
  const crop = resolveTennisPortrait(player.name);
  const src = safeTennisPortraitSource(player.portrait);
  return <span className={styles.portrait}>
    {src && failedSrc !== src
      ? <Image src={src} width={72} height={72} unoptimized alt="" loading="lazy"
          style={crop?.scale ? { objectFit: 'cover', objectPosition: crop.position, transform: `scale(${crop.scale})`, transformOrigin: '50% 0%' } : undefined}
          onError={() => setFailedSrc(src)} />
      : <Icon name="person" />}
  </span>;
}

function RecentColumn({ player }: { player: FixturePlayer }) {
  const [more, setMore] = useState(false);
  const recent = player.recent;
  const old = recent?.matches[0] && Date.parse(`${recent.through}T00:00:00Z`) - Date.parse(`${recent.matches[0].date}T00:00:00Z`) > 365 * 86400000;
  return <section aria-label={`${player.name} recent results`}>
    <div className={styles.recentHead}><Portrait player={player} /><h4>{player.name}</h4></div>
    {!recent ? <p className={styles.note}>Results not linked for this player yet. The other player’s record is independent.</p>
      : !recent.matches.length ? <p className={styles.note}>No results found in the last three years of our archive.</p>
      : <>
        {old && <p className={styles.note}>Last recorded appearance: {dayLabel(recent.matches[0].date)}. This is older history.</p>}
        <ol className={styles.recentList}>{recent.matches.slice(0, more ? 10 : 5).map(m => <li key={m.id}>
          <span className={styles.badge} data-o={m.status === 'walkover' ? 'wo' : m.winner ? 'win' : 'loss'}><span aria-hidden="true">{m.status === 'walkover' ? 'W/O' : m.winner ? 'W' : 'L'}</span><span className="sr-only">{m.status === 'walkover' ? 'Walkover' : m.winner ? 'Won' : 'Lost'}</span></span>
          <div className={styles.recentBody}>
            <strong>{m.opponent}</strong>
            <small><time dateTime={m.date}>{dayLabel(m.date)}</time><span>{m.event}</span><span>{m.round}</span><Surface surface={m.surface} />{m.status === 'retired' && <span className={styles.warn}>Retirement</span>}{m.verification && <span className={styles.warn}>Retained result under review</span>}</small>
          </div>
          <span className={styles.recentScore}>{m.status === 'walkover' ? 'Not played' : m.score}</span>
        </li>)}</ol>
        {!!recent.omitted && <p className={styles.note}>{recent.omitted} {recent.omitted === 1 ? 'result with an unrecognised score omitted' : 'results with unrecognised scores omitted'} from this date window.</p>}
        {recent.matches.length > 5 && <button className={styles.more} type="button" aria-expanded={more} onClick={() => setMore(!more)}>{more ? 'Show five' : `Show ${Math.min(recent.matches.length, 10)}`}</button>}
      </>}
  </section>;
}

function Meetings({ fixture: f }: { fixture: TennisFixture }) {
  const [all, setAll] = useState(false);
  const rows = all ? f.history : f.history.slice(0, 3);
  return <>
    <ol className={styles.meetingList}>{rows.map(m => <li key={`${m.date}:${m.event}`}>
      <div><strong>{surname(f.players[m.winner].name)} won</strong> {m.score || 'Score unavailable'}
        <small>{isDay(m.date) && <><time dateTime={m.date}>{dayLabel(m.date, 'numeric')}</time> · </>}{m.event}{m.competition ? ` · ${m.competition}` : ''} · {surfaceLabel(m.surface)}</small>
        {m.priceBasis && <small>{m.priceBasis}</small>}
      </div>
      {m.odds.some(p => p !== null) && <span className={styles.meetingPrices}><span className="sr-only">Recorded odds: </span>{f.players.map((p, i) => `${surname(p.name)} ${price(m.odds[i])}`).join(' · ')}</span>}
    </li>)}</ol>
    {f.history.length > 3 && <button className={styles.more} type="button" aria-expanded={all} onClick={() => setAll(!all)}>{all ? 'Show three' : `Show all ${f.history.length} meetings`}</button>}
  </>;
}

function MatchPanel({ fixture: f, now }: { fixture: TennisFixture; now: Date }) {
  const quote = matchdayQuote(f, now);
  const through = f.players.map(p => p.recent?.through).filter(isDay).sort()[0];
  return <article aria-label={`${f.players[0].name} versus ${f.players[1].name}`}>
    <div className={styles.panelGrid}>{f.players.map(p => <RecentColumn key={p.name} player={p} />)}</div>
    <section className={styles.block} aria-label="Head-to-head">
      <div className={styles.blockHead}><h4>Head-to-head</h4><small>All recorded surfaces</small></div>
      {f.wins && f.meetings
        ? <><H2HRecord compact showCoverage={false} results={f.wins} meetings={f.meetings} names={f.players.map(p => p.name)} />
            <p className={styles.note}>{f.meetings} completed {f.meetings === 1 ? 'meeting' : 'meetings'}. Retirements and walkovers excluded.</p></>
        : <p className={styles.note}>{f.meetings === 0 ? `No completed meetings found in our archive.${isDay(f.coverageThrough) ? ` Checked ${format(`${f.coverageThrough}T12:00:00Z`, { day: 'numeric', month: 'short' })}.` : ''}`
            : f.h2hStatus === 'unchecked' ? 'H2H not checked yet. Both players’ recent results are shown above.'
            : 'H2H awaits a verified player link. Available recent results are shown above.'}</p>}
      {f.history.length > 0 && <Meetings fixture={f} />}
    </section>
    {(f.href || f.players.every(p => p.id)) && <div className={styles.links}>
      {f.href && <Link href={f.href} prefetch={false}>Explore this H2H<Icon name="arrow" /></Link>}
      {f.players.every(p => p.id) && <Link href={atlasResearchHref(f.players[0].id, f.players[1].id)} prefetch={false}><Icon name="record" />Player returns</Link>}
    </div>}
    {f.priced >= 5 && <details className={styles.returns}>
      <summary>Hypothetical past returns · {f.priced} priced meetings</summary>
      <p>What a 1u bet on each player would have returned in these meetings. Two separate strategies, not a forecast.</p>
      <dl>{f.players.map((p, i) => <div key={p.name}><dt>{p.name}</dt><dd><strong>{units(f.profit[i])}</strong><span>{percent(f.roi[i])} ROI · {f.priced}u staked</span></dd></div>)}</dl>
      <p>Recorded odds for {f.priced} of {f.meetings} meetings. Missing prices are excluded.</p>
    </details>}
    <p className={styles.panelMeta}>
      {through ? `Results archive through ${dayLabel(through, 'numeric')}, newest first, qualifying included. W/O was not played.` : 'Results coverage unavailable.'}{' '}
      {quote ? `Pinnacle prices captured ${stamp(quote.capturedAt)}; they may have moved.` : 'No fresh paired prices for this fixture.'}
    </p>
  </article>;
}

function FixtureRow({ fixture: f, now, showEvent }: { fixture: TennisFixture; now: Date; showEvent: boolean }) {
  const [open, setOpen] = useState(false);
  const detailId = useId();
  const quote = matchdayQuote(f, now), event = tournamentOf(f);
  const round = event.round || (isQualifying(f) ? 'Qualifying' : '');
  const formText = f.players.map(p => { const form = recentForm(p); return form.length ? `${p.name}: ${form.filter(m => m.winner).length} won of last ${form.length}.` : ''; }).join(' ');
  return <div className={styles.row} data-fixture={f.id} data-singles-order={f.programme?.order}>
    <button className={styles.rowBtn} type="button" aria-expanded={open} aria-controls={detailId} onClick={() => setOpen(!open)}>
      <span className={styles.when}>{f.programme ? <>{f.programme.order === 1 ? '1st' : '2nd'}<small>singles</small></>
        : <><time dateTime={f.start}>{format(f.start, { hour: '2-digit', minute: '2-digit' })}</time>{!showEvent && round && <small>{round}</small>}</>}</span>
      <span className={styles.players}>
        {f.players.map((p, i) => <span key={i} className={styles.line}><span className={styles.name}>{p.name}</span><FormDots player={p} /><DecimalPrice value={quote?.odds[i]} /></span>)}
        {showEvent && <span className={styles.eventLine}><Flag country={countryOf(f)} /><span>{event.displayName}{round ? ` · ${round}` : ''}</span><Surface surface={event.surface} /></span>}
      </span>
      <span className={styles.h2h}>{f.meetings !== null && f.meetings > 0 && <><strong>{f.wins?.[0]}–{f.wins?.[1]}</strong>H2H</>}</span>
      <span className={styles.chev}><Icon name="chevron" /></span>
      <span className="sr-only">{formText} {open ? 'Close' : 'Open'} recent results and head-to-head.</span>
    </button>
    <div id={detailId} hidden={!open} className={styles.panel}>{open && <MatchPanel fixture={f} now={now} />}</div>
  </div>;
}

const defaults = readBrowseState('');
export default function TennisMatchdayClient({ board, renderedAt, tournamentHistory }: { board: TennisBoard; renderedAt: string; tournamentHistory: ReturnProjection }) {
  const [state, setState] = useState<BrowseState>(defaults);
  const [now, setNow] = useState(() => new Date(renderedAt));
  const [searchOpen, setSearchOpen] = useState(false);
  const searchId = useId();
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
  const showSearch = searchOpen || !!search;

  // Phones: the search field sits behind one icon beside the view switch.
  const viewSwitch = <>
    <div className={styles.seg} role="group" aria-label="Browse tennis">
      <button type="button" aria-pressed={state.view === 'upcoming'} onClick={() => update({ view: 'upcoming', tournament: 'all' })}>Upcoming</button>
      <button type="button" aria-pressed={state.view === 'results'} onClick={() => update({ view: 'results', tournament: 'all' })}>Results</button>
    </div>
    <button type="button" className={styles.searchToggle} aria-expanded={showSearch} aria-controls={searchId} onClick={() => setSearchOpen(!showSearch)}>
      <Icon name="search" /><span className="sr-only">Search player or tournament</span>
    </button>
  </>;
  const searchBox = <label id={searchId} className={styles.search} data-open={showSearch}><Icon name="search" /><span className="sr-only">Search player or tournament</span>
    <input type="search" placeholder="Player or tournament" value={search} onChange={e => update({ search: e.target.value })} /></label>;

  if (state.view === 'results') return <section className={styles.browser} aria-label="Tennis Matchday results">
    <MatchdayResults board={board} state={state} update={update} now={now} viewSwitch={viewSwitch} searchBox={searchBox} />
  </section>;

  const stale = board.stale || !board.capturedAt || now.getTime() - Date.parse(board.capturedAt) > 86400000;
  const upcoming = fixturesFor(stale ? board.fixtures.filter(f => f.programme) : board.fixtures, 'upcoming', 'all', '', now);
  const ties = stale || tournament !== 'all' ? [] : teamTiesFor(board.teamTies ?? [], 'upcoming', tour, search, now);
  const filter = displayDay(state.filter, [...upcoming.filter(f => tour === 'all' || f.tour === tour), ...ties], now);
  const visibleTies = teamTiesFor(ties, filter, tour, search, now);
  const dated = fixturesFor(upcoming, filter, 'all', search, now).filter(f => qualifying || !isQualifying(f));
  const candidates = dated.filter(f => tour === 'all' || f.tour === tour);
  // Keep event choices across date/search changes; an empty filter never silently switches the event.
  const options = new Map<string, RailItem>();
  for (const f of upcoming.filter(f => tour === 'all' || f.tour === tour)) {
    const event = tournamentOf(f);
    if (!options.has(event.key)) options.set(event.key, { key: event.key, name: event.displayName, count: 0, surface: event.surface, country: countryOf(f) });
  }
  for (const f of candidates) { const item = options.get(tournamentOf(f).key); if (item) item.count++; }
  const selectedEvent = options.get(tournament);
  const shown = candidates.filter(f => tournament === 'all' || tournamentOf(f).key === tournament);
  const reset = (widen = false) => update({ ...defaults, tour: widen ? 'all' : defaults.tour, view: 'upcoming', filter: widen ? 'upcoming' : state.filter });
  const filtered = tour !== 'ATP' || tournament !== 'all' || !!search || !qualifying;

  const days = new Map<string, Map<string, { event: ReturnType<typeof tournamentOf> | null; country: Country; fixtures: TennisFixture[] }>>();
  for (const fixture of shown) {
    const date = format(fixture.start, { weekday: 'long', day: 'numeric', month: 'long' });
    const event = tournamentOf(fixture), key = order === 'time' ? 'time' : event.key;
    if (!days.has(date)) days.set(date, new Map());
    const groups = days.get(date)!;
    if (!groups.has(key)) groups.set(key, { event: order === 'time' ? null : event, country: order === 'time' ? null : countryOf(fixture), fixtures: [] });
    groups.get(key)!.fixtures.push(fixture);
  }
  const priced = shown.filter(f => matchdayQuote(f, now)).length;
  const captureAge = board.capturedAt ? now.getTime() - Date.parse(board.capturedAt) : 0;

  return <section className={styles.browser} aria-label="Tennis Matchday fixtures">
    <div className={styles.bar}>
      {viewSwitch}
      <div className={styles.days} role="group" aria-label="Match date">{[['today', 'Today'], ['tomorrow', 'Tomorrow'], ['upcoming', 'Next 3 days']].map(([value, label]) => {
        const count = fixturesFor(upcoming, value, tour, search, now).filter(f => qualifying || !isQualifying(f)).length;
        return <button key={value} type="button" aria-pressed={filter === value} data-empty={count === 0} onClick={() => update({ filter: value })}>{label}<small>{count}</small></button>;
      })}</div>
      {searchBox}
    </div>
    <TournamentRail label="Filter by tournament" items={[...options.values()]} selected={tournament} total={candidates.length} onSelect={key => update({ tournament: key })} />
    <OptionsBar tally={`${tour === 'all' ? 'All tours' : tour} · ${shown.length} ${shown.length === 1 ? 'match' : 'matches'}`} active={Number(tour !== 'ATP') + Number(!qualifying) + Number(order === 'time')}>
      <span className={styles.optGroup} role="group" aria-label="Tour">{[['all', 'All'], ['ATP', 'ATP'], ['Challenger', 'Challenger']].map(([value, label]) =>
        <button key={value} type="button" className={styles.opt} aria-pressed={tour === value} onClick={() => update({ tour: value, tournament: 'all' })}>{label}</button>)}</span>
      <label className={styles.check}><input type="checkbox" checked={qualifying} onChange={e => update({ qualifying: e.target.checked })} />Qualifying</label>
      <span className={styles.optGroup} role="group" aria-label="Order">
        <button type="button" className={styles.opt} aria-pressed={order === 'tournament'} onClick={() => update({ order: 'tournament' })}>By tournament</button>
        <button type="button" className={styles.opt} aria-pressed={order === 'time'} onClick={() => update({ order: 'time' })}>By time</button></span>
      {filtered && <button type="button" className={styles.clear} onClick={() => reset()}>Clear filters</button>}
    </OptionsBar>
    {/* One line. The bookmaker is named in words; the source time is always shown. */}
    <p className={styles.status}>
      {board.capturedAt
        ? <span><b>Pinnacle match-winner odds · decimal</b> <time dateTime={board.capturedAt}>{stamp(board.capturedAt)}</time> · {priced
            ? `${priced} of ${shown.length} priced`
            : <span className={styles.warn}>{captureAge >= 7200000 ? 'prices withheld, capture over two hours old' : 'no fresh paired prices in this view'}</span>}</span>
        : <span>Schedule unavailable</span>}
      <span className={styles.wide}>UK time · provisional starts · prices may have moved</span>
    </p>

    {visibleTies.map(tie => <section className={styles.group} key={tie.id} aria-label={tie.event + ' team tie'}>
      <header className={styles.groupHead}><div><p className={styles.groupMeta}>{tie.event} · Team tie · <time dateTime={tie.start}>{format(tie.start, { weekday: 'short', day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' })} UK</time></p>
        <h3>{tie.teams.join(' v ')}</h3><p className={styles.groupMeta}>Individual singles are listed separately when player pairings reach the schedule.</p></div></header>
    </section>)}
    {shown.length ? [...days].map(([date, groups]) => <div key={date}>
      <h2 className={styles.dayHead}>{date}</h2>
      {[...groups].map(([key, group]) => <section className={styles.group} key={key} aria-label={`${group.event?.displayName || 'All tournaments'}, ${date}`}>
        {group.event
          ? <header className={styles.groupHead} data-surface={group.event.surface}>
              <Flag country={group.country} />
              <div><h3>{group.event.displayName}</h3>
                <p className={styles.groupMeta}><span>{group.event.tour}</span>{group.country && <span>{group.country.name}</span>}<Surface surface={group.event.surface} /></p></div>
              <span className={styles.groupCount}>{group.fixtures.length}<span className="sr-only"> matches</span></span>
            </header>
          : <header className={styles.groupHead}><div><h3>All tournaments</h3><p className={styles.groupMeta}>In start order</p></div><span className={styles.groupCount}>{group.fixtures.length}</span></header>}
        {[...new Set(group.fixtures.flatMap(f => f.programme ? [f.programme.tie] : []))].map(tie =>
          <p key={tie} className={styles.status}>{tie} · Singles order of play for today.</p>)}
        {group.event?.tour === 'ATP' && group.fixtures.some(f => !isQualifying(f)) && <TournamentReturns summary={tournamentHistory.byTournament[group.event.key] || { availability: 'unavailable', name: group.event.displayName, reason: 'No audited price history is linked to this tournament edition and surface yet.' }} />}
        <OddsColumns />
        {group.fixtures.map(f => <FixtureRow fixture={f} now={now} showEvent={order === 'time'} key={f.id} />)}
      </section>)}
    </div>) : visibleTies.length ? null : <div className={styles.empty}>
      <h3>{stale ? 'Waiting for a fresh schedule' : 'No upcoming matches in this view'}</h3>
      <p>{stale ? 'The schedule is unavailable or more than 24 hours old. Results and player research remain available.' : `${selectedEvent ? `${selectedEvent.name}: ` : ''}try another date or clear the filters. We show captured fixtures, not a complete tennis calendar.`}</p>
      {!stale && <button type="button" onClick={() => reset(true)}>Show all captured fixtures</button>}
    </div>}

    <details className={styles.about}><summary>About this board</summary>
      <p>Tournament returns cover ATP main draws with audited paired Pinnacle prices. Challenger and qualifying returns are unavailable until comparable price coverage is verified. Historical returns refresh with the existing daily archive update. Each panel shows its source date; these returns are separate from today’s captured odds.</p>
      <p>Men’s ATP and Challenger singles, including qualifying when captured. No WTA or doubles. Times are UK time and provisional. Prices are paired Pinnacle quotes and may have moved; they expire after two hours, and schedules after 24 hours. A dash means no fresh paired price. Started matches leave the list automatically.</p>
      <p>Dots show each player’s latest recorded results from the last year, newest first; a filled dot is a win. H2H counts completed meetings on all surfaces. The flag is the country where the tournament is played. The coloured dot is the verified court type, not its speed; unverified editions stay neutral.</p>
      <p>{isDay(board.resultsThrough) ? `Results archive through ${dayLabel(board.resultsThrough, 'numeric')}${board.resultsUpdatedAt ? `, refreshed ${stamp(board.resultsUpdatedAt)}` : ''}. ` : ''}{isDay(board.historyThrough) ? `H2H through ${dayLabel(board.historyThrough, 'numeric')}. ` : ''}Retirements, unfinished matches, exhibitions and juniors are excluded from H2H. Coverage can be incomplete. <a href="#tennis-matchday-faq">Full explanation</a></p>
    </details>
  </section>;
}
