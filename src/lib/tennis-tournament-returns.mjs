// Display-only projection of the audited historical snapshot. No forecast inputs.
import { tournamentOf, isQualifying } from './tennis-matchday-browse.mjs';

export function reconciles(c, favourite, underdog) {
  if (!c || Object.values(c).some(n => !Number.isSafeInteger(n) || n < 0)) return false;
  if (c.completed !== c.paired + c.unpriced || c.paired !== c.pickems + c.bettable) return false;
  for (const side of [favourite, underdog]) {
    if (!side || !Number.isSafeInteger(side.wins) || side.wins < 0 || !Number.isSafeInteger(side.losses) || side.losses < 0
      || side.stake !== c.bettable || side.wins + side.losses !== c.bettable || !Number.isFinite(side.profit)) return false;
    if (side.stake ? !Number.isFinite(side.roi) || Math.abs(side.roi - 100 * side.profit / side.stake) > 0.0001 : side.profit !== 0 || side.roi !== null) return false;
  }
  return favourite.wins + underdog.wins === c.bettable;
}
const counts = x => ({ completed:x.completed, paired:x.paired, unpriced:x.noPrice,
  pickems:x.pickems, bettable:x.bettable, notCompleted:x.excluded?.incompleteOrRetired || 0 });
const basis = {
  'Pinnacle last recorded pre-match':'Last recorded pre-match',
  'Pinnacle opening':'Opening',
  'Pinnacle archived snapshot (closing time unverified)':'Archived snapshot (final tick unverified)',
  'Pinnacle captured pre-match (not assumed closing)':'Captured pre-match (final tick unverified)',
  'Pinnacle historical match odds checked on TennisExplorer; exact closing timestamp unverified.':'Historical match odds (final tick unverified)',
};
const mix = x => Object.entries(x.priceMix).map(([label,count]) => ({label:basis[label] || label,count}));
const status = {included:'eligible', current:'current', opening:'opening-basis', 'previous-venue':'other-regime', excluded:'low-coverage'};
const sidePair = x => ({favourite:x.favourite,underdog:x.underdog});
function windowView(x) {
  return {requested:x.requested,editionIds:x.editions.filter(e=>e.status==='included').map(e=>e.id),years:x.years,
    counts:counts(x.pool),priceMix:mix(x.pool),...sidePair(x.pool),
    bands:x.bands.map((b,i)=>({label:['Under 1.30','1.30 to under 1.60','1.60 and longer'][i],min:b.lower,max:i===2?null:b.upper,fixtures:b.bettable,...sidePair(b)}))};
}
export function editionCompletionLabel(completion) {
  return completion?.state==='completed' ? 'Completed' : 'Completion unverified';
}
export function summaryForFamily(data, family) {
  if (family.editions.some(e=>e.excluded?.unresolvedIdentity) || Object.values(family.windows).some(w=>Object.keys(w.pool.priceMix).some(k=>/opening/i.test(k))))
    return {availability:'unavailable',name:family.name,reason:'Price basis or unresolved identities prevent verified coverage.'};
  const three=windowView(family.windows['3']),candidate=windowView(family.windows['5']);
  const five=JSON.stringify(three.editionIds)===JSON.stringify(candidate.editionIds)?null:candidate;
  const editions=family.editions.map(e=>({editionId:e.id,year:e.year,fromDate:e.fromDate,throughDate:e.throughDate,
    completion:{state:e.completion?.state || 'unverified',completedAt:e.completion?.completedAt || null},status:status[e.status] || 'no-data',excludedReason:e.excludedReason,counts:counts(e),priceMix:mix(e),...sidePair(e)})).reverse();
  if ([three,...(five?[five]:[]),...editions].some(x=>!reconciles(x.counts,x.favourite,x.underdog) || x.priceMix.reduce((n,m)=>n+m.count,0)!==x.counts.paired))
    return {availability:'unavailable',name:family.name,reason:'Historical counts or prices failed reconciliation; figures are withheld.'};
  return {availability:'available',family:family.id,name:family.name,tour:family.tour,surface:family.surface,city:family.city,
    notes:[...family.notes,...(family.familyId==='atp-finals'?['Round-robin matches, including those with alternates and matches after qualification was decided, remain included when completed.']:[])],
    snapshotYear:Number(data.asOf.slice(0,4)),coverageUpdatedAt:data.coverageUpdatedAt,windows:{three,five},editions};
}
export function familyForFixture(data,fixture) {
  if (fixture.tour!=='ATP' || isQualifying(fixture) || fixture.start.slice(0,4)!==data.asOf.slice(0,4)) return null;
  const e=tournamentOf(fixture);
  if(e.surface==='unknown')return null;
  const matches=data.families.filter(f=>f.tour===fixture.tour && f.surface===e.surface && [...f.aliases,...f.feedLabels].includes(e.label));
  return matches.length===1?matches[0]:null;
}
export function projectTournamentReturns(data,fixtures) {
  const byTournament={};
  for (const fixture of fixtures) {
    const family=familyForFixture(data,fixture);
    if(family)byTournament[tournamentOf(fixture).key]=summaryForFamily(data,family);
  }
  return {byTournament};
}
