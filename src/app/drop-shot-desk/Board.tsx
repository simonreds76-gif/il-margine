"use client";

import { useCallback, useEffect, useId, useMemo, useRef, useState } from "react";
import type { KeyboardEvent } from "react";
import { useRouter } from "next/navigation";
import styles from "./board.module.css";
import OddsChart, { KeyGlyph, spanText } from "./OddsChart";
import Roundups from "./Roundups";
import { SETTLING_NOTE, State, VenueFlag, hostOf as placeOf, impliedText, marketName, pointsText, venueKey } from "./DeskParts";
import type { VenueMap } from "./DeskParts";
import {
  availability, buildRoundups, cutoffOf, defaultRoundup, delta, dropPct, isOpen, isQualifying, moveKey, outcomeLabel, outcomeOf, paper,
  groupDrops, matchKey, orderDrops, percent, price, tally, units, utcClock, utcDate, utcStamp,
} from "./desk";
import type { DeskFixture, DeskMove, DropOrder } from "./desk";

const TOURS = ["All tours", "ATP", "Challenger"];
const DRAWS = ["All rounds", "Main draw", "Qualifying"];
type Scope = "upcoming" | "all";
/** The three orders, in the words used on the control and in the line that explains the list. */
const SORTS: { value: DropOrder; label: string; note: string }[] = [
  { value: "largest", label: "Largest", note: "largest rise first" },
  { value: "newest", label: "Newest", note: "latest detection first" },
  { value: "oldest", label: "Oldest", note: "earliest detection first" },
];
const NO_VENUES: VenueMap = {};
const ROUNDUPS_HASH = "#desk-roundups";
/** Records are re-read at most this often, and only while the page is visible. */
const REFRESH_MS = 15 * 60_000;
/** Longest the local clock sleeps between checks; it wakes exactly on the next cutoff anyway. */
const TICK_MS = 60_000;

/** "ATP Challenger Helsinki - R1" reads as "Helsinki": the tour is already said beside it. */

const roundOf = (league: string) => { const parts = league.split(" - "); return parts.length > 1 ? parts[parts.length - 1].trim() : ""; };

/** Tiny time-true trace of the recorded prices; breaks in capture stay open. */
function Spark({ move }: { move: DeskMove }) {
  const w = 104, h = 20, pad = 3;
  const pts = move.quotes
    .map(q => ({ t: Date.parse(q.time), p: q.price, gap: q.gap === true }))
    .filter(q => Number.isFinite(q.t) && Number.isFinite(q.p));
  if (!pts.length) return null;
  const t0 = pts[0].t, t1 = pts[pts.length - 1].t;
  let lo = Infinity, hi = -Infinity;
  for (const q of pts) { if (q.p < lo) lo = q.p; if (q.p > hi) hi = q.p; }
  const x = (t: number) => (t1 > t0 ? pad + ((t - t0) / (t1 - t0)) * (w - 2 * pad) : w / 2);
  const y = (p: number) => (hi > lo ? pad + ((hi - p) / (hi - lo)) * (h - 2 * pad) : h / 2);
  const d = pts.map((q, i) => (i === 0 || q.gap ? "M" : "L") + x(q.t).toFixed(1) + " " + y(q.p).toFixed(1)).join(" ");
  const ta = Date.parse(move.after);
  const hit = pts.find(q => q.t === ta);
  return <svg className={styles.spark} width={w} height={h} viewBox={`0 0 ${w} ${h}`} aria-hidden="true" focusable="false">
    <path d={d} fill="none" stroke="#b7c6d0" strokeOpacity="0.75" strokeWidth="1.4" strokeLinejoin="round" strokeLinecap="round" />
    {pts.length === 1 && <circle cx={x(pts[0].t)} cy={y(pts[0].p)} r="2" fill="#b7c6d0" />}
    {hit && <circle cx={x(hit.t)} cy={y(hit.p)} r="2.8" fill="#8ce5bd" />}
  </svg>;
}

