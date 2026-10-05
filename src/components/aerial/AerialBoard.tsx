'use client';
import {useEffect,useState} from 'react';
import Image from 'next/image';
import type {Board,Fixture,Player,Team,WindowKey} from './types';
import {isBoard} from './types';

const value=(n:number|null|undefined,dp=0)=>typeof n==='number'&&Number.isFinite(n)?n.toFixed(dp):'Not available';
const shortDate=(s:string)=>new Intl.DateTimeFormat('en-GB',{timeZone:'Europe/London',day:'numeric',month:'short',year:'numeric'}).format(new Date(s));
const date=(s:string)=>new Intl.DateTimeFormat('en-GB',{timeZone:'Europe/London',day:'numeric',month:'short',hour:'2-digit',minute:'2-digit',timeZoneName:'short'}).format(new Date(s));
export function AerialIcon({kind='height'}:{kind?:string}) {
 const paths:Record<string,React.ReactNode>={height:<><path d="M5 20V4m-3 3 3-3 3 3m-6 10 3 3 3-3M13 4h7v16h-7zM16 8h4m-4 4h4m-4 4h4"/></>,duel:<><circle cx="7" cy="5" r="2"/><circle cx="18" cy="7" r="2"/><path d="m3 12 4-4 5 4M7 9v6l-3 6m3-6 5 6m3-7 3-4 4 3m-4-3v7l3 4m-3-4-4 4"/></>,corner:<><path d="M4 21V3l9 3-9 3m0 12h17M4 15a6 6 0 0 1 6 6m4-11c5 0 7 3 7 7m-3-2 3 2 2-3"/></>,players:<><circle cx="9" cy="7" r="3"/><path d="M3 21v-4a6 6 0 0 1 12 0v4m0-17a3 3 0 0 1 0 6m3 3a5 5 0 0 1 3 5v3"/></>};
 return <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">{paths[kind]||paths.height}</svg>;
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
function Section({id,kind,title,text}:{id:string;kind:string;title:string;text:string}) {
 return <header id={id} className="aerial-section-heading"><span className="aerial-icon"><AerialIcon kind={kind}/></span><div><h2>{title}</h2><p>{text}</p></div></header>;
}
function Players({team,windowKey}:{team:Team;windowKey:WindowKey}) {
 const [role,setRole]=useState('all'); const [sort,setSort]=useState('height');
 const players=team.players.filter(p=>p.role!=='GK'&&(role==='all'||role===p.role)).toSorted((a,b)=>{
   const metric=(p:Player)=>sort==='headers'?p.histories[windowKey].headers_per90:sort==='duels'?(p.histories[windowKey].aerial_attempts>=20?p.histories[windowKey].aerial_win_pct:null):p.height_cm;
   return (metric(b)??-1)-(metric(a)??-1)||a.name.localeCompare(b.name);
 });
 return <section className="aerial-panel"><div className="aerial-table-controls"><TeamName team={team}/><label>Role<select value={role} onChange={e=>setRole(e.target.value)}><option value="all">All outfield players</option><option value="DEF">Defenders</option><option value="MID">Midfielders</option><option value="ATT">Attacking players</option></select></label><label>Sort by<select value={sort} onChange={e=>setSort(e.target.value)}><option value="height">Reported height</option><option value="headers">Headed shots per 90</option><option value="duels">Aerial success</option></select></label></div>
 <div className="aerial-table-head" aria-hidden="true"><span>Player</span><span>Height</span><span>Duels won</span><span>Headed shots</span><span>Minutes</span></div>
 {players.map(p=>{const h=p.histories[windowKey];return <details className="aerial-player" key={p.id}><summary><span className="aerial-person"><Portrait player={p}/><span><strong>{p.name}</strong><small>{p.role==='UNK'?'Role unavailable':p.role} · {h.matches} matches{h.small_sample?<b className="aerial-limited">Limited data</b>:null}</small></span></span><span><small>Reported height</small>{value(p.height_cm)}{p.height_cm!==null?' cm':''}</span><span><small>Aerial duels won</small>{value(h.aerial_win_pct,0)}{h.aerial_win_pct!==null?'%':''}<em>{h.aerial_won} of {h.aerial_attempts} contests</em></span><span><small>Headed shots</small>{h.head_matches?h.headed_shots:'Not available'}<em>{value(h.headers_per90,2)} per 90</em></span><span><small>Playing time</small>{h.minutes.toLocaleString()}<em>Open matches ↓</em></span></summary><div className="aerial-player-detail"><p>{p.height_source?<a href={p.height_source} target="_blank" rel="noreferrer">Reported height source ↗</a>:'Height has not been verified.'}{p.height_observed_at?` · Checked ${p.height_observed_at.slice(0,10)}`:''}</p>
 <div className="aerial-scroll" role="region" aria-label={`${p.name} earlier matches`} tabIndex={0}><table><thead><tr><th>Date / match</th><th>Minutes</th><th>Duels won / attempted</th><th>Headed shots</th></tr></thead><tbody>{h.appearances.map(a=><tr key={a.fixture_id}><td>{a.date}<strong>{a.match}</strong></td><td>{a.minutes}</td><td>{value(a.won)} / {value(a.attempts)}</td><td>{value(a.headed_shots)}</td></tr>)}</tbody></table></div>{!h.matches&&<p>No earlier appearances in this archive.</p>}</div></details>})}
 {!players.length&&<p>No starters in this role.</p>}<p className="aerial-note">Roles describe usual positions. They do not assign attacking targets or marking duties. Aerial success needs at least 20 contests to enter the sort order.</p></section>;
}
function Comparison({fixture,windowKey}:{fixture:Fixture;windowKey:WindowKey}) {
 const [ids,setIds]=useState<string[]>([]);
 const chosen=fixture.teams.map((t,i)=>t.players.find(p=>p.id===ids[i])||t.players.filter(p=>p.role!=='GK').toSorted((a,b)=>(b.height_cm??0)-(a.height_cm??0))[0]);
 return <section className="aerial-panel"><div className="aerial-compare-pickers">{fixture.teams.map((t,i)=><label key={t.id}><TeamName team={t}/><span className="aerial-person"><Portrait player={chosen[i]}/><select value={chosen[i].id} onChange={e=>setIds(old=>{const n=[...old];n[i]=e.target.value;return n})}>{t.players.filter(p=>p.role!=='GK').map(p=><option key={p.id} value={p.id}>{p.name}</option>)}</select></span></label>)}</div>
 {(['Reported height','Aerial contests won','Headed shots','Playing time'] as const).map((label,i)=><div className="aerial-compare-row" key={label}><strong>{metric(chosen[0],i,windowKey)}</strong><span>{label}</span><strong>{metric(chosen[1],i,windowKey)}</strong></div>)}<p className="aerial-comparison-note">Two player records side by side. This is not a predicted marking matchup.</p></section>;
}
function metric(p:Player,i:number,w:WindowKey) {const h=p.histories[w];return i===0?(p.height_cm===null?'Not available':`${p.height_cm} cm`):i===1?(h.duel_matches?`${h.aerial_won} / ${h.aerial_attempts}`:'Not available'):i===2?(h.head_matches?`${h.headed_shots} in ${h.head_matches} matches`:'Not available'):`${h.minutes} minutes`;}
function Overall({f,w}:{f:Fixture;w:WindowKey}) {
 const heights=f.teams.map(t=>t.height.mean_cm); const d=f.teams.map(t=>t.histories[w]);
 const enough=heights.every(h=>h!==null)&&d.every(x=>x.corners.matches>=3&&x.crosses.matches>=3);
 let text='A combined comparison needs all ten outfield heights on each side and at least three earlier matches with corners and crosses. Explore the available figures above.';
 if(enough){const gap=heights[0]!-heights[1]!;const c=d[0].corners.average!-d[1].corners.average!;const x=d[0].crosses.average!-d[1].crosses.average!;
 text=(Math.abs(gap)<1?`The average heights are ${Math.abs(gap).toFixed(1)} cm apart. `:`${f.teams[gap>0?0:1].name} are ${Math.abs(gap).toFixed(1)} cm taller on average. `)+(c*x>0?`${f.teams[c>0?0:1].name} recorded more corners and attempted crosses in the covered matches. `:'The corners and crosses records do not both favour the same side. ')+'Read that alongside the players’ aerial contests and headed shots. These figures describe size and involvement, not the chance of scoring.';}
 return <section className="aerial-verdict"><span className="aerial-kicker">THE OVERALL READ</span><h2>{enough?'How the pieces fit together':'More evidence needed'}</h2><p>{text}</p></section>;
}
function Match({f,board,now}:{f:Fixture;board:Board;now:number}) {
 const [w,setW]=useState<WindowKey>('recent');
 const active=(f.state==='confirmed'||f.state==='expected')&&now<Date.parse(f.valid_until)&&now-Date.parse(board.generated_at)>=-300_000&&now-Date.parse(board.generated_at)<36*3600_000&&now-Date.parse(board.calendar_observed_at)<36*3600_000;
 return <><section className="aerial-match"><div className="aerial-status"><span>{f.competition} · {date(f.kickoff)}</span><strong className={active?'aerial-badge':''}>{active?(f.state==='confirmed'?'Confirmed XI':'Expected XI'):f.state==='pending'?'Awaiting lineups':'Lineup no longer current'}</strong></div><div className="aerial-teams">{f.teams.map((t,i)=><div key={t.id}><span className="aerial-kicker">{i?'AWAY':'HOME'}</span><TeamName team={t}/><p>{active?t.formation:'Lineup not available'}</p></div>)}</div>{active&&<p className="aerial-note">Lineup seen {date(f.observed_at!)}. {f.state==='expected'?'These players may change before kickoff.':''}</p>}</section>
 {!active?<div className="aerial-empty"><AerialIcon kind="players"/><h2>{f.state==='pending'?'The fixture is here. The starting XIs are not yet published.':'This lineup needs a fresh check.'}</h2><p>The height and player comparison appears when a current expected or confirmed XI is available for both teams.</p><p>Updates reuse the football lineup refresh. The source must publish a team before we can show it.</p></div>:<>
 <nav className="aerial-jumps" aria-label="On this page"><a href="#height">The height ↓</a><a href="#players">The players ↓</a><a href="#delivery">The delivery ↓</a></nav>
 <Section id="height" kind="height" title="Size across the starting XI" text="Reported heights of the ten outfield starters. Goalkeepers are kept separate."/>
 <div className="aerial-height-grid">{f.teams.map((t,i)=><section className={`aerial-panel aerial-side-${i}`} key={t.id}><TeamName team={t}/><div className="aerial-height-number">{value(t.height.mean_cm,1)}{t.height.mean_cm!==null&&<small>cm average</small>}</div><p>{t.height.known} of 10 outfield heights available</p><div className="aerial-height-plot" aria-label={`${t.name} player heights`}>{t.players.filter(p=>p.role!=='GK'&&p.height_cm!==null).toSorted((a,b)=>a.height_cm!-b.height_cm!).map((p,index)=><span key={p.id} style={{left:`${Math.max(0,Math.min(100,(p.height_cm!-155)/55*100))}%`,top:`${12+(index%3)*16}px`}} tabIndex={0} aria-label={`${p.name}, ${p.height_cm} centimetres`}><i/><em>{p.name}: {p.height_cm} cm</em></span>)}</div><div className="aerial-axis"><span>155 cm</span><span>180 cm</span><span>210 cm</span></div><div className="aerial-height-extras"><span>Tallest three, average<strong>{value(t.height.tallest_three_mean_cm,1)} cm</strong></span><span>Outfield starters ≥185 cm<strong>{value(t.height.at_least_185)} / 10</strong></span></div></section>)}</div>
 <div className="aerial-history-control"><label>Choose the history<select value={w} onChange={e=>setW(e.target.value as WindowKey)}><option value="recent">Both seasons</option><option value="current">{board.seasons[0]}</option><option value="previous">{board.seasons[1]}</option></select></label><p>Up to 10 covered appearances per player and five earlier matches per team. Always before this fixture.</p></div>
 <Section id="players" kind="duel" title="Who actually uses their height?" text="Compare two starters, then open the matches behind every player’s figures."/>
 <Comparison key={f.id} fixture={f} windowKey={w}/>{f.teams.map(t=><Players key={t.id} team={t} windowKey={w}/>)}
 <Section id="delivery" kind="corner" title="The delivery into the box" text="Recent corners and attempted crosses show how often each side supplied the box. They do not measure delivery quality."/>
 <div className="aerial-height-grid">{f.teams.map(t=><section className="aerial-panel" key={t.id}><TeamName team={t}/><div className="aerial-delivery">{(['corners','crosses'] as const).map(k=><div key={k}><AerialIcon kind="corner"/><strong>{value(t.histories[w][k].average,1)}</strong><span>{k==='corners'?'Corners':'Crosses attempted'} per match</span><small>{t.histories[w][k].matches} covered matches</small></div>)}</div></section>)}</div><Overall f={f} w={w}/></>}
 </>;
}
export default function AerialBoard({url,example=false}:{url:string;example?:boolean}) {
 const [board,setBoard]=useState<Board|null>(null);const [error,setError]=useState(false);const [id,setId]=useState('');const [now,setNow]=useState(0);
 useEffect(()=>{let active=true;const controller=new AbortController();
  const load=async()=>{try {const r=await fetch(url,{signal:controller.signal});if(!r.ok)throw new Error();const b:unknown=await r.json();if(!isBoard(b))throw new Error();if(active){setBoard(b);setError(false);setId(old=>old||new URLSearchParams(location.search).get('match')||'');}}catch(e){if(active&&!(e instanceof Error&&e.name==='AbortError'))setError(true);}};
  void load();setNow(Date.now());const clock=setInterval(()=>setNow(Date.now()),30_000);const poll=setInterval(()=>{if(!document.hidden)void load();},300_000);return()=>{active=false;controller.abort();clearInterval(clock);clearInterval(poll);};
 },[url]);
 const clock=example&&board?Date.parse(board.generated_at):now;
 const fixtures=board?.fixtures.filter(f=>Date.parse(f.kickoff)>clock)||[];
 const selected=fixtures.find(f=>f.id===id)||fixtures[0];
 return <div className="aerial-board" aria-live="polite">{example&&<p className="aerial-warning">Historical verification example. This is not a current fixture or a saved prediction.</p>}{error&&<p className="aerial-warning" role="status">The latest update could not be loaded.{board?' The last loaded time remains visible below.':' Please try again shortly.'}</p>}{!board&&!error&&<p className="aerial-empty" role="status">Loading upcoming fixtures…</p>}{board&&<>{now-Date.parse(board.calendar_observed_at)>36*3600_000&&<p className="aerial-warning">The fixture schedule needs a fresh check. Comparisons are paused.</p>}<div className="aerial-fixture-control"><label>Explore a match<select value={selected?.id||''} disabled={!fixtures.length} onChange={e=>setId(e.target.value)}>{fixtures.map(f=><option key={f.id} value={f.id}>{f.teams[0].name} v {f.teams[1].name} · {date(f.kickoff)}</option>)}{!fixtures.length&&<option>No upcoming fixtures</option>}</select></label><p>Updated {date(board.generated_at)}<br/>Match statistics through {shortDate(board.history_through)}</p></div>{now&&selected?<Match key={selected.id} f={selected} board={board} now={clock}/>:!fixtures.length?<div className="aerial-empty"><h2>No fixtures in the next eight days.</h2><p>This tool covers the Premier League, Serie A, La Liga, Bundesliga and Ligue 1. Cups and international matches are outside its coverage.</p></div>:null}</>}
 </div>;
}

