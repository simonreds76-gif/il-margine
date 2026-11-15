import type { TennisBoard, CompletedResult } from '@/lib/tennis-matchday.mjs';
import type { BrowseState } from '@/lib/tennis-matchday-browse.mjs';
import { surfaceNames } from '@/lib/tennis-matchday-browse.mjs';
import styles from './matchday.module.css';

const label = (day:string) => new Intl.DateTimeFormat('en-GB',{day:'numeric',month:'short',year:'numeric',timeZone:'UTC'}).format(new Date(`${day}T12:00:00Z`));
export default function MatchdayResults({board,state,update,now}:{board:TennisBoard;state:BrowseState;update:(patch:Partial<BrowseState>)=>void;now:Date}) {
  const results=board.results, all=results?.matches ?? [];
  const days=[...new Set(all.map(m=>m.date))].sort().reverse();
  const selected=state.resultDay==='latest' ? days[0] : state.resultDay;
  const dated=all.filter(m=>(state.resultDay==='all'||m.date===selected)&&(state.tour==='all'||state.tour===m.tour)&&(state.qualifying||!m.qualifying));
  const norm=(s:string)=>s.normalize('NFD').replace(/\p{M}/gu,'').toLowerCase();
  const events=[...new Set(dated.map(m=>m.event))].sort();
  const shown=dated.filter(m=>(state.tournament==='all'||state.tournament===m.event)&&norm(`${m.players.join(' ')} ${m.event}`).includes(norm(state.search)));
  const groups=new Map<string,CompletedResult[]>();
  for(const m of shown){const k=JSON.stringify([m.date,m.event,m.tour,m.surface]);if(!groups.has(k))groups.set(k,[]);groups.get(k)!.push(m);}
  const overdue=!board.resultsUpdatedAt||now.getTime()-Date.parse(board.resultsUpdatedAt)>36*3600000;
  return <section aria-label="Completed tennis results" className={styles.resultsBoard}>
    <div className={styles.boardHeader}><h2>Latest results</h2><span className={styles.matchCount}>{shown.length} matches</span></div>
    <p className={`${styles.resultFreshness} ${overdue?styles.oldResults:''}`}>{board.resultsUpdatedAt ? `Archive refreshed ${new Date(board.resultsUpdatedAt).toLocaleString('en-GB',{timeZone:'Europe/London'})} UK.` : 'Archive update unavailable.'} {overdue?'Update overdue. ':''}Completed records by date, not live scores.</p>
    <p className={styles.listKey}>Men’s ATP and Challenger singles · qualifying included · latest seven completed calendar days. Winner shown first. Retirement and walkover records are labelled; a walkover was not played. No completion time is supplied.</p>
    {!!results?.omitted && <p className={`${styles.resultFreshness} ${styles.oldResults}`}>{results.omitted} records in this window await a verified identity or score. Available results remain visible.</p>}
    {!!results?.retained && <p className={`${styles.resultFreshness} ${styles.oldResults}`}>{results.retained} previously recorded results retained while a source discrepancy is reviewed.</p>}
    <div className={styles.resultControls}>
      <label>Date<select aria-label="Results date" value={state.resultDay} onChange={e=>update({resultDay:e.target.value,tournament:'all'})}><option value="latest">Latest{days[0]?` · ${label(days[0]).replace(/ \d{4}$/,'')}`:''}</option><option value="all">All seven days</option>{days.map(d=><option key={d} value={d}>{label(d)}</option>)}</select></label>
      <label>Tour<select aria-label="Results tour" value={state.tour} onChange={e=>update({tour:e.target.value,tournament:'all'})}><option value="all">ATP &amp; Challenger</option><option value="ATP">ATP</option><option value="Challenger">Challenger</option></select></label>
      <label>Tournament<select aria-label="Results tournament" value={state.tournament} onChange={e=>update({tournament:e.target.value})}><option value="all">All tournaments</option>{events.map(e=><option key={e} value={e}>{e}</option>)}</select></label>
      <label>Search<input type="search" aria-label="Search results" value={state.search} placeholder="Player or tournament" onChange={e=>update({search:e.target.value})}/></label>
      <label className={styles.qualifyingToggle}><input type="checkbox" checked={state.qualifying} onChange={e=>update({qualifying:e.target.checked})}/> Include qualifying</label>
    </div>
    <p className="sr-only" aria-live="polite">{shown.length} result records shown</p>
    {[...groups].map(([key,rows])=>{const first=rows[0];return <section className={styles.fixtureGroup} key={key} aria-label={`${first.event} ${first.date}`}>
      <header className={styles.groupHeading} data-surface={first.surface}><div><h3>{first.event}</h3><p>{first.tour} · {surfaceNames[first.surface]||first.surface} · {label(first.date)}</p></div><span>{rows.length}</span></header>
      <ol className={styles.completedList}>{rows.map(m=><li key={m.id} data-result={m.id}>
        <span className={styles.completedRound}>{m.round}<small>{m.verification ? 'Retained · under review' : m.status==='walkover'?'Walkover · not played':m.status==='retired'?'Retirement':'Completed'}</small></span>
        <div className={styles.completedPlayers}><strong>{m.players[0]} <span className="sr-only">{m.status==='walkover'?'advanced':'won'}</span><span aria-hidden="true">✓</span></strong><span>{m.players[1]}</span></div>
        <strong className={styles.completedScore}>{m.status==='walkover'?'W/O':m.score}</strong>
      </li>)}</ol></section>})}
    {!shown.length&&<div className={styles.empty}><h3>No recorded results in this view</h3><p>{results?'Try another date or clear the filters. Missing records do not mean no matches were played.':'The results snapshot is unavailable. The upcoming schedule remains separate.'}</p><button type="button" onClick={()=>update({resultDay:'all',tour:'all',tournament:'all',search:'',qualifying:true})}>Show all recorded results</button></div>}
    <details className={styles.coverageDetails}><summary>Results coverage &amp; updates</summary><p>{results?`Recorded date window: ${label(results.from)} to ${label(new Date(Date.parse(results.before+'T12:00:00Z')-86400000).toISOString().slice(0,10))}. `:''}Updated by the existing daily archive publication after a verified source refresh. Today’s matches are held for the next dated update. This archive can be incomplete; scheduled starts are never treated as completed results. Results are independent of price availability and do not change historical bets or model records.</p></details>
  </section>;
}
