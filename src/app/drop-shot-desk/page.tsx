import Link from "next/link";
import Image from "next/image";
import { notFound } from "next/navigation";
import brand from "./drop-shot-mark.png";
import { DeskIcon } from "./DeskIcon";
import Board from "./Board";
import { readArchive, readDay } from "./reader";
import styles from "./board.module.css";

export const dynamic="force-dynamic";
export const fetchCache="force-no-store";
export const metadata={title:"Drop Shot Desk · Tennis odds moves",robots:{index:false,follow:false}};
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
export default async function PriceMoves({searchParams}:{searchParams:Promise<{view?:Query;day?:Query;batch?:Query}>}) {
  // The team's deployment protection covers preview URLs. A production build must
  // never expose the pilot by guessing its path, even if this commit is promoted.
  if(process.env.VERCEL_ENV!=="preview" && process.env.NODE_ENV!=="development")notFound();
  const params=await searchParams,archive=one(params.view)==="archive",today=new Date().toISOString().slice(0,10);
  const day=validDay(one(params.day),today);
  const batchParam=one(params.batch);
  const batch=batchParam&&/^[A-Za-z0-9_-]{1,64}$/.test(batchParam)?batchParam:undefined;
  let content;
  try{
    if(archive){
      const {moves,summary:s}=await readArchive();
      content=<>
        <section className={styles.replay} aria-label="Historical replay record">
          <p className={styles.replayNote}><span className={styles.replayTag}><DeskIcon name="replay"/>Historical replay</span>22 Oct – 18 Nov 2026 · Historical replay at the price shown at detection. Each settled selection carries 1u.</p>
          <p className={styles.record}>
            <span className={styles.wl}><b>{s.wins}</b> won · <b>{s.losses}</b> lost · <b>{s.voids}</b> void</span>
            <span className={styles.net} data-tone={s.net_units>0?"won":s.net_units<0?"lost":undefined}><b>{signed(s.net_units)}u</b> on {s.settled_stake}u settled · <b>{signed(s.roi_pct)}%</b> replay ROI · {moves.length} {moves.length===1?"move":"moves"}</span>
          </p>
        </section>
        <Board moves={moves} fixtures={[]} archive/></>;
    } else {
      // Stamped after the read so the first paint never treats a record as open later than the server saw it.
      const data=await readDay(day),now=Date.now(),seen=Date.parse(data.observed),known=Number.isFinite(seen);
      const late=known&&day===today&&(now-seen)/60000>40;
      const earlier=day>firstDay?shiftDay(day,-1):null,later=day<today?shiftDay(day,1):null;
      content=<>
        <section className={styles.dayBar} aria-label="Observation date">
          <form className={styles.date} action={route}>
            <label htmlFor="desk-day">Observation date (UTC)</label>
            <div className={styles.dateRow}>
              {earlier?<Link className={styles.dayStep} href={route+"?day="+earlier} aria-label="Previous day"><span aria-hidden="true">‹</span></Link>:<span className={styles.dayStep} aria-hidden="true" data-off="true">‹</span>}
              <input id="desk-day" name="day" type="date" min={firstDay} max={today} defaultValue={day} key={day}/>
              {later?<Link className={styles.dayStep} href={route+"?day="+later} aria-label="Next day"><span aria-hidden="true">›</span></Link>:<span className={styles.dayStep} aria-hidden="true" data-off="true">›</span>}
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
        <p className={styles.fresh} role="status" data-late={late?"true":undefined}>{known?<>Latest watchlist at {new Date(seen).toISOString().slice(0,16).replace("T"," ")} UTC{late?" · overdue for a new scan":""}.</>:"No watchlist has been recorded for this date."}</p>
        <Board moves={data.moves} fixtures={data.fixtures} archive={false} initialBatchId={batch} day={day} now={now} today={day===today}/></>;
    }
  }catch{content=<p className={styles.problem} role="status">The private price records could not be loaded. Refresh to try again.</p>}
  return <main className={styles.page} data-mode={archive?"archive":"daily"}>
    <div className={styles.topline}><Link className={styles.back} href="/tennis-matchday">← Tennis Matchday</Link><span className={styles.lab}>Private preview</span></div>
    <header className={styles.mast}>
      <div className={styles.brand}><Image src={brand} unoptimized alt="" width={66} height={36} priority/><div><p className={styles.kicker}>Tennis odds moves</p><h1>Drop Shot Desk</h1></div></div>
      <nav aria-label="Price history" className={styles.tabs}><Link aria-current={!archive?"page":undefined} href={route}><DeskIcon name="drop"/>Daily moves</Link><Link aria-current={archive?"page":undefined} href={route+"?view=archive"}><DeskIcon name="replay"/>Historical replay</Link></nav>
    </header>
    <p className={styles.standfirst}>Follow ATP and Challenger match winners, total games and games handicaps. Telegram flags the first rise of 4 percentage points in implied probability from an earlier high price on the same selection and line, at any time before play.</p>
    {content}</main>;
}
