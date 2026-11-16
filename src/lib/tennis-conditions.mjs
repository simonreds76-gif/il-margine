import registry from '../data/tennis-conditions-evidence.json' with {type:'json'};
import {contextIcon} from './tennis-context-icons.mjs';

const esc=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const day=v=>typeof v==='string'&&/^\d{4}-\d{2}-\d{2}/.test(v)?v.slice(0,10):null;
const stamp=v=>day(v)?new Date(day(v)+'T12:00:00Z').toLocaleDateString('en-GB',{day:'numeric',month:'short',year:'numeric',timeZone:'UTC'}):'Not supplied';
const label=v=>String(v??'').trim().replace(/\s+[–—]\s+/g,' - ').replace(/\s+/g,' ');
const validSource=s=>s&&typeof s.url==='string'&&/^https:\/\//.test(s.url);
const link=s=>validSource(s)?`<a href="${esc(s.url)}" target="_blank" rel="noopener noreferrer">${esc(s.label)} <span aria-hidden="true">↗</span></a>`:'';
const validReading=m=>Number.isFinite(m?.value)&&m.value>0&&m.unit==='CPI'&&validSource(m.source);
const validEstimate=e=>Number.isFinite(e?.value)&&e.value>0&&validSource(e.source);

// Display registry only. No model imports, name fuzzy matching or previous-year
// measurement fallback. Unsupported tours/editions remain visibly unverified.
export function conditionsFor({event,tour,date,surface},data=registry){
  if(!day(date)||!event)return null;
  const year=Number(date.slice(0,4));
  const hits=data.families.filter(f=>f.tour===tour&&(!surface||surface==='unknown'||surface===f.surface)&&f.aliases.map(label).includes(label(event)));
  const family=hits.length===1?hits[0]:null;
  const edition=family?.editions.find(e=>e.year===year)??null;
  const history=family?.editions.filter(e=>e.year<=year).sort((a,b)=>b.year-a.year)??[];
  const previousEstimate=history.find(e=>e.year===year-1&&validEstimate(e.estimate))?.estimate??null;
  return {name:family?.name||event,tour,year,family:family?.key??null,edition,history,
    estimate:validEstimate(edition?.estimate)?edition.estimate:previousEstimate,checkedAt:data.checkedAt};
}

export function latestSharedConditions(schedules,asOf){
  if(schedules.length!==2||!day(asOf))return null;
  const entries=schedules.map(rows=>{
    const map=new Map();
    for(const row of rows){
      if(!day(row.date)||row.date>=asOf||!label(row.event))continue;
      const titled=/(Masters|ATP Finals|Tour Finals)/i.test(row.event);
      const c=titled?conditionsFor({event:row.event,tour:'ATP',date:row.date,surface:row.court&&String(row.court)!=='3'?'other':undefined}):null;
      const key=(c?.family||label(row.event))+':'+row.date.slice(0,4);
      if(!map.has(key)||row.date>map.get(key).last)map.set(key,{conditions:c,last:row.date});
    }
    return map;
  });
  // Find the latest shared event INCLUDING unreviewed ones, then decide whether
  // it has evidence. Never skip a later event to display an older Paris card.
  const latest=[...entries[0]].filter(([key])=>entries[1].has(key))
    .map(([key,value])=>({...value,last:[value.last,entries[1].get(key).last].sort()[1]}))
    .sort((a,b)=>b.last.localeCompare(a.last))[0];
  return latest?.conditions?.edition?latest.conditions:null;
}

