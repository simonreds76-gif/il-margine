const dayMs=86400000;
const safe=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const stamp=v=>Date.parse(v+'T00:00:00Z');
const label=v=>new Intl.DateTimeFormat('en-GB',{day:'numeric',month:'short',timeZone:'UTC'}).format(new Date(stamp(v)));
const glyph=(kind)=>`<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" aria-hidden="true">${kind==='calendar'?'<rect x="4" y="5" width="16" height="16" rx="3"/><path d="M8 3v4m8-4v4M4 11h16m-12 4h2m4 0h2m-8 3h2"/>':kind==='mountain'?'<path d="m2 20 7-13 4 6 3-10 6 17H2Zm5-9 2 2 2-2m3-2 2 2 2-2"/>':'<circle cx="12" cy="12" r="9"/><path d="M12 6v6l4 2"/>'}</svg>`;

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
  const workload=(s,key)=>!s?'Unavailable':s[key].matches?`<strong>${s[key].matches}<small> matches</small></strong><span>${s[key].sets} completed sets · ${s[key].games} games</span>${s[key].retirements?`<small>Includes ${s[key].retirements} retirement</small>`:''}`:'<strong class="context-empty">No recorded matches</strong>';
  const row=(title,icon,render)=>`<div class="context-row"><div class="context-label">${glyph(icon)}<span>${title}</span></div>${sums.map((s,i)=>`<div class="context-value side-${i}">${render(s)}</div>`).join('')}</div>`;
  return `<section class="section match-context" id="comparison-context"><div class="context-heading"><div><p class="eyebrow">THE SCHEDULE BEHIND THE MATCHUP</p><h2>Match context</h2><p>Recent workload before ${label(asOf)}. Compare the schedule behind each player’s record.</p></div><span class="context-date">${glyph('calendar')}Before ${label(asOf)}</span></div>
  <div class="context-players"><span>Recorded workload</span>${players.map((p,i)=>`<strong class="side-${i}">${safe(p.name)}</strong>`).join('')}</div>
  ${row('Last 7 days','calendar',s=>workload(s,'week'))}${row('Last 14 days','calendar',s=>workload(s,'fortnight'))}
  ${row('Last recorded match','clock',s=>s?.last?`<strong>${label(s.last.date)}</strong><span>${safe(s.last.event)}</span><small>${s.gap} calendar ${s.gap===1?'day':'days'} earlier${s.gap>=28?' · Gap in recorded activity':''}</small>`:s?'<span>No earlier match in the available record</span>':'<span>Unavailable for this date</span>')}
  ${sums.some(s=>s?.last?.venue)?row('Previous venue elevation','mountain',s=>s?.last?.venue?`<strong>~${Math.round(s.last.venue.elevation)} m</strong><a href="${safe(s.last.venue.source)}" target="_blank" rel="noopener noreferrer">Mapped venue · terrain estimate ↗</a>`:'<span>Not verified</span>'):''}
  <p class="context-coverage">Results recorded through ${meta.through?label(meta.through):'an unavailable date'}. All opponents and surfaces, independent of the filters above. No recorded matches does not guarantee no recent play.</p>
  <details class="context-evidence"><summary>Inspect the schedule and coverage</summary><p>${safe(meta.scope)} Walkovers are excluded. Completed sets and all recorded games from retirements are included. Calendar gaps are not hours of rest or evidence of injury. Court time and weather are not shown because verified duration and fixture weather are not available in this snapshot.</p><div class="context-evidence-columns">${sums.map((s,i)=>`<div><h3>${safe(players[i].name)} · last 14 days</h3>${s?.fortnight.rows.length?`<ul>${[...s.fortnight.rows].reverse().map(r=>`<li><time>${label(r.date)}</time><span>${safe(r.opponent||r.event)}<small>${safe(r.event)}</small><small>${safe(r.score)} · winner first · ${r.sets} completed sets</small></span></li>`).join('')}</ul>`:'<p>No recorded matches in this window.</p>'}</div>`).join('')}</div></details></section>`;
}
