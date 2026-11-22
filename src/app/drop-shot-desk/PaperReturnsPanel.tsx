"use client";

import { useState, type KeyboardEvent } from "react";
import { useSearchParams } from "next/navigation";
import type { ClosingSummary } from "./closing";
import RollingRecord from "./RollingRecord";
import css from "./paper-record.module.css";

export type Result = {
  entries:number; fixtures:number; won:number; lost:number; halfWon:number; halfLost:number;
  pushes:number; voids:number; pending:number; stake:number; net:number; roi:number|null; clv?:ClosingSummary|null;
};
/** One period of the record: every pre-match move ≥4 pp, and the final-hour subset kept as a reference. */
export type PaperSlice = { all4:Result; late4:Result|null };
/** The selected board date. "early" is a date before this tour's record began. */
export type PaperDay =
  | { state:"ok"; through:string; all4:Result; late4:Result|null; all45:Result|null; late45:Result|null }
  | { state:"early"|"awaiting"|"none" };
type Period = "life"|"rolling"|"month"|"day";

const MONTHS = ["January","February","March","April","May","June","July","August","September","October","November","December"];
// Figures are printed as supplied, to two places. Only the glyphs change: a true minus, and no sign on a zero.
const isZero = (v:number) => Number(Math.abs(v).toFixed(2))===0;
const signed = (v:number) => (isZero(v) ? "" : v>0 ? "+" : "−") + Math.abs(v).toFixed(2);
const plain = (v:number) => String(Math.round(v*100)/100);
const count = (v:number,one:string,many=one+"s") => v + " " + (v===1 ? one : many);
const tone = (v:number|null) => (v===null || isZero(v) ? undefined : v>0 ? "won" : "lost");
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

/** Bar and legend order: wins from the left, losses from the right, everything undecided or returned between. */
const KINDS = [["won","Won"],["halfWon","Half-won"],["pushes","Pushes"],["voids","Voids"],["pending","Pending"],["halfLost","Half-lost"],["lost","Lost"]] as const;

const Dash = () => <><span aria-hidden="true">—</span><span className={css.vh}>not available</span></>;
const UnitSpace = () => <span className={`${css.unit} ${css.unitSpacer}`} aria-hidden="true" />;

/** The scoreline. Net and ROI are the supplied figures; without settled stake there is no return to state, so both show a dash. */
function Score({r}:{r:Result}) {
  const settled = r.roi!==null;
  return <dl className={css.score}>
    <div data-tone={settled ? tone(r.net) : undefined}>
      <dt>Net paper P/L</dt>
      <dd className={css.fig}>{settled ? <>{signed(r.net)}<span className={css.unit}>u</span></> : <><Dash /><UnitSpace /></>}</dd>
      <dd className={css.sub}><b>{plain(r.stake)}u</b> settled · 1u per entry</dd>
    </div>
    <div data-tone={tone(r.roi)}>
      <dt>Settled ROI</dt>
      <dd className={css.fig}>{settled ? <>{signed(r.roi as number)}<span className={css.unit}>%</span></> : <><Dash /><UnitSpace /></>}</dd>
      <dd className={css.sub}>{settled ? "Net ÷ settled stake" : "Nothing settled yet"}</dd>
    </div>
    <div data-tone={tone(r.clv?.mean ?? null)}>
      <dt><abbr title="Closing line value">CLV</abbr></dt>
      <dd className={css.fig}>{r.clv?.mean!=null ? <>{signed(r.clv.mean)}<span className={css.unit}>%</span></> : <Dash/>}</dd>
      <dd className={css.sub}>{r.clv ? <><b>{r.clv.measured} of {r.entries}</b> measured</> : "Coverage unavailable"}</dd>
    </div>
    <div>
      <dt>Won–lost</dt>
      <dd className={css.fig}><span aria-hidden="true">{r.won}–{r.lost}</span><UnitSpace /><span className={css.vh}>{r.won} won, {r.lost} lost</span></dd>
      <dd className={css.sub}><b>{count(r.entries,"entry","entries")}</b> · {r.pending ? r.pending+" pending" : "none pending"}</dd>
    </div>
  </dl>;
}

/** Every entry by result: one bar in proportion to the real counts, and a legend that states each count exactly. */
function Breakdown({r}:{r:Result}) {
  const any = KINDS.some(([k])=>r[k]>0);
  return <div className={css.split}>
    <h3>Every entry by result{r.fixtures>0 && <span> · across {count(r.fixtures,"fixture")}</span>}</h3>
    <div className={css.bar} aria-hidden="true" data-empty={any ? undefined : ""}>
      {KINDS.map(([k])=>r[k]>0 && <span key={k} data-kind={k} style={{flexGrow:r[k]}} />)}
    </div>
    <dl className={css.key}>
      {KINDS.map(([k,label])=><div key={k} data-kind={k} data-zero={r[k] ? undefined : ""}><dt>{label}</dt><dd>{r[k]}</dd></div>)}
    </dl>
  </div>;
}

