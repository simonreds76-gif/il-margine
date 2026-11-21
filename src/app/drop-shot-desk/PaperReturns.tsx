import { getSupabaseAdmin } from "@/lib/supabase-server";
import type { Circuit } from "./types";
import styles from "./board.module.css";

type Result = {
  entries:number; fixtures:number; won:number; lost:number; halfWon:number; halfLost:number;
  pushes:number; voids:number; pending:number; stake:number; net:number; roi:number|null;
};
const rules = [["all4","All pre-match ≥4 pp"],["all45","All pre-match ≥4.5 pp"],
  ["late4","Final hour ≥4 pp"],["late45","Final hour ≥4.5 pp"]] as const;
type Report = {day:string; through:string; circuits:Record<Circuit,{coveredScans:number;
  rules:Record<typeof rules[number][0],Result>}>};
const signed = (v:number) => (v>0?"+":"") + v.toFixed(2);
async function load(day:string): Promise<Report|null> {
  try {
    const {data,error} = await getSupabaseAdmin().storage.from("tennis-price-moves-private")
      .download("presentation/drop-paper-v1/summary/"+day+".json");
    if (!data || error) return null;
    const report:Report = JSON.parse(await data.text());
    return report.day===day ? report : null;
  } catch { return null; }
}
export async function PaperReturns({day,circuit}:{day:string;circuit:Circuit}) {
  if(day<"2026-11-20" || (circuit==="WTA" && day<"2026-11-21")) return null;
  const report=await load(day);
  const summary=report?.circuits[circuit];
  return <section className={styles.results} id="big-drop-returns" aria-labelledby="paper-return-title">
    <header className={styles.resultsHead}><h2 id="paper-return-title">Big-drop paper returns <small>{day} UTC</small></h2></header>
    {!summary ? <p>Paper results for this date are awaiting an update.</p> : !summary.coveredScans ?
      <p>No {circuit} matches with recorded odds on this date.</p> : <>
      <p>≥4 pp and ≥4.5 pp mean rises of at least 4 and 4.5 percentage points in implied probability. Compare the rows separately.</p>
      <div className={styles.paperScroll} role="region" aria-label="Paper returns by timing and threshold" tabIndex={0}>
        <table className={styles.paperTable}><thead><tr>{["Move","Picks","Matches","W–L","Open","Stake","P/L","ROI"].map(s=><th scope="col" key={s}>{s}</th>)}</tr></thead>
        <tbody>{rules.map(([key,label])=>{
          const r=summary.rules[key];
          return <tr key={key}><th scope="row">{label}</th><td>{r.entries}</td><td>{r.fixtures}</td>
            <td>{r.won}–{r.lost}{r.halfWon||r.halfLost ? " ("+r.halfWon+" half W, "+r.halfLost+" half L)" : ""}
              {r.pushes?" · "+r.pushes+" push":""}{r.voids?" · "+r.voids+" void":""}</td>
            <td>{r.pending}</td><td>{r.stake}u</td><td>{r.stake?signed(r.net)+"u":"—"}</td>
            <td data-positive={r.net===0?undefined:r.net>0}>{r.roi===null?"—":signed(r.roi)+"%"}</td></tr>;
        })}</tbody></table>
      </div>
      <details className={styles.fold}><summary>How to read the comparison</summary>
        <p className={styles.fine}>Each rule records 1u at the first qualifying odds for a match, market, line and side. A repeat drop on that same side and line adds no stake. A move on the other player, or a different handicap, can count separately. “Picks” counts those entries and “Matches” counts distinct fixtures. One fixture can drive several wins or losses.</p>
        <p className={styles.fine}>A move can qualify in several rows at different odds. Adding rows would double-count overlapping picks. Both observations must fall inside the final hour for the final-hour rows. ROI uses settled stakes. The Telegram record above counts delivered alerts.</p>
        <p className={styles.fine}>The initial replay used saved scans through 21 November 2026 at 10:15 UTC. Later entries use the same rules as new scans arrive.</p>
      </details>
    </>}
  </section>;
}
