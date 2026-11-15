'use client';
import { Fragment, useState } from 'react';
import { reconciles, editionCompletionLabel } from '@/lib/tennis-tournament-returns.mjs';
import s from './tournament-returns.module.css';

/* Descriptive tournament history: what a flat 1u on every favourite, or every
   underdog, returned at earlier editions. Presentation only. This component
   never computes a return; it shows the figures it is given, and withholds
   them if the supplied totals do not reconcile. */

// ---------- data contract (the generator should emit exactly this) ----------

/** One hypothetical flat-stake strategy over the bettable fixtures. `roi` is a percentage, null when stake is 0. */
export type SideReturn = { wins: number; losses: number; stake: number; profit: number; roi: number | null };

/** completed = paired + unpriced; paired = pickems + bettable. `notCompleted` (retirements, walkovers, unfinished) sits outside `completed`. */
export type ReturnCounts = { completed: number; paired: number; unpriced: number; pickems: number; bettable: number; notCompleted: number };

/** Exact recorded price-basis classes, e.g. "Last recorded pre-match". Never "closing". */
export type PriceMixItem = { label: string; count: number };

/** Intrinsic status of an edition. Whether an eligible edition is pooled depends on the window. */
export type EditionStatus = 'eligible' | 'current' | 'opening-basis' | 'low-coverage' | 'other-regime' | 'no-data';

export type EditionRow = {
  editionId: string; year: number; fromDate: string | null; throughDate: string | null;
  completion: {state: 'completed' | 'unverified'; completedAt: string | null};
  status: EditionStatus; excludedReason?: string | null;
  counts: ReturnCounts; priceMix: PriceMixItem[];
  favourite: SideReturn | null; underdog: SideReturn | null;
};

/** Fixed bands on the favourite's price. `max` null means open-ended. ROI is shown only from 30 fixtures. */
export type BandRow = { label: string; min: number; max: number | null; fixtures: number; favourite: SideReturn | null; underdog: SideReturn | null };

export type ReturnWindow = {
  requested: 3 | 5;
  /** Editions actually pooled: earlier than the snapshot year, same regime, same price class, coverage >= 80%. */
  editionIds: string[]; years: number[];
  counts: ReturnCounts; priceMix: PriceMixItem[];
  favourite: SideReturn | null; underdog: SideReturn | null;
  bands?: BandRow[] | null;
};

export type TournamentReturnsSummary =
  | { availability: 'available'; family: string; name: string; tour: string; surface: string; city: string | null;
      /** Regime and format notes, e.g. a venue move or a round-robin stage. */
      notes: string[];
      snapshotYear: number; coverageUpdatedAt: string;
      windows: { three: ReturnWindow; five: ReturnWindow | null };
      /** Every recorded edition of this regime and its neighbours, newest first. */
      editions: EditionRow[] }
  | { availability: 'unavailable'; name: string; reason: string };

// ---------- formatting ----------

const BAND_MINIMUM = 30;
const units = (n: number) => { const rounded = Math.round((Math.abs(n) + Number.EPSILON) * 100) / 100; return `${rounded ? n < 0 ? '−' : '+' : ''}${rounded.toFixed(2)}u`; };
const percent = (n: number | null) => n === null || !Number.isFinite(n) ? '—' : `${n < 0 ? '−' : n > 0 ? '+' : ''}${Math.abs(n).toFixed(1)}%`;
const isDay = (d: unknown): d is string => typeof d === 'string' && /^\d{4}-\d{2}-\d{2}/.test(d);
const day = (d: string) => new Intl.DateTimeFormat('en-GB', { timeZone: 'UTC', day: 'numeric', month: 'short', year: 'numeric' }).format(new Date(`${d.slice(0, 10)}T12:00:00Z`));
const span = (years: number[]) => {
  const sorted = [...years].sort((a, b) => a - b);
  if (!sorted.length) return '';
  const contiguous = sorted.every((y, i) => i === 0 || y === sorted[i - 1] + 1);
  return sorted.length > 2 && contiguous ? `${sorted[0]}–${sorted[sorted.length - 1]}` : sorted.join(', ');
};
const coverage = (c: ReturnCounts) => c.completed > 0 ? `${Math.round(100 * c.paired / c.completed)}%` : '—';

// The contract's identities. If any fails, figures are withheld rather than shown wrong.
// ---------- pieces ----------

function Figure({ side }: { side: SideReturn | null }) {
  if (!side || side.stake <= 0) return <span className={s.none}>—<span className="sr-only">Not available</span></span>;
  return <><span className={side.profit > 0 ? s.pos : undefined}>{units(side.profit)}</span><small>{percent(side.roi)}</small></>;
}

