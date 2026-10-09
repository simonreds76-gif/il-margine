'use client';
import { useEffect, useState } from 'react';
import Link from 'next/link';
import Image from 'next/image';
import { fixturesFor, matchdayQuote, type TennisBoard, type TennisFixture, type FixturePlayer } from '@/lib/tennis-matchday.mjs';
import { atlasResearchHref } from '@/components/return-atlas/research-links.mjs';
import styles from './matchday.module.css';

const zone = 'Europe/London';
const format = (date: string, options: Intl.DateTimeFormatOptions) => new Intl.DateTimeFormat('en-GB', { timeZone: zone, ...options }).format(new Date(date));
const stamp = (date: string) => format(date, { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit', timeZoneName: 'short' });
const percent = (n: number | null) => n === null ? 'Not available' : `${n > 0 ? '+' : ''}${n.toFixed(1)}%`;
const surname = (name: string) => name.split(' ').slice(-1).join(' ');
const price = (n: number | null) => n !== null && Number.isFinite(n) && n > 1 ? n.toFixed(3).replace(/0$/, '') : 'Unavailable';
const cash = (n: number) => `${n < 0 ? '−' : '+'}£${Math.abs(n).toFixed(2)}`;

function MeetingHistory({ fixture: f }: { fixture: TennisFixture }) {
  return <details className={styles.meetings}>
    <summary><span>All {f.history.length} {f.history.length === 1 ? 'meeting' : 'meetings'} & odds</span><Icon name="arrow" /></summary>
    <p className={styles.historyKey}>Recorded odds for each match. Profit or loss assumes £10 on each player separately. Scores show the winner first.</p>
    <ol className={styles.historyList}>{f.history.map(m => {
      const priced = m.odds.every(p => p !== null && Number.isFinite(p) && p > 1);
      return <li className={styles.historyMatch} key={`${m.date}:${m.event}`}>
        <div className={styles.historyHeading}><time dateTime={m.date}>{format(`${m.date}T12:00:00Z`, { day: 'numeric', month: 'short', year: 'numeric' })}</time><span>{m.surface.replace('-', ' ')}</span></div>
        <p className={styles.historyEvent}>{m.event}</p>
        <p className={styles.historyResult}><strong>{surname(f.players[m.winner].name)} won</strong><span>{m.score || 'Score unavailable'}</span></p>
        <dl className={styles.historyPrices}>{f.players.map((p, i) => <div key={p.name}><dt>{surname(p.name)} odds</dt><dd><strong>{price(m.odds[i])}</strong><span>{priced ? cash((m.winner === i ? (m.odds[i] as number) - 1 : -1) * 10) : 'Excluded from ROI'}</span></dd></div>)}</dl>
      </li>;
    })}</ol>
    <div className={styles.historyTotal}><p>{f.priced} priced {f.priced === 1 ? 'meeting' : 'meetings'} · £{f.priced * 10} staked on each player</p><dl>{f.players.map((p, i) => <div key={p.name}><dt>{surname(p.name)}</dt><dd>{cash(f.profit[i] * 10)}<small>{percent(f.roi[i])} ROI</small></dd></div>)}</dl></div>
  </details>;
}

function Icon({ name }: { name: 'clock' | 'arrow' | 'person' | 'record' | 'search' }) {
  return <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
    {name === 'clock' ? <><circle cx="12" cy="12" r="8.5" /><path d="M12 7v5l3 2" /></> : name === 'arrow' ? <path d="M5 12h14m-6-6 6 6-6 6" /> : name === 'person' ? <><circle cx="12" cy="8" r="3.5" /><path d="M4 21v-2a8 8 0 0 1 16 0v2" /></> : name === 'record' ? <><path d="M4 19h16M6 15V9m6 6V5m6 10v-7" /><path d="m4 7 5-3 5 2 6-4" /></> : <><circle cx="10" cy="10" r="6" /><path d="m15 15 5 5" /></>}
  </svg>;
}

function Portrait({ player }: { player: FixturePlayer }) {
  const [failed, setFailed] = useState(false);
  return <span className={styles.portrait}>{player.portrait && !failed
    ? <Image src={player.portrait} width={72} height={72} unoptimized alt="" loading="lazy" onError={() => setFailed(true)} />
    : <Icon name="person" />}</span>;
}

function FixtureCard({ fixture: f, now }: { fixture: TennisFixture; now: Date }) {
  const limited = f.meetings !== null && f.meetings > 0 && f.meetings < 10;
  const quote = matchdayQuote(f, now);
  const bothPositive = f.roi.every(p => p !== null && p > 0);
  const oneWin = bothPositive && f.priced === f.meetings ? f.players.findIndex((_, i) => f.wins?.[i] === 1) : -1;
  const winningPrice = oneWin >= 0 ? f.history.find(m => m.winner === oneWin)?.odds[oneWin] : null;
  return <article className={styles.card}>
    <div className={styles.cardTop}><span className={styles.event}><span className={styles.tour}>{f.tour}</span>{f.event}{f.qualifying && <span>Qualifying</span>}</span><time dateTime={f.start}><Icon name="clock" />{format(f.start, { hour: '2-digit', minute: '2-digit' })}</time></div>
    <div className={styles.match}><div><Portrait player={f.players[0]} /><h3>{f.players[0].name}</h3></div><span className={styles.versus}>VS</span><div><Portrait player={f.players[1]} /><h3>{f.players[1].name}</h3></div></div>
    <div className={styles.quote}>
      <div className={styles.quoteHeading}><span>UPCOMING MATCH ODDS</span><span>Pinnacle</span></div>
      {quote ? <><dl>{f.players.map((p, i) => <div key={p.name}><dt>{surname(p.name)}</dt><dd>{price(quote.odds[i])}</dd></div>)}</dl><p>Recorded <time dateTime={quote.capturedAt}>{stamp(quote.capturedAt)}</time>. Prices may have moved.</p></>
        : <p>{f.quote ? 'Price too old to display. Waiting for a fresh capture.' : 'No paired price captured for this match yet.'}</p>}
    </div>
    <div className={styles.record}>
      <div className={styles.recordLabel}><span>ARCHIVE H2H</span><small>{f.meetings === null ? 'Player coverage missing' : f.meetings === 0 ? 'No recorded meetings' : `${f.meetings} ${f.meetings === 1 ? 'meeting' : 'meetings'} · all courts`}</small></div>
      {f.wins && f.meetings ? <><div className={styles.score}><strong>{f.wins[0]}<small>{surname(f.players[0].name)} wins</small></strong><div className={styles.bars} aria-label={`${f.players[0].name} ${f.wins[0]} wins, ${f.players[1].name} ${f.wins[1]} wins`}><span style={{ flex: f.wins[0] || .03 }} /><span style={{ flex: f.wins[1] || .03 }} /></div><strong>{f.wins[1]}<small>{surname(f.players[1].name)} wins</small></strong></div>
        <div className={styles.returns}><span><Icon name="record" />H2H ROI<small>{f.priced} priced {f.priced === 1 ? 'match' : 'matches'}</small></span>{f.roi.map((value, i) => <strong key={i} className={value !== null && value > 0 ? styles.positive : styles.neutral}>{percent(value)}<small>{surname(f.players[i].name)}</small></strong>)}</div>
        <p className={styles.roiKey}>Backing each player separately in every recorded meeting.</p>
        {bothPositive && <p className={styles.explanation}>{oneWin >= 0 && winningPrice ? `${surname(f.players[oneWin].name)}’s win at ${price(winningPrice)} covered ${f.priced - 1} losing ${f.priced - 1 === 1 ? 'bet' : 'bets'}.` : 'A win at long odds can cover several losses.'} Both historical returns can be positive.</p>}
        {limited && <p className={styles.sample}>Only {f.meetings} {f.meetings === 1 ? 'meeting' : 'meetings'}. One result can change the ROI sharply.</p>}</> : <p className={styles.noHistory}>{f.meetings === null ? 'We do not yet have a profile for both players in this pairing. Explore other players in Matchup Lab.' : 'No completed meetings found in our ATP archive since 2022. You can still compare the players’ wider profiles.'}</p>}
    </div>
    {f.history.length > 0 && <MeetingHistory fixture={f} />}
    <div className={styles.actions}>{f.href ? <Link href={f.href} prefetch={false}><Image src="/tennis-matchup/court-v1.webp" alt="" width={27} height={27} unoptimized /><span>Explore this H2H</span><Icon name="arrow" /></Link> : <Link href="/tennis-matchup" prefetch={false}><span>Search Matchup Lab</span><Icon name="arrow" /></Link>}
      {f.players.every(p => p.id) && <Link href={atlasResearchHref(f.players[0].id, f.players[1].id)} prefetch={false} title="Open both players’ records against all opponents"><Icon name="record" /><span>Player returns</span></Link>}
    </div>
  </article>;
}

export default function TennisMatchdayClient({ board, renderedAt }: { board: TennisBoard; renderedAt: string }) {
  const [filter, setFilter] = useState('upcoming'), [tour, setTour] = useState('ATP'), [search, setSearch] = useState('');
  const [now, setNow] = useState(() => new Date(renderedAt));
  useEffect(() => { const tick = () => setNow(new Date()); tick(); const id = setInterval(tick, 60000); return () => clearInterval(id); }, []);
  const stale = board.stale || !board.capturedAt || now.getTime() - Date.parse(board.capturedAt) > 86400000;
  const shown = stale ? [] : fixturesFor(board.fixtures, filter, tour, search, now);
  const groups = new Map<string, TennisFixture[]>();
  for (const fixture of shown) {
    const date = format(fixture.start, { weekday: 'long', day: 'numeric', month: 'long' });
    groups.set(date, [...(groups.get(date) ?? []), fixture]);
  }
  return <section className={styles.board} aria-labelledby="upcoming-tennis">
    <div className={styles.boardHeader}><div><p className={styles.eyebrow}>NEXT ON COURT</p><h2 id="upcoming-tennis">Upcoming matches</h2></div><div className={styles.summary}><strong>{shown.length}</strong><span>{shown.length === 1 ? 'match' : 'matches'}<small>{shown.filter(f => (f.meetings ?? 0) > 0).length} with H2H</small></span></div></div>
    <div className={styles.toolbar}><div className={styles.tabs} role="group" aria-label="Match date">{[['upcoming', 'Next 3 days'], ['today', 'Today'], ['tomorrow', 'Tomorrow']].map(([value, label]) => <button key={value} type="button" aria-pressed={filter === value} onClick={() => setFilter(value)}>{label}<span>{stale ? 0 : fixturesFor(board.fixtures, value, tour, '', now).length}</span></button>)}</div><div className={styles.filters}><label><span>Competition</span><select value={tour} onChange={e => setTour(e.target.value)}><option value="ATP">ATP</option><option value="Challenger">Challenger</option><option value="all">All captured singles</option></select></label><label className={styles.search}><span>Player or tournament</span><span className={styles.searchInput}><Icon name="search" /><input type="search" placeholder="Search the fixtures" value={search} onChange={e => setSearch(e.target.value)} /></span></label></div></div>
    <p className={styles.feed}><Icon name="clock" /><span>UK time ({format(now.toISOString(), { timeZoneName: 'short' }).split(' ').at(-1)}). Schedule may change. {board.capturedAt ? <>Schedule captured <time dateTime={board.capturedAt}>{stamp(board.capturedAt)}</time>.</> : 'Schedule unavailable.'} Odds are recorded snapshots; quotes over two hours old are hidden.</span></p>
    <p className={styles.coverage}>H2H history: ATP main draws since 2022, through {format(`${board.historyThrough}T12:00:00Z`, { day: 'numeric', month: 'short', year: 'numeric' })}. Includes only the completed, priced matches in our archive. <a href="#tennis-matchday-faq">What this covers</a></p>
    <p className="sr-only" aria-live="polite">{shown.length} upcoming {shown.length === 1 ? 'match' : 'matches'} shown</p>
    {shown.length ? [...groups].map(([date, fixtures]) => <section className={styles.day} key={date} aria-label={date}><h3>{date}<span>{fixtures.length} {fixtures.length === 1 ? 'match' : 'matches'}</span></h3><div className={styles.grid}>{fixtures.map(fixture => <FixtureCard fixture={fixture} now={now} key={fixture.id} />)}</div></section>) : <div className={styles.empty}><Image src="/tennis-matchday/mark.svg" alt="" width={56} height={56} unoptimized /><h3>{stale ? 'Waiting for a fresh schedule' : 'No upcoming matches in this view'}</h3><p>{stale ? 'The feed is unavailable or its capture is more than 24 hours old. Player research is still available below.' : 'Try another day or competition. This board shows the fixtures captured by our feed, so an empty list does not mean no tennis is being played.'}</p>{!stale && <button onClick={() => { setFilter('upcoming'); setTour('all'); setSearch(''); }}>Show all captured fixtures</button>}</div>}
  </section>;
}
