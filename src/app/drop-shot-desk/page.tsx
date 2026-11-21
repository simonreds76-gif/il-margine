import Link from "next/link";
import Image from "next/image";
import { isAdminSession } from "@/lib/admin-auth";
import { publicFixture, publicMove } from "./public-view";
import brand from "./drop-shot-mark.png";
import { DeskIcon } from "./DeskIcon";
import Board from "./Board";
import { hostOf, venueKey } from "./DeskParts";
import type { VenueMap } from "./DeskParts";
import { readArchive, readDay } from "./reader";
import styles from "./board.module.css";
import { PaperReturns } from "./PaperReturns";
import { countryForTournament } from "@/lib/tennis-tournament-country.mjs";

export const dynamic="force-dynamic";
export const fetchCache="force-no-store";
export const metadata={title:"Drop Shot Desk · Tennis odds moves",robots:{index:false,follow:false,noarchive:true}};
const route="/drop-shot-desk";
const firstDay="2026-11-19";
type Query=string|string[]|undefined;
const one=(v:Query)=>Array.isArray(v)?v[0]:v;
const signed=(n:number)=>(n>0?"+":"")+n;
function validDay(input:string|undefined,today:string) {
  if(!input||!/^\d{4}-\d{2}-\d{2}$/.test(input)||input<firstDay||input>today)return today;
  const d=new Date(input+"T00:00:00Z");return Number.isFinite(+d)&&d.toISOString().slice(0,10)===input?input:today;
}
function shiftDay(day:string,by:number) {
  return new Date(Date.parse(day+"T00:00:00Z")+by*86400000).toISOString().slice(0,10);
}
/** Resolved on the server, so the registry never ships to the browser; the board receives a plain map. */
function venuesFor(rows: { tour: string; league: string; start: string }[]) {
  const out: VenueMap = {}, tried = new Set<string>();
  for (const r of rows) {
    const key = venueKey(r.league, r.start, r.tour);
    if (tried.has(key)) continue;
    tried.add(key);
    const venue = countryForTournament(hostOf(r.league), r.tour, r.start.slice(0, 10));
    if (venue) out[key] = venue;
  }
  return out;
}
export default async function PriceMoves({searchParams}:{searchParams:Promise<{view?:Query;day?:Query;batch?:Query;tour?:Query}>}) {
  const fullBoard = await isAdminSession();
  const params=await searchParams,archive=one(params.view)==="archive",today=new Date().toISOString().slice(0,10);
  const day=validDay(one(params.day),today);
  const circuit=one(params.tour)?.toLowerCase()==="wta" ? "WTA" : "ATP";
  const dailyUrl=(tour: "ATP"|"WTA", date=day)=>route+"?tour="+tour.toLowerCase()+"&day="+date;
  const batchParam=one(params.batch);
  const batch=batchParam&&/^[A-Za-z0-9_-]{1,64}$/.test(batchParam)?batchParam:undefined;
  let content;
  try{
    if(archive && circuit==="WTA"){
      content=<p className={styles.empty}>The historical replay covers ATP and Challenger matches. <Link href={dailyUrl("WTA")}>See WTA daily moves</Link></p>;
    } else if(archive){
      const {moves,summary:s}=await readArchive();
      content=<>
        <section className={styles.replay} aria-label="Historical replay record">
          <p className={styles.replayNote}><span className={styles.replayTag}><DeskIcon name="replay"/>Historical replay</span>22 Oct – 18 Nov 2026 · Historical replay at the price shown at detection. Each settled selection carries 1u.</p>
          <p className={styles.record}>
            <span className={styles.wl}><b>{s.wins}</b> won · <b>{s.losses}</b> lost · <b>{s.voids}</b> void</span>
            <span className={styles.net} data-tone={s.net_units>0?"won":s.net_units<0?"lost":undefined}><b>{signed(s.net_units)}u</b> on {s.settled_stake}u settled · <b>{signed(s.roi_pct)}%</b> replay ROI · {moves.length} {moves.length===1?"move":"moves"}</span>
          </p>
        </section>
        <Board moves={fullBoard ? moves : moves.map(publicMove)} fixtures={[]} archive venues={venuesFor(moves)}/></>;
    } else {
      // Stamped after the read so the first paint never treats a record as open later than the server saw it.
      const data=await readDay(day,circuit),now=Date.now(),seen=Date.parse(data.observed),known=Number.isFinite(seen);
      const late=known&&day===today&&(now-seen)/60000>40;
      const earlier=day>firstDay?shiftDay(day,-1):null,later=day<today?shiftDay(day,1):null;
      content=<>
        <section className={styles.dayBar} aria-label="Observation date">
          <form className={styles.date} action={route}>
            <input type="hidden" name="tour" value={circuit.toLowerCase()}/>
            <label htmlFor="desk-day">Observation date (UTC)</label>
            <div className={styles.dateRow}>
              {earlier?<Link className={styles.dayStep} href={dailyUrl(circuit,earlier)} aria-label="Previous day"><span aria-hidden="true">‹</span></Link>:<span className={styles.dayStep} aria-hidden="true" data-off="true">‹</span>}
              <input id="desk-day" name="day" type="date" min={firstDay} max={today} defaultValue={day} key={day}/>
              {later?<Link className={styles.dayStep} href={dailyUrl(circuit,later)} aria-label="Next day"><span aria-hidden="true">›</span></Link>:<span className={styles.dayStep} aria-hidden="true" data-off="true">›</span>}
              <button>Show date</button>
            </div>
          </form>
          <dl className={styles.facts}>
            <div><dt>Recorded scans</dt><dd>{data.scans}</dd></div>
            <div><dt>Match comparisons</dt><dd>{data.compared}</dd></div>
            <div><dt>Price drops</dt><dd>{data.moves.length}</dd></div>
            <div><dt>Watchlist matches</dt><dd>{data.fixtures.length}</dd></div>
          </dl>
        </section>
        <p className={styles.fresh} role="status" data-late={late?"true":undefined}>{known?<>Latest watchlist at {new Date(seen).toISOString().slice(0,16).replace("T"," ")} UTC{late?" · overdue for a new scan":day===today?" · the cloud scan runs every 15 minutes":""}.</>:"No watchlist has been recorded for this date."}</p>
        {day >= (circuit==="ATP"?"2026-11-20":"2026-11-21") && <a className={styles.back} href="#big-drop-returns">See big-drop paper returns ↓</a>}
        <Board key={circuit} circuit={circuit} moves={fullBoard ? data.moves : data.moves.map(publicMove)} fixtures={fullBoard ? data.fixtures : data.fixtures.map(publicFixture)} archive={false} initialBatchId={batch} day={day} now={now} today={day===today} venues={venuesFor([...data.moves,...data.fixtures])}/>
        <PaperReturns day={day} circuit={circuit}/></>;
    }
  }catch{content=<p className={styles.problem} role="status">The price records could not be loaded. Refresh to try again.</p>}
  return <main className={styles.page} data-mode={archive?"archive":"daily"}>
    <div className={styles.topline}><Link className={styles.back} href="/tennis-matchday">← Tennis Matchday</Link><span className={styles.lab}>Unlisted pilot</span></div>
    <header className={styles.mast}>
      <div className={styles.brand}><Image src={brand} unoptimized alt="" width={66} height={36} priority/><div><p className={styles.kicker}>Tennis odds moves</p><h1>Drop Shot Desk</h1></div></div>
      <nav aria-label="Price history" className={styles.tabs}><Link aria-current={!archive?"page":undefined} href={dailyUrl(circuit)}><DeskIcon name="drop"/>Daily moves</Link><Link aria-current={archive?"page":undefined} href={route+"?view=archive&tour=atp&day="+day}><DeskIcon name="replay"/>Historical replay{circuit==="WTA"?" (ATP only)":""}</Link></nav>
    </header>
    <nav className={styles.circuit} aria-label="Tennis tour">
      {(["ATP","WTA"] as const).map(tour=><Link key={tour} prefetch={false} aria-current={circuit===tour?"page":undefined}
        href={archive && tour==="ATP" ? route+"?view=archive&tour=atp&day="+day : dailyUrl(tour)}>
        <span className={styles.tourBadge}><Image unoptimized width={58} height={24} src={tour==="ATP"?"/icons/drop-shot-desk/atp-tour.png":"/icons/drop-shot-desk/wta-tour.svg"} alt={tour}/></span>
        <small>{tour==="ATP"?"incl. Challenger":"incl. WTA 125"}</small>
      </Link>)}
    </nav>
    <p className={styles.standfirst}>Spot possible sharp money before the first serve. We check {circuit==="ATP"?"ATP and Challenger":"WTA Tour and WTA 125"} odds about every 15 minutes and show which players, game totals and games handicaps are shortening. Open a chart to see when the odds fell and whether they drifted back.</p>
    <details className={styles.fold}>
      <summary>What triggers an alert?</summary>
      <p className={styles.fine}>Telegram flags a selection once if its implied probability rises by at least four percentage points in the final hour before the scheduled start. Odds of 2.00 at 45 minutes out and 1.85 at 15 minutes out imply a rise from 50% to 54.1%. Both readings must be for the same selection and line. The board also shows earlier moves. Returns use the odds at detection.</p>
      <p className={styles.fine}>A drop can reflect betting pressure or news. Our scans record the odds at each check. Betting volumes and bettor identities are unavailable.</p>
    </details>
    {content}</main>;
}
