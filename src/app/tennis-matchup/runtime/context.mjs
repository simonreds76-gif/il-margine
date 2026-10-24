const dayMs=86400000;
const safe=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const stamp=v=>Date.parse(v+'T00:00:00Z');
const label=v=>new Intl.DateTimeFormat('en-GB',{day:'numeric',month:'short',timeZone:'UTC'}).format(new Date(stamp(v)));
const glyph=(kind)=>`<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${kind==='court'?'<rect x="4" y="3" width="16" height="18" rx="2"/><path d="M7 3v18M17 3v18M4 12h16M7 7h10M7 17h10M12 7v10"/><circle cx="18" cy="6" r="3" fill="#13282c"/><path d="m16.5 6 1 1 2-2"/>':kind==='timeline'?'<path d="M3 6h18M3 12h18M3 18h18"/><circle cx="7" cy="6" r="2" fill="#13282c"/><circle cx="16" cy="12" r="2" fill="#13282c"/><circle cx="11" cy="18" r="2" fill="#13282c"/>':'<circle cx="12" cy="12" r="8"/><path d="M12 7v5l3 2M9 2h6"/>'}</svg>`;

export function scheduleDays(summary,asOf){
  if(!summary)return [];
  return Array.from({length:14},(_,i)=>{
    const date=new Date(stamp(asOf)-(14-i)*dayMs).toISOString().slice(0,10);
    return {date,count:summary.fortnight.rows.filter(r=>r.date===date).length,recent:i>=7};
  });
}

export function scheduleSummary(schedule,asOf,meta,mapped=true){
  if(!meta?.from||!mapped||asOf<meta.from||asOf>meta.asOf)return null;
  const rows=(schedule??[]).filter(r=>r.date<asOf&&r.date>=meta.from);
  const window=n=>{const from=stamp(asOf)-n*dayMs;const recent=rows.filter(r=>stamp(r.date)>=from);return {matches:recent.length,sets:recent.reduce((n,r)=>n+r.sets,0),games:recent.reduce((n,r)=>n+r.games,0),retirements:recent.filter(r=>r.retired).length,rows:recent};};
  const last=[...rows].sort((a,b)=>b.date.localeCompare(a.date))[0];
  return {week:window(7),fortnight:window(14),last,gap:last?Math.round((stamp(asOf)-stamp(last.date))/dayMs):null};
}

export function contextPanel(players,selected,schedules,meta,asOf){
  if(!meta?.asOf)return '';
  const sums=selected.map(i=>scheduleSummary(schedules?.[i],asOf,meta,meta.mapped?.[i]!==false));
  const workload=s=>!s?'<span>Unavailable</span>':`<div class="context-timeline" aria-label="Recorded match days over the last 14 days">${scheduleDays(s,asOf).map(d=>`<span class="context-day${d.recent?' recent':''}${d.count?' played':''}" title="${label(d.date)}: ${d.count?d.count+' recorded '+(d.count===1?'match':'matches'):'no recorded match'}" aria-label="${label(d.date)}: ${d.count} recorded matches">${d.count?`<i aria-hidden="true">${d.count>1?d.count:''}</i>`:''}</span>`).join('')}</div><div class="context-timeline-axis"><span>${label(new Date(stamp(asOf)-14*dayMs).toISOString().slice(0,10))}</span><span>${label(new Date(stamp(asOf)-dayMs).toISOString().slice(0,10))}</span></div><div class="context-counts">${[['week','7 days'],['fortnight','14 days']].map(([key,title])=>`<div><b>${title}</b><span>${s[key].matches?`<strong>${s[key].matches}</strong> matches<span class="context-count-detail">${s[key].sets} sets · ${s[key].games} games</span>`:'No recorded matches'}</span></div>`).join('')}</div>${s.fortnight.retirements?`<small>Includes ${s.fortnight.retirements} retirement${s.fortnight.retirements===1?'':'s'}</small>`:''}`;
  const row=(title,icon,render)=>`<div class="context-row"><div class="context-label"><span class="context-icon">${glyph(icon)}</span><span>${title}${icon==='timeline'?'<small>Dots mark recorded match days.<br>Lighter cells show the last 7 days.</small>':''}</span></div>${sums.map((s,i)=>`<div class="context-value side-${i}">${render(s)}</div>`).join('')}</div>`;
  return `<section class="section match-context" id="comparison-context"><div class="context-heading"><span class="context-emblem">${glyph('court')}</span><div><p class="eyebrow">THE SCHEDULE BEHIND THE MATCHUP</p><h2>Match context</h2><p>Recent workload before ${label(asOf)}. See when each player competed.</p></div></div>
  <div class="context-players"><span>Recorded workload</span>${players.map((p,i)=>`<strong class="side-${i}">${safe(p.name)}</strong>`).join('')}</div>
  ${row('Recent schedule','timeline',workload)}
  ${row('Last recorded match','clock',s=>s?.last?`<strong>${label(s.last.date)}</strong><span>${safe(s.last.event)}</span><small>${s.gap} calendar ${s.gap===1?'day':'days'} earlier${s.gap>=28?' · Gap in recorded activity':''}</small>`:s?'<span>No earlier match in the available record</span>':'<span>Unavailable for this date</span>')}
  <p class="context-coverage">Results recorded through ${meta.through?label(meta.through):'an unavailable date'}. All opponents and surfaces, independent of the filters above. ITF coverage is partial. No recorded matches does not guarantee no recent play.</p>
  <details class="context-evidence"><summary>Inspect the schedule and coverage</summary><p>${safe(meta.scope)} Walkovers are excluded. Completed sets and all recorded games from retirements are included. A set unfinished at retirement is not counted as completed. Calendar gaps are not hours of rest or evidence of injury. Court time and weather are not shown because verified duration and fixture weather are not available in this snapshot.</p><div class="context-evidence-columns">${sums.map((s,i)=>`<div><h3>${safe(players[i].name)} · last 14 days</h3>${s?.fortnight.rows.length?`<ul>${[...s.fortnight.rows].reverse().map(r=>`<li><time>${label(r.date)}</time><span>${safe(r.opponent||r.event)}<small>${safe(r.event)}</small><small>${r.won===true?'W · ':r.won===false?'L · ':''}${safe(r.score)} · winner first · ${r.sets} completed sets</small></span></li>`).join('')}</ul>`:'<p>No recorded matches in this window.</p>'}</div>`).join('')}</div></details></section>`;
}
