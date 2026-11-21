"use client";

import { useState } from "react";
import styles from "./board.module.css";

export type Result = {
  entries:number; fixtures:number; won:number; lost:number; halfWon:number; halfLost:number;
  pushes:number; voids:number; pending:number; stake:number; net:number; roi:number|null;
};
/** One period of the record: every pre-match move ≥4 pp, and the final-hour subset kept as a reference. */
export type PaperSlice = { all4:Result; late4:Result|null };
/** The selected board date. "early" is a date before this tour's record began. */
export type PaperDay =
  | { state:"ok"; through:string; all4:Result; late4:Result|null; all45:Result|null; late45:Result|null }
  | { state:"early"|"awaiting"|"none" };
type Period = "life"|"month"|"day";

const MONTHS = ["January","February","March","April","May","June","July","August","September","October","November","December"];
const signed = (v:number) => (v>0?"+":"") + v.toFixed(2);
const plain = (v:number) => String(Math.round(v*100)/100);
// Dates are printed by hand from the stored strings, so the server and the browser always agree.
function dayText(day:string) {
  const m = /^(\d{4})-(\d{2})-(\d{2})/.exec(day);
  const name = m ? MONTHS[Number(m[2])-1] : undefined;
  return m && name ? Number(m[3]) + " " + name.slice(0,3) + " " + m[1] : day;
}
function monthText(key:string) {
  const name = MONTHS[Number(key.slice(5,7))-1];
  return name ? name + " " + key.slice(0,4) : key;
}
function asOf(through:string) {
  const m = /^(\d{4}-\d{2}-\d{2})(?:[T ](\d{2}):(\d{2}))?/.exec(through);
  if (!m) return through;
  if (!m[2]) return dayText(m[1]);
  // A stamp with a zone is converted to UTC; one without is taken as UTC already.
  const d = /(?:Z|[+-]\d{2}:?\d{2})$/i.test(through) ? new Date(through) : null;
  const iso = d && !Number.isNaN(d.getTime()) ? d.toISOString() : m[1] + "T" + m[2] + ":" + m[3];
  return dayText(iso.slice(0,10)) + ", " + iso.slice(11,16) + " UTC";
}
const tone = (v:number|null) => (v===null || v===0 ? undefined : v>0 ? "won" : "lost");

/** ROI first, then the four counts behind it. Without settled stake there is no return to state: ROI and net show a dash. */
function Figures({r,reference}:{r:Result;reference?:boolean}) {
  const settled = r.roi!==null;
  const extra = [r.halfWon && r.halfWon+" half-won", r.halfLost && r.halfLost+" half-lost",
    r.pushes && r.pushes+(r.pushes===1?" push":" pushes"), r.voids && r.voids+" void"].filter(Boolean).join(" · ");
  return <dl className={styles.paperFigures} data-size={reference ? "ref" : undefined}>
    <div className={styles.paperRoi} data-tone={tone(r.roi)}><dt>ROI<span className={styles.vh}> on settled stake</span></dt><dd>{settled ? signed(r.roi as number)+"%" : "—"}</dd></div>
    <div><dt>W–L</dt><dd>{r.won}–{r.lost}{extra && <small>{extra}</small>}</dd></div>
    <div><dt>Pending</dt><dd>{r.pending}</dd></div>
    <div><dt>Stake</dt><dd>{plain(r.stake)}u</dd></div>
    <div data-tone={settled ? tone(r.net) : undefined}><dt>Net</dt><dd>{settled ? signed(r.net)+"u" : "—"}</dd></div>
  </dl>;
}

