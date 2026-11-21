"use client";

import { useEffect, useState, type ReactNode } from "react";
import type { Result } from "./PaperReturnsPanel";
import css from "./paper-record.module.css";

type Entry = {selection:string;fixture:string;league:string;result:string;at:string;odds:number;sent:boolean};
type Packet = {tour:string;start:string;end:string;through:string;firstCovered:string|null;coveredDays:number;
  summary:Result;page:number;pages:number;rows:Entry[]};
const date = new Intl.DateTimeFormat("en-GB",{day:"numeric",month:"short",year:"numeric",timeZone:"UTC"});
const stamp = new Intl.DateTimeFormat("en-GB",{day:"numeric",month:"short",hour:"2-digit",minute:"2-digit",hourCycle:"h23",timeZone:"UTC"});
const odds = new Intl.NumberFormat("en-GB",{minimumFractionDigits:2,maximumFractionDigits:4});
const day = (s:string)=>date.format(new Date(s+"T00:00:00Z"));

export default function RollingRecord({circuit,sent,onScope,metrics}:{circuit:string;sent:boolean;onScope:(v:boolean)=>void;metrics:(r:Result)=>ReactNode}) {
  const [page,setPage]=useState(1);
  const [attempt,retry]=useState(0);
  const [loaded,setLoaded]=useState<{url:string;data:Packet|null}|null>(null);
  const url="/api/drop-shot-desk/rolling?tour="+circuit.toLowerCase()+"&group="+(sent?"telegram":"all")+"&page="+page;
  useEffect(()=>{
    const controller=new AbortController();
    fetch(url,{signal:controller.signal}).then(async r=>{
      if(!r.ok)throw new Error();
      const data:Packet=await r.json();
      if(!controller.signal.aborted)setLoaded({url,data});
    }).catch(()=>{if(!controller.signal.aborted)setLoaded({url,data:null});});
    return ()=>controller.abort();
  },[url,attempt]);
  const data=loaded && (loaded.url===url || (loaded.data && loaded.url.split("&page=")[0]===url.split("&page=")[0])) ? loaded.data : undefined;
  const busy=loaded?.url!==url;
  function select(next:boolean){setPage(1);onScope(next);}
  return <>
    <div className={css.rollingScope} role="group" aria-label="30-day selection filter">
      <button type="button" aria-pressed={!sent} onClick={()=>select(false)}>All big drops</button>
      <button type="button" aria-pressed={sent} onClick={()=>select(true)}>Sent on Telegram</button>
    </div>
    {data===undefined ? <p className={css.empty} role="status">Loading the {circuit} record…</p>
      : data===null ? <p className={css.empty} role="status">The rolling record could not be loaded. <button type="button" onClick={()=>{setLoaded(null);retry(n=>n+1);}}>Try again</button></p>
      : <>
        <div className={css.when}>
          <p className={css.span} aria-live="polite"><b>{sent?"Sent on Telegram":"All big drops"}</b> · {day(data.start)} – {day(data.end)}</p>
          <p className={css.stamp}>Odds through <b>{stamp.format(new Date(data.through))} UTC</b></p>
        </div>
        <p className={css.note}>{data.firstCovered ? "Odds recorded on "+data.coveredDays+" of 30 days, starting "+day(data.firstCovered)+"." : "No days with recorded odds for this tour in the window."} {sent
          ? "Each selection counts once at the odds in its first confirmed qualifying Telegram alert."
          : "Each selection counts once at its first qualifying odds."} The window uses the UTC date of the first qualifying drop.</p>
        {metrics(data.summary)}
        <details className={css.fold} key={sent?"sent":"all"}>
          <summary><span>Selections <small>{data.summary.entries}</small></span></summary>
          {data.rows.length===0 ? <p className={css.fine}>{sent?"No confirmed qualifying Telegram alerts in this window.":"No qualifying drops in this window."}</p> : <>
            <p className={css.fine}>{sent?"Odds and time as sent on Telegram.":"Odds and time at first detection."} Latest first. Times are UTC.</p>
            <ol className={css.entries}>{data.rows.map(r=><li key={[r.fixture,r.league,r.selection,r.at].join("|")}>
              <div><b>{r.selection}</b><small>{r.fixture} · {r.league}</small></div>
              <div><b>{odds.format(r.odds)}</b><small>{stamp.format(new Date(r.at))}</small></div>
              <div><b>{r.result}</b>{!sent && r.sent && <small>Telegram ✓</small>}</div>
            </li>)}</ol>
            {data.pages>1 && <div className={css.pager} aria-label="Selection pages">
              <button type="button" disabled={busy || data.page===1} onClick={()=>setPage(data.page-1)}>Previous</button>
              <span>Page {data.page} of {data.pages}</span>
              <button type="button" disabled={busy || data.page===data.pages} onClick={()=>setPage(data.page+1)}>Next</button>
            </div>}
          </>}
        </details>
      </>}
  </>;
}
