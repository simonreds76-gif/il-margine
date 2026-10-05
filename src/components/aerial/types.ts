export type History = { matches:number; minutes:number; duel_matches:number; aerial_won:number; aerial_attempts:number; aerial_win_pct:number|null; head_matches:number; head_minutes:number; headed_shots:number; headers_per90:number|null; small_sample:boolean; appearances:{fixture_id:string;date:string;match:string;minutes:number;won:number|null;attempts:number|null;headed_shots:number|null}[] };
export type WindowKey = 'recent'|'current'|'previous';
export type Player = { id:string;name:string;role:string;height_cm:number|null;height_source:string|null;height_observed_at:string|null;photo_url:string;histories:Record<WindowKey,History> };
export type Delivery = {corners:{average:number|null;matches:number};crosses:{average:number|null;matches:number}};
export type Team = {id:string;name:string;formation:string;players:Player[];height:{known:number;total:number;mean_cm:number|null;tallest_three_mean_cm:number|null;at_least_185:number|null};histories:Record<WindowKey,Delivery>};
export type Fixture = {id:string;competition:string;kickoff:string;source_url:string;state:'pending'|'stale'|'expected'|'confirmed';observed_at:string|null;valid_until:string;teams:Team[]};
export type Board = {schema_version:1;version:string;generated_at:string;calendar_observed_at:string;history_through:string;history_matches:number;seasons:string[];fixtures:Fixture[]};
export function isBoard(value:unknown): value is Board {
  if (!value || typeof value !== 'object') return false;
  const b=value as Board;
  const numeric=(v:unknown)=>typeof v==='number'&&Number.isFinite(v)&&v>=0;
  const optional=(v:unknown)=>v===null||numeric(v);
  const windows:WindowKey[]=['recent','current','previous'];
  return b.schema_version===1 && Number.isFinite(Date.parse(b.generated_at)) && Number.isFinite(Date.parse(b.calendar_observed_at)) &&
    Number.isFinite(Date.parse(b.history_through)) && Array.isArray(b.seasons) && b.seasons.length===2 && b.seasons.every(s=>typeof s==='string') &&
    Array.isArray(b.fixtures) && b.fixtures.every(f => f &&
    typeof f.id==='string' && typeof f.competition==='string' && Number.isFinite(Date.parse(f.kickoff)) && Number.isFinite(Date.parse(f.valid_until)) && ['pending','stale','expected','confirmed'].includes(f.state) &&
    Array.isArray(f.teams) && f.teams.length===2 && f.teams.every(t => t && typeof t.id==='string' && typeof t.name==='string' && Array.isArray(t.players) &&
      !!t.height && numeric(t.height.known) && optional(t.height.mean_cm) && optional(t.height.tallest_three_mean_cm) && optional(t.height.at_least_185) &&
      !!t.histories && windows.every(w=>t.histories[w]&&(['corners','crosses'] as const).every(k=>t.histories[w][k]&&numeric(t.histories[w][k].matches)&&optional(t.histories[w][k].average))) &&
      (!['confirmed','expected'].includes(f.state)||(t.players.length===11&&t.players.filter(p=>p.role==='GK').length===1)) &&
      t.players.every(p=>p&&typeof p.id==='string'&&typeof p.name==='string'&&typeof p.role==='string'&&typeof p.photo_url==='string'&&optional(p.height_cm)&&
        (!p.height_source||/^https?:\/\//.test(p.height_source))&&p.histories&&windows.every(w=>{
          const h=p.histories[w];return h&&[h.matches,h.minutes,h.duel_matches,h.aerial_won,h.aerial_attempts,h.head_matches,h.headed_shots].every(numeric)&&
            optional(h.aerial_win_pct)&&optional(h.headers_per90)&&Array.isArray(h.appearances)&&h.appearances.every(a=>a&&typeof a.fixture_id==='string'&&typeof a.date==='string'&&typeof a.match==='string'&&numeric(a.minutes)&&optional(a.won)&&optional(a.attempts)&&optional(a.headed_shots));
        }))));
}

