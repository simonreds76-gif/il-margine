import type { CSSProperties, ReactNode } from 'react';
import type { TennisBoard, CompletedResult } from '@/lib/tennis-matchday.mjs';
import type { BrowseState } from '@/lib/tennis-matchday-browse.mjs';
import { countryForTournament } from '@/lib/tennis-tournament-country.mjs';
import { Flag, Surface, TournamentRail, OptionsBar, Icon, type Country, type RailItem } from './parts';
import styles from './matchday.module.css';

const utc = (day: string, options: Intl.DateTimeFormatOptions) => new Intl.DateTimeFormat('en-GB', { timeZone: 'UTC', ...options }).format(new Date(`${day}T12:00:00Z`));
const longDay = (day: string) => utc(day, { weekday: 'long', day: 'numeric', month: 'long' });
const stamp = (date: string) => new Intl.DateTimeFormat('en-GB', { timeZone: 'Europe/London', day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit', timeZoneName: 'short' }).format(new Date(date));
const norm = (s: string) => s.normalize('NFD').replace(/\p{M}/gu, '').toLowerCase();
const countryOf = (m: CompletedResult): Country => countryForTournament(m.event, m.tour, m.date) as Country;

// Display only: lay the supplied winner-first score out as set columns.
// Anything that is not plain set scores is shown exactly as supplied.
function setColumns(score: string) {
  const tokens = score.replace(/\s*ret\.?$/i, '').trim().split(/\s+/).filter(Boolean);
  const sets = tokens.map(token => /^(\d+)-(\d+)(?:\((\d+)\))?$/.exec(token));
  if (!sets.length || sets.some(set => !set)) return null;
  return sets.map(set => ({ winner: set![1], loser: set![2], tiebreak: set![3] ?? null, wonByWinner: Number(set![1]) > Number(set![2]) }));
}

function Score({ match: m, columns }: { match: CompletedResult; columns: number }) {
  if (m.status === 'walkover') return <span className={styles.rawScore}>W/O</span>;
  const sets = setColumns(m.score);
  if (!sets) return <span className={styles.rawScore}>{m.score}</span>;
  return <><span className="sr-only">{m.score}</span><span className={styles.sets} aria-hidden="true">{Array.from({length: columns}, (_, i) => {
    const set = sets[i], cell = {'--set-index':i} as CSSProperties;
    return [
      <span key={`w${i}`} className={styles.setWinner} style={cell} data-won={set?.wonByWinner}>{set?.winner}{set?.tiebreak && !set.wonByWinner && <sup>{set.tiebreak}</sup>}</span>,
      <span key={`l${i}`} className={styles.setLoser} style={cell} data-won={set ? !set.wonByWinner : undefined}>{set?.loser}{set?.tiebreak && set.wonByWinner && <sup>{set.tiebreak}</sup>}</span>
    ];
  })}</span></>;
}

export default function MatchdayResults({ board, state, update, now, viewSwitch, searchBox }: {
  board: TennisBoard; state: BrowseState; update: (patch: Partial<BrowseState>) => void; now: Date; viewSwitch: ReactNode; searchBox: ReactNode;
}) {
  const results = board.results, all = results?.matches ?? [];
  const scoped = all.filter(m => (state.tour === 'all' || state.tour === m.tour) && (state.qualifying || !m.qualifying));
  const days = [...new Set(all.map(m => m.date))].sort().reverse();
  const latestScoped = [...new Set(scoped.map(m => m.date))].sort().reverse()[0];
  const selected = state.resultDay === 'latest' ? latestScoped : state.resultDay;
  const dated = scoped.filter(m => state.resultDay === 'all' || m.date === selected);
  const searched = dated.filter(m => norm(`${m.players.join(' ')} ${m.event}`).includes(norm(state.search)));
  const rail = new Map<string, RailItem>();
  for (const m of searched) {
    if (!rail.has(m.event)) rail.set(m.event, { key: m.event, name: m.event, count: 0, surface: m.surface, country: countryOf(m) });
    rail.get(m.event)!.count++;
  }
  const shown = searched.filter(m => state.tournament === 'all' || state.tournament === m.event);
  const byDay = new Map<string, Map<string, CompletedResult[]>>();
  for (const m of shown) {
    if (!byDay.has(m.date)) byDay.set(m.date, new Map());
    const groups = byDay.get(m.date)!;
    if (!groups.has(m.event)) groups.set(m.event, []);
    groups.get(m.event)!.push(m);
  }
  const overdue = !board.resultsUpdatedAt || now.getTime() - Date.parse(board.resultsUpdatedAt) > 36 * 3600000;
  const filtered = state.tour !== 'ATP' || state.tournament !== 'all' || !!state.search || !state.qualifying;

  return <>
    <div className={styles.bar}>
      {viewSwitch}
      <div className={styles.days} role="group" aria-label="Results date">
        {days.map((day, i) => <button key={day} type="button" aria-pressed={selected === day && state.resultDay !== 'all'}
          onClick={() => update({ resultDay: day, tournament: 'all' })}>
          <span className="sr-only">{longDay(day)}</span><span aria-hidden="true">{utc(day, { weekday: 'short', day: 'numeric' })}</span><small>{scoped.filter(m => m.date === day).length}</small></button>)}
        {days.length > 1 && <button type="button" aria-pressed={state.resultDay === 'all'} onClick={() => update({ resultDay: 'all', tournament: 'all' })}>All {days.length} days</button>}
      </div>
      {searchBox}
    </div>
    <TournamentRail label="Filter results by tournament" items={[...rail.values()]} selected={state.tournament} total={searched.length} onSelect={key => update({ tournament: key })} />
    <OptionsBar tally={`${state.tour === 'all' ? 'All tours' : state.tour} · ${shown.length} ${shown.length === 1 ? 'result' : 'results'}`} active={Number(state.tour !== 'ATP') + Number(!state.qualifying)}>
      <span className={styles.optGroup} role="group" aria-label="Tour">{[['all', 'All'], ['ATP', 'ATP'], ['Challenger', 'Challenger']].map(([value, label]) =>
        <button key={value} type="button" className={styles.opt} aria-pressed={state.tour === value} onClick={() => update({ tour: value, tournament: 'all' })}>{label}</button>)}</span>
      <label className={styles.check}><input type="checkbox" checked={state.qualifying} onChange={e => update({ qualifying: e.target.checked })} />Qualifying</label>
      {filtered && <button type="button" className={styles.clear} onClick={() => update({ tour: 'ATP', tournament: 'all', search: '', qualifying: true })}>Clear filters</button>}
    </OptionsBar>
    <p className={styles.status}>
      <span className={overdue ? styles.warn : undefined}>{board.resultsUpdatedAt ? <>Archive refreshed <time dateTime={board.resultsUpdatedAt}>{stamp(board.resultsUpdatedAt)}</time></> : 'Archive update unavailable'}{overdue ? ' · update overdue' : ''}</span>
      <span>By date, not live</span>
      {!!results?.omitted && <span className={styles.warn}>{results.omitted} {results.omitted === 1 ? 'record awaits' : 'records await'} a verified identity or score</span>}
      {!!results?.retained && <span className={styles.warn}>{results.retained} earlier {results.retained === 1 ? 'result' : 'results'} retained under review</span>}
    </p>

    {shown.length ? [...byDay].map(([day, groups]) => <div key={day}>
      <h2 className={styles.dayHead}>{longDay(day)}</h2>
      {[...groups].map(([event, rows], groupIndex) => { const first = rows[0], country = countryOf(first);
        const columns = Math.max(3, ...rows.map(m => setColumns(m.score)?.length || 0));
        return <details className={`${styles.group} ${styles.resultGroup}`} key={`${event}:${state.tournament}:${state.search}`} data-result-group={event}
          open={state.tournament !== 'all' || !!state.search || groupIndex === 0} style={{'--set-count':columns} as CSSProperties}>
          <summary className={styles.groupHead} data-surface={first.surface} aria-label={`${event}, ${rows.length} results, ${longDay(day)}`}>
            <Flag country={country} />
            <div><h3>{event}</h3><p className={styles.groupMeta}><span>{first.tour}</span>{country && <span>{country.name}</span>}<Surface surface={first.surface} /></p></div>
            <span className={styles.groupCount}>{rows.length}<span className="sr-only"> results</span></span>
          <span className={styles.groupChevron}><Icon name="chevron" /></span>
          </summary>
          <div className={styles.resultColumns}><span className={styles.resultRoundHeader}>Round</span><span>Players</span>
            <span className={styles.scoreHeading}><span>Set scores</span><span className={styles.setLabels}>{Array.from({length: columns}, (_, i) => <span key={i}>{i+1}</span>)}</span></span>
          </div>
          <ol className={styles.resultList}>{rows.map((m, i) => {
            // The archive records the winner; today that is always the first name. Read it, never assume it.
            const w = m.winner === 1 ? 1 : 0;
            const repeat = i > 0 && rows[i - 1].round === m.round;
            const tagged = m.status !== 'completed' || !!m.verification;
            return <li className={styles.resultRow} key={m.id} data-result={m.id} data-repeat={repeat} data-bare={repeat && !tagged}>
              <span className={styles.when}><small>{m.round}</small>
                {m.status === 'retired' && <span className={styles.tag}>Retired</span>}
                {m.status === 'walkover' && <span className={styles.tag}>Not played</span>}
                {m.verification && <span className={styles.tag}>Under review</span>}</span>
              <span className={styles.pair}>
                <span className={styles.won}><b>{m.players[w]}</b><Icon name="tick" /><span className="sr-only">{m.status === 'walkover' ? 'advanced by walkover' : m.status === 'retired' ? 'won by retirement' : 'won'}</span></span>
                <span><b>{m.players[1 - w]}</b></span>
              </span>
              <Score match={m} columns={columns} />
            </li>; })}</ol>
        </details>; })}
    </div>) : <div className={styles.empty}>
      <h3>No recorded results in this view</h3>
      <p>{results ? 'Try another date or clear the filters. Missing records do not mean no matches were played.' : 'The results snapshot is unavailable. The upcoming schedule is separate.'}</p>
      {results && <button type="button" onClick={() => update({ resultDay: 'all', tour: 'all', tournament: 'all', search: '', qualifying: true })}>Show all recorded results</button>}
    </div>}

    <details className={styles.about}><summary>About these results</summary>
      <p>Men’s ATP and Challenger singles, qualifying included, for the latest seven completed calendar days{results ? ` (${utc(results.from, { day: 'numeric', month: 'short' })} to ${utc(new Date(Date.parse(`${results.before}T12:00:00Z`) - 86400000).toISOString().slice(0, 10), { day: 'numeric', month: 'short', year: 'numeric' })})` : ''}. Completed records by date, not live scores. The winner is shown first. Small figures are tie-break points. Retirements and walkovers are labelled; a walkover was not played. No completion time is supplied.</p>
      <p>Updated by the daily archive publication after a verified source refresh. Today’s matches are held for the next dated update; a scheduled start is never treated as a completed result. The flag is the country where the tournament is played; the coloured dot is the court type. The archive can be incomplete. Results are independent of price availability and do not change historical bets or model records.</p>
    </details>
  </>;
}
