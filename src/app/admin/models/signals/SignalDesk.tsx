"use client";
import {useEffect,useMemo,useState} from "react";
import catalog from "../../../../../config/admin-monitor-catalog.json";
import {signalCsv,resultGroup} from "@/lib/admin-signal-format";
type Row=Record<string,unknown>;
const label=(s:string)=>s.replaceAll("_"," ").replaceAll("-"," ");
const value=(v:unknown):string=>v===null||v===undefined||v===""?"Not recorded":typeof v==="object"?JSON.stringify(v):String(v);
const control="min-h-11 max-w-full rounded-lg border border-slate-600 bg-slate-950 px-3 py-2 text-sm";
const pick=(r:Row,keys:string[])=>keys.map(k=>r[k]).find(v=>v!==undefined&&v!==null&&v!=="");
const date=(s?:string)=>s&&Number.isFinite(Date.parse(s))?new Date(s).toLocaleString("en-GB",{timeZone:"Europe/London"}):"Not recorded";
function Records({rows}:{rows:Row[]}){
 const [search,setSearch]=useState(""),[status,setStatus]=useState("all"),[page,setPage]=useState(0),[sort,setSort]=useState("newest");
 const filtered=useMemo(()=>rows.filter(r=>(status==="all"||resultGroup(r)===status)&&JSON.stringify(r).toLowerCase().includes(search.toLowerCase())),[rows,search,status]);
 const keys=[...new Set(rows.flatMap(r=>Object.keys(r)))];
 const groups=[
  ['Date',['scheduled_start_utc','kickoff_at','kickoff_utc','kickoff','match_date','date']],
  ['Fixture',['match','player1','player2','home_team','away_team','opponent']],
  ['Selection',['selection','player','goalkeeper','team','side','line','market','bet_type']],
  ['Recorded odds',['selected_odds','odds_decimal','odds','book_price_at_publication','best_bookmaker_odds','spread_odds','pin_odds1','pin_odds2','bookmaker']],
  ['Model',['fair_odds','model_fair_odds','our_odds1','our_odds2','fair_over_odds','fair_under_odds','projected_aces','projected_dfs']],
  ['EV / edge as stored',['value_pct','ev_pct','edge','value_p1','value_p2']],
  ['Result',['bet_outcome','result','settlement_status','status','signal_status']],
  ['Stake / profit',['stake_units','pnl_units']]
 ] as const;
 const columns=groups.map(([title,fields])=>({title,fields:fields.filter(k=>keys.includes(k))})).filter(c=>c.fields.length);
 const ordered=useMemo(()=>{if(sort==='source')return filtered;const stamp=(row:Row)=>{const v=pick(row,['scheduled_start_utc','kickoff_at','kickoff_utc','kickoff','match_date','date','captured_at','created_at']);const parsed=Date.parse(String(v??''));return Number.isFinite(parsed)?parsed:0;};return [...filtered].sort((a,b)=>(stamp(b)-stamp(a))*(sort==='newest'?1:-1));},[filtered,sort]);
 const visible=ordered.slice(page*40,(page+1)*40);
 return <div className="min-w-0"><div className="my-4 flex flex-wrap gap-3"><input className={`${control} min-w-0 flex-1`} aria-label="Search records" placeholder="Search player, match or bookmaker" value={search} onChange={e=>{setSearch(e.target.value);setPage(0);}}/><select className={control} aria-label="Result filter" value={status} onChange={e=>{setStatus(e.target.value);setPage(0);}}><option value="all">All records</option><option value="pending">Pending / open</option><option value="settled">Settled / void</option><option value="other">Candidates / other</option></select><select className={control} aria-label="Sort records" value={sort} onChange={e=>{setSort(e.target.value);setPage(0);}}><option value="newest">Newest first</option><option value="oldest">Oldest first</option><option value="source">Original order</option></select></div><p className="mb-3 text-xs text-slate-400">{filtered.length.toLocaleString()} matching records out of {rows.length.toLocaleString()}. Every recorded field is available under Details. Missing outcomes are not assumed to be pending bets.</p>
 <div className="hidden max-w-full overflow-x-auto rounded-xl border border-slate-700 md:block"><table className="w-full text-left text-xs"><thead className="bg-slate-900"><tr>{columns.map(c=><th key={c.title} className="whitespace-nowrap p-3 text-slate-400">{c.title}</th>)}<th className="p-3">Details</th></tr></thead><tbody>{visible.map((r,i)=><tr key={page*40+i} className="border-t border-slate-800 align-top">{columns.map(c=><td key={c.title} className="min-w-28 max-w-56 whitespace-normal break-words p-3"><Fields row={Object.fromEntries(c.fields.filter(k=>r[k]!==undefined&&r[k]!==null&&r[k]!=='').map(k=>[k,r[k]]))}/></td>)}<td className="p-3"><details><summary className="cursor-pointer text-emerald-200">All fields</summary><Fields row={r}/></details></td></tr>)}</tbody></table></div>
 <div className="space-y-3 md:hidden">{visible.map((r,i)=><article key={i} className="min-w-0 rounded-xl border border-slate-700 bg-slate-900/60 p-4"><p className="text-xs text-slate-400">{value(pick(r,['scheduled_start_utc','kickoff_at','kickoff','kickoff_utc','match_date','date','captured_at']))}</p><h3 className="mt-2 font-semibold">{value(pick(r,['match','fixture'])??[pick(r,['home_team','player1','team','player','goalkeeper']),pick(r,['away_team','player2','opponent'])].filter(Boolean).join(' vs '))}</h3><p className="mt-2 text-sm text-emerald-200">{[r.selection,r.player||r.goalkeeper,r.side||r.recommended_side,r.line,r.market].filter(Boolean).map(value).join(' · ')}</p><div className="mt-3 grid grid-cols-2 gap-3 text-sm">{columns.filter(c=>!['Date','Fixture','Selection'].includes(c.title)).map(c=><div key={c.title} className="min-w-0"><p className="font-medium text-slate-200">{c.title}</p><Fields row={Object.fromEntries(c.fields.filter(k=>r[k]!==undefined&&r[k]!==null&&r[k]!=='').map(k=>[k,r[k]]))}/></div>)}</div><details className="mt-4"><summary className="cursor-pointer text-sm text-emerald-200">All recorded fields</summary><Fields row={r}/></details></article>)}</div>
 {!filtered.length&&<p className="rounded-xl border border-slate-700 p-5">No records match this view.</p>}<div className="mt-4 flex flex-wrap items-center gap-3"><button className={control} disabled={page===0} onClick={()=>setPage(page-1)}>Previous</button><span className="text-sm">Page {page+1} of {Math.max(1,Math.ceil(filtered.length/40))}</span><button className={control} disabled={(page+1)*40>=filtered.length} onClick={()=>setPage(page+1)}>Next</button></div></div>;
}
function Fields({row}:{row:Row}){return <dl className="mt-3 grid min-w-0 gap-2 text-xs">{Object.entries(row).map(([k,v])=><div key={k} className="min-w-0"><dt className="capitalize text-slate-400">{label(k)}</dt><dd className="break-words [overflow-wrap:anywhere]">{value(v)}</dd></div>)}</dl>}
function Report({data,depth=0}:{data:unknown;depth?:number}){
 if(Array.isArray(data))return data.length&&data.every(v=>v&&typeof v==='object'&&!Array.isArray(v))?<Records rows={data as Row[]}/>:<p className="break-words text-sm">{data.map(value).join(' · ')||'No entries recorded'}</p>;
 if(!data||typeof data!=='object')return <p className="break-words text-sm">{value(data)}</p>;
 const entries=Object.entries(data as Row),simple=Object.fromEntries(entries.filter(([,v])=>v===null||typeof v!=='object'));
 return <div className="min-w-0 space-y-3"><Fields row={simple}/>{entries.filter(([,v])=>v!==null&&typeof v==='object').map(([k,v])=><details key={k} open={depth===0&&['selections','live_bets','recent_pending'].includes(k)} className="min-w-0 rounded-lg border border-slate-700 p-3"><summary className="cursor-pointer capitalize text-emerald-200">{label(k)}{Array.isArray(v)?` · ${v.length}`:''}</summary><div className="mt-3"><Report data={v} depth={depth+1}/></div></details>)}</div>;
}
export default function SignalDesk(){
 const [id,setId]=useState('props-board'),[refresh,setRefresh]=useState(0),[data,setData]=useState<{generated_at:string;manifest:Array<{id:string;available:boolean;modified_at?:string}>;content?:string}|null>(null),[error,setError]=useState(''),[loading,setLoading]=useState(true);
 useEffect(()=>{
  let active=true;
  const controller=new AbortController();
  const timeout=setTimeout(()=>controller.abort(),15000);
  fetch(`/api/admin/model-signals?view=${encodeURIComponent(id)}`,{cache:'no-store',signal:controller.signal})
   .then(async response=>{const payload=await response.json();if(!response.ok||!payload.ok)throw Error(payload.error||'Could not load');if(active)setData(payload);})
   .catch(error=>{if(active)setError(controller.signal.aborted?'Loading timed out. Please refresh.':error.message);})
   .finally(()=>{clearTimeout(timeout);if(active)setLoading(false);});
  return()=>{active=false;clearTimeout(timeout);controller.abort();};
 },[id,refresh]);
 const reset=()=>{setLoading(true);setError('');setData(null);};
 const view=catalog.find(v=>v.id===id)!;const source=data?.manifest?.find(v=>v.id===id);
 const parsed=useMemo(()=>{if(typeof data?.content!=='string')return {error:'This file is not included in the saved snapshot. It is unavailable, not an empty record.'};try{return {value:view.file.endsWith('.csv')?signalCsv(data.content):JSON.parse(data.content)}}catch{return {error:'The saved file could not be read. No results have been inferred.'}}},[data,view.file]);
 return <section className="min-w-0 rounded-2xl border border-slate-700 p-4 sm:p-6"><div className="flex flex-wrap items-end gap-3"><label className="min-w-0 basis-full text-sm sm:flex-1 sm:basis-auto">Model and view<select className={`${control} mt-2 w-full`} value={id} onChange={e=>{reset();setId(e.target.value);}}>{[...new Set(catalog.map(v=>v.group))].map(g=><optgroup key={g} label={g}>{catalog.filter(v=>v.group===g).map(v=><option key={v.id} value={v.id}>{v.label}</option>)}</optgroup>)}</select></label><button className={control} onClick={()=>{reset();setRefresh(refresh+1);}}>Refresh saved data</button></div><h2 className="mt-6 text-xl font-semibold">{view.label}</h2><p className="mt-2 text-xs text-amber-200">{view.kind==='board'||view.kind==='candidates'?'Candidate prices and forecasts. A row is not automatically a qualifying or tracked bet.':view.kind==='observations'?'Research observations. Check the signal flag; not every observation is a bet.':'Original records and outcomes, including their recorded model versions and exclusions.'}</p>{data&&<p className="mt-3 text-xs text-slate-400">Private upload: {date(data.generated_at)} UK · Source file modified: {date(source?.modified_at)} UK. Upload time does not establish price freshness. Values and percentage scales are shown as stored.</p>}
 {loading?<p role="status" className="mt-6">Loading saved records...</p>:error?<p role="alert" className="mt-6 text-rose-300">{error}</p>:parsed.error?<p className="mt-6 text-amber-200">{parsed.error}</p>:<div className="mt-5 min-w-0" key={id}>{Array.isArray(parsed.value)?<Records rows={parsed.value}/>:<Report data={parsed.value}/>}</div>}<p className="mt-6 text-xs text-slate-500">Updates arrive through the existing daily pipeline. This screen does not run models, place bets or change settlements.</p></section>;
}
