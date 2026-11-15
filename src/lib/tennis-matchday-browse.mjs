import editions from '../data/tennis-matchday-editions.json' with { type: 'json' };

// Display-only metadata. Never infer a surface from the previous edition.
export function tournamentOf(f) {
  const split = /^(.*?)\s+[-–—]\s+(R(?:1|2|3|4|8|16|32|64|128)|Q[1-3F]|SF|F|Final|Semi[- ]?finals?|Quarter[- ]?finals?|Groups|Round Robin|Qualifiers?|Qualifying(?:\s+[RQ][1-3])?|Qualifications?)$/i.exec(f.event);
  const label = split?.[1]?.trim() || f.event;
  const round = split?.[2] || (f.qualifying ? 'Qualifying' : '');
  const date = f.start.slice(0,10);
  const found = editions.filter(e => e.tour === f.tour && e.label === label && date >= e.fromDate && date <= e.throughDate);
  const edition = found.length === 1 ? found[0] : null;
  return { key: JSON.stringify([f.tour, label, edition?.edition || date.slice(0,4)]), label, displayName: edition?.displayName || label, tour: f.tour, round,
    surface: edition?.surface || 'unknown' };
}
export const surfaceNames = { 'outdoor-hard':'Outdoor hard', 'indoor-hard':'Indoor hard', clay:'Clay', grass:'Grass', unknown:'Surface unverified' };
export const isQualifying = f => f.qualifying || /\b(?:qualifiers?|qualifying|qualifications?)\b/i.test(f.event);
export function readBrowseState(search) {
  const p = new URLSearchParams(search);
  return { view:p.get('view')==='results'?'results':'upcoming', resultDay:p.get('result-day') || 'latest', filter:['today','tomorrow','upcoming'].includes(p.get('day')) ? p.get('day') : 'auto',
    tour:['all','ATP','Challenger'].includes(p.get('tour')) ? p.get('tour') : 'ATP',
    tournament:p.get('tournament') || 'all', search:p.get('q') || '', qualifying:p.get('qualifying') !== 'off',
    order:p.get('order') === 'time' ? 'time' : 'tournament' };
}
export function browseQuery(state, search='') {
  const p = new URLSearchParams(search);
  for (const [key,value,defaultValue] of [['view',state.view || 'upcoming','upcoming'],['result-day',state.resultDay || 'latest','latest'],['day',state.filter,'auto'],['tour',state.tour,'ATP'],['tournament',state.tournament,'all'],['q',state.search,''],['qualifying',state.qualifying?'on':'off','on'],['order',state.order,'tournament']]) {
    if(value===defaultValue) p.delete(key); else p.set(key,value);
  }
  return p.toString();
}

export function displayDay(filter, fixtures, now) {
  if (filter !== 'auto') return filter;
  const day = value => new Intl.DateTimeFormat('en-CA',{timeZone:'Europe/London',year:'numeric',month:'2-digit',day:'2-digit'}).format(value);
  const today=day(now), tomorrow=new Date(Date.parse(`${today}T12:00:00Z`)+86400000).toISOString().slice(0,10);
  if(fixtures.some(f=>Date.parse(f.start)>now.getTime() && day(new Date(f.start))===today))return 'today';
  if(fixtures.some(f=>Date.parse(f.start)>now.getTime() && day(new Date(f.start))===tomorrow))return 'tomorrow';
  return 'upcoming';
}
