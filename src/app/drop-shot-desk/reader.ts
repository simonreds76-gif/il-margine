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
  fixture: string; event_id: string; contract?:string; market?:string; side?:number; selection?:string; opposite?:string;
  tour: string; league: string; player: string; opponent: string; start: string; before: string; after: string;
  old: number; new: number; old_opponent: number; new_opponent: number; move_id: string;
};
type Event = { contracts?: Record<string,{labels:[string,string];prices:[number,number]}>; id: string; fixture: string; tour:string; league:string; start:string; home:string; away:string; home_price:number; away_price:number };
type Scan = { policy?: string; alert_ids?: string[]; observed: string; moves: Saved[]; compared_pairs: number };
type Receipt = { state: string; move_ids: string[]; delivered_at: string; observed: string };
type Outcome = { result:string; score:string; profit?:number };
type ArchiveRow = Omit<Saved,"tour"> & { level:string; quotes:Quote[]; qualifying:boolean; result:{state:string; score?:string} };
type Archive = { moves: ArchiveRow[]; summary:{ wins:number; losses:number; voids:number; settled_stake:number; net_units:number; roi_pct:number } };

export async function readArchive() {
  const packet = await read<Archive>("presentation/archive-v1.json");
  const moves: Move[] = packet.moves.map(m => ({ fixtureRef:m.fixture,tour:m.level,league:m.league,player:m.player,opponent:m.opponent,start:m.start,
    before:m.before,after:m.after,old:m.old,new:m.new,quotes:m.quotes.map(q=>({time:q.time,price:q.price,other:q.other,gap:q.gap})),
    result:m.result.state,score:m.result.score,notified:false,qualifying:m.qualifying }));
  return { moves, summary:packet.summary };
}
type Tape = { slots: Record<string,string>; series: Record<string, {
  players: [string,string]; quotes: [string,number,number][];
}> };
type Delivery = { fourPointAlert: boolean; batchId:string; batchAt:string; alertedAt:string };

async function readTapes(moves:Saved[], observed:string) {
  if (!moves.length) return [];
  const days = new Set<string>();
  const earliest = Date.parse("2026-11-19T00:00:00Z");
  for (const move of moves) {
    const begin = Math.max(earliest,Date.parse(move.before)-86400000);
    const end = Math.min(Date.parse(observed),Date.parse(move.start));
    for (let t=Math.floor(begin/86400000)*86400000; t<=end; t+=86400000)
      days.add(new Date(t).toISOString().slice(0,10));
  }
  return Promise.all([...days].map(async day => {
    const name = day+".json";
    const listed = await storage().list("presentation/desk-tapes",{search:name,limit:2});
    if (listed.error) throw new Error("Private chart history unavailable");
    return listed.data?.some(f=>f.name===name) ? read<Tape>("presentation/desk-tapes/"+name) : null;
  }));
}

function availableUntil(start: string, observed: string, now: number): string | undefined {
  const seen = Date.parse(observed);
  const cutoff = Math.min(Date.parse(start), seen + 20 * 60_000);
  return seen <= now && now < cutoff ? new Date(cutoff).toISOString() : undefined;
}

function moveCutoff(move: Saved, event: Event | undefined, observed: string, now: number) {
  if (!event || event.fixture !== move.fixture || Date.parse(event.start) !== Date.parse(move.start)) return;
  if(move.contract && move.contract!=="winner" && !event.contracts?.[move.contract])return;
  const same = event.home === move.player && event.away === move.opponent;
  const reversed = event.away === move.player && event.home === move.opponent;
  if (same || reversed) return availableUntil(event.start, observed, now);
}

