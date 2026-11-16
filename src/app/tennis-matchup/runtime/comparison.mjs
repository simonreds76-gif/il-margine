import {METRICS} from './core.mjs';
import {symbol} from './identity.mjs';

const esc=value=>String(value??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const number=value=>value.toLocaleString('en-GB');
const pct=value=>value===null?'Unavailable':`${value.toFixed(1)}%`;
const signed=value=>value===null?'—':`${value>0?'+':''}${value.toFixed(1)}`;
const chip=(player,slot)=>`<span class="player-chip side-${slot}"><i aria-hidden="true"></i>${esc(player.name)}</span>`;
// Round once for display; a rounded zero shows as 0.0, never -0.0.
const fixed=(value,digits)=>{const v=Number(value.toFixed(digits))||0;return {tone:v>0?'positive':v<0?'negative':'neutral',text:`${v>0?'+':''}${v.toFixed(digits)}`};};

// PREVIEW ONLY (Fable, 16 Nov 2026). New display block, kept in one place so it is easy to check or replace.
// It reads the rows rowsFor() already returns and the counts summary() already gives:
//   bets = summaries[i].priced (both prices recorded), won = summaries[i].actual.
// The only figure worked out here is the flat one-unit total: recorded price minus the stake for a win,
// minus the stake for a loss, over exactly those priced rows. ROI is that total divided by the bets.
// core.mjs is untouched. Check these figures against the house return rules before any sign-off.
export function historicalReturns(players,rows,summaries,h2h,links) {
  const unit=h2h?['meeting','meetings']:['match','matches'];
  const cells=players.map((player,i)=>{
    const s=summaries[i];
    const coverage=`${number(s.priced)} of ${number(s.n)} ${s.n===1?unit[0]:unit[1]} had recorded odds`;
    const link=`<a class="mx-atlas-link" href="${esc(links[i])}" aria-label="View ${esc(player.name)} betting returns in Return Atlas">${symbol('odds')}<span>Betting returns in Return Atlas <span aria-hidden="true">↗</span></span></a>`;
    if(!s.priced)return `<div class="mx-return side-${i}">${chip(player,i)}<p class="mx-roi neutral"><strong>—</strong><span>ROI</span></p><p class="mx-return-line">${s.n?`No return shown. ${coverage[0].toUpperCase()+coverage.slice(1)}.`:`No ${unit[1]} in this selection.`}</p>${link}</div>`;
    const total=rows[i].reduce((sum,row)=>row.probability===null?sum:sum+(row.won?row.odds-1:-1),0);
    const roi=fixed(100*total/s.priced,1),profit=fixed(total,2);
    return `<div class="mx-return side-${i}">${chip(player,i)}<p class="mx-roi ${roi.tone}"><strong>${roi.text}%</strong><span>ROI</span></p><p class="mx-return-line"><b>${profit.text} units</b> from ${number(s.priced)} one-unit ${s.priced===1?'bet':'bets'} · ${number(s.actual)} won</p><p class="mx-return-cover">${coverage}</p>${link}</div>`;
  }).join('');
  return `<div class="mx-returns"><div class="mx-returns-head"><h3>${symbol('odds')}<span>Historical return</span></h3><p>What one unit on each player to win would have returned in ${h2h?'their meetings with recorded pre-match odds':'each player’s matches with recorded pre-match odds, against all opponents'}.</p></div>
    <div class="mx-returns-grid">${cells}</div>
    <p class="mx-returns-note">${summaries.some(s=>s.priced<30)?'Small sample. One result can move these figures substantially. ':''}Past results at the prices recorded before each match. Not a forecast, and not current odds.</p>
    <details class="mx-returns-explainer"><summary>How is the return worked out?</summary><p>Every ${unit[0]} with recorded odds for both players counts as one bet of one unit on the player to win. A win adds the recorded price minus the stake. A loss costs the stake. ROI is the total divided by the number of bets.</p><p><strong>Example:</strong> wins at 1.80 and 2.10 and one loss give +0.80 +1.10 -1.00 = +0.90 units from 3 bets, an ROI of +30.0%.</p><p>${unit[1][0].toUpperCase()+unit[1].slice(1)} without odds count in the record but not in the return. Each price is listed with its match under Matches.</p></details></div>`;
}

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
