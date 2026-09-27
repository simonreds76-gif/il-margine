import { observations, seasonMatches, latestSeason, summary } from '../../src/components/football-atlas/football-core.ts';

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
export function marketContext(rows) {
  let expectedWins=0,expectedPoints=0,actualWins=0,actualPoints=0;
  for(const r of rows){
    const total=r.odds.reduce((s,p)=>s+1/p,0), win=(1/r.teamOdds)/total, draw=(1/r.odds[1])/total;
    expectedWins+=win;expectedPoints+=3*win+draw;
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
