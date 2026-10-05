import { defaults, summary, bands, leagues } from './football-core.mjs';
import { portraits as reviewedPortraits } from './portraits.mjs';
import { icon, brandMark } from './identity.mjs';
import { managerRows, matchMarket, marketContext, clubRecords, observedSpells, strategyReturns, rankingMinimum, isVerifiedActive, activeReviewDue } from './core.mjs';
const $=id=>document.getElementById(id), escape=s=>String(s).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const units=n=>`${n>0?'+':''}${n.toFixed(2)}u`, pct=n=>`${n>0?'+':''}${n.toFixed(1)}%`, color=n=>n<0?'negative':'positive';
let chartMode='profit', chartValues=[], chartGeometry;
let data, activity, portraits={...reviewedPortraits}, side='team', shown=50, rankShown=50, current=[];
const option=(value,label)=>`<option value="${escape(value)}">${escape(label)}</option>`;
function avatar(manager,compact=false){
 const photo=portraits[manager.id];
 return `<span class="avatar ${compact?'compact':''} ${photo?'has-photo':'no-photo'}" title="${photo?'Manager portrait':'Portrait unavailable'}" aria-hidden="true">${photo?`<img src="${escape(photo.file)}" alt="" width="64" height="64" loading="lazy" decoding="async">`:icon('manager')}</span>`;
}
function portraitsFor(manager,opponent){
 $('manager-faces').innerHTML=[manager,...(opponent?[opponent]:[])].map(m=>`<div class="person">${avatar(m)}<span>${escape(m.name)}</span></div>`).join('<span class="versus">vs</span>');
}
function matchExample(){
 const row=current.at(-1);
 $('market-example').hidden=!row;
 if(!row)return;
 const p=matchMarket(row),other=row.odds[row.venue==='home'?2:0];
 $('example-match').textContent=`${row.date} · ${row.home} ${row.hg}–${row.ag} ${row.away}`;
 $('example-prices').innerHTML=[[row.team,row.teamOdds,p.win],['Draw',row.odds[1],p.draw],[row.opponent,other,p.opponent]].map(([label,odds,prob],i)=>`<div class="price-tile"><span>${escape(label)}</span><strong>${odds.toFixed(2)}</strong><small>About ${(100*prob).toFixed(0)} chances in 100</small><div class="probability-track"><i style="width:${100*prob}%" class="outcome-${i}"></i></div></div>`).join('');
 $('example-explanation').textContent=`For this match, the recorded odds suggest roughly ${Math.round(p.win*100)} wins for ${row.team} if the same situation happened 100 times. So it adds ${p.win.toFixed(2)} to the expected-win total. One match can only end in a win, draw or loss; the fraction is an average expectation. We adjust all three odds together to remove the bookmaker’s built-in margin, then repeat this for every match in your selection.`;
}
function filters(){const b=bands[Number($('band').value)];return {...defaults,side,league:$('league').value,season:$('season').value,venue:$('venue').value,role:$('role').value,...($('band').value==='all'?{}:{min:b.min,max:b.max,upperExclusive:true})};}
const find=name=>data.managers.find(m=>m.name.toLowerCase()===name.trim().toLowerCase());
function rows(id,f,opp){return managerRows(data.fixtures,id,f,opp,$('club').value);}
function ledger(){
 $('ledger').innerHTML=current.slice().reverse().slice(0,shown).map(m=>`<tr><td>${escape(m.date)}</td><td><b>${escape(m.home)} – ${escape(m.away)}</b><div class="ledger-coaches">${[m.homeManager,m.awayManager].map(id=>`<span>${avatar({id,name:data.names[id]},true)}${escape(data.names[id])}</span>`).join('<em>vs</em>')}</div></td><td><span class="score-pill">${m.hg}–${m.ag}</span></td><td>${escape(side==='draw'?'Draw':side==='team'?m.team:m.opponent)}</td><td>${m.price.toFixed(2)}<small>${m.basis==='closing'?'Closing':'Last pre-match'}</small></td><td class="${color(m.profit)}">${units(m.profit)}</td></tr>`).join('');
 $('more').hidden=shown>=current.length;$('ledger-title').textContent=`Match ledger · ${current.length} bets · newest first`;
}
function chartReadout(index){
 const i=Math.max(0,Math.min(current.length,Number(index)||0)),row=current[i-1],value=chartValues[i]||0;
 $('chart-position').value=String(i);
 $('chart-readout').innerHTML=row?`<span>Bet ${i} of ${current.length} · ${escape(row.date)}</span><strong>${escape(row.home)} ${row.hg}–${row.ag} ${escape(row.away)}</strong><span>This bet: <b class="${color(row.profit)}">${units(row.profit)}</b> · ${chartMode==='profit'?'Running profit':'Below previous peak'}: <b>${units(value)}</b></span>`:'Before the first bet · 0u profit';
 if(chartGeometry){const {x,y}=chartGeometry;const cross=$('chart-crosshair'),dot=$('chart-dot');cross?.setAttribute('d',`M${x(i)} 25V260`);dot?.setAttribute('cx',x(i));dot?.setAttribute('cy',y(value));}
}
function chart(s){
 let peak=0;const falls=s.curve.map(v=>{peak=Math.max(peak,v);return v-peak;});
 chartValues=chartMode==='profit'?s.curve:falls;
 const lo=Math.min(0,...chartValues),hi=Math.max(0,...chartValues),pad=Math.max(1,(hi-lo)*.14),min=lo-pad,max=hi+pad;
 const width=window.matchMedia('(max-width:600px)').matches?430:1000,left=width===430?55:70,right=width-28;
 $('chart').setAttribute('viewBox',`0 0 ${width} 310`);
 $('chart').setAttribute('aria-label',chartMode==='profit'?'Running profit after each settled bet':'Fall below the previous profit peak after each bet');
 const y=v=>260-(v-min)/(max-min)*225,x=i=>left+i/Math.max(1,current.length)*(right-left);chartGeometry={x,y,left,right,width};
 const path=chartValues.map((v,i)=>`${i?'L':'M'}${x(i).toFixed(2)},${y(v).toFixed(2)}`).join(' '),area=`${path}L${x(current.length)} ${y(0)}L${left} ${y(0)}Z`;
 const ticks=[min+(max-min)*.15,min+(max-min)*.5,min+(max-min)*.85].filter(v=>Math.abs(v)>(max-min)*.07);
 $('chart').innerHTML=`<defs><linearGradient id="profit-fill" x1="0" y1="0" x2="0" y2="1"><stop stop-color="#8de4bc" stop-opacity=".3"/><stop offset="1" stop-color="#8de4bc" stop-opacity=".02"/></linearGradient><clipPath id="chart-above"><rect x="${left}" y="0" width="${right-left}" height="${y(0)}"/></clipPath><clipPath id="chart-below"><rect x="${left}" y="${y(0)}" width="${right-left}" height="310"/></clipPath></defs>`+ticks.map(v=>`<path d="M${left} ${y(v)}H${right}" stroke="#263d33"/><text x="${left-10}" y="${y(v)+5}" text-anchor="end">${v.toFixed(1)}u</text>`).join('')+`<path d="M${left} ${y(0)}H${right}" stroke="#6c8779" stroke-dasharray="4 5"/><text x="${left-10}" y="${y(0)+5}" text-anchor="end">0u</text><path d="${area}" fill="url(#profit-fill)" clip-path="url(#chart-above)"/><path d="${area}" fill="#db8e7733" clip-path="url(#chart-below)"/><path d="${path}" fill="none" stroke="#a0edc9" stroke-width="2.8" clip-path="url(#chart-above)"/><path d="${path}" fill="none" stroke="#e4a18a" stroke-width="2.8" clip-path="url(#chart-below)"/><path id="chart-crosshair" stroke="#b5d0c3" stroke-dasharray="3 4"/><circle id="chart-dot" r="5" fill="#ecfff4" stroke="#113524" stroke-width="2"/><text x="${left}" y="296">${escape(current[0]?.date||'No matches')}</text><text x="${right}" y="296" text-anchor="end">${escape(current.at(-1)?.date||'')}</text>`;
 $('chart-summary').innerHTML=`<div><small>Return on stakes</small><strong class="${color(s.roi)}">${s.bets?pct(s.roi):'—'}</strong></div><div><small>Total profit</small><strong class="${color(s.profit)}">${units(s.profit)}</strong></div><div><small>Biggest fall from a peak</small><strong>${s.drawdown.toFixed(2)}u</strong></div><div><small>Matches</small><strong>${s.bets}</strong></div>`;
 $('chart-description').textContent=chartMode==='profit'?'The running total after every bet, oldest to newest. Green is profit; coral is a loss. The dashed 0u line means you have broken even.':'How far the running profit fell below its previous high. A 5u fall means giving back five stakes — £50 if each stake is £10.';
 $('chart-caption').textContent=current.length?`Every point is a recorded result, with one equal stake per match. Move across the chart or use the slider to inspect a bet. This is past performance, not a forecast.`:'No matches meet these filters.';
 $('chart-position').max=String(current.length);$('chart-position').disabled=!current.length;chartReadout(current.length);
}