export function PaperReturnsPanel({circuit,day,since,through,lifetime,months,dayView}:{
  circuit:string; day:string; since:string; through:string;
  lifetime:PaperSlice|null; months:{key:string;slice:PaperSlice}[]; dayView:PaperDay;
}) {
  const [period,setPeriod] = useState<Period>(lifetime ? "life" : months.length ? "month" : "day");
  const [monthKey,setMonthKey] = useState(() => (months.find(m=>m.key===day.slice(0,7)) ?? months[0])?.key ?? "");
  const month = months.find(m=>m.key===monthKey) ?? months[0];
  const slice:PaperSlice|null = period==="life" ? lifetime : period==="month" ? month?.slice ?? null : dayView.state==="ok" ? dayView : null;

  const span = period==="life" ? <><b>Lifetime</b> · since {dayText(since)}{through ? ", to "+asOf(through) : ""}</>
    : period==="month" ? <><b>{month ? monthText(month.key) : "Month"}</b>{month && through.slice(0,7)===month.key ? " · to date" : ""}{month && since.slice(0,7)===month.key ? " · from "+dayText(since) : ""}</>
    : <><b>{dayText(day)}</b> · UTC day</>;
  const empty = period!=="day" ? "This record is awaiting an update."
    : dayView.state==="early" ? "The "+circuit+" paper record starts on "+dayText(since)+"."
    : dayView.state==="none" ? "No "+circuit+" matches with recorded odds on this date."
    : "Paper results for this date are awaiting an update.";
  const stamp = period==="day" ? (dayView.state==="ok" ? dayView.through : "") : through;
  const tab = (id:Period,label:string,off=false) =>
    <button type="button" aria-pressed={period===id} disabled={off} onClick={()=>setPeriod(id)}>{label}</button>;

  return <section className={styles.results} id="big-drop-returns" aria-labelledby="paper-return-title">
    <header className={styles.paperHead}>
      <h2 id="paper-return-title"><span className={styles.lab}>{circuit} paper record</span>All pre-match moves ≥4 pp</h2>
      <div className={styles.paperSwitch}>
        <div className={styles.period} role="group" aria-label="Period of the paper record">
          {tab("life","Lifetime",!lifetime)}{tab("month","Month",!months.length)}{tab("day","Day")}
        </div>
        {period==="month" && months.length>1 && <label className={styles.pick}><span>Month</span>
          <select value={month?.key ?? ""} onChange={e=>setMonthKey(e.target.value)}>
            {months.map(m=><option key={m.key} value={m.key}>{monthText(m.key)}</option>)}
          </select></label>}
      </div>
    </header>

    <p className={styles.paperSpan} aria-live="polite">{span}</p>
    {!slice ? <p className={styles.paperEmpty}>{empty}</p> : <>
      <Figures r={slice.all4} />
      {slice.late4 && <div className={styles.paperRef}>
        <h3>Final hour ≥4 pp <small>timing reference · overlaps with the all-day record</small></h3>
        <Figures r={slice.late4} reference />
      </div>}
    </>}
    <p className={styles.paperNote}>
      {stamp && <><b>As of {asOf(stamp)}.</b>{" "}</>}{circuit==="ATP" ? "ATP and Challenger." : "WTA and WTA 125."}
      {" "}Each paper entry uses 1u at the recorded odds, including moves at low limits.
    </p>

    <details className={styles.fold}><summary>How to read this record</summary>
      <p className={styles.fine}>≥4 pp means a rise of at least 4 percentage points in implied probability. The headline row is an independent paper record of every pre-match move that large, thin moves included, whether or not an alert was sent. Delivered Telegram alerts have their own record below.</p>
      <p className={styles.fine}>Each entry records 1u at the first qualifying odds for a match, market, line and side. A repeat drop on that same side and line adds no stake. A move on the other player, or a different handicap, can count separately, so one fixture can drive several wins or losses.</p>
      <p className={styles.fine}>The final-hour row is a reference. Both observations must fall inside the final hour, and the same move can also sit in the row above at different odds, so adding the two rows would double-count.</p>
      <p className={styles.fine}>ROI is net result over settled stake across the whole period, so it is weighted by stake and is not an average of daily figures. Pending entries carry no result yet. With no settled stake, ROI and net show a dash.</p>
      <p className={styles.fine}>On retirement or disqualification, moneyline picks settle on the official winner once one full set has been played. Before that, both sides are void. Whole-match games handicaps and totals are void on retirement. A walkover voids all three markets.</p>
      <p className={styles.fine}>The initial replay used saved scans through 21 November 2026 at 10:15 UTC. Later entries use the same rules as new scans arrive.</p>
      {period==="day" && dayView.state==="ok" && (dayView.all45 || dayView.late45) && <>
        <p className={styles.fine}>The original ≥4.5 pp rows for {dayText(day)} are kept here for comparison. They overlap the rows above and are not part of the headline record.</p>
        <div className={styles.paperScroll} role="region" aria-label="Original 4.5 point rows for this day" tabIndex={0}>
          <table className={styles.paperTable}><thead><tr>{["Move","W–L","Pending","Stake","Net","ROI"].map(s=><th scope="col" key={s}>{s}</th>)}</tr></thead>
          <tbody>{([["All pre-match ≥4.5 pp",dayView.all45],["Final hour ≥4.5 pp",dayView.late45]] as const).map(([label,r])=>r &&
            <tr key={label}><th scope="row">{label}</th><td>{r.won}–{r.lost}</td><td>{r.pending}</td><td>{plain(r.stake)}u</td>
              <td>{r.roi===null ? "—" : signed(r.net)+"u"}</td>
              <td data-positive={r.roi===null || r.net===0 ? undefined : r.net>0}>{r.roi===null ? "—" : signed(r.roi)+"%"}</td></tr>)}</tbody></table>
        </div>
      </>}
    </details>
  </section>;
}
