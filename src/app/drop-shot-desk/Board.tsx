"use client";
import { useRef, useState } from "react";
import type { Move, Fixture } from "./types";
import styles from "./board.module.css";
import { DeskIcon } from "./DeskIcon";

const uk=new Intl.DateTimeFormat("en-GB",{day:"numeric",month:"short",hour:"2-digit",minute:"2-digit",timeZone:"UTC"});
const stamp=(t:string)=>uk.format(new Date(t))+" UTC";
const price=(p:number)=>p.toFixed(3).replace(/0$/,"");
const money=(p:number)=>(p>0?"+":"")+Number(p.toFixed(3))+"u";

function Plot({move:m}:{move:Move}) {
  const ref=useRef<SVGSVGElement>(null);
  const [error,setError]=useState("");
  const [windowHours,setWindowHours]=useState(24);
  const quotes=m.quotes.filter(q=>Date.parse(q.time)>=Math.min(Date.parse(m.start)-windowHours*3600000,Date.parse(m.before)));
  const prices=quotes.map(q=>q.price);
  const lo=Math.min(...prices),hi=Math.max(...prices),span=Math.max(.02,hi-lo);
  const first=Date.parse(quotes[0].time),last=Date.parse(quotes[quotes.length-1].time);
  const points=quotes.map(q=>({ ...q,x:50+440*(Date.parse(q.time)-first)/Math.max(1,last-first),y:31+97*(hi-q.price)/span }));
  const path=points.map((q,i)=>(i===0||q.gap?"M":"L")+q.x+" "+q.y).join(" ");
  async function download() {
    if(!ref.current)return;
    const svg=ref.current.cloneNode(true) as SVGSVGElement;
    svg.setAttribute("width","1080");svg.setAttribute("height","344");
    const url=URL.createObjectURL(new Blob([new XMLSerializer().serializeToString(svg)],{type:"image/svg+xml;charset=utf-8"}));
    try {
      const image=new Image(); image.src=url; await image.decode();
      const c=document.createElement("canvas");c.width=1080;c.height=344;
      const ctx=c.getContext("2d");if(!ctx)throw new Error();
      ctx.drawImage(image,0,0);const link=document.createElement("a");
      link.href=c.toDataURL("image/png");link.download="il-margine-drop-shot-desk.png"; link.click();setError("");
    } catch {setError("The chart could not be downloaded.");} finally {URL.revokeObjectURL(url);}
  }
  return <><div className={styles.tools}><strong>Decimal odds</strong>{m.quotes.length>2&&<label>Window <select value={windowHours} onChange={e=>setWindowHours(Number(e.target.value))}><option value={2}>Final 2 hours</option><option value={24}>24 hours</option></select></label>}<button type="button" onClick={download}><DeskIcon name="download"/>Save chart</button></div>
    <svg ref={ref} className={styles.chart} xmlns="http://www.w3.org/2000/svg" viewBox="0 0 540 172" role="img" aria-label={m.player+" decimal odds, earlier "+price(m.old)+", at detection "+price(m.new)}>
      <title>{m.player} · {price(m.old)} → {price(m.new)} · {stamp(m.after)}</title>
      <rect width="540" height="172" rx="9" fill="#111923"/>
      <g fontFamily="system-ui, Segoe UI, sans-serif" fill="#d6dfeb" fontSize="13">
        <text x="12" y="18">{m.player} · {price(m.old)} → {price(m.new)}</text>
        <text x="525" y="18" textAnchor="end" fill="#aae7cb" fontSize="12">Il Margine · Drop Shot Desk</text>
        {[hi,lo].map((v,i)=><g key={i}><path d={"M47 "+(31+97*(hi-v)/span)+"h448"} stroke="#415268"/><text x="4" y={36+97*(hi-v)/span}>{price(v)}</text></g>)}
        <path d={path} fill="none" stroke="#57d196" strokeWidth="2.5"/>
        {points.map(q=><circle key={q.time} cx={q.x} cy={q.y} r={q.time===m.before||q.time===m.after?5:2.8} stroke="#a4ecd0" strokeWidth="1.7" fill={q.time===m.before?"#111923":"#57d196"}><title>{stamp(q.time)} · {price(q.price)}</title></circle>)}
        <text x="48" y="157">{stamp(quotes[0].time)}</text><text x="495" y="157" textAnchor="end">{stamp(quotes[quotes.length-1].time)}</text>
      </g>
    </svg>{error&&<p role="status">{error}</p>}
    <details><summary>Recorded prices ({quotes.length})</summary><div className={styles.scroll}><table><thead><tr><th>Time (UTC)</th><th>{m.player}</th><th>{m.opponent}</th></tr></thead><tbody>{quotes.map(q=><tr key={q.time}><td>{stamp(q.time).replace(" UTC","")}</td><td>{price(q.price)}</td><td>{price(q.other)}</td></tr>)}</tbody></table></div></details></>;
}
export default function Board({moves,fixtures,archive}:{moves:Move[];fixtures:Fixture[];archive:boolean}) {
  const [tour,setTour]=useState("All tours"),[draw,setDraw]=useState("All rounds"),[selected,select]=useState(0);
  const isQ=(m:Move)=>m.qualifying??/(?: - Q\d+\b|qualif)/i.test(m.league);
  const rows=moves.filter(m=>(tour==="All tours"||m.tour===tour)&&(draw==="All rounds"||isQ(m)===(draw==="Qualifying")));
  const m=rows[selected]??rows[0];
  return <div className={styles.board}><div className={styles.tools}>
    <label>Tour <select value={tour} onChange={e=>{setTour(e.target.value);select(0)}}>{["All tours","ATP","Challenger"].map(v=><option key={v}>{v}</option>)}</select></label>
    <label>Draw <select value={draw} onChange={e=>{setDraw(e.target.value);select(0)}}>{["All rounds","Main draw","Qualifying"].map(v=><option key={v}>{v}</option>)}</select></label>
  </div>{m?<div className={styles.grid}><section className={styles.list} aria-label="Recorded moves"><h2>Price drops <small>{rows.length}</small></h2>
    {rows.map((r,i)=><button key={[r.player,r.opponent,r.after].join("/")} aria-pressed={m===r} onClick={()=>select(i)}><strong>{r.player}</strong><span>vs {r.opponent}</span><b>{price(r.old)} → {price(r.new)}</b></button>)}
  </section><article className={styles.detail}><p>{m.tour} · {m.league}</p><h2>{m.player}</h2><p>vs {m.opponent} · {stamp(m.start)}</p>
    <dl className={styles.pair}>{[["Earlier price",m.old,m.before],["Price at detection",m.new,m.after]].map(([name,n,time])=><div key={name}><dt>{name}</dt><dd>{price(Number(n))}</dd><small>{stamp(String(time))}</small></div>)}</dl>
    <p className={styles.outcome}><strong>{m.result}</strong>{m.score?" · "+m.score:""}{archive?" · "+money(m.result==="Won"?m.new-1:m.result==="Lost"?-1:0)+" on the replay":m.notified?" · Private alert delivered":" · Observed drop"}</p>
    <Plot key={[m.player,m.after].join("/")} move={m}/>
  </article></div>:<p role="status">No recorded drops match these filters.</p>}
  {fixtures.length>0&&<details><summary>Latest watchlist ({fixtures.length} matches)</summary><div className={styles.scroll}><table><thead><tr><th>Match</th><th>Tournament</th><th>Start (UTC)</th></tr></thead><tbody>{fixtures.filter(f=>tour==="All tours"||tour===f.tour).sort((a,b)=>a.start.localeCompare(b.start)).map(f=><tr key={[f.home,f.away,f.start].join("/")}><td>{f.home} {price(f.homePrice)}<br/>{f.away} {price(f.awayPrice)}</td><td>{f.league}</td><td>{stamp(f.start)}</td></tr>)}</tbody></table></div></details>}</div>;
}
