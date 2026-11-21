import { getSupabaseAdmin } from "@/lib/supabase-server";
import { loadClosing, closingKey, summariseClosing, publicClose } from "@/app/drop-shot-desk/closing";
import type { Result } from "@/app/drop-shot-desk/PaperReturnsPanel";

type Row = {selection:string; fixture:string; league:string; at:string; odds:number; result:string; sent:boolean};
type Packet = {version:number; tour:string; start:string; end:string; through:string; firstCovered:string|null;
  coveredDays:number; all:Result; telegram:Result; rows:Row[]; sentRows:Row[]};
const pageSize = 12;
const headers = {"X-Robots-Tag":"noindex, nofollow","Cache-Control":"public, max-age=0, s-maxage=60"};

export async function GET(request:Request) {
  const q = new URL(request.url).searchParams;
  const tour = q.get("tour"), group = q.get("group");
  const page = Number(q.get("page") ?? 1);
  if ((tour!=="atp" && tour!=="wta") || (group!=="all" && group!=="telegram") || !Number.isSafeInteger(page) || page<1) {
    return new Response(null,{status:400});
  }
  try {
    const [packet,closing] = await Promise.all([getSupabaseAdmin().storage.from("tennis-price-moves-private")
      .download("presentation/drop-paper-v1/rolling-30-v2/"+tour+".json"),loadClosing(tour)]);
    const {data,error}=packet;
    if (error || !data) throw new Error();
    const p:Packet = JSON.parse(await data.text());
    if (p.version!==2 || p.tour!==tour.toUpperCase()) throw new Error();
    const rows = group==="telegram" ? p.sentRows : p.rows;
    const s = p[group];
    if (!s || rows.length!==s.entries) throw new Error();
    const index=new Map(closing?.filter(e=>e.group===group).map(e=>[closingKey(e),e.close]));
    const clv=closing?summariseClosing(rows.map(r=>index.get(closingKey(r)))):null;
    const pages = Math.max(1,Math.ceil(rows.length/pageSize));
    const current = Math.min(page,pages);
    // Allowlist presentation fields. Storage paths, supplier and delivery identifiers are private.
    const {entries,fixtures,won,lost,halfWon,halfLost,pushes,voids,pending,stake,net,roi} = s;
    return Response.json({tour:p.tour,start:p.start,end:p.end,through:p.through,firstCovered:p.firstCovered,
      coveredDays:p.coveredDays,summary:{entries,fixtures,won,lost,halfWon,halfLost,pushes,voids,pending,stake,net,roi,clv},
      page:current,pages,rows:rows.slice((current-1)*pageSize,current*pageSize).map(r=>({
        selection:r.selection,fixture:r.fixture,league:r.league,result:r.result,at:r.at,
        odds:r.odds,sent:r.sent,close:publicClose(index.get(closingKey(r))),
      }))},{headers});
  } catch {
    return Response.json({error:"The rolling record is temporarily unavailable."},
      {status:503,headers:{"Cache-Control":"no-store","X-Robots-Tag":"noindex"}});
  }
}
