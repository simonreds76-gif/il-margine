"use client";
import {useState} from 'react';
import {numeric, pairedAceTotal, tournamentHistory, text, currentMostAcesModel, type SignalRow} from '@/lib/admin-monitor-display';
const fmt=(v:unknown,d=1)=>{const n=numeric(v);return n===null?'Not supplied':n.toFixed(d);};
const stamp=(v:unknown)=>Number.isFinite(Date.parse(text(v)))?new Date(text(v)).toLocaleString('en-GB',{timeZone:'Europe/London',dateStyle:'short',timeStyle:'short'}):'Not supplied';
export function PlayerAceForecast({rows}:{rows:SignalRow[]}) {
 const total=pairedAceTotal(rows);
 return <div className="mt-4"><div className="rounded-xl border border-cyan-400/20 bg-cyan-400/5 p-4"><p className="text-xs text-slate-400">Props forecast · expected match aces</p><p className="mt-1 text-2xl font-semibold tabular-nums text-cyan-100">{total===null?'Incomplete player forecasts':fmt(total)}</p><p className="mt-1 text-xs text-slate-400">Sum of both players’ expected counts, not a betting line.</p></div><div className="mt-4 grid grid-cols-[minmax(0,1fr)_3.5rem_3.5rem] gap-2 text-xs text-slate-400"><span>Player</span><span>Aces</span><span>DFs</span></div>{rows.map((r,i)=><div key={i} className="mt-2 grid grid-cols-[minmax(0,1fr)_3.5rem_3.5rem] gap-2 border-t border-slate-700/60 pt-3 text-sm"><span className="break-words font-medium">{text(r.player)}</span><span className="tabular-nums">{fmt(r.projected_aces)}</span><span className="tabular-nums">{fmt(r.projected_dfs)}</span></div>)}<p className="mt-3 text-xs leading-relaxed text-slate-400">Match-length input: {text(rows[0]?.expected_match_games_source)==='fair_odds'?'match-pricing model':text(rows[0]?.expected_match_games_source)||'Not supplied'} · {fmt(rows[0]?.expected_match_games)} expected games. Forecasts are estimates, not selections.</p><TournamentHistory rows={rows}/></div>;
}
export function MostAcesComparison({data}:{data:unknown}) {
 const [model,setModel]=useState('count');
 const report=data as {generated_at?:string;note?:string;status?:string;matches?:SignalRow[];records?:SignalRow[]};
 const selectedModel=currentMostAcesModel(report.matches||[],report.records||[],model);
 const rows=(report.matches||[]).filter(r=>r.model===selectedModel);
 const record=(report.records||[]).find(r=>r.model===selectedModel);
 return <div className="mt-5 space-y-4"><div className="flex flex-wrap gap-2">{[['count','Count model · paper alerts'],['direct','Direct model · comparison only']].map(([id,label])=><button key={id} onClick={()=>setModel(id)} aria-pressed={model===id} className={`min-h-11 rounded-lg border px-3 py-2 text-sm ${model===id?'border-cyan-400/50 text-cyan-100':'border-slate-600 text-slate-400'}`}>{label}</button>)}</div>{model==='direct'&&selectedModel!=='most_aces_direct_1x2_v1'&&<p className="text-xs text-cyan-200">Refreshed input cohort · previous Direct results are kept separate. Comparison only; no Direct alerts.</p>}<p className="text-sm leading-relaxed text-slate-300">Most Aces 1X2 means player 1, tie, or player 2 to serve the most aces. These are separate experimental models, not match-winner odds.</p><p className="text-xs text-slate-400">Comparison checked {stamp(report.generated_at)} UK. Recorded prices may have moved; a missing source is not a zero price.</p>{record&&<p className="rounded-xl border border-slate-700 bg-slate-900 p-4 text-sm">Paper research: <strong>{text(record.wins)}W / {text(record.losses)}L</strong> · ROI <strong className={Number(record.roi)<0?'text-rose-300':'text-slate-100'}>{record.roi===null?'Awaiting results':`${fmt(record.roi)}%`}</strong> · {fmt(record.profit,2)}u on {text(record.stake)}u. Small sample; source observations can overlap. This is not a record of alerted bets.</p>}{report.status==='REFRESH_FAILED'&&<p role="alert" className="text-amber-200">The Most Aces refresh failed. Earlier prices are not fresh signals.</p>}<div className="grid gap-4 xl:grid-cols-2">{rows.map((r,i)=>{const prices=Array.isArray(r.prices)?r.prices as SignalRow[]:[];return <article key={i} className="min-w-0 rounded-xl border border-slate-700 bg-slate-900/50 p-4"><p className="text-xs text-slate-400">{text(r.date)} · {text(r.tournament)}</p><h3 className="mt-2 text-lg font-semibold">{text(r.player1)} vs {text(r.player2)}</h3><div className="mt-4 grid grid-cols-3 gap-2 text-center text-xs"><span className="min-w-0 break-words">{text(r.player1)}</span><span>Tie</span><span className="min-w-0 break-words">{text(r.player2)}</span></div><p className="mt-3 text-xs text-cyan-200">Model fair odds</p><div className="mt-1 grid grid-cols-3 gap-2 text-center font-semibold tabular-nums">{['fair_player1','fair_draw','fair_player2'].map(k=><span key={k}>{fmt(r[k],2)}</span>)}</div>{numeric(r.player1_mean)!==null&&numeric(r.player2_mean)!==null&&<p className="mt-3 text-xs text-slate-400">Expected aces · {fmt(r.player1_mean)} + {fmt(r.player2_mean)} = {fmt(Number(r.player1_mean)+Number(r.player2_mean))} match total · this model’s counts.</p>}{prices.map((p,j)=>{const c=p.candidate as SignalRow|undefined;return <div key={j} className="mt-4 border-t border-slate-700 pt-3"><p className="text-xs font-medium text-slate-200">{text(p.bookmaker)} · recorded odds</p><div className="mt-2 grid grid-cols-3 gap-2 text-center tabular-nums">{['player1_odds','draw_odds','player2_odds'].map(k=><span key={k}>{fmt(p[k],2)}</span>)}</div><p className="mt-2 text-xs text-slate-400">Captured {stamp(p.captured_at)} UK</p><p className="mt-1 text-xs text-amber-200">{c?text(c.eligibility_reason).replaceAll('_',' ').replaceAll('|',' · '):'Research only · forecast or contract checks not passed'}</p></div>})}{!prices.length&&<p className="mt-4 text-sm text-amber-200">No fresh, complete 1X2 price matched in the saved comparison. Fair odds alone are not a signal.</p>}<TournamentHistory rows={Array.isArray(r.tournament_players)?r.tournament_players as SignalRow[]:[]}/><p className="mt-3 text-xs text-slate-400">Forecast {stamp(r.generated_at_utc)} · {text(r.quote_status).replaceAll('_',' ')}</p></article>})}</div>{!rows.length&&<p className="text-amber-200">No current model forecasts supplied.</p>}</div>;
}


