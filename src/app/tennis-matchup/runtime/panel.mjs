import {compactOddsComparison,comparisonMetrics} from './comparison.mjs';
import {symbol} from './identity.mjs';
import {SURFACES,rowsFor,summary,startDate,recordedCount} from './core.mjs';

export async function mountMatchup(root,manifestUrl,signal){
const $=id=>root.querySelector(`[id="${id}"]`);
const esc=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const num=v=>v.toLocaleString('en-GB');
const pct=v=>v===null?'—':v.toFixed(1)+'%';
const date=v=>new Intl.DateTimeFormat('en-GB',{day:'numeric',month:'short',year:'numeric',timeZone:'UTC'}).format(new Date(v+'T12:00:00Z'));
const icon=name=>symbol(name==='region'?'odds':name,'section-icon');
const metricIcon=key=>`<span class="metric-symbol" aria-hidden="true">${symbol(key)}</span>`;
root.querySelectorAll('[data-brand-symbol]').forEach(el=>{el.innerHTML=symbol(el.dataset.brandSymbol);});
const playerChip=(player,slot)=>`<span class="player-chip side-${slot}"><i aria-hidden="true"></i>${esc(player.name)}</span>`;
let data;
let requestSequence=0;
const cache=new Map();
let selected=[];
let sorted=[];
const labels=new Map();
const fields=['months','as-of','surface','region','country'];
function filters(){return {mode:root.querySelector('[name=record-mode]:checked').value,months:$('months').value,asOf:$('as-of').value,surface:$('surface').value,region:$('region').value,country:$('country').value};}
function label(player){return `${player.name} (${player.country})`;}
function populateCountries(){
  const current=$('country').value;
  const countries=data.countries.filter(c=>$('region').value==='all'||c.region===$('region').value).sort((a,b)=>a.name.localeCompare(b.name));
  $('country').innerHTML='<option value="all">All countries</option>'+countries.map(c=>`<option value="${esc(c.code)}">${esc(c.name)}</option>`).join('');
  if(countries.some(c=>c.code===current)) $('country').value=current;
}
function playerCard(player,s,i) {
  const portrait=data.portraits[player.id]?.url;
  return `<article class="player-card side-${i}"><div class="identity">${portrait?`<img src="${esc(portrait)}" width="72" height="72" alt="" decoding="async">`:'<span class="portrait-empty" aria-hidden="true">'+esc(player.initials)+'</span>'}<div><p class="eyebrow">${esc(player.country)} · PLAYER ${i+1}</p><h2>${esc(player.name)}</h2></div></div><div class="player-record"><strong>${s.wins}<small> W</small> <span>/</span> ${s.losses}<small> L</small></strong><span>${num(s.n)} matches ${s.n<15?'<b class="sample">Small sample</b>':''}</span></div><p>${s.n?`${date(s.first)} – ${date(s.last)}`:'No matches in this selection'}</p></article>`;
}
function surfaceCell(s){return `<td class="${s.n<15?'thin':''}"><strong>${pct(s.winRate)}</strong><span>${s.wins} wins · ${s.losses} losses</span><small>${s.n} ${s.n===1?'match':'matches'}${s.n>0&&s.n<15?' · small sample':''}</small></td>`;}
function countLabel(stats,key){const count=recordedCount(stats,key);return count===null?'—':num(count);}
function historyRows(rows,limit=10){return [...rows].reverse().slice(0,limit).map(r=>`<tr><td><time>${date(r.date)}</time><strong>${esc(data.players[r.opponent].name)}</strong><small>${esc(r.event)} · ${esc(r.country||'Location unknown')}</small>${r.score?`<small>Winner: ${esc(data.players[r.winner===0?r.p1:r.p2].name)} · ${esc(r.score)} (winner first)</small>`:''}<div class="match-counts"><span>Aces <b>${countLabel(r.stats,'aces')}</b></span><span>Double faults <b>${countLabel(r.stats,'doubleFaults')}</b></span></div></td><td><span class="result ${r.won?'win':'loss'}">${r.won?'W':'L'}</span></td><td><strong>${Number.isFinite(r.odds)&&r.odds>1?r.odds.toFixed(2):'—'}</strong><small>${pct(r.probability===null?null:100*r.probability)} chance from odds</small></td></tr>`).join('');}
function h2hHistory(rows,players){
  if(!rows.length)return '<p class="empty">No meetings match these filters. Try more years or a wider location.</p>';
  const wins=rows.filter(r=>r.won).length;
  return `<details class="h2h-record"><summary><span class="record-toggle-icon" aria-hidden="true">${icon('history')}</span><span class="record-toggle-title">Head-to-head match record<small>${rows.length} meetings · ${esc(players[0].name)} ${wins}–${rows.length-wins} ${esc(players[1].name)}</small></span><span class="record-toggle-action"><span class="when-closed">Show matches</span><span class="when-open">Hide matches</span><b aria-hidden="true">⌄</b></span></summary><p class="record-help">Select a match to show or hide its statistics. Both players use the same rows so you can compare at a glance.</p><div class="meeting-list">${[...rows].reverse().map((r,index)=>{
    const winName=data.players[r.winner===0?r.p1:r.p2].name;
    const winSlot=r.won?0:1;
    const sides=players.map((_,i)=>{
      const first=selected[i]===r.p1;
      return {stats:first?r.stats1:r.stats2,odds:first?r.o1:r.o2,probability:r.probability===null?null:100*(i===0?r.probability:1-r.probability)};
    });
    const rate=(stats,key)=>{const pair=stats?.[key];return recordedCount(stats,key)===null?'—':`${pct(100*pair[0]/pair[1])}<small>${pair[0]} / ${pair[1]} points</small>`;};
    const metrics=[
      ['Aces','aces',s=>countLabel(s.stats,'aces')],
      ['Double faults','doubleFaults',s=>countLabel(s.stats,'doubleFaults')],
      ['Service points won','serve',s=>rate(s.stats,'serve')],
      ['Return points won','return',s=>rate(s.stats,'return')],
      ['Pre-match odds',null,s=>Number.isFinite(s.odds)&&s.odds>1?s.odds.toFixed(2):'—'],
      ['Chance from odds',null,s=>pct(s.probability)],
    ];
    return `<details class="meeting match-accordion"${index===0?' open':''}><summary><span class="meeting-event"><time>${date(r.date)}</time><strong>${esc(r.event)}</strong></span><span class="meeting-outcome"><span class="winner-badge side-${winSlot}">Winner · ${esc(winName)}</span><span class="meeting-score">${esc(r.score||'Score unavailable')}</span></span><span class="match-chevron" aria-hidden="true">⌄</span></summary><div class="match-detail"><p class="score-key">Score shown with the winner first. A dash means the statistic is unavailable.</p><table class="match-stats"><caption class="sr-only">${esc(r.event)}, ${date(r.date)}: statistics for both players</caption><thead><tr><th scope="col">Match statistic</th>${players.map((p,i)=>`<th scope="col">${playerChip(p,i)}</th>`).join('')}</tr></thead><tbody>${metrics.map(([name,key,value])=>`<tr><th scope="row"><span class="match-stat-label">${key?metricIcon(key):'<span class="price-symbol" aria-hidden="true">'+symbol(name==='Pre-match odds'?'odds':'expected')+'</span>'}${name}</span></th>${sides.map((s,i)=>`<td class="side-${i}">${value(s)}</td>`).join('')}</tr>`).join('')}</tbody></table></div></details>`;
  }).join('')}</div></details>`;
}
function syncExample(){ $('load-example').hidden=Boolean($('player-a').value.trim()||$('player-b').value.trim()); }
function pauseComparison(){
  requestSequence++;
  syncExample();
  $('results').hidden=true;$('form-error').hidden=true;
  $('selection').textContent='Choose two players above, then select Compare players.';
}
function updateSuggestions(input,list){
  const query=input.value.trim().toLocaleLowerCase();
  list.innerHTML=query.length<2?'':sorted.filter(({p})=>p.name.toLocaleLowerCase().includes(query)).slice(0,12).map(({p})=>`<option value="${esc(label(p))}"></option>`).join('');
}
function render(){
  const f=filters();
  $('filter-summary').textContent=[$('months').selectedOptions[0].textContent,SURFACES[f.surface]||'All surfaces',f.country!=='all'?$('country').selectedOptions[0].textContent:f.region==='all'?'All locations':f.region].join(' · ');
  if(selected.length!==2 || !f.asOf || f.asOf<'2022-01-02' || f.asOf>data.asOf)return;
  const players=selected.map(i=>data.players[i]);
  const h2h=f.mode==='h2h';
  const forPlayer=(slot,surface=f.surface)=>({...f,surface,...(h2h?{opponent:selected[1-slot]}:{})});
  const recordLabel=h2h?'Head-to-head · only each other':'Player profile · all opponents';
  const rows=selected.map((i,slot)=>rowsFor(data,i,forPlayer(slot)));
  const summaries=rows.map(summary);
  const location=f.country!=='all'?data.countries.find(c=>c.code===f.country)?.name:f.region==='all'?'All regions':f.region;
  const scope=`${recordLabel} · ${location} · ${SURFACES[f.surface]||'All surfaces'} · ${date(startDate(f.asOf,f.months))} to before ${date(f.asOf)}`;
  $('selection').textContent=scope;
  $('results').innerHTML=`<div class="player-grid">${players.map((p,i)=>playerCard(p,summaries[i],i)).join('')}</div>
  <nav class="comparison-nav" aria-label="Comparison sections"><a href="#comparison-odds">${symbol('odds')}<span>Results &amp; odds</span></a><a href="#comparison-profile">${symbol('serve')}<span>Serve &amp; return</span></a><a href="#comparison-courts">${symbol('court')}<span>Courts</span></a><a href="#comparison-matches">${symbol('history')}<span>Matches</span></a></nav>
  <section class="section" id="comparison-odds"><div class="section-heading">${icon('region')}<div><p class="eyebrow">RESULTS &amp; PRE-MATCH ODDS</p><h2>Did the results beat the odds?</h2></div></div><p class="section-copy">Compare actual wins with the number suggested by the recorded prices.</p>${compactOddsComparison(players,summaries)}</section>
  <section class="section" id="comparison-profile"><div class="section-heading">${icon('serve')}<div><p class="eyebrow">THE PLAYING PROFILE</p><h2>Serve, return and the points between.</h2></div></div><p class="section-copy">Compare point rates and average aces and double faults. Open each statistic for totals and sample size.</p>${comparisonMetrics(players,summaries)}</section>
  <section class="section" id="comparison-courts"><div class="section-heading">${icon('court')}<div><p class="eyebrow">SURFACE / ENVIRONMENT</p><h2>Different courts. Different records.</h2></div></div><p class="section-copy">${h2h?'Meetings between these two players only':'Each player against all opponents'}, with the same dates and location, across all four court categories. Select a court to apply it to the full comparison. The percentage is the share of matches won.</p><div class="surface-table"><table><thead><tr><th scope="col">Court</th>${players.map(p=>`<th scope="col">${esc(p.name)}</th>`).join('')}</tr></thead><tbody>${Object.entries(SURFACES).map(([key,name])=>`<tr${f.surface===key?' class="selected-court"':''}><th scope="row"><button data-surface="${key}" aria-pressed="${f.surface===key}"><i class="court-dot ${key}"></i>${name}</button></th>${selected.map((i,slot)=>surfaceCell(summary(rowsFor(data,i,forPlayer(slot,key))))).join('')}</tr>`).join('')}</tbody></table></div></section>
  <section class="section" id="comparison-matches"><div class="section-heading">${icon('history')}<div><p class="eyebrow">CHECK THE UNDERLYING MATCHES</p><h2>${h2h?'Head-to-head matches in this selection':'Each player’s matches against all opponents'}</h2></div></div><p class="section-copy">${h2h?'Each meeting appears once, with both players’ statistics side by side. Retirements are excluded.':'Latest ten matches per player within the filters. Aces and double faults belong to the player named above each list.'}</p><p class="section-copy">Each price is the named player’s recorded pre-match odds. “Chance from odds” estimates the win chance after removing the bookmaker’s margin. A dash means the statistic is missing; it does not mean zero.</p>${h2h?h2hHistory(rows[0],players):`<div class="two-up histories">${players.map((p,i)=>`<details${h2h?' open':''}><summary>${esc(p.name)} · ${h2h?'all '+rows[i].length:'latest '+Math.min(10,rows[i].length)} matches</summary><table><thead><tr><th scope="col">Date / opponent</th><th scope="col">Result</th><th scope="col">Pre-match odds</th></tr></thead><tbody>${historyRows(rows[i],h2h?rows[i].length:10)||'<tr><td colspan="3">No matching records.</td></tr>'}</tbody></table></details>`).join('')}</div>`}</section>`;
  $('results').querySelectorAll('img').forEach(img=>img.addEventListener('error',()=>{img.hidden=true;},{once:true}));
  $('results').querySelectorAll('[data-surface]').forEach(button=>button.addEventListener('click',()=>{
    const key=button.dataset.surface;$('surface').value=key;render();$('results').querySelector(`[data-surface="${key}"]`).focus({preventScroll:true});
  }));
}
async function applyPlayers(){
  const sequence=++requestSequence;
  syncExample();
  const a=labels.get($('player-a').value.trim().toLocaleLowerCase()),b=labels.get($('player-b').value.trim().toLocaleLowerCase());
  const error=a===undefined||b===undefined?'Select both players from the search suggestions.':a===b?'Choose two different players.':'';
  $('form-error').hidden=!error;$('form-error').textContent=error;
  if(error){$('results').hidden=true;$('selection').textContent='Comparison paused: '+error;return false;}
  $('results').hidden=true;
  $('selection').textContent='Loading the selected players’ records…';
  try {
    const lists=await Promise.all([a,b].map(async player=>{
      if(cache.has(player))return cache.get(player);
      const response=await fetch(new URL(`${player}.json`,new URL(manifestUrl,location.origin)),{signal});
      if(!response.ok)throw new Error('Player records unavailable');
      const shard=await response.json();
      if(shard.version!==data.version||shard.player!==player||!Array.isArray(shard.matches))throw new Error('Snapshot mismatch');
      cache.set(player,shard.matches);return shard.matches;
    }));
    if(signal.aborted||sequence!==requestSequence)return false;
    data.matches=[...new Map(lists.flat().map(row=>[row.id,row])).values()];
    selected=[a,b];$('results').hidden=false;render();return true;
  } catch(error) {
    if(signal.aborted||sequence!==requestSequence)return false;
    $('form-error').hidden=false;$('form-error').textContent='These records could not load. Please select Compare players to try again.';
    $('selection').textContent='Comparison unavailable; no results are being shown.';
    console.error(error);return false;
  }
}
try {
  const response=await fetch(manifestUrl,{signal});
  if(!response.ok)throw new Error('Data unavailable');
  data=await response.json();
  if(data.schema!==2 || !Array.isArray(data.players))throw new Error('Invalid snapshot');
  if(signal.aborted)return;
  data.matches=[];
  sorted=data.players.map((p,i)=>({p,i})).sort((a,b)=>a.p.name.localeCompare(b.p.name));
  sorted.forEach(({p,i})=>{labels.set(label(p).toLocaleLowerCase(),i);labels.set(p.name.toLocaleLowerCase(),i);});
  ['a','b'].forEach(side=>{
    const input=$('player-'+side),list=$('player-options-'+side);
    input.addEventListener('input',()=>{updateSuggestions(input,list);pauseComparison();});
    input.addEventListener('focus',()=>input.select());
  });
  $('load-example').addEventListener('click',()=>{
    const players=['Carlos Alcaraz','Jannik Sinner'].map(name=>data.players.find(p=>p.name===name));
    if(players.some(p=>!p))return;
    $('player-a').value=label(players[0]);$('player-b').value=label(players[1]);
    root.querySelector('[name=record-mode][value=h2h]').checked=true;
    $('months').value='archive';$('surface').value='outdoor-hard';$('region').value='all';populateCountries();$('country').value='all';applyPlayers();
  });
  $('as-of').value=data.asOf;$('as-of').max=data.asOf;
  populateCountries();
  $('as-of').addEventListener('invalid',()=>{$('filter-drawer').open=true;});
  $('controls').addEventListener('submit',event=>{event.preventDefault();applyPlayers();});
  const refresh=()=>{if(!$('player-a').value.trim()||!$('player-b').value.trim()){pauseComparison();return;}if($('controls').reportValidity())applyPlayers();};
  root.querySelectorAll('[name=record-mode]').forEach(input=>input.addEventListener('change',refresh));
  fields.forEach(id=>$(id).addEventListener('change',()=>{if(id==='region')populateCountries();refresh();}));
  $('swap').addEventListener('click',()=>{const a=$('player-a').value;$('player-a').value=$('player-b').value;$('player-b').value=a;refresh();});
  $('coverage').textContent=`Data checked ${date(data.asOf)}. Latest included result: ${date(data.through)}. ${num(data.totalMatches)} matches in the archive. Your filters determine how many are shown.`;
  $('loading').hidden=true;$('tool').hidden=false;

} catch(error) {
  if(signal.aborted)return;
  $('loading').textContent='The player index could not load. Please reload the page to try again.';
  $('loading').setAttribute('role','alert');console.error(error);
}

}
