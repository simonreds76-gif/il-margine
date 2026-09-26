import { defaults, summary, bands, leagues } from './football-core.mjs';
import { managerRows } from './core.mjs';
const $=id=>document.getElementById(id), escape=s=>String(s).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const units=n=>`${n>0?'+':''}${n.toFixed(2)}u`, pct=n=>`${n>0?'+':''}${n.toFixed(1)}%`, color=n=>n<0?'negative':'positive';
let data, side='team', shown=50, current=[];
const option=(value,label)=>`<option value="${escape(value)}">${escape(label)}</option>`;
function filters(){const b=bands[Number($('band').value)];return {...defaults,side,league:$('league').value,season:$('season').value,venue:$('venue').value,role:$('role').value,...($('band').value==='all'?{}:{min:b.min,max:b.max,upperExclusive:true})};}
const find=name=>data.managers.find(m=>m.name.toLowerCase()===name.trim().toLowerCase());
function rows(id,f,opp){return managerRows(data.fixtures,id,f,opp,$('club').value);}
function ledger(){
 $('ledger').innerHTML=current.slice().reverse().slice(0,shown).map(m=>`<tr><td>${escape(m.date)}</td><td>${escape(m.home)} – ${escape(m.away)}<small>${escape(data.names[m.homeManager])} / ${escape(data.names[m.awayManager])}</small></td><td>${m.hg}–${m.ag}</td><td>${escape(side==='draw'?'Draw':side==='team'?m.team:m.opponent)}</td><td>${m.price.toFixed(2)}<small>${escape(m.basis)}</small></td><td class="${color(m.profit)}">${units(m.profit)}</td></tr>`).join('');
 $('more').hidden=shown>=current.length;$('ledger-title').textContent=`Match ledger · ${current.length} bets · newest first`;
}
function chart(s){
 const lo=Math.min(0,...s.curve),hi=Math.max(0,...s.curve),pad=Math.max(2,(hi-lo)*.1),min=lo-pad,max=hi+pad;
 const y=v=>230-(v-min)/(max-min)*210,x=i=>70+i/Math.max(1,current.length)*905;
 const path=s.curve.map((v,i)=>`${i?'L':'M'}${x(i).toFixed(2)},${y(v).toFixed(2)}`).join(' ');
 $('chart').innerHTML=`<defs><linearGradient id="profit-fill" x1="0" y1="0" x2="0" y2="1"><stop stop-color="#78dfb7" stop-opacity=".3"/><stop offset="1" stop-color="#78dfb7" stop-opacity=".02"/></linearGradient></defs>`+[min,0,max].map(v=>`<path d="M70 ${y(v)}H975" stroke="#33454e" ${v===0?'stroke-dasharray="5 5"':''}/><text x="60" y="${y(v)+5}" text-anchor="end">${v.toFixed(1)}u</text>`).join('')+`<path d="${path}L975 ${y(0)}L70 ${y(0)}Z" fill="url(#profit-fill)"/><path d="${path}" fill="none" stroke="#80e8c2" stroke-width="3"/><text x="70" y="267">${escape(current[0]?.date||'No matches')}</text><text x="975" y="267" text-anchor="end">${escape(current.at(-1)?.date||'')}</text>`;
 $('chart-caption').textContent=current.length?`${current.length} bets · ${units(s.profit)} final profit · ${s.drawdown.toFixed(2)}u maximum fall from a previous profit peak.`:'No priced matches meet this selection.';
}
function render(){
 const manager=find($('manager').value),opponent=find($('opponent').value),f=filters();
 const invalid=($('manager').value.trim()&&!manager)||($('opponent').value.trim()&&!opponent);
 $('status').textContent=invalid?'Choose an exact manager name from the suggestions.':manager&&manager.id===opponent?.id?'Choose two different managers.':'';
 if(invalid||manager?.id===opponent?.id&&manager){$('record').hidden=true;$('rankings').innerHTML='';return;}
 $('record').hidden=!manager;$('swap').hidden=!manager||!opponent;
 if(manager){current=rows(manager.id,f,opponent?.id||'all');const s=summary(current);
  $('record-title').textContent=manager.name+(opponent?' vs '+opponent.name:'');
  $('stats').innerHTML=[['Bets',String(s.bets),'1u per bet'],['Profit',units(s.profit),`${s.wins} winning / ${s.losses} losing bets`],['ROI',s.bets?pct(s.roi):'—','Profit divided by stakes'],['Team W / D / L',`${s.results.W} / ${s.results.D} / ${s.results.L}`,s.bets<30?'Small sample — interpret cautiously':'Results of the manager’s team']].map(([label,value,note])=>`<div class="stat"><span>${label}</span><strong>${value}</strong><small class="muted">${note}</small></div>`).join('');chart(s);ledger();
 }
 const ranking=data.managers.map(m=>({...m,...summary(rows(m.id,f,opponent?.id||'all'))})).filter(m=>m.bets>=Number($('minimum').value)).sort((a,b)=>b[$('sort').value]-a[$('sort').value]||b.bets-a.bets);
 $('rankings').innerHTML=ranking.slice(0,50).map(m=>`<tr><td><button data-manager="${escape(m.id)}">${escape(m.name)} →</button></td><td>${m.bets}</td><td>${m.results.W} / ${m.results.D} / ${m.results.L}</td><td class="${color(m.profit)}">${units(m.profit)}</td><td class="${color(m.roi)}">${pct(m.roi)}</td><td>${m.drawdown.toFixed(2)}u</td></tr>`).join('');
 $('rank-count').textContent=`Showing ${Math.min(50,ranking.length)} of ${ranking.length} qualifying managers. Search any manager above to inspect their record.`;
}
async function init(){
 const response=await fetch('data.json');if(!response.ok)throw Error('Archive unavailable');data=await response.json();data.names=Object.fromEntries(data.managers.map(m=>[m.id,m.name]));
 $('coverage').textContent=`${data.fixtures.length.toLocaleString('en-GB')} priced matches · ${data.managers.length} manager identities · ${data.fromDate} to ${data.through}`;
 $('managers').innerHTML=data.managers.map(m=>option(m.name,m.name)).join('');
 $('club').innerHTML+= [...new Set(data.fixtures.flatMap(m=>[m.home,m.away]))].sort().map(t=>option(t,t)).join('');
 $('league').innerHTML+=Object.entries(leagues).map(([k,v])=>option(k,v)).join('');
 $('season').innerHTML+=[...new Set(data.fixtures.map(m=>m.season))].sort().reverse().map(s=>option(s,s)).join('');
 $('band').innerHTML+=bands.map((b,i)=>option(i,b.label)).join('');
 document.querySelectorAll('select,input').forEach(el=>el.addEventListener('change',()=>{shown=50;render();}));
 document.querySelectorAll('[data-side]').forEach(el=>el.addEventListener('click',()=>{side=el.dataset.side;document.querySelectorAll('[data-side]').forEach(b=>b.setAttribute('aria-pressed',String(b===el)));shown=50;render();}));
 $('example').onclick=()=>{$('manager').value='Pep Guardiola';$('opponent').value='Jürgen Klopp';shown=50;render();};
 $('swap').onclick=()=>{const a=$('manager').value;$('manager').value=$('opponent').value;$('opponent').value=a;render();};
 $('more').onclick=()=>{shown+=50;ledger();};
 $('reset').onclick=()=>{document.querySelectorAll('select').forEach(e=>e.selectedIndex=0);$('manager').value='';$('opponent').value='';document.querySelector('[data-side="team"]').click();};
 $('rankings').onclick=e=>{const b=e.target.closest('[data-manager]');if(b){$('manager').value=data.names[b.dataset.manager];shown=50;render();$('record').scrollIntoView({behavior:'smooth',block:'start'});}};
 render();
}
init().catch(()=>{$('status').textContent='The archive could not load. Reload this preview to try again.';});
