"use client";
import {useEffect,useState} from 'react';
import {bestFreshComparison} from '@/lib/tennis-fresh-comparison.mjs';
import {text,type SignalRow} from '@/lib/admin-monitor-display';
export default function MatchupPriceCard({row}:{row:SignalRow}) {
 const [now,setNow]=useState<number|null>(null);
 useEffect(()=>{const tick=()=>setNow(Date.now());tick();const id=setInterval(tick,30000);return()=>clearInterval(id);},[]);
 const comparison=bestFreshComparison(row,now??NaN);
 return <section className="mt-4 rounded-xl border border-cyan-300/20 bg-cyan-300/5 p-3" aria-label="Most Aces fresh price comparison">
 <p className="text-xs font-semibold uppercase tracking-wide text-cyan-100">Most Aces · price check</p>
 <p className="mt-1 text-xs leading-relaxed text-slate-400">Best captured price per outcome. Complete 1X2 markets only; quotes expire after 30 minutes.</p>
 <div className="mt-3 grid gap-3 sm:grid-cols-3">{comparison.map((c,i)=><div key={c.side} className="min-w-0 rounded-lg border border-slate-700/60 bg-slate-950/40 p-3">
 <h4 className="min-h-10 break-words text-sm font-medium text-slate-100">{i===1?'Tie':text(row[i===0?'player1':'player2'])}</h4>
 <dl className="mt-2 space-y-2 text-xs"><div className="flex items-baseline justify-between gap-2"><dt className="text-slate-400">Fair odds</dt><dd className="font-semibold tabular-nums">{c.fair?.toFixed(2)??'—'}</dd></div>
 <div className="flex items-baseline justify-between gap-2"><dt className="text-slate-400">Best fresh</dt><dd className="text-lg font-semibold tabular-nums">{c.odds?.toFixed(2)??'—'}</dd></div>
 <div className="flex items-baseline justify-between gap-2"><dt className="text-slate-400">Estimated EV</dt><dd className={`font-semibold tabular-nums ${c.ev===null?'text-slate-400':c.ev>0?'text-emerald-300':c.ev<0?'text-rose-300':'text-slate-100'}`}>{c.ev===null?'—':`${c.ev>0?'+':''}${c.ev.toFixed(1)}%`}</dd></div></dl>
 <p className="mt-2 break-words text-[11px] leading-relaxed text-slate-400">{c.bookmaker?`${c.bookmaker} · observed ${c.ageMinutes} min ago`:now===null?'Checking quote ages…':c.reason}</p>
 {c.bookmaker&&c.ev===null&&<p className="mt-1 text-[11px] text-amber-200">{c.reason}</p>}
 {c.buffer!==null&&c.buffer>0&&<p className="mt-2 text-[11px] leading-relaxed text-slate-300">Edge disappears if this outcome’s probability is {c.buffer.toFixed(1)} percentage points lower.</p>}
 </div>)}</div><p className="mt-3 text-[11px] leading-relaxed text-slate-400">Paper model estimate, not a new signal. The buffer is sensitivity to estimation error, not an estimated medical-timeout effect. Eligibility checks below still apply.</p>
 </section>;
}
