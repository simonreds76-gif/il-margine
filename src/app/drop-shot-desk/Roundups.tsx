"use client";

import { useId } from "react";
import type { Ref } from "react";
import styles from "./board.module.css";
import { SETTLING_NOTE, pointsText } from "./DeskParts";
import { availability, isOpen, moveKey, outcomeLabel, outcomeOf, paper, percent, price, selectionKey, tally, units, utcClock, utcDate } from "./desk";
import type { DeskMove, Roundup } from "./desk";

/**
 * Telegram roundups are delivery receipts: one per message sent. The history is folded
 * away by default; open, a single select (latest first) and a pair of steppers reach
 * every send, and each one keeps its own totals, lines and exact locked prices.
 */
export default function Roundups({ roundups, active, currentKey, now, open, onToggle, onSelect, onOpen, sectionRef }: {
  roundups: Roundup[];
  active: Roundup | null;
  currentKey: string | null;
  /** The desk's clock in ms; null while availability cannot be verified. Status only: it never changes the record or the tally. */
  now: number | null;
  /** Whether the receipt history is unfolded. The board owns it so links and jumps can open it. */
  open: boolean;
  onToggle: () => void;
  onSelect: (id: string) => void;
  onOpen: (move: DeskMove) => void;
  sectionRef?: Ref<HTMLElement>;
}) {
  const bodyId = useId();
  const sum = active ? tally(active.picks) : null;
  const stillOpen = active ? active.picks.filter(m => isOpen(m, now)).length : 0;
  // Latest first, as in the message history itself.
  const sends = [...roundups].reverse();
  const at = active ? sends.findIndex(r => r.id === active.id) : -1;
  const latest = sends.length ? sends[0] : null;
  const brief = latest
    ? sends.length + (sends.length === 1 ? " delivery receipt" : " delivery receipts") + " · latest " + utcClock(latest.at) + " UTC"
    : "None on this date";

  return <section className={styles.roundups} id="desk-roundups" ref={sectionRef} aria-labelledby="desk-roundups-title">
    <h2 className={styles.roundupsTitle}>
      <button type="button" aria-expanded={open} aria-controls={bodyId} onClick={onToggle}>
        <span id="desk-roundups-title">Telegram roundups</span>
        <small>{brief}</small>
      </button>
    </h2>

    <div className={styles.roundupsBody} id={bodyId} hidden={!open}>
      {!active || !sum
        ? <p className={styles.empty} role="status">No Telegram roundup is on record for this date.</p>
        : <>
          <p className={styles.roundupsNote}>Each roundup is the receipt of one Telegram message and is tallied on its own: 1u flat per selection at the locked price.</p>
          <div className={styles.sendBar}>
            <label className={styles.pick}><span>Sent</span>
              <select value={active.id} onChange={e => onSelect(e.target.value)}>
                {sends.map((r, i) => {
                  const t = tally(r.picks);
                  return <option key={r.id} value={r.id}>
                    {utcDate(r.at) + " · " + utcClock(r.at) + " UTC — " + t.picks + (t.picks === 1 ? " selection" : " selections") + " · " + (t.settled ? units(t.net) : t.pending ? "pending" : "no result") + (i === 0 ? " (latest)" : "")}
                  </option>;
                })}
              </select></label>
            <div className={styles.stepper} role="group" aria-label="Step through roundups">
              <button type="button" aria-label="Earlier roundup" disabled={at < 0 || at >= sends.length - 1} onClick={() => onSelect(sends[at + 1].id)}><span aria-hidden="true">‹</span></button>
              <span>Send {sends.length - at} of {sends.length}</span>
              <button type="button" aria-label="Later roundup" disabled={at <= 0} onClick={() => onSelect(sends[at - 1].id)}><span aria-hidden="true">›</span></button>
            </div>
          </div>

          <div className={styles.roundup} data-batch={active.id}>
            <div className={styles.roundupHead}>
              <h3>Roundup of {utcDate(active.at)} · {utcClock(active.at, true)} UTC</h3>
              <p>
                {active.sent !== null ? "Sent " + utcClock(active.sent, true) + " UTC" : active.confirmed ? "Delivery confirmed" : "Delivery not confirmed"}
                {active.confirmed && active.picks.every(p => p.fourPointAlert === false) && <span className={styles.ref}>Earlier pilot rules</span>}
                <span className={styles.ref}>Ref {active.id}</span>
              </p>
            </div>
            <p className={styles.avail} data-state={stillOpen ? "open" : "closed"}>
              {stillOpen
                ? <><b>{stillOpen} of {sum.picks}</b> {stillOpen === 1 ? "selection is" : "selections are"} still open pre-match. Closed selections stay listed exactly as sent.</>
                : <><b>Closed roundup</b> · {sum.picks === 1 ? "its selection is no longer" : "none of its " + sum.picks + " selections is still"} verified open pre-match. Locked prices stay exactly as sent; a result is filled in once a final score is matched.</>}
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
                <th role="columnheader" scope="col">Locked price · probability rise</th>
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
                  <td role="cell" data-label="Locked price"><b>{price(m.new)}</b> <small>from {price(m.old)} · {pointsText(m)}</small></td>
                  <td role="cell" data-label="Result"><span className={styles.pill} data-outcome={o}>{outcomeLabel(m)}</span>{m.score ? <small> {m.score}</small> : null}</td>
                  <td role="cell" data-label="Paper P/L" data-tone={pl === null || pl === 0 ? undefined : pl > 0 ? "won" : "lost"}>{pl === null ? "—" : units(pl)}</td>
                </tr>;
              })}</tbody>
            </table>
            <p className={styles.fine}>pp is the rise in implied probability from the earlier price to the locked price. ROI is paper P/L divided by settled, non-void selections; pending and void rows stay out of the denominator. Roundups are not added together, so a selection repeated in a later roundup is never counted as a second bet. {SETTLING_NOTE}</p>
          </div>
        </>}
    </div>
  </section>;
}
