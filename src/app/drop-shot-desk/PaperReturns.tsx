import { getSupabaseAdmin } from "@/lib/supabase-server";
import type { Circuit } from "./types";
import { PaperReturnsPanel } from "./PaperReturnsPanel";
import type { PaperDay, PaperSlice, Result } from "./PaperReturnsPanel";

// Private paper files. The daily summaries and the lifetime/month performance file share this base.
const BUCKET = "tennis-price-moves-private";
const BASE = "presentation/drop-paper-v1";

type MatchReport = {version:number; tour:string; through:string; firstDay:string|null;
  lifetime:unknown; months:Record<string,unknown>; days:Record<string,unknown>};
type ArchiveDay = {day:string; circuits:Record<string,{rules:Record<string,unknown>}>};

async function read<T>(path:string): Promise<T|null> {
  try {
    const {data,error} = await getSupabaseAdmin().storage.from(BUCKET).download(BASE+"/"+path);
    if (!data || error) return null;
    return JSON.parse(await data.text()) as T;
  } catch { return null; }
}
// The files are private and hand over only what the panel shows: each figure is copied field by field.
const num = (v:unknown) => (typeof v==="number" && Number.isFinite(v) ? v : 0);
function result(v:unknown, perMatch=true): Result|null {
  if (!v || typeof v!=="object") return null;
  const r = v as Record<string,unknown>;
  if (typeof r.entries!=="number" || (perMatch && r.entries!==r.fixtures)) return null;
  const clv = r.clv as {measured?:unknown;mean?:unknown}|null;
  return {entries:num(r.entries), fixtures:num(r.fixtures), won:num(r.won), lost:num(r.lost), halfWon:num(r.halfWon), halfLost:num(r.halfLost),
    pushes:num(r.pushes), voids:num(r.voids), pending:num(r.pending), stake:num(r.stake), net:num(r.net),
    clv:clv ? {measured:num(clv.measured),mean:typeof clv.mean==="number" ? clv.mean : null} : null,
    roi:typeof r.roi==="number" && Number.isFinite(r.roi) ? r.roi : null};
}
function slice(v:unknown): PaperSlice|null {
  if (!v || typeof v!=="object") return null;
  const o = v as Record<string,unknown>;
  const all4 = result(o.all4);
  return all4 ? {all4, late4:result(o.late4)} : null;
}

export async function PaperReturns({day,circuit}:{day:string;circuit:Circuit}) {
  const [report,archive] = await Promise.all([read<MatchReport>("first-match-v1/"+circuit.toLowerCase()+".json"),
    read<ArchiveDay>("summary/"+day+".json")]);
  const tour = report?.version===1 && report.tour===circuit ? report : null;
  const firstDay = tour?.firstDay ?? (circuit==="WTA" ? "2026-11-21" : "2026-11-20");
  const dayOpen = day>=firstDay;
  const lifetime = slice(tour?.lifetime);
  const months:{key:string;slice:PaperSlice}[] = [];
  for (const [key,value] of Object.entries(tour?.months ?? {})) {
    const s = /^\d{4}-\d{2}$/.test(key) ? slice(value) : null;
    if (s) months.push({key, slice:s});
  }
  months.sort((a,b)=>(a.key<b.key ? 1 : -1));
  // Before the record began and with nothing longer to show, the panel stays away, as it always has.
  if (!dayOpen && !lifetime && !months.length) return null;

  const daily = slice(tour?.days[day]);
  const legacy = archive?.day===day ? archive.circuits?.[circuit]?.rules : undefined;
  const dayView:PaperDay = !dayOpen ? {state:"early"} : !tour || day>tour.through.slice(0,10) ? {state:"awaiting"}
    : daily ? {state:"ok", through:tour.through, ...daily, all45:result(legacy?.all45,false), late45:result(legacy?.late45,false)} : {state:"none"};
  return <PaperReturnsPanel circuit={circuit} day={day} since={firstDay}
    through={tour?.through ?? ""} lifetime={lifetime} months={months} dayView={dayView} />;
}