/** A reference line, small: for the final-hour subset and the archived ≥4.5 pp rows. */
function RefRow({label,r}:{label:string;r:Result}) {
  const settled = r.roi!==null;
  const extra = [r.halfWon>0 && r.halfWon+" half-won", r.halfLost>0 && r.halfLost+" half-lost",
    r.pushes>0 && count(r.pushes,"push","pushes"), r.voids>0 && count(r.voids,"void")].filter(Boolean).join(", ");
  return <div className={css.ref}>
    <h3>{label}</h3>
    <dl>
      <div data-tone={settled ? tone(r.net) : undefined}><dt>Net</dt><dd>{settled ? signed(r.net)+"u" : <Dash />}</dd></div>
      <div data-tone={tone(r.roi)}><dt>ROI<span className={css.vh}> on settled stake</span></dt><dd>{settled ? signed(r.roi as number)+"%" : <Dash />}</dd></div>
      <div><dt>W–L</dt><dd>{r.won}–{r.lost}</dd></div>
      <div><dt>Pending</dt><dd>{r.pending}</dd></div>
      <div><dt>Stake</dt><dd>{plain(r.stake)}u</dd></div>
    </dl>
    {extra && <p>Also {extra}.</p>}
  </div>;
}

const RULES:[string,string][] = [
  ["≥4 pp", "A rise of at least 4 percentage points in implied probability, seen before the match starts."],
  ["Independent record", "New paper entries require a reported limit of at least $200 on the same selection and line at detection. In the 30-day view, choose Sent on Telegram to see confirmed alerts at their sent odds."],
  ["One entry, 1u", "Each entry records 1u at the first qualifying odds for a match, market, line and side. A repeat drop on that same side and line adds no stake. A move on the other player, or a different handicap, can count separately, so one fixture can drive several wins or losses."],
  ["Net and ROI", "ROI is net result over settled stake across the whole period, so it is weighted by stake and is not an average of daily figures. Pending entries carry no result yet. With no settled stake, net and ROI show a dash."],
  ["Closing line value (CLV)", "We compare the entry odds with the last recorded odds on the same selection and line before the verified start. Positive CLV means the entry got better odds. The figure is the average percentage price advantage across entries with a later reading. Open the 30-day selections for odds and minutes before play."],
  ["Final hour", "A timing reference. Both observations must fall inside the final hour, and the same move can also sit in the main record at different odds, so adding the two would double-count."],
  ["Retirements", "On retirement or disqualification, moneyline picks settle on the official winner once one full set has been played. Before that, both sides are void. Whole-match games handicaps and totals are void on retirement. A walkover voids all three markets."],
  ["Source", "The record was first compiled from saved scans up to 21 November 2026 at 10:15 UTC. The $200 minimum started on 22 November 2026. Earlier entries count under the rules in force when recorded."],
  ["Historical replay", "The fixed historical replay (22 October to 18 November 2026, last qualifying move 16 November) is a separate product and is not part of this record."],
];