function DropRow({ move: r, selected, archive, at, venue, onChoose }: {
  move: DeskMove; selected: boolean; archive: boolean; at: number | null;
  venue?: VenueMap[string]; onChoose: (move: DeskMove) => void;
}) {
  const settled = archive ? paper(r) : null;
  const tag = archive && !r.market ? "" : marketName(r);
  return (
    <button type="button" className={styles.item} data-drop="" aria-pressed={selected} onClick={() => onChoose(r)}>
      <strong className={styles.itemName}>{r.player}</strong>
      <span className={styles.itemVs}>{r.fixtureLabel ?? ("vs "+r.opponent)}</span>
      <span className={styles.itemMeta}>
        <VenueFlag venue={venue} />
        <span>{[r.tour + (isQualifying(r) ? " qual." : ""), placeOf(r.league), archive ? utcDate(r.start) : ""].filter(Boolean).join(" · ")}</span>
      </span>
      <b className={styles.itemGain}>{pointsText(r)}<span className={styles.vh}> implied probability</span></b>
      <span className={styles.itemOdds}><span>{price(r.old)} → </span>{price(r.new)}</span>
      <span className={styles.itemWhen}>{tag ? tag + " · " : ""}detected <time dateTime={r.after}>{archive ? utcStamp(r.after, true) : utcClock(r.after, true) + " UTC"}</time></span>
      <span className={styles.itemState}>
        <State move={r} now={at} archive={archive} />
        {settled !== null && <small data-tone={settled > 0 ? "won" : settled < 0 ? "lost" : undefined}>{units(settled)}</small>}
      </span>
      <Spark move={r} />
    </button>
  );
}