function TournamentHistory({rows}:{rows:SignalRow[]}) {
 return <section className="mt-5 border-t border-slate-700/70 pt-4" aria-label="Current tournament results">
  <h4 className="text-sm font-semibold text-slate-100">This tournament · recorded results</h4>
  <p className="mt-1 text-xs leading-relaxed text-slate-400">Completed matches in this edition, including qualifying where recorded. Counts below are actual results, separate from the next-match forecast.</p>
  <div className="mt-3 grid gap-3">
   {rows.map((row,index)=>{
    const history=tournamentHistory(row);
    return <section key={`${text(row.player)}-${index}`} className="min-w-0 rounded-xl border border-slate-700/70 bg-slate-950/40 p-3" aria-label={`${text(row.player)} tournament history`}>
     <div className="flex flex-wrap items-baseline justify-between gap-x-3 gap-y-1">
      <h5 className="break-words text-sm font-semibold text-slate-100">{text(row.player)}</h5>
      <p className="text-xs text-slate-400">{text(row.tournament)} · {history.logs.length} recorded {history.logs.length===1?'match':'matches'}</p>
     </div>
     {history.logs.length>0?<>
      <dl className="my-3 grid grid-cols-2 gap-3 rounded-lg bg-slate-800/50 p-3">
       {(['aces','dfs'] as const).map(field=>{
        const stat=history[field],complete=stat.covered===history.logs.length&&!history.incomplete;
        return <div key={field}><dt className="text-xs text-slate-400">{field==='aces'?'Aces':'Double faults'}<span className="block">{complete?'recorded total':'recorded subtotal'}</span></dt><dd className="mt-1 text-xl font-semibold tabular-nums text-slate-100">{fmt(stat.value,0)}</dd>{!complete&&<p className="mt-1 text-xs text-amber-200">Stats in {stat.covered} of {Math.max(history.logs.length,history.expected||0)} recorded matches</p>}</div>;
       })}
      </dl>
      <table className="w-full table-fixed text-xs">
       <caption className="sr-only">{text(row.player)} completed matches in {text(row.tournament)}</caption>
       <thead><tr className="text-slate-400"><th scope="col" className="pb-2 text-left font-normal">Opponent / result</th><th scope="col" className="w-12 pb-2 text-right font-normal">Aces</th><th scope="col" className="w-12 pb-2 text-right font-normal"><abbr title="Double faults" className="no-underline">DFs</abbr></th></tr></thead>
       <tbody>{history.logs.map((log,i)=><tr key={`${text(log.date)}-${text(log.opponent)}-${i}`} className="border-t border-slate-700/60"><th scope="row" className="py-2 pr-2 text-left font-normal"><span className="block break-words text-slate-200">{text(log.opponent)}</span><span className="mt-1 block text-[11px] text-slate-400">{text(log.date)} · {text(log.draw_round||log.round)}<br/>{text(log.result)||'Score not supplied'}</span></th><td className="py-2 text-right align-top font-semibold tabular-nums text-slate-100">{numeric(log.aces)===null?'—':fmt(log.aces,0)}</td><td className="py-2 text-right align-top font-semibold tabular-nums text-slate-100">{numeric(log.dfs)===null?'—':fmt(log.dfs,0)}</td></tr>)}</tbody>
      </table>
      <p className="mt-2 text-[11px] leading-relaxed text-slate-400">Saved OnCourt results through {text(history.logs.at(-1)?.date)}. Matches without statistics may be absent from this log.</p>
     </>:<p className="mt-3 text-xs leading-relaxed text-amber-200">No completed match statistics supplied for this tournament edition. This does not mean zero aces or double faults.</p>}
     {history.incomplete&&<p className="mt-2 text-xs text-amber-200">Some recorded tournament matches are missing from this round log.</p>}
    </section>;
   })}
   {!rows.length&&<p className="text-xs text-amber-200">Current-tournament history was not supplied in this snapshot.</p>}
  </div>
 </section>;
}