export function PaperReturnsPanel({circuit,day,since,through,lifetime,months,dayView}:{
  circuit:string; day:string; since:string; through:string;
  lifetime:PaperSlice|null; months:{key:string;slice:PaperSlice}[]; dayView:PaperDay;
}) {
  const [localPeriod,setLocalPeriod] = useState<Period>("rolling");
  const record = useSearchParams().get("record");
  const period = record==="30d" || record==="sent30" ? "rolling" : localPeriod;
  function changeRecord(value:string|null) {
    const url=new URL(window.location.href);
    if(value)url.searchParams.set("record",value);
    else url.searchParams.delete("record");
    window.history.replaceState(null,"",url.href);
  }
  function setPeriod(next:Period) {
    if(next==="rolling") changeRecord(record==="30d" ? "30d" : "sent30");
    else {setLocalPeriod(next);changeRecord(null);}
  }
  const [monthKey,setMonthKey] = useState(() => (months.find(m=>m.key===day.slice(0,7)) ?? months[0])?.key ?? "");
  const month = months.find(m=>m.key===monthKey) ?? months[0];
  const slice:PaperSlice|null = period==="life" ? lifetime : period==="month" ? month?.slice ?? null : dayView.state==="ok" ? dayView : null;

  const name = period==="life" ? "Lifetime" : period==="month" ? (month ? monthText(month.key) : "Month") : dayText(day);
  const range = period==="life" ? (since ? "since "+dayText(since) : "")
    : period==="month" ? [month && through.slice(0,7)===month.key ? "to date" : "", month && since.slice(0,7)===month.key ? "from "+dayText(since) : ""].filter(Boolean).join(" · ")
    : "UTC day";
  const empty = period!=="day" ? "This record is awaiting an update."
    : dayView.state==="early" ? "The "+circuit+" paper record starts on "+dayText(since)+"."
    : dayView.state==="none" ? "No "+circuit+" matches with recorded odds on this date."
    : "Paper results for this date are awaiting an update.";
  const stamp = period==="day" ? (dayView.state==="ok" ? dayView.through : "") : through;
  // The original ≥4.5 pp rows are archived per day and shown for comparison only.
  const archived:[string,Result][] = [];
  if (period==="day" && dayView.state==="ok") {
    if (dayView.all45) archived.push(["All pre-match ≥4.5 pp",dayView.all45]);
    if (dayView.late45) archived.push(["Final hour ≥4.5 pp",dayView.late45]);
  }

  const tab = (id:Period,label:string,off=false) =>
    <button type="button" aria-pressed={period===id} disabled={off} onClick={()=>setPeriod(id)}>{label}</button>;
  // Left and right arrows walk the available periods; Enter or Space selects, as on any button.
  const arrows = (e:KeyboardEvent<HTMLDivElement>) => {
    const step = e.key==="ArrowRight" ? 1 : e.key==="ArrowLeft" ? -1 : 0;
    if (!step) return;
    const on = Array.from(e.currentTarget.querySelectorAll<HTMLButtonElement>("button:not(:disabled)"));
    const at = on.indexOf(e.target as HTMLButtonElement);
    if (at<0 || on.length<2) return;
    e.preventDefault();
    on[(at+step+on.length)%on.length]?.focus();
  };

  return <section className={css.card} id="big-drop-returns" aria-labelledby="paper-return-title">
    <header className={css.head}>
      <div className={css.title}>
        <h2 id="paper-return-title">{circuit} paper record</h2>
        <p>{circuit==="ATP" ? "ATP and Challenger" : "WTA and WTA 125"} · {period==="rolling" && record!=="30d" ? "Telegram alerts, last 30 days" : "qualifying pre-match moves ≥4 pp"}</p>
      </div>
      <div className={css.controls}>
        <div className={css.seg} role="group" aria-label="Period of the paper record" onKeyDown={arrows}>
          {tab("rolling","30 days")}{tab("life","Lifetime",!lifetime)}{tab("month","Month",!months.length)}{tab("day","Day")}
        </div>
        {period==="month" && months.length>1 && <label className={css.pick}><span>Month</span>
          <select value={month?.key ?? ""} onChange={e=>setMonthKey(e.target.value)}>
            {months.map(m=><option key={m.key} value={m.key}>{monthText(m.key)}</option>)}
          </select></label>}
      </div>
    </header>

    {period==="rolling" ? <RollingRecord key={circuit} circuit={circuit} sent={record!=="30d"}
      onScope={v=>changeRecord(v?"sent30":"30d")} metrics={r=><><Score r={r}/><Breakdown r={r}/></>} /> : <>
    <div className={css.when}>
      <p className={css.span} aria-live="polite"><b>{name}</b>{range && " · "+range}</p>
      {stamp && <p className={css.stamp}>Data as of <b>{asOf(stamp)}</b></p>}
    </div>

    {!slice ? <p className={css.empty}>{empty}</p> : <>
      <Score r={slice.all4} />
      <Breakdown r={slice.all4} />
    </>}

    <p className={css.note}>
      Each paper entry stakes 1u at the recorded odds. New entries require a $200 limit or higher. Earlier entries remain in the totals. Dates are UTC.
    </p>

    </>}
    <div className={css.folds}>
      {period!=="rolling" && slice?.late4 && <details className={css.fold}>
        <summary><span>Final hour ≥4&nbsp;pp<small>timing reference</small></span></summary>
        <div className={css.foldBody}>
          <RefRow label={"Final hour ≥4 pp · "+name} r={slice.late4} />
          <p className={css.fine}>These moves overlap the record above, sometimes at different odds. Read the two side by side and never add them.</p>
        </div>
      </details>}
      {archived.length>0 && <details className={css.fold}>
        <summary><span>Original ≥4.5 pp rows<small>{dayText(day)}, for comparison</small></span></summary>
        <div className={css.foldBody}>
          <p className={css.fine}>The original ≥4.5 pp rows for {dayText(day)} are kept here for comparison. They overlap the record above and are not part of it.</p>
          {archived.map(([label,r])=><RefRow key={label} label={label} r={r} />)}
        </div>
      </details>}
      <details className={css.fold}>
        <summary><span>How this record works</span></summary>
        <div className={css.foldBody}>
          <dl className={css.rules}>{RULES.map(([term,text])=><div key={term}><dt>{term}</dt><dd>{text}</dd></div>)}</dl>
        </div>
      </details>
    </div>
  </section>;
}
