import {METRICS} from './core.mjs';
import {symbol} from './identity.mjs';

const esc=value=>String(value??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const number=value=>value.toLocaleString('en-GB');
const pct=value=>value===null?'Unavailable':`${value.toFixed(1)}%`;
const signed=value=>value===null?'—':`${value>0?'+':''}${value.toFixed(1)}`;
const chip=(player,slot)=>`<span class="player-chip side-${slot}"><i aria-hidden="true"></i>${esc(player.name)}</span>`;

export function compactOddsComparison(players,summaries) {
  const definitions=[
    ['actual','Actual wins','actual',s=>s.priced?number(s.actual):'—','wins'],
    ['expected','Wins suggested by odds','expected',s=>s.priced?s.expected.toFixed(1):'—','wins'],
    ['excess','Excess wins','excess',s=>signed(s.residual),'wins'],
    ['gap','Win frequency gap','gap',s=>signed(s.residualPer100),'percentage points'],
  ];
  return `<div class="compact-odds"><table><caption class="sr-only">Results compared with recorded pre-match odds</caption><thead><tr><th scope="col">In this selection</th>${players.map((p,i)=>`<th scope="col">${chip(p,i)}<small>${summaries[i].priced} matches with odds</small></th>`).join('')}</tr></thead><tbody>${definitions.map(([key,name,icon,value,unit])=>`<tr class="${key==='excess'||key==='gap'?'derived-result':''}"><th scope="row"><span class="comparison-label">${symbol(icon)}<span>${name}<small>${unit}</small></span></span></th>${summaries.map((s,i)=>`<td class="side-${i}">${value(s)}</td>`).join('')}</tr>`).join('')}</tbody></table></div>
    <p class="comparison-caption">${summaries.some(s=>s.priced<30)?'Small sample. One result can move these figures substantially. ':''}These compare past results with the odds. They are not ROI or a forecast.</p>
    <details class="comparison-explainer"><summary>What do excess wins and the gap mean?</summary><p><strong>Excess wins:</strong> if the odds suggested 6 wins and a player won 8, that is 2 more wins than expected.</p><p><strong>Win frequency gap:</strong> 8 wins from 10 matches is 80%. If the odds suggested 60%, the gap is +20 percentage points.</p><div class="comparison-rates">${summaries.map((s,i)=>`<p>${chip(players[i],i)}<span>${pct(s.priced?100*s.actual/s.priced:null)} actual win rate · ${pct(s.priced?100*s.expected/s.priced:null)} suggested by odds</span></p>`).join('')}</div><p>Expected wins add up the win chances from the recorded prices after removing the bookmaker’s margin. The prices are not necessarily closing prices and are not our model’s predictions.</p></details>`;
}

export function comparisonMetrics(players,summaries) {
  return `<div class="comparison-metrics">${Object.entries(METRICS).map(([key,[name]])=>{
    const count=key==='aces'||key==='doubleFaults';
    const metrics=summaries.map(s=>s.metrics[key]);
    const values=metrics.map(m=>count?m.perMatch:m.rate);
    const scale=count?Math.max(1,...values.filter(v=>v!==null)):100;
    return `<article class="comparison-metric"><header><span class="metric-symbol" aria-hidden="true">${symbol(key)}</span><div><h3>${name}</h3><p>${count?'Average per match':'Share of recorded points won'}${key==='doubleFaults'?' · lower is better':''}</p></div></header>${players.map((p,i)=>`<div class="paired-stat side-${i}"><div>${chip(p,i)}<strong>${values[i]===null?'—':values[i].toFixed(1)+(count?'':'%')}</strong></div><div class="comparison-track" aria-hidden="true">${values[i]===null?'':`<span style="width:${Math.max(0,Math.min(100,100*values[i]/scale))}%"></span>`}</div></div>`).join('')}<details><summary>Totals and coverage${metrics.some(m=>m.matches>0&&(m.matches<15||(!count&&m.denominator<500)))?' · small sample':''}</summary>${metrics.map((m,i)=>`<div class="metric-coverage side-${i}">${chip(players[i],i)}<p>${m.matches===0?'No recorded statistics.':count?`${number(m.numerator)} ${key==='aces'?'aces':'double faults'} recorded${m.rate===null?'':` · ${m.rate.toFixed(1)} per 100 service points`}`:`${number(m.numerator)} of ${number(m.denominator)} points won`}<br>Statistics available in ${m.matches} of ${summaries[i].n} matches.</p></div>`).join('')}<p class="scale-note">${count?'Bars use the same scale for both players. Match length affects these averages.':'Both bars use a scale from 0% to 100%.'}</p></details></article>`;
  }).join('')}</div>`;
}