function Tile({ label, hint, side }: { label: string; hint: string; side: SideReturn | null }) {
  const has = !!side && side.stake > 0;
  return <div className={s.tile}>
    <span className={s.tileLabel}>{label}<small>{hint}</small></span>
    {has ? <>
      <strong className={side!.profit > 0 ? s.pos : undefined}>{units(side!.profit)}</strong>
      <span className={s.tileSub}>{percent(side!.roi)} ROI · {side!.wins} won · {side!.losses} lost · {side!.stake}u staked</span>
    </> : <strong className={s.none}>—<span className="sr-only">Not available</span></strong>}
  </div>;
}

function editionNote(row: EditionRow, pooled: boolean, snapshotYear: number) {
  if (pooled) return null;
  const currentYear = row.year === snapshotYear;
  const reason = row.status === 'opening-basis' ? 'Opening prices'
    : row.status === 'low-coverage' ? (row.excludedReason || 'Under 80% of matches priced')
    : row.status === 'other-regime' ? (row.excludedReason?.split(',')[0] || 'Different venue or surface')
    : row.status === 'no-data' ? (row.excludedReason || 'No recorded matches')
    : row.status === 'eligible' ? 'Not in this window' : null;
  const date = !currentYear ? null : row.completion.state === 'completed' && isDay(row.completion.completedAt)
    ? `Completed ${day(row.completion.completedAt)}`
    : `Completion unverified${isDay(row.throughDate) ? `; matches recorded through ${day(row.throughDate)}` : ''}`;
  return [date, reason, row.status !== 'eligible' ? 'not pooled' : null].filter(Boolean).join(' · ');
}

// ---------- component ----------