export function renderConditions(c,{compact=false,embedded=false,contextLabel=''}={}){
  if(!c)return '';
  if(!c.family)return '<p class="tc-empty">Court conditions not yet reviewed for this edition.</p>';
  const e=c.edition,m=validReading(e?.measurement)?e.measurement:null,s=c.estimate;
  const estimate=validEstimate(s)?s:null;
  const changes=e?.changes?.filter(x=>validSource(x.source))??[];
  const sub=m?`Reported CPI ${String(m.value)}`:estimate?`Estimated ace index ${estimate.value.toFixed(2)} · ${estimate.year}`:'Pace not verified';
  const heading=`${esc(c.name)} · ${c.year}`;
  const noEvidence=!c.family;
  const emptyBody=`<p>No verified pace, venue or ball evidence is linked to this edition yet.</p><p class="tc-muted">We do not reuse another tournament's reading or infer pace from the surface. The match schedule, results and H2H remain available.</p>`;
  const body=noEvidence?emptyBody:`${contextLabel?`<p class="tc-context">${esc(contextLabel)}. Separate from the H2H record and surface filters.</p>`:''}
    <div class="tc-metrics">
      <div class="tc-metric" data-kind="measured"><span class="tc-kind">Measured pace · reported CPI</span><strong>${m?String(m.value):'Unavailable'}${m?'<small>CPI</small>':''}</strong><span class="tc-period">${c.year} edition</span>
        <p>${m?'Reading shown in an archived broadcast graphic.':'No reviewed measurement for this edition. We do not substitute an older reading.'}</p>${m?`<p class="tc-muted">${esc(m.court)} · measurement date not supplied.</p>`:''}</div>
      <div class="tc-metric" data-kind="estimated"><span class="tc-kind">Estimated pace</span><strong>${estimate?estimate.value.toFixed(2):'Unavailable'}${estimate?'<small>ace index</small>':''}</strong><span class="tc-period">${estimate?`${estimate.year} edition${estimate.year<c.year?' · historical reference':''}`:'No verified estimate'}</span>
        <p>${estimate?'Ace rate adjusted for the players who served and returned. 1.00 is the tour-average reference.':'An unmeasured court is not automatically average or slow.'}</p>${estimate?'<p class="tc-muted">Sample size not supplied. Not a physical measurement.</p>':''}${estimate&&estimate.year<c.year&&changes.length?'<p class="tc-before-change">Historical reference from before the verified '+esc(changes.map(x=>x.kind).join(' / '))+' change.</p>':''}</div>
    </div>
    <p class="tc-scale">Different scales, shown separately. Neither is a match prediction.</p>
    <dl class="tc-facts"><div><dt>Venue</dt><dd>${validSource(e?.venue?.source)?esc(e.venue.name):'Not verified for this edition'}</dd></div><div><dt>Ball</dt><dd>${validSource(e?.ball?.source)?esc(e.ball.name):'Not verified for this edition'}</dd></div></dl>
    ${changes.length?`<ul class="tc-changes">${changes.map(x=>`<li><span>Verified change</span>${esc(x.label)}</li>`).join('')}</ul>`:'<p class="tc-muted">No verified change recorded here does not mean conditions stayed the same.</p>'}
    <details class="tc-evidence"><summary>Edition history &amp; evidence</summary>
      ${c.history.length?`<div class="tc-history">${c.history.map(row=>`<div><b>${row.year}</b><div><strong>${validSource(row.venue?.source)?esc(row.venue.name):'Venue unverified'}</strong><span>${validReading(row.measurement)?'Reported CPI '+String(row.measurement.value):'No reviewed CPI'}${validEstimate(row.estimate)?' · estimated ace index '+row.estimate.value.toFixed(2):''}</span><span>Ball: ${validSource(row.ball?.source)?esc(row.ball.name):'unverified'}</span>${(row.changes??[]).filter(x=>validSource(x.source)).map(x=>`<em>${esc(x.label)}</em>`).join('')}</div></div>`).join('')}</div>`:'<p>No verified edition history is linked. Missing evidence is kept missing.</p>'}
      <p>Only editions with reviewed evidence are listed.</p><p>Readings cover the stated edition and court only. Qualifying and outer-court conditions may differ. Earlier editions are not pooled into a current rating.</p>
      ${m?`<p>Chart first observed ${stamp(m.firstSeenAt)}. Original measurement and publication times are not supplied; this reading is descriptive evidence, not a verified pre-match input.</p>`:''}
      ${estimate?`<p>Estimate window: ${estimate.year} edition. Match and service-point counts unavailable. The original retained snapshot was dated ${stamp(estimate.originalSnapshotAt)}; these figures were checked ${stamp(estimate.source.checkedAt)}.</p>`:''}
      <div class="tc-sources">${[m?.source,estimate?.source,e?.venue?.source,e?.ball?.source,...changes.map(x=>x.source),...c.history.flatMap(row=>[row.measurement?.source,row.estimate?.source,row.venue?.source,row.ball?.source,...(row.changes??[]).map(x=>x.source)])].filter(validSource).filter((x,i,a)=>a.findIndex(y=>y.url===x.url)===i).map(link).join('')}</div>
      <p class="tc-muted">Evidence reviewed ${stamp(c.checkedAt)}. Presentation only; existing pricing and historical records are unchanged.</p>
    </details>`;
  const title=`<span class="tc-icon" aria-hidden="true">${contextIcon('conditions')}</span><span><${compact?'strong':'h3'}>${compact?'Court conditions':heading}</${compact?'strong':'h3'}><small>${compact?sub:'Measured and estimated, with edition context'}</small></span>`;
  return compact?`<details class="tennis-conditions tc-compact" data-conditions="${esc(c.family||'unverified')}"><summary class="tc-heading">${title}<span class="tc-chevron" aria-hidden="true">⌄</span></summary><div class="tc-body"><h4>${heading}</h4>${body}</div></details>`:`<${embedded?'article':'section'} class="tennis-conditions" data-conditions="${esc(c.family||'unverified')}" aria-label="${esc(c.name)} ${c.year} court conditions"><div class="tc-heading">${title}</div><div class="tc-body">${body}</div></${embedded?'article':'section'}>`;
}
