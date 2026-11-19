import "server-only";
import { getSupabaseAdmin } from "@/lib/supabase-server";
import type { Move, Fixture, Quote } from "./types";

const storage = () => getSupabaseAdmin().storage.from("tennis-price-moves-private");
async function read<T>(path: string): Promise<T> {
  const { data, error } = await storage().download(path);
  if (!data || error) throw new Error("Private board unavailable");
  return JSON.parse(await data.text()) as T;
}
async function files(prefix: string) {
  const { data, error } = await storage().list(prefix, { limit: 200, sortBy: { column: "name", order: "asc" } });
  if (error || !data || data.length === 200) throw new Error("Scan listing incomplete");
  return data.map(row => row.name).filter(name => /^\d{6}-\d{6}\.json$/.test(name));
}
type Saved = {
  tour: string; league: string; player: string; opponent: string; start: string; before: string; after: string;
  old: number; new: number; old_opponent: number; new_opponent: number; move_id: string;
};
type Event = { tour:string; league:string; start:string; home:string; away:string; home_price:number; away_price:number };
type Scan = { observed: string; moves: Saved[]; compared_pairs: number };
type Receipt = { state: string; move_ids: string[] };
type Outcome = { result:"Won"|"Lost"|"Void"; score:string };
type ArchiveRow = Omit<Saved,"tour"> & { level:string; quotes:Quote[]; qualifying:boolean; result:{state:string; score?:string} };
type Archive = { moves: ArchiveRow[]; summary:{ wins:number; losses:number; voids:number; settled_stake:number; net_units:number; roi_pct:number } };

export async function readArchive() {
  const packet = await read<Archive>("presentation/archive-v1.json");
  const moves: Move[] = packet.moves.map(m => ({ tour:m.level,league:m.league,player:m.player,opponent:m.opponent,start:m.start,
    before:m.before,after:m.after,old:m.old,new:m.new,quotes:m.quotes.map(q=>({time:q.time,price:q.price,other:q.other,gap:q.gap})),
    result:m.result.state,score:m.result.score,notified:false,qualifying:m.qualifying }));
  return { moves, summary:packet.summary };
}
export async function readDay(day: string) {
  const path = day.replaceAll("-", "/");
  const scans = "drop-scans-v2/" + path, deliveries = "drop-deliveries-v2/" + path;
  const results="presentation/outcomes";
  const [latest, names, notices, listed] = await Promise.all([read<{observed:string; events:Record<string,Event>}>("latest.json"),files(scans),files(deliveries),storage().list(results,{search:day+".json",limit:2})]);
  if(listed.error)throw new Error("Private results unavailable");
  const outcomes=listed.data?.some(row=>row.name===day+".json")?await read<Record<string,Outcome>>(results+"/"+day+".json"):{};
  const notified = new Set<string>();
  const batches: Scan[] = [];
  for (let i=0;i<names.length;i+=8) {
    const chunk=names.slice(i,i+8);
    const checked=await Promise.all(chunk.map(async name => {
      const [scan,receipt]=await Promise.all([read<Scan>(scans+"/"+name),notices.includes(name)?read<Receipt>(deliveries+"/"+name):undefined]);
      if (receipt?.state==="sent") receipt.move_ids.forEach(id=>notified.add(id));
      return scan;
    }));
    batches.push(...checked);
  }
  const moves: Move[] = batches.reverse().flatMap(batch=>batch.moves.map(m=>({
    tour:m.tour,league:m.league,player:m.player,opponent:m.opponent,start:m.start,before:m.before,after:m.after,
    old:m.old,new:m.new,quotes:[{time:m.before,price:m.old,other:m.old_opponent},{time:m.after,price:m.new,other:m.new_opponent}],
    result:outcomes[m.move_id]?.result??"Awaiting verified result",score:outcomes[m.move_id]?.score,notified:notified.has(m.move_id),
  })));
  const fixtures:Fixture[]=Object.values(latest.events).map(e=>({tour:e.tour,league:e.league,start:e.start,home:e.home,away:e.away,homePrice:e.home_price,awayPrice:e.away_price}));
  return { moves,fixtures,observed:latest.observed,scans:names.length,compared:batches.reduce((n,b)=>n+b.compared_pairs,0) };
}
