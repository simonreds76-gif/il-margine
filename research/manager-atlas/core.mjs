import { observations, seasonMatches, latestSeason } from '../../src/components/football-atlas/football-core.ts';

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