export default function Board({ moves, fixtures, archive, initialBatchId, day, now, today, venues = NO_VENUES }: {
  moves: DeskMove[];
  fixtures: DeskFixture[];
  archive: boolean;
  initialBatchId?: string;
  day?: string;
  /** Server render time in ms. The first paint uses it, so server and browser agree on what is still open. */
  now?: number;
  /** True when `day` is the current UTC date. */
  today?: boolean;
  /** Host-country flags resolved on the server from the shared tournament registry; unknown venues are simply absent. */
  venues?: VenueMap;
}) {
  const router = useRouter();
  const listId = useId();
  const headId = useId();
  const sortId = useId();
  const noteId = useId();
  const resultsId = useId();
  // Roundups are built from every recorded move, whatever the list is showing.
  const roundups = useMemo(() => (archive ? [] : buildRoundups(moves)), [moves, archive]);
  // Today opens on what is still open; past dates and direct roundup links open on the full record.
  const defaultScope: Scope = today && !initialBatchId ? "upcoming" : "all";
  const [scope, setScope] = useState<Scope>(defaultScope);
  // One order per scope: Upcoming keeps its own choice, All recorded keeps its own.
  const [orders, setOrders] = useState<Record<Scope, DropOrder>>({ upcoming: "largest", all: "largest" });
  const [scopeDay, setScopeDay] = useState(day);
  const [clock, setClock] = useState<number | null>(now ?? null);
  const [lapsedKey, setLapsedKey] = useState<string | null>(null);
  if (scopeDay !== day) { setScopeDay(day); setScope(defaultScope); setLapsedKey(null); }
  const [tour, setTour] = useState(TOURS[0]);
  const [market,setMarket] = useState("all");
  const [draw, setDraw] = useState(DRAWS[0]);
  const [alertedOnly, setAlertedOnly] = useState(false);
  const [expandedGroups, setExpandedGroups] = useState<Record<string, boolean>>({});
  const [query, setQuery] = useState("");
  const [pickerOpen, setPickerOpen] = useState(false);
  const [pickedBatch, setPickedBatch] = useState<string | undefined>(initialBatchId);
  // The receipt history is folded away for normal browsing; a direct ?batch= link arrives with it open.
  const [roundupsOpen, setRoundupsOpen] = useState(!!initialBatchId);
  const [selectedKey, setSelectedKey] = useState<string | null>(() => {
    const linked = initialBatchId ? roundups.find(r => r.id === initialBatchId) : undefined;
    return linked && linked.picks.length ? moveKey(linked.picks[0]) : null;
  });
  const listRef = useRef<HTMLOListElement>(null);
  const stageRef = useRef<HTMLElement>(null);
  const roundupsRef = useRef<HTMLElement>(null);
  const revealed = useRef(false);

  useEffect(() => { setPickedBatch(initialBatchId); if (initialBatchId) setRoundupsOpen(true); }, [initialBatchId]);

  // A direct ?batch= link lands on that roundup.
  useEffect(() => {
    if (revealed.current || !initialBatchId || !roundups.some(r => r.id === initialBatchId)) return;
    revealed.current = true;
    roundupsRef.current?.scrollIntoView({ block: "start" });
  }, [initialBatchId, roundups]);

  // The plain #desk-roundups anchor, on arrival or later, opens the history and reveals it.
  useEffect(() => {
    if (archive) return;
    const sync = () => {
      if (window.location.hash !== ROUNDUPS_HASH) return;
      setRoundupsOpen(true);
      window.requestAnimationFrame(() => roundupsRef.current?.scrollIntoView({ block: "start" }));
    };
    sync();
    window.addEventListener("hashchange", sync);
    return () => window.removeEventListener("hashchange", sync);
  }, [archive]);

  // The desk's "now": never earlier than the latest server stamp, and unknown (nothing open) without one.
  const at = archive || clock === null ? null : Math.max(clock, now ?? 0);
  const upcomingOnly = !archive && scope === "upcoming";

  const needle = query.trim().toLowerCase();
  const passes = useCallback((r: DeskMove) =>
    (archive || !alertedOnly || r.notified)
    && (tour === TOURS[0] || r.tour === tour)
    && (market==="all" || (r.market??"winner")===market)
    && (draw === DRAWS[0] || isQualifying(r) === (draw === "Qualifying"))
    && (!needle || (r.player + " " + r.opponent + " " + (r.fixtureLabel??"") + " " + r.league).toLowerCase().includes(needle)), [tour, draw, needle, market, alertedOnly, archive]);
  const matching = useMemo(() => moves.filter(passes), [moves, passes]);
  const upcoming = useMemo(() => (archive ? [] : matching.filter(r => isOpen(r, at))), [archive, matching, at]);
  const sortScope = upcomingOnly ? "upcoming" : "all";
  const order = orders[sortScope];
  const groups = useMemo(() => groupDrops(archive ? matching : orderDrops(upcomingOnly ? upcoming : matching, order)),
    [archive, matching, upcoming, upcomingOnly, order]);
  const rows = useMemo(() => groups.flatMap(group => group.drops), [groups]);
  const index = Math.max(0, rows.findIndex(m => moveKey(m) === selectedKey));
  const m = rows.length ? rows[index] : undefined;
  const currentKey = m ? moveKey(m) : null;
  const activeRoundup = roundups.find(r => r.id === pickedBatch) ?? defaultRoundup(roundups);

  // Every moment at which a move or a watchlist match stops being actionable.
  const cutoffs = useMemo(() => {
    if (archive) return [];
    const set = new Set<number>();
    for (const r of moves) { const c = cutoffOf(r); if (c !== null) set.add(c); }
    for (const f of fixtures) { const c = cutoffOf(f); if (c !== null) set.add(c); }
    return Array.from(set).sort((a, b) => a - b);
  }, [archive, moves, fixtures]);
  const live = !archive && (today === true || moves.some(r => outcomeOf(r.result) === "pending"));
  const seen = useRef<number | null>(now ?? null);
  const refreshed = useRef(0);

  // Local clock: it wakes on the next cutoff and whenever the tab comes back, so a
  // record leaves the upcoming list and the watchlist without any network call.
  // The records themselves are re-read at most once per quarter hour while visible,
  // or on return to the tab if they are older than that.
  useEffect(() => {
    if (archive || now === undefined) return;
    const wall = Date.now(), mono = performance.now();
    // The later of the device clock and the server stamp plus elapsed time, so a slow device clock cannot keep a record open.
    const read = () => Math.max(Date.now(), now + Math.max(0, Date.now() - wall, performance.now() - mono));
    let timer: number | undefined;
    const tick = () => {
      window.clearTimeout(timer);
      const t = read(), prev = Math.max(seen.current ?? 0, now);
      if (cutoffs.some(c => c > prev && c <= t)) { seen.current = t; setClock(t); }
      if (document.visibilityState !== "visible") return;
      if (live && t - now >= REFRESH_MS && t - refreshed.current >= REFRESH_MS) { refreshed.current = t; router.refresh(); }
      const next = cutoffs.find(c => c > t);
      timer = window.setTimeout(tick, Math.min(TICK_MS, Math.max(250, next === undefined ? TICK_MS : next - t + 50)));
    };
    tick();
    document.addEventListener("visibilitychange", tick);
    window.addEventListener("pageshow", tick);
    window.addEventListener("focus", tick);
    return () => {
      window.clearTimeout(timer);
      document.removeEventListener("visibilitychange", tick);
      window.removeEventListener("pageshow", tick);
      window.removeEventListener("focus", tick);
    };
  }, [archive, now, cutoffs, live, router]);

  // When the drop on stage closes and drops out of the upcoming list, say so instead of swapping silently.
  const stageKey = useRef<string | null>(null);
  useEffect(() => {
    const prev = stageKey.current;
    stageKey.current = currentKey;
    if (!upcomingOnly || !prev || prev === currentKey) return;
    const was = matching.find(r => moveKey(r) === prev);
    if (was && !isOpen(was, at)) setLapsedKey(prev);
  }, [currentKey, upcomingOnly, matching, at]);
  const lapsed = upcomingOnly && lapsedKey ? matching.find(r => moveKey(r) === lapsedKey && !isOpen(r, at)) : undefined;

  // Keep the selected row visible inside the rail without moving the page.
  useEffect(() => {
    const list = listRef.current;
    const row = list?.querySelector<HTMLElement>('[data-drop][aria-pressed="true"]');
    if (!list || !row) return;
    const top = row.getBoundingClientRect().top - list.getBoundingClientRect().top + list.scrollTop;
    const bottom = top + row.offsetHeight;
    if (top < list.scrollTop) list.scrollTop = top;
    else if (bottom > list.scrollTop + list.clientHeight) list.scrollTop = bottom - list.clientHeight;
  }, [currentKey, pickerOpen]);

  const choose = (move: DeskMove) => {
    setSelectedKey(moveKey(move));
    setLapsedKey(null);
    setPickerOpen(false);
    const key = matchKey(move);
    if (expandedGroups[key] === false) {
      setExpandedGroups(previous => {
        const next = { ...previous };
        delete next[key];
        return next;
      });
    }
  };
  const step = (dir: number) => { if (rows.length) choose(rows[(index + dir + rows.length) % rows.length]); };
  const clearFilters = () => { setTour(TOURS[0]); setDraw(DRAWS[0]); setMarket("all"); setQuery(""); setAlertedOnly(false); };
  const changeScope = (next: Scope) => { setScope(next); setLapsedKey(null); };
  // A new order starts from its own first entry; pressing the order already in use changes nothing.
  const changeOrder = (value: DropOrder) => {
    if (value === order) return;
    setOrders(previous => ({ ...previous, [sortScope]: value }));
    setSelectedKey(null);
  };
  const toStage = () => window.requestAnimationFrame(() => stageRef.current?.scrollIntoView({ block: "start" }));
  // A roundup row always opens its chart: a closed selection switches the list to the
  // full record, and the filters are only cleared when they would hide that selection.
  const openFromRoundup = (move: DeskMove) => {
    if (!passes(move)) clearFilters();
    if (upcomingOnly && !isOpen(move, at)) setScope("all");
    choose(move);
    toStage();
  };
  const openLapsed = () => {
    if (lapsedKey) setSelectedKey(lapsedKey);
    changeScope("all");
  };
  const selectBatch = (id: string) => {
    setPickedBatch(id);
    try {
      const url = new URL(window.location.href);
      if (day) url.searchParams.set("day", day);
      url.searchParams.set("batch", id);
      window.history.replaceState(null, "", url);
    } catch { /* the address bar is a convenience, not a requirement */ }
  };
  const toRoundup = (id: string) => {
    selectBatch(id);
    setRoundupsOpen(true);
    window.requestAnimationFrame(() => roundupsRef.current?.scrollIntoView({ block: "start" }));
  };
  // As in the original ledger: up, down, Home and End move focus between entries.
  const onListKey = (e: KeyboardEvent<HTMLOListElement>) => {
    const buttons = Array.from(e.currentTarget.querySelectorAll<HTMLButtonElement>("button"));
    const i = buttons.findIndex(b => b === document.activeElement);
    const j = e.key === "ArrowDown" ? i + 1 : e.key === "ArrowUp" ? i - 1 : e.key === "Home" ? 0 : e.key === "End" ? buttons.length - 1 : -1;
    if (i < 0 || j < 0 || !buttons[j]) return;
    e.preventDefault();
    buttons[j].focus();
  };

  const filtered = (!archive && alertedOnly) || market!=="all" || tour !== TOURS[0] || draw !== DRAWS[0] || needle !== "";
  const lastQuote = m && m.quotes.length ? m.quotes[m.quotes.length - 1] : undefined;
  const latestIsDetection = !!(m && lastQuote && Date.parse(lastQuote.time) === Date.parse(m.after));
  const outcome = m ? outcomeOf(m.result) : "pending";
  const pl = m ? paper(m) : null;
  const ownRoundup = m && m.batchId ? roundups.find(r => r.id === m.batchId) : undefined;
  const status = m && !archive ? availability(m, at, lastQuote?.time) : null;
  // The stage figures: the gap between the two captures and the lead before the scheduled start.
  const tBefore = m ? Date.parse(m.before) : NaN, tAfter = m ? Date.parse(m.after) : NaN, tStart = m ? Date.parse(m.start) : NaN;
  const apart = tAfter - tBefore, lead = tStart - tAfter;
  const showOut = !!m && (archive || outcome !== "pending");
  const round = m ? roundOf(m.league) : "";
  const kick = m ? [placeOf(m.league), round, isQualifying(m) && !/^q/i.test(round) ? "Qualifying" : "", (archive ? "Start " : "Scheduled start ") + utcStamp(m.start)].filter(Boolean).join(" · ") : "";
  const dayFixtures = fixtures.filter(f => tour === TOURS[0] || tour === f.tour).sort((a, b) => a.start.localeCompare(b.start));
  const openFixtures = dayFixtures.filter(f => isOpen(f, at));
  const shownFixtures = upcomingOnly ? openFixtures : dayFixtures;
  const plural = (n: number, one: string, many: string) => n + " " + (n === 1 ? one : many);
  const sortNote = SORTS.find(s => s.value === order)?.note ?? "";
  const blank = !moves.length
    ? (archive ? "No recorded drops are in the replay." : "No price drops were recorded on this date.")
    : upcomingOnly && matching.length
      ? (matching.length === 1 ? "The one recorded drop here is no longer" : "None of the " + matching.length + " recorded drops here is still") + " verified open before its scheduled start."
      : alertedOnly ? "No confirmed Telegram alerts match these filters." : "No recorded drops match these filters.";

  return <div className={styles.board} data-archive={archive ? "true" : undefined}>
    {/* One line of controls: what to show, three quiet filters, the search. The order of the list lives on the list. */}
    <div className={styles.tools}>
      {!archive && <div className={styles.scope} role="group" aria-label="Show drops">
        <button type="button" aria-pressed={scope === "upcoming"} onClick={() => changeScope("upcoming")}>Upcoming <small>{upcoming.length}</small></button>
        <button type="button" aria-pressed={scope === "all"} onClick={() => changeScope("all")}>All recorded <small>{matching.length}</small></button>
      </div>}
      <div className={styles.filters} role="group" aria-label="Filter drops">
        <label className={styles.pick} data-on={tour !== TOURS[0] ? "true" : undefined}><span>Tour</span>
          <select value={tour} onChange={e => setTour(e.target.value)}>{TOURS.map(v => <option key={v}>{v}</option>)}</select></label>
        <label className={styles.pick} data-on={draw !== DRAWS[0] ? "true" : undefined}><span>Draw</span>
          <select value={draw} onChange={e => setDraw(e.target.value)}>{DRAWS.map(v => <option key={v}>{v}</option>)}</select></label>
        {!archive && <label className={styles.pick} data-on={market !== "all" ? "true" : undefined}><span>Market</span>
          <select value={market} onChange={e=>setMarket(e.target.value)}><option value="all">All markets</option><option value="winner">Match winner</option><option value="totals">Total games</option><option value="spreads">Games handicap</option></select></label>}
        {!archive && <label className={styles.alertFilter}>
          <input type="checkbox" checked={alertedOnly} onChange={e => setAlertedOnly(e.target.checked)} />
          Alerted only
        </label>}
        {filtered && <button type="button" className={styles.clear} onClick={clearFilters}>Clear filters</button>}
      </div>
      {moves.length > 8 && <label className={`${styles.pick} ${styles.search}`} data-on={needle ? "true" : undefined}><span>Find</span>
        <input type="search" value={query} onChange={e => setQuery(e.target.value)} placeholder="Player or tournament" aria-label="Find a player or tournament" autoComplete="off" /></label>}
      {!archive && roundups.length > 0 && <a className={styles.jump} href={ROUNDUPS_HASH} onClick={() => setRoundupsOpen(true)}>Telegram roundups ({roundups.length}) <span aria-hidden="true">↓</span></a>}
    </div>

    {lapsed && <p className={styles.lapsed} role="status">
      <span><b>{lapsed.player}</b> vs {lapsed.opponent} is closed and off the upcoming list · {availability(lapsed, at).reason}.</span>
      <button type="button" className={styles.linkish} onClick={openLapsed}>See its recorded chart</button>
    </p>}

    {m ? <div className={styles.desk}>
      {/* The ledger: each entry reads who and where on the left, the figures on the right, all on one right edge. */}
      <section className={styles.rail} aria-label={upcomingOnly ? "Upcoming moves" : "Recorded moves"}>
        <div className={styles.railHead}>
          <h2>{upcomingOnly ? "Upcoming drops" : "Price drops"} <small>{plural(groups.length, "match", "matches")} · {plural(rows.length, "drop", "drops")}</small></h2>
          {!archive && <div className={styles.sortRow} role="group" aria-labelledby={sortId} aria-describedby={noteId}>
            <span className={styles.lab} id={sortId}>Sort</span>
            <div className={styles.sort}>
              {SORTS.map(s => <button key={s.value} type="button" aria-pressed={order === s.value} onClick={() => changeOrder(s.value)}>{s.label}</button>)}
            </div>
          </div>}
          <p className={styles.railNote} id={noteId}>
            <b>pp</b> is the rise in implied probability (1 ÷ price) from the earlier price to detection.
            {!archive && <> {upcomingOnly ? "Upcoming" : "All recorded"}: {sortNote}.</>}
          </p>
        </div>
        {/* Phones and tablets: the entry on stage is a switcher; the ledger opens beneath it and folds away on choice. */}
        <button type="button" className={styles.picker} aria-expanded={pickerOpen} aria-controls={listId} onClick={() => setPickerOpen(open => !open)}>
          <span className={styles.pickerLabel}>Showing {index + 1} of {rows.length}</span>
          <strong>{m.player}</strong>
          <span className={styles.pickerMove}><b>{pointsText(m)}</b> implied probability · <span>{price(m.old)} → </span>{price(m.new)}</span>
          <span className={styles.pickerCue}>{pickerOpen ? "Close list" : rows.length > 1 ? "Choose from " + rows.length : "Show list"}</span>
        </button>
        <ol id={listId} className={styles.railList} ref={listRef} data-open={pickerOpen ? "true" : "false"} onKeyDown={onListKey}>
          {groups.map(({key, drops}, i) => {
            const lead = drops[0];
            const more = drops.length - 1;
            const expanded = expandedGroups[key] ?? (!!m && m !== lead && drops.includes(m));
            const linesId = listId + "-lines-" + i;
            const renderRow = (r: DeskMove) => <DropRow key={moveKey(r)} move={r} selected={r === m} archive={archive}
              at={at} venue={venues[venueKey(r.league, r.start, r.tour)]} onChoose={choose} />;
            return <li key={key}>
              {renderRow(lead)}
              {more > 0 && <>
                <button type="button" className={styles.moreDrops} aria-expanded={expanded} aria-controls={linesId}
                  onClick={() => setExpandedGroups(previous => ({...previous, [key]: !expanded}))}>
                  <span aria-hidden="true">{expanded ? "−" : "+"}</span>
                  {expanded ? "Hide" : "Show"} {more} more {more === 1 ? "drop" : "drops"}
                  <span className={styles.vh}> for {lead.fixtureLabel ?? (lead.player + " vs " + lead.opponent)}</span>
                </button>
                <div id={linesId} className={styles.otherDrops} hidden={!expanded}>
                  {expanded && drops.slice(1).map(renderRow)}
                </div>
              </>}
            </li>;
          })}
        </ol>
      </section>

      {/* The stage: host tournament and stepper, the selection against the move in large figures, status, timing, then the chart. */}
      <article className={styles.stage} ref={stageRef} aria-labelledby={headId}>
        <div className={styles.stageTop}>
          <p className={styles.kick}>
            <VenueFlag venue={venues[venueKey(m.league, m.start, m.tour)]} />
            <span><b>{m.tour}</b> · {kick}</span>
            {archive && <span className={styles.tagMode}>Historical replay</span>}
          </p>
          <div className={styles.stepper} role="group" aria-label="Step through price drops">
            <button type="button" aria-label="Previous price drop" disabled={rows.length < 2} onClick={() => step(-1)}><span aria-hidden="true">‹</span></button>
            <span>{index + 1} / {rows.length}</span>
            <button type="button" aria-label="Next price drop" disabled={rows.length < 2} onClick={() => step(1)}><span aria-hidden="true">›</span></button>
          </div>
        </div>

        <div className={styles.hero} data-out={showOut ? "true" : undefined}>
          <div className={styles.heroWho}>
            {marketName(m) && <p className={styles.market}>{marketName(m)}</p>}
            <h2 id={headId}>{m.player}</h2>
            <p className={styles.versus}>{m.fixtureLabel ?? ("vs "+m.opponent)}</p>
          </div>
          <div className={styles.heroMove}>
            <p className={styles.lab}>Earlier price → price at detection</p>
            <p className={styles.movement}>
              <span className={styles.was} title="Earlier price">{price(m.old)}</span><span className={styles.arrow}> → </span><span className={styles.now} title="Price at detection">{price(m.new)}</span>
            </p>
            {/* The two magnitudes are never left bare: probability in points first, price in percent second. */}
            <p className={styles.gain}><b>{pointsText(m)}</b> implied probability <span>{impliedText(m.old)} → {impliedText(m.new)}</span></p>
            <p className={styles.shift}>Price <b>{delta(m.new - m.old)} ({percent(dropPct(m))})</b>{Number.isFinite(apart) && apart > 0 ? " · captures " + spanText(apart) + " apart" : ""}</p>
          </div>
          {showOut && <div className={styles.heroOut}>
            <p className={styles.settled} data-outcome={outcome}><b>{outcomeLabel(m)}</b>{archive && pl !== null && <span>{units(pl)}</span>}</p>
            {m.score ? <p className={styles.score}>{m.score}</p> : null}
          </div>}
          <div className={styles.statusLine}>
            {status && <p className={styles.avail} data-state={status.open ? "open" : "closed"}>
              <b>{status.label}</b> · {status.reason}. {status.detail}
            </p>}
            {!showOut && m.notified && <span className={styles.pill} data-outcome={outcome}>{outcomeLabel(m)}</span>}
            {archive
              ? <span>{pl === null ? "Not settled in the replay" : "Historical replay · 1u at the price at detection"}</span>
              : <span>{m.notified || m.alertedAt ? "Private alert delivered" : "Observed drop"}{m.alertedAt ? " · sent " + utcClock(m.alertedAt, true) + " UTC" : ""}</span>}
            {ownRoundup && <button type="button" className={styles.linkish} onClick={() => toRoundup(ownRoundup.id)}>In the {utcClock(ownRoundup.at)} UTC roundup</button>}
          </div>
        </div>

        <dl className={styles.timing}>
          <div data-role="earlier">
            <dt><KeyGlyph kind="earlier" />Earlier capture</dt>
            <dd><time dateTime={m.before}>{utcClock(m.before, true)} UTC</time><small>{utcDate(m.before)} · price {price(m.old)}</small></dd>
          </div>
          <div data-role="detected">
            <dt><KeyGlyph kind="detected" />Detection capture</dt>
            <dd><time dateTime={m.after}>{utcClock(m.after, true)} UTC</time><small>{utcDate(m.after)} · price {price(m.new)}</small></dd>
          </div>
          <div data-role="lead">
            <dt>Before scheduled start</dt>
            <dd>{lead >= 0 ? spanText(lead) : "—"}<small>{lead < 0 ? "detected after the scheduled time" : "scheduled " + utcStamp(m.start)}</small></dd>
          </div>
          <div data-role="latest">
            <dt><KeyGlyph kind="latest" />Latest observation</dt>
            <dd>{lastQuote ? price(lastQuote.price) : "—"}<small>{lastQuote
              ? <><time dateTime={lastQuote.time}>{utcStamp(lastQuote.time, true)}</time>{latestIsDetection ? " · same as detection" : " · " + delta(lastQuote.price - m.new) + " since detection"}</>
              : "No recorded prices"}</small></dd>
          </div>
        </dl>

        <OddsChart key={currentKey ?? "chart"} move={m} archive={archive} />
      </article>
    </div> : <div className={styles.blank}>
      <div>
        <p role="status">{blank}</p>
        {filtered && moves.length > 0 && <button type="button" className={styles.ghost} onClick={clearFilters}>Clear filters</button>}
        {upcomingOnly && matching.length > 0 && <button type="button" className={styles.ghost} onClick={() => changeScope("all")}>Show all recorded ({matching.length})</button>}
      </div>
      {/* The empty-court drawing from the original "no price drop seen yet" state. */}
      <svg className={styles.court} viewBox="0 0 238 112" aria-hidden="true" focusable="false">
        <g fill="none" stroke="#33454f" strokeWidth="2"><rect x="2" y="2" width="234" height="108" /><path d="M2 15.5H236M2 96.5H236M56 15.5V96.5M182 15.5V96.5M56 56H182" /></g>
        <path d="M119 0V112" stroke="#8497a4" strokeWidth="2" strokeDasharray="2 4" />
      </svg>
    </div>}

    {/* The day's alert results stay in the open: three ruled cells, one per market, the same tallies as before. */}
    {!archive && <section className={styles.results} aria-labelledby={resultsId}>
      <header className={styles.resultsHead}>
        <h2 id={resultsId}>Alert results <small>{day} UTC</small></h2>
        <p>Sent alerts under the 4 pp rule. Each selection is tracked at 1u using its alerted line and price.</p>
      </header>
      <div className={styles.returnGrid}>{[["winner","Match winner"],["spreads","Games handicap"],["totals","Total games"]].map(([key,label])=>{
        const sum=tally(moves.filter(row=>row.fourPointAlert && (row.market ?? "winner") === key));
        return <section key={key}><h3>{label}</h3>
          <p className={styles.returnNet} data-tone={sum.settled ? (sum.net > 0 ? "won" : sum.net < 0 ? "lost" : undefined) : undefined}>{sum.settled ? units(sum.net) : "—"} <small>paper P/L</small></p>
          <p>{sum.won}W · {sum.lost}L · {sum.pending} pending{sum.pushed ? " · "+sum.pushed+" push" : ""}{sum.voided ? " · "+sum.voided+" void" : ""}{sum.split ? " · "+sum.split+" split" : ""}</p>
          <p>{sum.settled}u settled · ROI {sum.roi===null ? "—" : percent(sum.roi)}</p>
        </section>;
      })}</div>
      <details className={styles.fold}>
        <summary>How results are settled</summary>
        <p className={styles.fine}>{SETTLING_NOTE} A push returns the stake. Voids and pending selections are left out of settled stake.</p>
      </details>
    </section>}
    {!archive && <Roundups roundups={roundups} active={activeRoundup} currentKey={currentKey} now={at} open={roundupsOpen} onToggle={() => setRoundupsOpen(open => !open)} onSelect={selectBatch} onOpen={openFromRoundup} sectionRef={roundupsRef} />}

    {fixtures.length > 0 && <details className={styles.fold}>
      <summary>{upcomingOnly
        ? "Upcoming watchlist (" + plural(openFixtures.length, "match", "matches") + ")"
        : "Latest watchlist (" + plural(dayFixtures.length, "match", "matches") + " · " + openFixtures.length + " still open)"}</summary>
      {shownFixtures.length ? <div className={styles.scroll}>
        <table className={styles.table}>
          <thead><tr><th scope="col">Match</th><th scope="col">Tournament</th><th scope="col">Scheduled start (UTC)</th></tr></thead>
          <tbody>{shownFixtures.map(f => {
            const a = availability(f, at);
            return <tr key={[f.home, f.away, f.start].join("/")}>
              <td>{f.home} {f.homePrice !== undefined && <b>{price(f.homePrice)}</b>}<br />{f.away} {f.awayPrice !== undefined && <b>{price(f.awayPrice)}</b>}</td>
              <td><span className={styles.venue}><VenueFlag venue={venues[venueKey(f.league, f.start, f.tour)]} /><span>{f.league}</span></span></td>
              <td>{utcStamp(f.start)}<br /><span className={styles.state} data-open={a.open ? "true" : undefined}>{a.label} · {a.reason}</span></td>
            </tr>;
          })}</tbody>
        </table>
      </div> : <p className={styles.empty} role="status">{upcomingOnly ? "No watchlist match is still verified open before its scheduled start." : "No watchlist match fits this tour."}</p>}
    </details>}
  </div>;
}
