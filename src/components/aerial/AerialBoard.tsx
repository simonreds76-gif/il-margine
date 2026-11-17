'use client';
import {useEffect,useState} from 'react';
import Image from 'next/image';
import ResearchIcon from '@/components/ResearchIcon';
import type {Board,Fixture,Player,Team,WindowKey} from './types';
import {isBoard} from './types';
import {summarizeKnownHeights} from '@/lib/aerial-height-display';

const value=(n:number|null|undefined,dp=0)=>typeof n==='number'&&Number.isFinite(n)?n.toFixed(dp):'Not available';
const shortDate=(s:string)=>new Intl.DateTimeFormat('en-GB',{timeZone:'Europe/London',day:'numeric',month:'short',year:'numeric'}).format(new Date(s));
const date=(s:string)=>new Intl.DateTimeFormat('en-GB',{timeZone:'Europe/London',day:'numeric',month:'short',hour:'2-digit',minute:'2-digit',timeZoneName:'short'}).format(new Date(s));
// Presentation only. Day headings for the fixture list use the same London clock as date(); the axis marks use
// the same 155–210 cm scale as the dots they sit behind. Neither feeds a calculation.
const day=(s:string)=>new Intl.DateTimeFormat('en-GB',{timeZone:'Europe/London',weekday:'long',day:'numeric',month:'long'}).format(new Date(s));
const axisMarks=[160,170,180,190,200];
const axisAt=(cm:number)=>`${(cm-155)/55*100}%`;
type LineupState='confirmed'|'expected'|'pending'|'stale';
export function AerialIcon({kind='height'}:{kind?:string}) {
 return <ResearchIcon name={kind==='height'?'height':kind==='duel'?'duel':kind==='corner'?'delivery':'managers'}/>;
}
/** A shape for each lineup state, so the state never rests on colour alone. */
function StateIcon({kind}:{kind:LineupState}) {
 return <svg className="aerial-state-icon" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">{
  kind==='confirmed'?<path d="m5 12.5 4.5 4.5L19 7.5"/>:
  kind==='expected'?<><circle cx="12" cy="12" r="8.5" strokeDasharray="3 3.4"/><path d="m8.5 12.3 2.5 2.5 4.5-5"/></>:
  kind==='stale'?<><path d="M12 4 2.8 19.5h18.4Z"/><path d="M12 10v4.5m0 2.8v.2"/></>:
  <><circle cx="12" cy="12" r="8.5"/><path d="M12 7.5V12l3 2"/></>}</svg>;
}
function Chevron() {
 return <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d="m6 9 6 6 6-6"/></svg>;
}
function Portrait({player}:{player:Player}) {
 const [failed,setFailed]=useState<string|null>(null);
 return /^https:\/\/images\.fotmob\.com\/image_resources\/playerimages\/\d+\.png$/.test(player.photo_url)&&failed!==player.id?
 <Image unoptimized src={player.photo_url} alt="" width={44} height={48} onError={()=>setFailed(player.id)} className="aerial-photo" loading="lazy"/>:
 <span className="aerial-photo aerial-avatar" aria-label={`Photo unavailable for ${player.name}`}><AerialIcon kind="players"/></span>;
}
function TeamName({team}:{team:Team}) {
 const [failed,setFailed]=useState(false);
 return <span className="aerial-team-name">{!failed&&<Image unoptimized src={`https://images.fotmob.com/image_resources/logo/teamlogo/${team.id}.png`} alt="" width={32} height={32} onError={()=>setFailed(true)}/>}<strong>{team.name}</strong></span>;
}
function HeightPanel({team,index}:{team:Team;index:number}) {
 const h=summarizeKnownHeights(team.players);
 const ordered=h.players.toSorted((a,b)=>a.height_cm!-b.height_cm!);
 return <section className={`aerial-panel aerial-height-panel aerial-side-${index}`}>
  <div className="aerial-panel-head"><TeamName team={team}/><span className="aerial-kicker">{index?'AWAY':'HOME'}</span></div>
  <div className={`aerial-height-number${h.mean===null?' aerial-na':''}`}>{value(h.mean,1)}{h.mean!==null&&<small>{h.complete?'cm average':'cm known-player average'}</small>}</div>
  <div className={`aerial-coverage${h.complete?'':' aerial-coverage-partial'}`}>
   <span className="aerial-coverage-meter" aria-hidden="true">{Array.from({length:10},(_,slot)=><i key={slot} className={slot<h.known?'aerial-known':undefined}/>)}</span>
   <p>{h.known} of 10 outfield heights available{!h.complete?' · Partial coverage':''}</p>
  </div>
  {!h.complete&&h.missing.length>0&&<p className="aerial-note aerial-missing">Height missing: {h.missing.join(', ')}. {h.known>0?'Figures below use only the known players.':'No height summary is available yet.'}</p>}
  <div className="aerial-height-chart">
   <div className="aerial-height-plot" aria-label={`${team.name} reported player heights`}>{axisMarks.map(cm=><b key={cm} style={{left:axisAt(cm)}} aria-hidden="true"/>)}<b className="aerial-threshold" style={{left:axisAt(185)}} aria-hidden="true"/>{ordered.map((p,index)=><span key={p.id} style={{left:`${Math.max(0,Math.min(100,(p.height_cm!-155)/55*100))}%`,top:`${12+(index%3)*16}px`}} tabIndex={0} aria-label={`${p.name}, ${p.height_cm} centimetres`}><i/><em>{p.name}: {p.height_cm} cm</em></span>)}</div>
   <div className="aerial-axis" aria-hidden="true">{axisMarks.map(cm=><span key={cm} style={{left:axisAt(cm)}}>{cm}</span>)}</div>
   <p className="aerial-plot-caption">Each dot is one outfield starter with a reported height, in cm. Dashed line: 185 cm.</p>
  </div>
  {ordered.length>0&&<details className="aerial-height-list"><summary>List the {ordered.length} reported heights</summary><ol>{ordered.toReversed().map(p=><li key={p.id}><span>{p.name}</span><strong>{p.height_cm} cm</strong></li>)}</ol></details>}
  <div className="aerial-height-extras">
   <span>{h.complete?'Tallest three, average':'Tallest three known, average'}<strong className={h.tallestThreeMean===null?'aerial-na':undefined}>{value(h.tallestThreeMean,1)}{h.tallestThreeMean!==null?' cm':''}</strong></span>
   <span>{h.complete?'Outfield starters ≥185 cm':'Known outfield starters ≥185 cm'}<strong className={h.atLeast185===null?'aerial-na':undefined}>{h.atLeast185===null?'Not available':`${h.atLeast185} / ${h.known}${h.complete?'':' known'}`}</strong></span>
  </div>
 </section>;
}
function Section({id,kind,title,text}:{id:string;kind:string;title:string;text:string}) {
 return <header id={id} className="aerial-section-heading"><span className="aerial-icon"><AerialIcon kind={kind}/></span><div><h2>{title}</h2><p>{text}</p></div></header>;
}
function Players({team,windowKey}:{team:Team;windowKey:WindowKey}) {
 const [role,setRole]=useState('all'); const [sort,setSort]=useState('height');
 const players=team.players.filter(p=>p.role!=='GK'&&(role==='all'||role===p.role)).toSorted((a,b)=>{
   const metric=(p:Player)=>sort==='headers'?p.histories[windowKey].headers_per90:sort==='duels'?(p.histories[windowKey].aerial_attempts>=20?p.histories[windowKey].aerial_win_pct:null):p.height_cm;
   return (metric(b)??-1)-(metric(a)??-1)||a.name.localeCompare(b.name);
 });
 return <section className="aerial-panel aerial-players"><div className="aerial-table-controls"><TeamName team={team}/><label>Role<select value={role} onChange={e=>setRole(e.target.value)}><option value="all">All outfield players</option><option value="DEF">Defenders</option><option value="MID">Midfielders</option><option value="ATT">Attacking players</option></select></label><label>Sort by<select value={sort} onChange={e=>setSort(e.target.value)}><option value="height">Reported height</option><option value="headers">Headed shots per 90</option><option value="duels">Aerial success</option></select></label></div>
 <div className="aerial-table-head" aria-hidden="true"><span>Player</span><span>Height</span><span>Duels won</span><span>Headed shots</span><span>Minutes</span><span>Matches</span></div>
 {players.map(p=>{const h=p.histories[windowKey];return <details className="aerial-player" key={p.id}><summary><span className="aerial-person"><Portrait player={p}/><span><strong>{p.name}</strong><small>{p.role==='UNK'?'Role unavailable':p.role} · {h.matches} matches{h.small_sample?<b className="aerial-limited">Limited data</b>:null}</small></span></span><span><small>Reported height</small>{value(p.height_cm)}{p.height_cm!==null?' cm':''}</span><span><small>Aerial duels won</small>{value(h.aerial_win_pct,0)}{h.aerial_win_pct!==null?'%':''}<em>{h.aerial_won} of {h.aerial_attempts} contests</em></span><span><small>Headed shots</small>{h.head_matches?h.headed_shots:'Not available'}<em>{value(h.headers_per90,2)} per 90</em></span><span><small>Playing time</small>{h.minutes.toLocaleString()}<em>minutes</em></span><span className="aerial-row-toggle"><span className="aerial-row-toggle-open">Show matches</span><span className="aerial-row-toggle-close">Hide matches</span><Chevron/></span></summary><div className="aerial-player-detail"><p>{p.height_source?'Reported height verified':'Height has not been verified.'}{p.height_observed_at?` · Checked ${p.height_observed_at.slice(0,10)}`:''}</p>
 <div className="aerial-scroll" role="region" aria-label={`${p.name} earlier matches`} tabIndex={0}><table><thead><tr><th>Date / match</th><th>Minutes</th><th>Duels won / attempted</th><th>Headed shots</th></tr></thead><tbody>{h.appearances.map(a=><tr key={a.fixture_id}><td>{a.date}<strong>{a.match}</strong></td><td>{a.minutes}</td><td>{value(a.won)} / {value(a.attempts)}</td><td>{value(a.headed_shots)}</td></tr>)}</tbody></table></div>{!h.matches&&<p>No earlier appearances in this archive.</p>}</div></details>})}
 {!players.length&&<p>No starters in this role.</p>}<p className="aerial-note">Roles describe usual positions. They do not assign attacking targets or marking duties. Aerial success needs at least 20 contests to enter the sort order.</p></section>;
}
function Comparison({fixture,windowKey}:{fixture:Fixture;windowKey:WindowKey}) {
 const [ids,setIds]=useState<string[]>([]);
 const chosen=fixture.teams.map((t,i)=>t.players.find(p=>p.id===ids[i])||t.players.filter(p=>p.role!=='GK').toSorted((a,b)=>(b.height_cm??0)-(a.height_cm??0))[0]);
 return <section className="aerial-panel aerial-compare"><div className="aerial-compare-pickers">{fixture.teams.map((t,i)=><label key={t.id}><TeamName team={t}/><span className="aerial-person"><Portrait player={chosen[i]}/><select value={chosen[i].id} onChange={e=>setIds(old=>{const n=[...old];n[i]=e.target.value;return n})}>{t.players.filter(p=>p.role!=='GK').map(p=><option key={p.id} value={p.id}>{p.name}</option>)}</select></span></label>)}</div>
 <div className="aerial-compare-rows">{(['Reported height','Aerial contests won','Headed shots','Playing time'] as const).map((label,i)=><div className="aerial-compare-row" key={label}><strong>{metric(chosen[0],i,windowKey)}</strong><span>{label}</span><strong>{metric(chosen[1],i,windowKey)}</strong></div>)}</div><p className="aerial-comparison-note">Two player records side by side. This is not a predicted marking matchup.</p></section>;
}
function metric(p:Player,i:number,w:WindowKey) {const h=p.histories[w];return i===0?(p.height_cm===null?'Not available':`${p.height_cm} cm`):i===1?(h.duel_matches?`${h.aerial_won} / ${h.aerial_attempts}`:'Not available'):i===2?(h.head_matches?`${h.headed_shots} in ${h.head_matches} matches`:'Not available'):`${h.minutes} minutes`;}
function Overall({f,w}:{f:Fixture;w:WindowKey}) {
 const heights=f.teams.map(t=>t.height.mean_cm); const d=f.teams.map(t=>t.histories[w]);
 const enough=heights.every(h=>h!==null)&&d.every(x=>x.corners.matches>=3&&x.crosses.matches>=3);
 let text='A combined comparison needs all ten outfield heights on each side and at least three earlier matches with corners and crosses. Explore the available figures above.';
 if(enough){const gap=heights[0]!-heights[1]!;const c=d[0].corners.average!-d[1].corners.average!;const x=d[0].crosses.average!-d[1].crosses.average!;
 text=(Math.abs(gap)<1?`The average heights are ${Math.abs(gap).toFixed(1)} cm apart. `:`${f.teams[gap>0?0:1].name} are ${Math.abs(gap).toFixed(1)} cm taller on average. `)+(c*x>0?`${f.teams[c>0?0:1].name} recorded more corners and attempted crosses in the covered matches. `:'The corners and crosses records do not both favour the same side. ')+'Read that alongside the players’ aerial contests and headed shots. These figures describe size and involvement, not the chance of scoring.';}
 return <section className={`aerial-verdict${enough?'':' aerial-verdict-pending'}`}><span className="aerial-kicker">THE OVERALL READ</span><h2>{enough?'How the pieces fit together':'More evidence needed'}</h2><p>{text}</p></section>;
}
function Match({f,board,now}:{f:Fixture;board:Board;now:number}) {
 const [w,setW]=useState<WindowKey>('recent');
 const active=(f.state==='confirmed'||f.state==='expected')&&now<Date.parse(f.valid_until)&&now-Date.parse(board.generated_at)>=-300_000&&now-Date.parse(board.generated_at)<36*3600_000&&now-Date.parse(board.calendar_observed_at)<36*3600_000;
 // Styling hook only. It follows the same branches as the label below: active confirmed or expected, pending, otherwise stale.
 const state:LineupState=active?(f.state==='confirmed'?'confirmed':'expected'):f.state==='pending'?'pending':'stale';
 const windowLabel=w==='recent'?'Both seasons':w==='current'?board.seasons[0]:board.seasons[1];
 return <><section className={`aerial-match aerial-match-${state}`}><div className="aerial-status"><span>{f.competition} · {date(f.kickoff)}</span><strong className={`aerial-state aerial-state-${state}${active?' aerial-badge':''}`}><StateIcon kind={state}/>{active?(f.state==='confirmed'?'Confirmed XI':'Expected XI'):f.state==='pending'?'Awaiting lineups':'Lineup no longer current'}</strong></div><div className="aerial-teams">{f.teams.map((t,i)=><div key={t.id}><span className="aerial-kicker">{i?'AWAY':'HOME'}</span><TeamName team={t}/><p>{active?t.formation:'Lineup not available'}</p></div>)}</div>{active&&<p className="aerial-note">Lineup seen {date(f.observed_at!)}. {f.state==='expected'?'These players may change before kickoff.':''}</p>}</section>
 {!active?<div className={`aerial-empty aerial-empty-${state}`}><span className="aerial-empty-icon">{state==='pending'?<AerialIcon kind="players"/>:<StateIcon kind="stale"/>}</span><div><h2>{f.state==='pending'?'The fixture is scheduled. Lineups are still pending.':'This lineup needs a fresh check.'}</h2><p>The height and player comparison appears when a current expected or confirmed XI is available for both teams.</p><p>Expected XIs come first. Confirmed teams replace them when available. We look for lineups for today and the next three days; fixtures further away can appear here before their teams.</p>
  {state==='pending'&&<><p className="aerial-upcoming-label">With the lineup you will see</p><ul className="aerial-upcoming"><li><ResearchIcon name="height"/>Height</li><li><ResearchIcon name="duel"/>Players</li><li><ResearchIcon name="delivery"/>Delivery</li></ul></>}</div></div>:<>
 <nav className="aerial-jumps" aria-label="On this page"><a href="#height"><ResearchIcon name="height"/>Height</a><a href="#players"><ResearchIcon name="duel"/>Players</a><a href="#delivery"><ResearchIcon name="delivery"/>Delivery</a></nav>
 <Section id="height" kind="height" title="Size across the starting XI" text="Reported heights of the ten outfield starters. Goalkeepers are kept separate."/>
 <div className="aerial-height-grid">{f.teams.map((t,i)=><HeightPanel key={t.id} team={t} index={i}/>)}</div>
 <Section id="players" kind="duel" title="Who actually uses their height?" text="Compare two starters, then open the matches behind every player’s figures."/>
 <div className="aerial-history-control"><label>Choose the history<select value={w} onChange={e=>setW(e.target.value as WindowKey)}><option value="recent">Both seasons</option><option value="current">{board.seasons[0]}</option><option value="previous">{board.seasons[1]}</option></select></label><p>Up to 10 covered appearances per player and five earlier matches per team. Always before this fixture.</p><p className="aerial-history-scope">Applies to the player figures here and to Delivery below. Heights do not change.</p></div>
 <Comparison key={f.id} fixture={f} windowKey={w}/>{f.teams.map(t=><Players key={t.id} team={t} windowKey={w}/>)}
 <Section id="delivery" kind="corner" title="The delivery into the box" text="Recent corners and attempted crosses show how often each side supplied the box. They do not measure delivery quality."/>
 <p className="aerial-window-note">History shown: <strong>{windowLabel}</strong>. <a href="#players">Change it in Players</a></p>
 <div className="aerial-height-grid aerial-delivery-grid">{f.teams.map((t,i)=><section className={`aerial-panel aerial-side-${i}`} key={t.id}><div className="aerial-panel-head"><TeamName team={t}/><span className="aerial-kicker">{i?'AWAY':'HOME'}</span></div><div className="aerial-delivery">{(['corners','crosses'] as const).map(k=><div key={k}><strong className={t.histories[w][k].average===null?'aerial-na':undefined}>{value(t.histories[w][k].average,1)}</strong><span>{k==='corners'?'Corners':'Crosses attempted'} per match</span><small>{t.histories[w][k].matches} covered matches</small></div>)}</div></section>)}</div><Overall f={f} w={w}/></>}
 </>;
}
export default function AerialBoard({url,example=false}:{url:string;example?:boolean}) {
 const [board,setBoard]=useState<Board|null>(null);const [error,setError]=useState(false);const [id,setId]=useState('');const [now,setNow]=useState(0);
 const [retry,setRetry]=useState(0);const [loading,setLoading]=useState(true);
 useEffect(()=>{let active=true;let controller:AbortController|null=null;let inFlight=false;
  const load=async()=>{
   if(inFlight)return;inFlight=true;setLoading(true);
   const request=new AbortController();controller=request;
   const timeout=setTimeout(()=>request.abort(),10_000);
   try {
    const r=await fetch(url,{signal:request.signal});if(!r.ok)throw new Error();
    const b:unknown=await r.json();if(!isBoard(b))throw new Error();
    if(active){setBoard(b);setError(false);setId(old=>old||new URLSearchParams(location.search).get('match')||'');}
   }catch {if(active)setError(true);}
   finally{clearTimeout(timeout);inFlight=false;if(active)setLoading(false);}
  };
  void load();setNow(Date.now());const clock=setInterval(()=>setNow(Date.now()),30_000);const poll=setInterval(()=>{if(!document.hidden)void load();},300_000);
  return()=>{active=false;controller?.abort();clearInterval(clock);clearInterval(poll);};
 },[url,retry]);
 const clock=example&&board?Date.parse(board.generated_at):now;
 const fixtures=board?.fixtures.filter(f=>Date.parse(f.kickoff)>clock)||[];
 const selected=fixtures.find(f=>f.id===id)||fixtures[0];
 const scheduleCurrent=!!board&&clock-Date.parse(board.calendar_observed_at)>=-300_000&&clock-Date.parse(board.calendar_observed_at)<=36*3600_000;
 // Presentation only: the same fixtures in the same order, with a day heading wherever the London date changes.
 const days=fixtures.reduce<{label:string;items:Fixture[]}[]>((groups,f)=>{const label=day(f.kickoff);const last=groups.at(-1);if(last&&last.label===label)last.items.push(f);else groups.push({label,items:[f]});return groups;},[]);
 return <div className="aerial-board" aria-live="polite">{example&&<p className="aerial-warning">Historical verification example. This is not a current fixture or a saved prediction.</p>}
 {error&&<div className="aerial-warning"><p>The latest update could not be loaded.{board?' The last loaded snapshot is shown with its original dates.':' Fixture availability could not be checked.'}</p><button type="button" className="aerial-retry" disabled={loading} onClick={()=>setRetry(n=>n+1)}>{loading?'Checking…':'Try again'}</button></div>}
 {!board&&!error&&<p className="aerial-empty aerial-loading">Loading upcoming fixtures…</p>}
 {board&&<>{!scheduleCurrent&&<p className="aerial-warning">The fixture schedule needs a fresh check. Comparisons are paused.</p>}<div className="aerial-fixture-control"><label>Explore a match<select value={selected?.id||''} disabled={!fixtures.length} onChange={e=>setId(e.target.value)}>{days.map((group,index)=><optgroup key={`${group.label}-${index}`} label={group.label}>{group.items.map(f=><option key={f.id} value={f.id}>{f.teams[0].name} v {f.teams[1].name} · {date(f.kickoff)}</option>)}</optgroup>)}{!fixtures.length&&<option>{scheduleCurrent?'No covered fixtures in this window':'Schedule awaiting refresh'}</option>}</select></label>{fixtures.length>0&&<p className="aerial-fixture-count">{fixtures.length} upcoming {fixtures.length===1?'fixture':'fixtures'} in the list, grouped by day</p>}<p className="aerial-freshness"><span>Updated {date(board.generated_at)}</span><span>Schedule checked {date(board.calendar_observed_at)}</span><span>Match statistics through {shortDate(board.history_through)}</span></p></div>{now&&selected?<Match key={selected.id} f={selected} board={board} now={clock}/>:!fixtures.length?<div className="aerial-empty"><div><h2>{!scheduleCurrent?'Waiting for a fresh fixture schedule.':error?'No fixtures in the last loaded snapshot.':'No covered league fixtures in the next eight days.'}</h2><p>{scheduleCurrent&&!error?'There are no matches to compare in this schedule window. Comparisons will appear when covered fixtures enter the window.':'The current fixture list could not be confirmed. This does not mean there are no matches.'}</p><p>Premier League, Serie A, La Liga, Bundesliga and Ligue 1 only. Cups and international matches are not included.</p></div></div>:null}</>}
 </div>;
}
