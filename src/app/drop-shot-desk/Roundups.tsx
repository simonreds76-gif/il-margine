"use client";

import type { Ref } from "react";
import styles from "./board.module.css";
import { availability, isOpen, moveKey, outcomeLabel, outcomeOf, paper, percent, price, selectionKey, tally, units, utcClock, utcDate } from "./desk";
import type { DeskMove, Roundup } from "./desk";

export default function Roundups({ roundups, active, currentKey, now, onSelect, onOpen, sectionRef }: {
  roundups: Roundup[];
  active: Roundup | null;
  currentKey: string | null;
  /** The desk's clock in ms; null while availability cannot be verified. Status only: it never changes the record or the tally. */
  now: number | null;
  onSelect: (id: string) => void;
  onOpen: (move: DeskMove) => void;
  sectionRef?: Ref<HTMLElement>;
}) {
  const sum = active ? tally(active.picks) : null;
  const open = active ? active.picks.filter(m => isOpen(m, now)).length : 0;
  return <section className={styles.roundups} id="desk-roundups" ref={sectionRef} aria-labelledby="desk-roundups-title">
    <header className={styles.roundupsHead}>
      <h2 id="desk-roundups-title">Telegram roundups <small>{roundups.length}</small></h2>
      <p>Choose a roundup by its UTC time. Each one is tallied on its own: 1u flat per selection at the locked price.</p>
    </header>

    {!active || !sum
      ? <p className={styles.empty} role="status">No Telegram roundup is on record for this date.</p>
      : <>
        <div className={styles.chips} role="group" aria-label="Roundups by time (UTC)">
          {roundups.map(r => {
            const t = tally(r.picks);
            return <button key={r.id} type="button" className={styles.chip} aria-pressed={r.id === active.id} onClick={() => onSelect(r.id)}>
              <span className={styles.chipTime}>{utcClock(r.at)} <small>UTC</small></span>
              <span className={styles.chipMeta}>{t.picks} {t.picks === 1 ? "selection" : "selections"} · {t.settled ? units(t.net) : t.pending ? "pending" : "no result"}</span>
            </button>;
          })}
        </div>

        <div className={styles.roundup} data-batch={active.id}>
          <div className={styles.roundupHead}>
            <h3>Roundup of {utcDate(active.at)} · {utcClock(active.at, true)} UTC</h3>
            <p>
              {active.sent !== null ? "Sent " + utcClock(active.sent, true) + " UTC" : active.confirmed ? "Delivery confirmed" : "Delivery not confirmed"}
              <span className={styles.ref}>Ref {active.id}</span>
            </p>
          </div>
          <p className={styles.avail} data-state={open ? "open" : "closed"}>
            {open
              ? <><b>{open} of {sum.picks}</b> {open === 1 ? "selection is" : "selections are"} still open pre-match. Closed selections stay listed exactly as sent.</>
              : <><b>Closed roundup</b> · {sum.picks === 1 ? "its selection is no longer" : "none of its " + sum.picks + " selections is still"} verified open pre-match. Locked prices, results and ROI stay as recorded on the receipt.</>}
          </p>

          <dl className={styles.stats}>
            <div><dt>Selections</dt><dd>{sum.picks}</dd></div>
            <div data-tone="won"><dt>Won</dt><dd>{sum.won}</dd></div>
            <div data-tone="lost"><dt>Lost</dt><dd>{sum.lost}</dd></div>
            {sum.pushed>0 && <div><dt>Push</dt><dd>{sum.pushed}</dd></div>}
            {sum.split>0 && <div><dt>Half wins / losses</dt><dd>{sum.split}</dd></div>}
            <div><dt>Void</dt><dd>{sum.voided}</dd></div>
            <div><dt>Pending</dt><dd>{sum.pending}</dd></div>
            <div data-tone={sum.settled ? (sum.net > 0 ? "won" : sum.net < 0 ? "lost" : undefined) : undefined}><dt>Paper P/L</dt><dd>{sum.settled ? units(sum.net) : "—"}</dd></div>
            <div data-tone={sum.roi !== null ? (sum.roi > 0 ? "won" : sum.roi < 0 ? "lost" : undefined) : undefined}><dt>ROI on {sum.settled} settled</dt><dd>{sum.roi !== null ? percent(sum.roi) : "—"}</dd></div>
          </dl>

          <table className={styles.picks} role="table">
            <thead role="rowgroup"><tr role="row">
              <th role="columnheader" scope="col">Selection</th>
              <th role="columnheader" scope="col">Locked price</th>
              <th role="columnheader" scope="col">Result</th>
              <th role="columnheader" scope="col">Paper P/L</th>
            </tr></thead>
            <tbody role="rowgroup">{active.picks.map(m => {
              const o = outcomeOf(m.result);
              const pl = paper(m);
              const prior = active.firstSent[selectionKey(m)];
              const a = o === "pending" ? availability(m, now) : null;
              return <tr role="row" key={moveKey(m)} data-current={moveKey(m) === currentKey ? "true" : undefined}>
                <td role="cell" className={styles.pickWho}>
                  <button type="button" onClick={() => onOpen(m)} aria-label={"Show the " + (a && a.open ? "" : "recorded ") + "price chart for " + m.player}>{m.player}</button>
                  <span>{m.fixtureLabel ?? ("vs "+m.opponent)} · {m.league}</span>
                  {a && <span className={styles.state} data-open={a.open ? "true" : undefined}>{a.label} · {a.reason}</span>}
                  {prior !== undefined && <span className={styles.note}>Price update · first sent in the {utcClock(prior)} UTC roundup</span>}
                </td>
                <td role="cell" data-label="Locked price"><b>{price(m.new)}</b> <small>from {price(m.old)}</small></td>
                <td role="cell" data-label="Result"><span className={styles.pill} data-outcome={o}>{outcomeLabel(m)}</span>{m.score ? <small> {m.score}</small> : null}</td>
                <td role="cell" data-label="Paper P/L" data-tone={pl === null || pl === 0 ? undefined : pl > 0 ? "won" : "lost"}>{pl === null ? "—" : units(pl)}</td>
              </tr>;
            })}</tbody>
          </table>
          <p className={styles.fine}>ROI is paper P/L divided by settled, non-void selections; pending and void rows stay out of the denominator. Roundups are not added together, so a selection repeated in a later roundup is never counted as a second bet.</p>
        </div>
      </>}
  </section>;
}
