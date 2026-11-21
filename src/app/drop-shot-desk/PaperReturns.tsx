import { getSupabaseAdmin } from "@/lib/supabase-server";
import type { Circuit } from "./types";
import { loadClosing, summariseClosing } from "./closing";
import { PaperReturnsPanel } from "./PaperReturnsPanel";
import type { PaperDay, PaperSlice, Result } from "./PaperReturnsPanel";

// Private paper files. The daily summaries and the lifetime/month performance file share this base.
const BUCKET = "tennis-price-moves-private";
const BASE = "presentation/drop-paper-v1";

type Report = {day:string; through:string; circuits:Record<string,{coveredScans:number; rules:Record<string,unknown>}>};
type Performance = {through:string; firstDay:string;
  circuits:Record<string,{lifetime:unknown; months:Record<string,unknown>}>};

async function read<T>(path:string): Promise<T|null> {
  try {
    const {data,error} = await getSupabaseAdmin().storage.from(BUCKET).download(BASE+"/"+path);
    if (!data || error) return null;
    return JSON.parse(await data.text()) as T;
  } catch { return null; }
}
// The files are private and hand over only what the panel shows: each figure is copied field by field.
const num = (v:unknown) => (typeof v==="number" && Number.isFinite(v) ? v : 0);
function result(v:unknown): Result|null {
  if (!v || typeof v!=="object") return null;
  const r = v as Record<string,unknown>;
  return {entries:num(r.entries), fixtures:num(r.fixtures), won:num(r.won), lost:num(r.lost), halfWon:num(r.halfWon), halfLost:num(r.halfLost),
    pushes:num(r.pushes), voids:num(r.voids), pending:num(r.pending), stake:num(r.stake), net:num(r.net),
    roi:typeof r.roi==="number" && Number.isFinite(r.roi) ? r.roi : null};
}
function slice(v:unknown): PaperSlice|null {
  if (!v || typeof v!=="object") return null;
  const o = v as Record<string,unknown>;
  const all4 = result(o.all4);
  return all4 ? {all4, late4:result(o.late4)} : null;
}

/**
 * The paper record of the selected tour: lifetime by default, a calendar month or the board's day on request.
 * Lifetime and months come from performance.json; the day comes from that date's own summary file.
 */
export async function PaperReturns({day,circuit}:{day:string;circuit:Circuit}) {
  // Each tour's record has its own first day; a board date before it has no day figures.
  const firstDay = circuit==="WTA" ? "2026-11-21" : "2026-11-20";
  const dayOpen = day>=firstDay;
  const [perf,report,closing] = await Promise.all([read<Performance>("performance.json"), dayOpen ? read<Report>("summary/"+day+".json") : null, loadClosing(circuit)]);

  const tour = perf?.circuits?.[circuit];
  const lifetime = slice(tour?.lifetime);
  const months:{key:string;slice:PaperSlice}[] = [];
  for (const [key,value] of Object.entries(tour?.months ?? {})) {
    const s = /^\d{4}-\d{2}$/.test(key) ? slice(value) : null;
    if (s) months.push({key, slice:s});
  }
  months.sort((a,b)=>(a.key<b.key ? 1 : -1));
  // Before the record began and with nothing longer to show, the panel stays away, as it always has.
  if (!dayOpen && !lifetime && !months.length) return null;

  const daily = report && report.day===day ? report.circuits?.[circuit] : undefined;
  const all4 = result(daily?.rules?.all4);
  const dayView:PaperDay = !dayOpen ? {state:"early"} : !daily || !report ? {state:"awaiting"} : !daily.coveredScans ? {state:"none"}
    : !all4 ? {state:"awaiting"} : {state:"ok", through:typeof report.through==="string" ? report.through : "", all4, late4:result(daily.rules.late4),
      all45:result(daily.rules.all45), late45:result(daily.rules.late45)};

  const measured = closing?.filter(r=>r.group==="all" && perf?.through && Date.parse(r.at)<=Date.parse(perf.through));
  const withClose=(s:PaperSlice|null, period:string) => {
    if(s && measured) s.all4.clv=summariseClosing(measured.filter(r=>r.at.startsWith(period)).map(r=>r.close));
  };
  withClose(lifetime,"");
  for(const m of months)withClose(m.slice,m.key);
  if(dayView.state==="ok")withClose(dayView, day);
  const stated = typeof perf?.firstDay==="string" ? perf.firstDay : "";
  return <PaperReturnsPanel circuit={circuit} day={day} since={stated>firstDay ? stated : firstDay}
    through={typeof perf?.through==="string" ? perf.through : ""} lifetime={lifetime} months={months} dayView={dayView} />;
}