function context(){
 const s=marketContext(current),signed=n=>`${n>0?'+':''}${n.toFixed(1)}`;
 const sample=current.length<30?'Small sample — a few results can change this substantially.':`${current.length} priced matches in this selection.`;
 $('market-stats').innerHTML=[['Extra wins versus the odds',signed(s.excessWins),s.actualWins,s.expectedWins,'wins'],['Extra league points versus the odds',signed(s.excessPoints),s.actualPoints,s.expectedPoints,'points']].map(([title,value,actual,expected,unit])=>`<article class="stat market-stat"><span>${title}</span><strong class="${color(Number(value))}">${current.length?value:'—'}</strong><div class="actual-expected"><div><small>Actual ${unit}</small><b>${current.length?actual:'—'}</b></div><div><small>From match odds</small><b>${current.length?expected.toFixed(1):'—'}</b></div></div><p>${current.length?`${Math.abs(Number(value)).toFixed(1)} ${Number(value)>=0?'more':'fewer'} ${unit} than the recorded odds suggested.`:'No matches meet these filters.'}</p></article>`).join('');
 $('market-sample').textContent=current.length?sample:'Try widening the season, opponent or price filters.';
 matchExample();
 $('club-records').innerHTML=clubRecords(current).map(c=>`<tr><td>${escape(c.club)}<small>${c.first} to ${c.last}</small></td><td>${c.bets}</td><td>${c.results.W} / ${c.results.D} / ${c.results.L}</td><td class="${color(c.profit)}">${units(c.profit)}</td><td class="${color(c.roi)}">${pct(c.roi)}</td></tr>`).join('');
 $('spells').innerHTML=observedSpells(current).map(c=>`<li><strong>${escape(c.club)}</strong><span>${c.first} → ${c.last}</span><small>${c.bets} selected matches</small></li>`).join('');
 const labels={team:'Back manager’s team',draw:'Back the draw',opponent:'Back opponent'};
 $('strategy-stats').innerHTML=strategyReturns(current).map(r=>`<article class="stat ${r.side===side?'selected-strategy':''}"><span>${labels[r.side]}</span><strong class="${color(r.roi)}">${r.bets?pct(r.roi):'—'} <em>ROI</em></strong><small class="strategy-profit">${units(r.profit)} profit · ${r.wins} winning bets</small><p>${r.side==='draw'?'Only a draw wins this bet.':'A draw loses this bet.'}</p></article>`).join('');
 const counts=current.reduce((acc,r)=>(acc[r.basis]=(acc[r.basis]||0)+1,acc),{});
 $('price-coverage').textContent=`Selected sample: ${counts.closing||0} closing prices · ${counts['last-pre-match']||0} last pre-match prices. All three strategies use these same ${current.length} fixtures.`;
}
function render(){
 const manager=find($('manager').value),opponent=find($('opponent').value),f=filters();
 const invalid=($('manager').value.trim()&&!manager)||($('opponent').value.trim()&&!opponent);
 $('status').textContent=invalid?'Choose an exact manager name from the suggestions.':manager&&manager.id===opponent?.id?'Choose two different managers.':'';
 if(invalid||manager?.id===opponent?.id&&manager){$('record').hidden=true;$('rankings').innerHTML='';$('rank-count').textContent='Correct the manager selection to see rankings.';$('more-rankings').hidden=true;current=[];return;}
 $('record').hidden=!manager;$('swap').hidden=!manager||!opponent;
 if(manager){portraitsFor(manager,opponent);current=rows(manager.id,f,opponent?.id||'all');const s=summary(current);
  $('record-title').textContent=manager.name+(opponent?' vs '+opponent.name:'');
  $('stats').innerHTML=[['ROI',s.bets?pct(s.roi):'—','Profit as a percentage of all stakes'],['Profit',units(s.profit),'If 1u = £10, '+new Intl.NumberFormat('en-GB',{style:'currency',currency:'GBP'}).format(s.profit*10)+' profit / loss'],['Bets',String(s.bets),`${s.wins} winning / ${s.losses} losing bets`],['Team W / D / L',`${s.results.W} / ${s.results.D} / ${s.results.L}`,s.bets<30?'Small sample — interpret cautiously':'Results of the manager’s team']].map(([label,value,note])=>`<div class="stat"><span>${label}</span><strong>${value}</strong><small class="muted">${note}</small></div>`).join('');chart(s);ledger();context();
 }
 const activeOnly=$('activity').value==='active',today=new Date().toISOString().slice(0,10);
 const candidates=data.managers.filter(m=>!activeOnly||isVerifiedActive(m.id,activity,today));
 const ranking=candidates.map(m=>({...m,...summary(rows(m.id,f,opponent?.id||'all'))})).filter(m=>m.bets>=rankingMinimum()).sort((a,b)=>b[$('sort').value]-a[$('sort').value]||b.bets-a.bets);
 $('rankings').innerHTML=ranking.slice(0,rankShown).map((m,i)=>`<tr${m.id===manager?.id?' class="selected-row"':''}><td><button data-manager="${escape(m.id)}"><span class="rank-number">${String(i+1).padStart(2,'0')}</span>${avatar(m,true)}<span>${escape(m.name)}</span>${icon('arrow')}</button></td><td>${m.bets}${m.bets<10?'<small class="sample-label">Very small sample</small>':m.bets<30?'<small class="sample-label">Small sample</small>':''}</td><td><span class="result-wins">${m.results.W}</span> / ${m.results.D} / ${m.results.L}</td><td class="${color(m.profit)}">${units(m.profit)}</td><td class="${color(m.roi)} roi-cell">${pct(m.roi)}</td><td>${m.drawdown.toFixed(2)}u</td></tr>`).join('');
 $('more-rankings').hidden=rankShown>=ranking.length;
 $('rank-count').textContent=`Showing ${Math.min(rankShown,ranking.length)} of ${ranking.length} qualifying managers. ${opponent?'H2H includes pairings from one recorded meeting. A few meetings cannot establish a reliable edge.':'Includes every manager with at least one matching fixture. Small samples are labelled, not hidden.'} Search any manager above to inspect their record.`;
 const reviewsDue=candidates.filter(m=>activeReviewDue(m.id,activity,today)).length;
 $('activity-note').textContent=activeOnly?(activity?`Showing ${candidates.length} managers active at their last check.${reviewsDue?' Some roles are due for review; their records remain available.':''} Choose Full historical archive for all managers.`:'Manager status could not load. Choose Full historical archive to see the records.'):'Showing current and past managers.';
}
async function init(){
 document.addEventListener('error',event=>{
  const image=event.target;
  if(!(image instanceof HTMLImageElement))return;
  const frame=image.closest('.avatar');
  if(frame){frame.classList.remove('has-photo');frame.classList.add('no-photo');frame.title='Portrait unavailable';frame.innerHTML=icon('manager');}
 },true);
 document.querySelectorAll('[data-icon]').forEach(el=>el.innerHTML=icon(el.dataset.icon));
 $('brand-mark').innerHTML=brandMark();
 const response=await fetch('data.json');if(!response.ok)throw Error('Archive unavailable');data=await response.json();data.names=Object.fromEntries(data.managers.map(m=>[m.id,m.name]));
 try{const r=await fetch('portraits-auto.json');if(r.ok)portraits={...await r.json(),...reviewedPortraits};}catch{/* Keep reviewed portraits and the explicit unavailable icon. */}
 try{const r=await fetch('activity.json');if(r.ok)activity=await r.json();}catch{/* Unknown status stays out of the active ranking. */}
 if($('activity-review-details'))$('activity-review-details').textContent=activity?`Manager status list updated ${activity.asOf}. Roles are checked individually. A review date does not remove a manager or their match history. Confirmed departures update this list; other managers remain searchable in the full archive.`:'';
 const dateLabel=value=>new Intl.DateTimeFormat('en-GB',{day:'numeric',month:'long',year:'numeric',timeZone:'UTC'}).format(new Date(value+'T12:00:00Z'));
 $('coverage').textContent=`League match history from ${dateLabel(data.fromDate)} to ${dateLabel(data.through)}. Coverage varies by manager and league.`;
 $('freshness-date').textContent=dateLabel(data.through);
 $('archive-count').textContent=data.fixtures.length.toLocaleString('en-GB');
 $('manager-count').textContent=data.managers.length.toLocaleString('en-GB');
 $('photo-count').textContent=`${Object.keys(portraits).length} managers have credited photos. A neutral manager symbol marks portraits not yet available.`;
 $('hero-portraits').innerHTML=['Pep Guardiola','Jürgen Klopp','Carlo Ancelotti'].map(name=>data.managers.find(m=>m.name===name)).filter(Boolean).map(m=>`<figure class="hero-portrait">${portraits[m.id]?`<img src="${escape(portraits[m.id].file)}" alt="" width="160" height="200" decoding="async">`:avatar(m)}<figcaption>${escape(m.name)}<small>IN THE ARCHIVE</small></figcaption></figure>`).join('');
 const exclusionLabels={disputed_manager_assignment:'disputed manager assignments',ambiguous_manager_identity:'ambiguous manager names',missing_manager:'missing managers',score_conflict:'conflicting scores',missing_or_ambiguous_atlas_fixture:'unmatched or duplicate price fixtures',unmapped_team:'unmapped clubs',missing_prices:'missing prices',ambiguous_manager_fixture:'duplicate manager fixtures',unknown_price_basis:'unknown price timing',duplicate_fixture:'duplicate fixtures'};
 $('exclusions').textContent=Object.entries(data.coverage?.exclusions||{}).map(([k,v])=>`${v.toLocaleString('en-GB')} ${exclusionLabels[k]||k.replaceAll('_',' ')}`).join(' · ');
 $('photo-credits').innerHTML=Object.values(portraits).map(p=>`<li><a href="${escape(p.source)}">${escape(p.name)} photo</a> — ${escape(p.credit)} · <a href="${escape(p.licenseUrl)}">${escape(p.license)}</a>. ${escape(p.changes)}</li>`).join('');
 $('managers').innerHTML=data.managers.map(m=>option(m.name,m.name)).join('');
 $('club').innerHTML+= [...new Set(data.fixtures.flatMap(m=>[m.home,m.away]))].sort().map(t=>option(t,t)).join('');
 $('league').innerHTML+=Object.entries(leagues).map(([k,v])=>option(k,v)).join('');
 $('season').innerHTML+=[...new Set(data.fixtures.map(m=>m.season))].sort().reverse().map(s=>option(s,s)).join('');
 $('band').innerHTML+=bands.map((b,i)=>option(i,b.label)).join('');
 window.matchMedia('(max-width:600px)').addEventListener('change',()=>{if(current.length)chart(summary(current));});
 document.querySelectorAll('select,input:not(#chart-position)').forEach(el=>el.addEventListener('change',()=>{shown=50;rankShown=50;render();}));
 document.querySelectorAll('[data-side]').forEach(el=>el.addEventListener('click',()=>{side=el.dataset.side;document.querySelectorAll('[data-side]').forEach(b=>b.setAttribute('aria-pressed',String(b===el)));shown=50;rankShown=50;render();}));
 $('chart-position').addEventListener('input',e=>chartReadout(e.target.value));
 document.querySelectorAll('[data-chart]').forEach(b=>b.addEventListener('click',()=>{chartMode=b.dataset.chart;document.querySelectorAll('[data-chart]').forEach(el=>el.setAttribute('aria-pressed',String(el===b)));chart(summary(current));}));
 $('chart').addEventListener('pointermove',e=>{if(!chartGeometry||!current.length)return;const box=e.currentTarget.getBoundingClientRect(),px=(e.clientX-box.left)/box.width*chartGeometry.width;chartReadout(Math.round((px-chartGeometry.left)/(chartGeometry.right-chartGeometry.left)*current.length));});
 $('example').onclick=()=>{$('manager').value='Pep Guardiola';$('opponent').value='Jürgen Klopp';shown=50;rankShown=50;render();$('record').scrollIntoView({behavior:'smooth',block:'start'});};
 $('swap').onclick=()=>{const a=$('manager').value;$('manager').value=$('opponent').value;$('opponent').value=a;render();};
 $('more').onclick=()=>{shown+=50;ledger();};
 $('more-rankings').onclick=()=>{rankShown+=50;render();};
 $('reset').onclick=()=>{document.querySelectorAll('select').forEach(e=>e.selectedIndex=0);$('manager').value='';$('opponent').value='';document.querySelector('[data-side="team"]').click();};
 $('rankings').onclick=e=>{const b=e.target.closest('[data-manager]');if(b){$('manager').value=data.names[b.dataset.manager];shown=50;render();$('record').scrollIntoView({behavior:'smooth',block:'start'});}};
 render();
}
init().catch(()=>{$('status').textContent='The archive could not load. Reload this preview to try again.';});
