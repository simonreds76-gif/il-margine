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
export const metadata={title:"Drop Shot Desk · Tennis odds moves | Il Margine",robots:{index:false,follow:false}};
const route="/drop-shot-desk";
const firstDay="2026-11-19";
function validDay(input:string|undefined,today:string) {
  if(!input||!/^\d{4}-\d{2}-\d{2}$/.test(input)||input<firstDay||input>today)return today;
  const d=new Date(input+"T00:00:00Z");return Number.isFinite(+d)&&d.toISOString().slice(0,10)===input?input:today;
}
export default async function PriceMoves({searchParams}:{searchParams:Promise<{view?:string;day?:string}>}) {
  // The team's deployment protection covers preview URLs. A production build must
  // never expose the pilot by guessing its path, even if this commit is promoted.
  if(process.env.VERCEL_ENV!=="preview" && process.env.NODE_ENV!=="development")notFound();
  const params=await searchParams,archive=params.view==="archive",today=new Date().toISOString().slice(0,10);
  const day=validDay(params.day,today);
  let content;
  try{
    if(archive){
      const {moves,summary:s}=await readArchive();
      content=<><p className={styles.info}>22 Oct – 18 Nov 2026 · Historical replay at the price shown at detection. Each settled selection carries 1u.</p>
        <p className={styles.summary}><DeskIcon name="record"/>{moves.length} moves · {s.wins} wins · {s.losses} losses · {s.voids} void · {s.net_units>0?"+":""}{s.net_units}u on {s.settled_stake}u · ROI {s.roi_pct>0?"+":""}{s.roi_pct}%</p>
        <Board moves={moves} fixtures={[]} archive/></>;
    } else {
      const data=await readDay(day),age=(Date.now()-Date.parse(data.observed))/60000;
      content=<><form className={styles.date} action={route}><label>Observation date (UTC) <input name="day" type="date" min={firstDay} max={today} defaultValue={day}/></label><button>Show date</button></form>
        <p className={styles.info}>{data.scans} recorded scans · {data.compared} match comparisons on this date</p>
        <p className={styles.info} role="status">Latest watchlist at {new Date(data.observed).toISOString().slice(0,16).replace("T"," ")} UTC{age>40?" · overdue for a new scan":""}.</p>
        <Board moves={data.moves} fixtures={data.fixtures} archive={false}/></>;
    }
  }catch{content=<p role="status">The private price records could not be loaded. Refresh to try again.</p>}
  return <main className={styles.page}><Link className={styles.back} href="/tennis-matchday">← Tennis Matchday</Link>
    <header className={styles.mast}><Image src={brand} unoptimized alt="" width={66} height={36} priority/><div><p>Tennis odds moves</p><h1>Drop Shot Desk</h1></div></header>
    <p className={styles.info}>Follow pre-match price drops in ATP and Challenger singles. See the earlier odds, the price when the drop was detected and the match result.</p>
    <nav aria-label="Price history" className={styles.tabs}><Link aria-current={!archive?"page":undefined} href={route}><DeskIcon name="drop"/>Daily moves</Link><Link aria-current={archive?"page":undefined} href={route+"?view=archive"}><DeskIcon name="replay"/>Historical replay</Link></nav>
    {content}</main>;
}