export default function TournamentReturns({ summary, defaultOpen = false }: { summary: TournamentReturnsSummary; defaultOpen?: boolean }) {
  const [size, setSize] = useState<3 | 5>(3);
  const chevron = <svg className={s.chev} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d="m6 9 6 6 6-6" /></svg>;
  const mark = <svg className={s.mark} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" aria-hidden="true"><path d="M4 19h16M6 15V9m6 6V5m6 10v-7" /></svg>;

  if (summary.availability === 'unavailable') return <details className={s.root} open={defaultOpen || undefined}>
    <summary className={s.bar}>{mark}<span className={s.barTitle}>Tournament history</span><span className={s.barMeta}>Not available for this event</span>{chevron}</summary>
    <div className={s.body}><p className={s.note}>{summary.reason}</p></div>
  </details>;

  const three = summary.windows.three, five = summary.windows.five;
  const win = size === 5 && five ? five : three;
  const pooled = new Set(win.editionIds);
  const ok = reconciles(win.counts, win.favourite, win.underdog);
  const limited = win.editionIds.length < 3 || win.counts.bettable < 100;

  return <details className={s.root} open={defaultOpen || undefined}>
    {/* Closed state: what the history is, never a percentage. */}
    <summary className={s.bar}>{mark}<span className={s.barTitle}>Tournament history</span>
      <span className={s.barMeta}>{win.editionIds.length
        ? `${win.editionIds.length} earlier ${win.editionIds.length === 1 ? 'edition' : 'editions'} · ${span(win.years)} · ${win.counts.bettable} matches`
        : 'No comparable earlier edition yet'}</span>{chevron}</summary>

    <div className={s.body}>
      <div className={s.head}>
        <h4>{summary.name}: backing every favourite, or every underdog</h4>
        <div className={s.switch} role="group" aria-label="Editions pooled">
          <button type="button" aria-pressed={win === three} onClick={() => setSize(3)}>3 editions</button>
          {five && <button type="button" aria-pressed={win === five} onClick={() => setSize(5)}>5 editions</button>}
        </div>
      </div>
      <p className={s.scope}>
        {win.editionIds.length
          ? <><b>{span(win.years)}</b>{win.editionIds.length < win.requested ? ` · ${win.editionIds.length} of ${win.requested} requested editions qualify` : ''}</>
          : <b>No earlier edition qualifies for pooling</b>}
        {' · '}{summary.tour} main draw{summary.city ? ` · ${summary.city}` : ''} · 1u on each eligible match
        {limited && win.editionIds.length > 0 && <span className={s.tag}>Small historical sample</span>}
      </p>

      {!ok ? <p className={s.withheld}>Figures withheld: the recorded totals for this window do not reconcile. Nothing is shown rather than something wrong.</p> : win.editionIds.length > 0 && <>
        <div className={s.tiles}>
          <Tile label="Every favourite" hint="shorter of the two prices" side={win.favourite} />
          <Tile label="Every underdog" hint="longer of the two prices" side={win.underdog} />
        </div>
        <p className={s.counts}>
          <b>{win.counts.bettable} matches</b> in both figures: the same matches, seen from each side.
          {' '}{win.counts.paired} of {win.counts.completed} recorded completed matches have paired prices ({coverage(win.counts)}).
          {win.counts.unpriced > 0 && ` ${win.counts.unpriced} without paired prices.`}
          {win.counts.pickems > 0 && ` ${win.counts.pickems} at equal prices, left out of both.`}
          {win.counts.notCompleted > 0 && ` ${win.counts.notCompleted} retirements, walkovers or unfinished matches are not counted.`}
        </p>
        {win.priceMix.length > 0 && <p className={s.counts}>Pinnacle price basis: {win.priceMix.map(m => `${m.label} ${m.count}`).join(' · ')}.</p>}
      </>}

      <table className={s.table}>
        <caption>By edition. Profit (u) and ROI; compare the variation between years. Matches exclude equal-price pairs.</caption>
        <thead><tr><th scope="col">Edition</th><th scope="col">Matches</th><th scope="col"><span className={s.full}>Favourites</span><span className={s.short} aria-hidden="true">Favs</span></th><th scope="col"><span className={s.full}>Underdogs</span><span className={s.short} aria-hidden="true">Dogs</span></th></tr></thead>
        <tbody>{summary.editions.map(row => {
          const inPool = pooled.has(row.editionId);
          const note = editionNote(row, inPool, summary.snapshotYear);
          const rowOk = reconciles(row.counts, row.favourite, row.underdog);
          return <Fragment key={row.editionId}><tr data-pooled={inPool}>
            <th scope="row">{row.year}{row.year === summary.snapshotYear && <small>{editionCompletionLabel(row.completion)}</small>}{note && <span className="sr-only">. {note}</span>}</th>
            <td>{row.counts.bettable}<small>{row.counts.paired}/{row.counts.completed} priced</small></td>
            {rowOk ? <><td><Figure side={row.favourite} /></td><td><Figure side={row.underdog} /></td></>
              : <td colSpan={2}><small>Totals do not reconcile; withheld</small></td>}
          </tr>{note && <tr className={s.noteRow} aria-hidden="true"><td colSpan={4}>{note}</td></tr>}</Fragment>;
        })}</tbody>
      </table>

      {ok && !!win.bands?.length && <table className={s.table}>
        <caption>By the favourite’s price. Each match sits in one row. Returns appear only from {BAND_MINIMUM} matches.</caption>
        <thead><tr><th scope="col"><span className={s.full}>Favourite’s price</span><span className={s.short} aria-hidden="true">Fav price</span></th><th scope="col">Matches</th><th scope="col"><span className={s.full}>Favourites</span><span className={s.short} aria-hidden="true">Favs</span></th><th scope="col"><span className={s.full}>Underdogs</span><span className={s.short} aria-hidden="true">Dogs</span></th></tr></thead>
        <tbody>{win.bands.map(band => <tr key={band.label} data-pooled="true">
          <th scope="row">{band.label}</th><td>{band.fixtures}</td>
          {band.fixtures >= BAND_MINIMUM ? <><td><Figure side={band.favourite} /></td><td><Figure side={band.underdog} /></td></>
            : <td colSpan={2}><small>Too few matches</small></td>}
        </tr>)}</tbody>
      </table>}

      {summary.notes.length > 0 && <ul className={s.notes}>{summary.notes.map(note => <li key={note}>{note}</li>)}</ul>}
      <p className={s.foot}>
        What happened at earlier editions, not a forecast and not a reason to back either player today. The favourite is the player with the shorter of the two recorded Pinnacle prices in that match; the underdog has the longer. Figures are in units (u) at a flat 1u per match; ROI is profit divided by stake. Coverage is of the completed matches recorded in our archive, not proof of the full official draw. Recorded prices are not guaranteed to be the final price before play, and were not necessarily available to you.
        {isDay(summary.coverageUpdatedAt) && ` Archive checked ${day(summary.coverageUpdatedAt)}.`}
      </p>
    </div>
  </details>;
}

/** Preview aid only: look at an out-of-season tournament without adding anything to the match list. */
export function TournamentReturnsPicker({ summaries }: { summaries: TournamentReturnsSummary[] }) {
  const [index, setIndex] = useState(0);
  if (!summaries.length) return null;
  const chosen = summaries[Math.min(index, summaries.length - 1)];
  return <section className={s.picker} aria-label="Preview tournament history" id="tournament-history-preview">
    <label>Preview: tournament history<select value={index} onChange={e => setIndex(Number(e.target.value))}>
      {summaries.map((item, i) => <option key={`${item.name}:${i}`} value={i}>{item.name}</option>)}</select></label>
    <div className={s.pickerFrame}><TournamentReturns key={index} summary={chosen} defaultOpen /></div>
  </section>;
}
