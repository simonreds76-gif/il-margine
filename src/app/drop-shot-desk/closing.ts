import "server-only";
import { getSupabaseAdmin } from "@/lib/supabase-server";

export type ClosingSummary = { measured:number; mean:number|null };
export type ClosingDetail = { odds:number; observed:string; start:string; minutes:number; change:number|null };
type Entry = {fixture:string; league:string; selection:string; at:string; odds:number};
type Saved = Entry & {group:"all"|"telegram"; close:ClosingDetail};

export function closingKey(entry:Entry) {
  return JSON.stringify([entry.fixture,entry.league,entry.selection,entry.at,entry.odds]);
}

export async function loadClosing(tour:string):Promise<Saved[]|null> {
  try {
    const {data,error}=await getSupabaseAdmin().storage.from("tennis-price-moves-private")
      .download("presentation/drop-paper-clv-v1/"+tour.toLowerCase()+".json");
    if(!data || error)return null;
    const packet=JSON.parse(await data.text());
    if(packet.version!==1 || packet.tour!==tour.toUpperCase() || !Array.isArray(packet.rows))return null;
    const seen=new Set<string>();
    for(const r of packet.rows as Saved[]) {
      const key=r.group+closingKey(r);
      const c=r.close;
      if(seen.has(key) || !["all","telegram"].includes(r.group) || !(r.odds>1) || !(c?.odds>1) ||
         !Number.isFinite(Date.parse(r.at)) || !Number.isFinite(Date.parse(c.start)) || !Number.isFinite(Date.parse(c.observed)) ||
         Date.parse(c.observed)>=Date.parse(c.start) || !Number.isFinite(c.minutes) || c.minutes<0 ||
         (c.change!==null && (Date.parse(c.observed)<=Date.parse(r.at) || !Number.isFinite(c.change) ||
          Math.abs(c.change-100*(r.odds/c.odds-1))>0.001))) return null;
      seen.add(key);
    }
    return packet.rows;
  } catch { return null; }
}

export function summariseClosing(details:(ClosingDetail|null|undefined)[]):ClosingSummary {
  const values=details.flatMap(c=>c?.change==null?[]:[c.change]);
  return {measured:values.length,mean:values.length?values.reduce((a,b)=>a+b,0)/values.length:null};
}

export function publicClose(c:ClosingDetail|undefined):ClosingDetail|null {
  if(!c)return null;
  return {odds:c.odds,observed:c.observed,start:c.start,minutes:c.minutes,change:c.change};
}
