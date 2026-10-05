import { observations, seasonMatches, latestSeason, summary } from '../../../components/football-atlas/football-core.ts';

export function managerRows(fixtures, manager, f, opponent='all', club='all') {
  const latest=latestSeason(fixtures);
  const selected=fixtures.filter(m=>{
    const home=m.homeManager===manager, away=m.awayManager===manager;
    return (home||away) && (opponent==='all'||(home?m.awayManager:m.homeManager)===opponent)
      && (club==='all'||(home?m.away:m.home)===club) && seasonMatches(m.season,f.season,latest);
  });
  const teams=new Set(selected.map(m=>m.homeManager===manager?m.home:m.away));
  return [...teams].flatMap(team=>observations(selected.filter(m=>(m.homeManager===manager?m.home:m.away)===team),team,{...f,season:'all'}))
    .sort((a,b)=>a.date.localeCompare(b.date)||a.id.localeCompare(b.id));
}

/** Market expectations concern the team's result, independent of the chosen bet. */
export function matchMarket(row) {
  const total=row.odds.reduce((s,p)=>s+1/p,0);
  const teamIndex=row.venue==='home'?0:2;
  const win=(1/row.odds[teamIndex])/total, draw=(1/row.odds[1])/total;
  return {win,draw,opponent:(1/row.odds[2-teamIndex])/total,overround:total-1,points:3*win+draw};
}

/** Keep every non-empty record; communicate small samples without hiding them. */
export function rankingMinimum() {
  return 1;
}

const validDate=value=>typeof value==='string' && /^\d{4}-\d{2}-\d{2}$/.test(value) && Number.isFinite(Date.parse(value)) && new Date(value).toISOString().slice(0,10)===value;

export function activeReviewDue(id, registry, today) {
  const entry=registry?.entries?.[id];
  return isVerifiedActive(id,registry,today) && (!validDate(entry.reviewBy) || entry.reviewBy<today);
}

export function isVerifiedActive(id, registry, today) {
  const entry=registry?.entries?.[id];
  // A review deadline marks freshness, not the end of a coaching role.
  return !!entry && entry.status==='active' && validDate(entry.checkedAt) && entry.checkedAt<=today;
}

export function marketContext(rows) {
  let expectedWins=0,expectedPoints=0,actualWins=0,actualPoints=0;
  for(const r of rows){
    const p=matchMarket(r);
    expectedWins+=p.win;expectedPoints+=p.points;
    actualWins+=Number(r.result==='W');actualPoints+=r.result==='W'?3:r.result==='D'?1:0;
  }
  return {expectedWins,expectedPoints,actualWins,actualPoints,excessWins:actualWins-expectedWins,excessPoints:actualPoints-expectedPoints};
}

export function clubRecords(rows){
  const clubs=new Map();
  for(const row of rows){if(!clubs.has(row.team))clubs.set(row.team,[]);clubs.get(row.team).push(row);}
  return [...clubs].map(([club,matches])=>({club,first:matches[0].date,last:matches.at(-1).date,...summary(matches)})).sort((a,b)=>b.bets-a.bets);
}

/** Observed sequences in the selected fixtures, not inferred employment dates. */
export function observedSpells(rows){
  const spells=[];
  for(const row of rows){let spell=spells.at(-1);if(!spell||spell.club!==row.team){spell={club:row.team,first:row.date,last:row.date,bets:0};spells.push(spell);}spell.last=row.date;spell.bets++;}
  return spells;
}

export function strategyReturns(rows){
  return ['team','draw','opponent'].map(side=>({side,...summary(rows.map(r=>{
    const other=r.odds[r.venue==='home'?2:0], price=side==='team'?r.teamOdds:side==='draw'?r.odds[1]:other;
    const won=r.result===(side==='team'?'W':side==='draw'?'D':'L');
    return {...r,price,won,profit:won?price-1:-1};
  }))}));
}