function quotesFor(m:Saved,tapes:(Tape|null)[],latest:{observed:string;events:Record<string,Event>}):Quote[] {
  const quotes = new Map<string,Quote>();
  const games = !!m.contract && m.contract !== "winner";
  const seriesKey = [m.event_id,m.fixture,m.start,...(games?[m.contract]:[])].join("|");
  const label = games ? m.selection : m.player, opposite = games ? m.opposite : m.opponent;
  for (const tape of tapes) {
    const series = tape?.series[seriesKey];
    if (!series) continue;
    const side = series.players.indexOf(label ?? "");
    if (side<0 || series.players[1-side]!==opposite) continue;
    for (const [time,a,b] of series.quotes)
      if (Date.parse(time)<Date.parse(m.start)) quotes.set(time,{time,price:side?b:a,other:side?a:b});
  }
  const e=latest.events[m.event_id];
  if(e?.fixture===m.fixture && e.start===m.start && Date.parse(latest.observed)<Date.parse(m.start)) {
    const home=e.home===m.player && e.away===m.opponent, away=e.away===m.player && e.home===m.opponent;
    const contract = games && m.contract ? e.contracts?.[m.contract] : undefined;
    if(contract && m.side !== undefined && contract.labels[m.side]===label)
      quotes.set(latest.observed,{time:latest.observed,price:contract.prices[m.side],other:contract.prices[1-m.side]});
    if(!games && (home || away)) quotes.set(latest.observed,{time:latest.observed,price:home?e.home_price:e.away_price,other:home?e.away_price:e.home_price});
  }
  for (const q of [{time:m.before,price:m.old,other:m.old_opponent},{time:m.after,price:m.new,other:m.new_opponent}])
    quotes.set(q.time,q);
  const sorted=[...quotes.values()].sort((a,b)=>Date.parse(a.time)-Date.parse(b.time));
  return sorted.map((q,i)=>({...q,gap:i>0 && Math.floor(Date.parse(q.time)/900000)-Math.floor(Date.parse(sorted[i-1].time)/900000)>1}));
}

export async function readDay(day: string) {
  const path = day.replaceAll("-", "/");
  const scans = "drop-scans-v2/" + path, deliveries = "drop-deliveries-v2/" + path;
  const results="presentation/outcomes";
  const [latest, names, notices, listed] = await Promise.all([read<{observed:string; events:Record<string,Event>}>("latest.json"),files(scans),files(deliveries),storage().list(results,{search:day+".json",limit:2})]);
  if(listed.error)throw new Error("Private results unavailable");
  const outcomes=listed.data?.some(row=>row.name===day+".json")?await read<Record<string,Outcome>>(results+"/"+day+".json"):{};
  const notified = new Map<string,Delivery>();
  const batches: Scan[] = [];
  for (let i=0;i<names.length;i+=8) {
    const chunk=names.slice(i,i+8);
    const checked=await Promise.all(chunk.map(async name => {
      const [scan,receipt]=await Promise.all([read<Scan>(scans+"/"+name),notices.includes(name)?read<Receipt>(deliveries+"/"+name):undefined]);
      if (receipt?.state==="sent" && receipt.observed===scan.observed) {
        const batchId=name.slice(0,-5);
        const eligible = new Set(scan.policy === "same-line-4pp-prematch-v1" ? scan.alert_ids : []);
        for (const id of receipt.move_ids) {
          notified.set(id, { batchId, batchAt: receipt.delivered_at, alertedAt: receipt.delivered_at, fourPointAlert: eligible.has(id) });
        }
      }
      return scan;
    }));
    batches.push(...checked);
  }
  const tapes=await readTapes(batches.flatMap(b=>b.moves),latest.observed);
  const now = Date.now();
  const quoteCache = new Map<string,Quote[]>();
  function historyFor(m:Saved){
    const key=[m.event_id,m.fixture,m.start,m.contract??"winner",m.selection??m.player].join("|");
    let qs=quoteCache.get(key);
    if(!qs || !qs.some(q=>q.time===m.before) || !qs.some(q=>q.time===m.after)){
      qs=quotesFor(m,tapes,latest);
      quoteCache.set(key,qs);
    }
    return qs;
  }
  const moves: Move[] = batches.reverse().flatMap(batch=>batch.moves.map(m=>({
    fixtureRef:m.fixture,tour:m.tour,league:m.league,market:m.market,player:m.selection??m.player,opponent:m.opposite??m.opponent,
    fixtureLabel:m.market && m.market!=="winner" ? [m.player,m.opponent].join(" vs "):undefined,
    start:m.start,before:m.before,after:m.after,profit:outcomes[m.move_id]?.profit,
    old:m.old,new:m.new,quotes:historyFor(m),...notified.get(m.move_id),
    activeUntil: outcomes[m.move_id] ? undefined : moveCutoff(m,latest.events[m.event_id],latest.observed,now),
    result:outcomes[m.move_id]?.result??"Awaiting verified result",score:outcomes[m.move_id]?.score,notified:notified.has(m.move_id),
  })));
  const fixtures:Fixture[]=Object.values(latest.events).map(e=>({tour:e.tour,league:e.league,start:e.start,home:e.home,away:e.away,homePrice:e.home_price,awayPrice:e.away_price,activeUntil:availableUntil(e.start,latest.observed,now)}));
  return { moves,fixtures,observed:latest.observed,scans:names.length,compared:batches.reduce((n,b)=>n+b.compared_pairs,0) };
}
