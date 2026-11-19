"use client";
import {useEffect,useState} from "react";
import {useRouter} from "next/navigation";
import MoveSummary from "./MoveSummary";
import type {MonitorMove} from "./reader";

export default function MonitorRoundup({moves,now}:{moves:MonitorMove[];now:number}) {
  const [clock,setClock]=useState(now);
  const [recorded,setRecorded]=useState(false);
  const router=useRouter();
  useEffect(()=>{
    const atMount=performance.now();
    const read=()=>Math.max(Date.now(),now+performance.now()-atMount);
    const deadlines=moves.flatMap(m=>m.until===null?[]:[m.until]);
    let timer:ReturnType<typeof setTimeout>;
    let refreshRequested=false;
    function wake(){
      clearTimeout(timer);
      if(document.visibilityState==="hidden")return;
      const time=read();
      setClock(time);
      if(time>=now+900_000&&!refreshRequested){refreshRequested=true;router.refresh();}
      const next=Math.min(...deadlines.filter(t=>t>time),refreshRequested?Infinity:now+900_000);
      if(Number.isFinite(next))timer=setTimeout(wake,Math.max(50,next-time+50));
    }
    wake();
    document.addEventListener("visibilitychange",wake);
    return ()=>{clearTimeout(timer);document.removeEventListener("visibilitychange",wake);};
  },[moves,now,router]);
  const active=moves.filter(m=>m.until!==null&&m.until>clock);
  return <><label className="mb-4 flex items-center gap-2 text-sm"><input type="checkbox" checked={recorded} onChange={e=>setRecorded(e.target.checked)}/>Show all {moves.length} originally sent</label>
    <div className="grid gap-4 lg:grid-cols-2">{(recorded?moves:active).map(m=><MoveSummary key={m.id} {...m}
      heading={m.until!==null&&m.until>clock?"Upcoming at the last check":"Recorded alert · closed"}/>)}</div>
    {!recorded&&!active.length&&<p className="text-slate-300">No selections in this roundup are still verified open before the scheduled start.</p>}</>;
}
