import "server-only";
import { getSupabaseAdmin } from "@/lib/supabase-server";
import type { MoveSummaryProps } from "./MoveSummary";

type Entry = MoveSummaryProps & { contract?:string; move_id: string; event_id: string; fixture: string };
type Event = { contracts?:Record<string,unknown>; fixture:string; start:string; home:string; away:string };
export type MonitorMove = MoveSummaryProps & { id:string; until:number | null };

export async function getRoundup() {
  const storage = getSupabaseAdmin().storage.from("tennis-price-moves-private");
  async function load<T>(key:string):Promise<T> {
    const {data,error}=await storage.download(key);
    if(error || !data)throw new Error("Private observation unavailable");
    return JSON.parse(await data.text()) as T;
  }
  const now=Date.now();
  for(const t of [now, now-86_400_000]) {
    const day=new Date(t).toISOString().slice(0,10).replaceAll("-","/");
    const prefix="drop-deliveries-v2/"+day;
    const {data,error}=await storage.list(prefix,{limit:96,sortBy:{column:"name",order:"desc"}});
    if(error)throw new Error("Private delivery list unavailable");
    for(const {name} of data??[]) {
      if(!/^\d{6}-\d{6}\.json$/.test(name))continue;
      const receipt=await load<{state:string;observed:string;delivered_at:string;move_ids:string[]}>(prefix+"/"+name);
      if(receipt.state!=="sent")continue;
      const [scan,latest]=await Promise.all([
        load<{observed:string;moves:Entry[]}>("drop-scans-v2/"+day+"/"+name),
        load<{observed:string;events:Record<string,Event>}>("latest.json")
      ]);
      const ids=new Set(receipt.move_ids);
      const matches=scan.moves.filter(m=>ids.has(m.move_id));
      if(receipt.observed!==scan.observed || !ids.size || ids.size!==receipt.move_ids.length ||
          new Set(matches.map(m=>m.move_id)).size!==ids.size || matches.length!==ids.size)
        throw new Error("Roundup and delivery disagree");
      const seen=Date.parse(latest.observed);
      const moves:MonitorMove[]=matches.map(m=>{
        const e=latest.events[m.event_id];
        const same=(!m.contract || m.contract==='winner' || !!e?.contracts?.[m.contract]) && e?.fixture===m.fixture && e.start===m.start &&
          ((e.home===m.player && e.away===m.opponent)||(e.away===m.player && e.home===m.opponent));
        const cutoff=Math.min(Date.parse(m.start),seen+20*60_000);
        return {id:m.move_id,player:m.player,opponent:m.opponent,selection:m.contract && m.contract!=='winner'?m.selection:undefined,league:m.league,start:m.start,
          before:m.before,after:m.after,old:m.old,new:m.new,until:same&&seen<=now&&cutoff>now?cutoff:null};
      });
      return {sent:receipt.delivered_at,moves,now};
    }
  }
  return null;
}
