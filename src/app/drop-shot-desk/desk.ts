import type { Fixture, Move } from "./types";

/** Maximum age for which a saved scan corroborates open pre-match availability. */
export const SCAN_VALIDITY_MINUTES = 20;
export const SCAN_VALIDITY_MS = SCAN_VALIDITY_MINUTES * 60_000;

/** Keep limit formatting identical on the server, in the list and on exported charts. */
export function amountText(n: number) {
  const abs = Math.abs(n);
  const fixed = Number.isInteger(abs) ? String(abs) : abs.toFixed(2).replace(/0+$/, "").replace(/\.$/, "");
  const [whole, frac] = fixed.split(".");
  return (n < 0 ? "−" : "") + whole.replace(/\B(?=(\d{3})+(?!\d))/g, ",") + (frac ? "." + frac : "");
}
export function displayedLimit(amount: number, currency: string) {
  return currency === "USD" ? "$" + amountText(amount) : amountText(amount) + " " + currency;
}

/**
 * Move plus the optional receipt fields. Declared as an intersection so this
 * compiles whether or not the fields have already been added to types.ts.
 * activeUntil is present only while the latest open pre-match quote still
 * corroborates the same fixture, start and players; absence means the record
 * is no longer verified available.
 */
export type DeskMove = Move & { batchAt?: string; batchId?: string; alertedAt?: string; activeUntil?: string };
export type DeskFixture = Fixture & { activeUntil?: string };
/** `reason` is a short phrase for lists; `detail` is the full-sentence qualification shown beside the selected record. */
export type Availability = { open: boolean; label: "Open" | "Closed"; reason: string; detail: string };
export type Outcome = "won" | "lost" | "void" | "pending";
export type Roundup = {
  id: string;
  /** Receipt time in ms (UTC). */
  at: number;
  /** Sent time in ms (UTC), when recorded. */
  sent: number | null;
  confirmed: boolean;
  picks: DeskMove[];
  /** selectionKey -> time of the earlier roundup that first carried the selection. */
  firstSent: Record<string, number>;
};
export type Tally = {
  picks: number; won: number; lost: number; pushed:number; split:number; voided: number; pending: number;
  /** Settled, non-void selections: the ROI denominator. */
  settled: number;
  net: number;
  roi: number | null;
};

type When = string | number;
const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
const two = (n: number) => String(n).padStart(2, "0");
const valid = (t: When) => Number.isFinite(new Date(t).getTime());

// Formatting is done by hand in UTC so server and browser output always match.
export function utcDate(t: When) {
  const d = new Date(t);
  return valid(t) ? d.getUTCDate() + " " + MONTHS[d.getUTCMonth()] : "—";
}
export function utcClock(t: When, seconds = false) {
  if (!valid(t)) return "—";
  const d = new Date(t);
  return two(d.getUTCHours()) + ":" + two(d.getUTCMinutes()) + (seconds ? ":" + two(d.getUTCSeconds()) : "");
}
export function utcStamp(t: When, seconds = false) {
  return valid(t) ? utcDate(t) + " · " + utcClock(t, seconds) + " UTC" : "—";
}

export function timeToStart(start: number, now: number) {
  const remaining = start - now;
  if (!Number.isFinite(remaining) || remaining <= 0) return null;
  if (remaining < 60_000) return "under 1 min";
  const minutes = Math.ceil(remaining / 60_000);
  if (minutes < 60) return minutes + " min";
  const hours = Math.floor(minutes / 60);
  const rest = minutes % 60;
  return hours + "h" + (rest ? " " + rest + "m" : "");
}

export function price(p: number) {
  return Number.isFinite(p) ? p.toFixed(3).replace(/0$/, "") : "—";
}
export function units(n: number) {
  return (n > 0 ? "+" : "") + Number(n.toFixed(3)) + "u";
}
export function percent(n: number) {
  const v = Number(n.toFixed(1));
  return (v > 0 ? "+" : v < 0 ? "-" : "") + Math.abs(v).toFixed(1) + "%";
}
export function delta(n: number) {
  const v = Number(n.toFixed(3));
  return (v > 0 ? "+" : v < 0 ? "-" : "") + price(Math.abs(v));
}
export function dropPct(m: Move) {
  return m.old > 0 ? ((m.new - m.old) / m.old) * 100 : 0;
}
export type DropOrder = "largest" | "newest" | "soonest" | "oldest";

export function movementPoints(m: Move) {
  return 100 * (1 / m.new - 1 / m.old);
}

export function orderDrops<T extends Move>(rows: T[], order: DropOrder): T[] {
  return [...rows].sort((a, b) => {
    if (order === "soonest") {
      const startA = Date.parse(a.start), startB = Date.parse(b.start);
      const start = (Number.isFinite(startA) ? startA : Infinity) - (Number.isFinite(startB) ? startB : Infinity);
      if (start) return start;
    }
    if (order === "largest" || order === "soonest") {
      const size = movementPoints(b) - movementPoints(a);
      if (size) return size;
    }
    const time = Date.parse(b.after) - Date.parse(a.after);
    return (order === "oldest" ? -time : time) || moveKey(a).localeCompare(moveKey(b), "en");
  });
}
export function slug(text: string) {
  return text.toLowerCase().normalize("NFKD").replace(/[^a-z0-9]+/g, "-").replace(/^-+|-+$/g, "").slice(0, 40) || "selection";
}

export function isQualifying(m: Move) {
  return m.qualifying ?? /(?: - Q\d+\b|qualif)/i.test(m.league);
}
export function selectionKey(m: Move) {
  return [m.fixtureLabel, m.market??"winner", m.player, m.opponent, m.start].join("|");
}
// Daily rows carry the collector's own fixture fingerprint. Replay winner records
// without one use the exact pair, tournament/round and scheduled start.
export function matchKey(m: Move) {
  return JSON.stringify([m.tour, m.league, m.start, m.fixtureRef || [m.player, m.opponent].sort()]);
}

// Input follows the selected sort, so the first drop represents the match and
// the remaining detections keep their order, including repeat moves on a line.
export function groupDrops(rows: Move[]) {
  const groups = new Map<string, Move[]>();
  for (const row of rows) {
    const key = matchKey(row);
    const entries = groups.get(key);
    if (entries) entries.push(row);
    else groups.set(key, [row]);
  }
  return Array.from(groups, ([key, drops]) => ({ key, drops }));
}

export function moveKey(m: Move) {
  return JSON.stringify([matchKey(m), m.market ?? "winner", m.player, m.opponent, m.after]);
}

export function outcomeOf(result: string | undefined): Outcome {
  const r = (result ?? "").trim().toLowerCase();
  if (r==="half won") return "won";
  if (r==="half lost") return "lost";
  if (/^(won|win)\b/.test(r)) return "won";
  if (/^(lost|loss|lose)\b/.test(r)) return "lost";
  if (/void|cancel|walkover|abandon|refund|push|no bet/.test(r)) return "void";
  return "pending";
}
export function outcomeLabel(m: Move) {
  return (m.result ?? "").trim() || "Pending";
}
/** Flat 1u paper result at the locked detection price; null while unsettled. */
export function paper(m: Move): number | null {
  if(typeof m.profit==="number")return m.profit;
  const o = outcomeOf(m.result);
  return o === "won" ? m.new - 1 : o === "lost" ? -1 : o === "void" ? 0 : null;
}

type Timed = { start: string; activeUntil?: string; result?: string };

/** Time in ms after which a record must not be shown as actionable; null when it is not verified available. */
export function cutoffOf(r: Timed): number | null {
  const until = r.activeUntil ? Date.parse(r.activeUntil) : NaN;
  if (!Number.isFinite(until)) return null;
  const start = Date.parse(r.start);
  return Number.isFinite(start) ? Math.min(until, start) : null;
}
/** Still verified open pre-match at `now` (ms). An unknown clock is never open. */
export function isOpen(r: Timed, now: number | null) {
  const cut = cutoffOf(r);
  return now !== null && cut !== null && now < cut && outcomeOf(r.result) === "pending";
}
/**
 * Open or closed, with a short reason and a full-sentence detail. Three times are kept apart:
 * - the recorded observation: when a price was actually seen (`observed`, always in the past);
 * - the quote freshness cutoff: when the desk stops treating that observation as current.
 *   It is a limit on the desk's listing, never a statement that the quote was or will be
 *   verified at that time, and never a guarantee of the price until then;
 * - the scheduled start: the planned time, not the actual first serve, which the desk does not track.
 * `observed` is the time of the latest recorded observation, when the caller has one.
 */
export function availability(r: Timed, now: number | null, observed?: When): Availability {
  const closed = (reason: string): Availability => ({ open: false, label: "Closed", reason, detail: "Saved for reference." });
  if (outcomeOf(r.result) !== "pending") return closed("result recorded");
  if (now === null) return closed("availability not verified");
  const at = (t: number) => (utcDate(t) === utcDate(now) ? "" : utcDate(t) + " · ") + utcClock(t) + " UTC";
  const start = Date.parse(r.start), cut = cutoffOf(r);
  if (cut !== null && now < cut) {
    // An observation is only ever quoted with its own, past, time.
    const seen = observed === undefined ? NaN : new Date(observed).getTime();
    const basis = Number.isFinite(seen) && seen <= now ? "Latest recorded observation " + at(seen) : "Based on the latest recorded observation";
    if (cut === start) return {
      open: true, label: "Open", reason: "listed until scheduled start " + at(start),
      detail: basis + ". Odds can change before first serve.",
    };
    return {
      open: true, label: "Open", reason: "listing expires at " + at(cut),
      detail: basis + ". Odds can change between scans.",
    };
  }
  if (Number.isFinite(start) && now >= start) return closed("scheduled start " + at(start) + " passed");
  return closed(cut !== null ? "last odds expired at " + at(cut) : "pre-match odds unavailable in the latest scan");
}

export function tally(picks: Move[]): Tally {
  let won = 0, lost = 0, voided = 0, pending = 0, net = 0, pushed = 0, split = 0;
  for (const m of picks) {
    const o = outcomeOf(m.result);
    if(m.result==="Push"){ pushed++; continue; }
    if(m.result==="Half won" || m.result==="Half lost"){ split++; net+=paper(m)??0; continue; }
    if (o === "won") { won += 1; net += m.new - 1; }
    else if (o === "lost") { lost += 1; net -= 1; }
    else if (o === "void") voided += 1;
    else pending += 1;
  }
  const settled = won + lost + pushed + split;
  return { picks: picks.length, won, lost, pushed, split, voided, pending, settled, net, roi: settled ? (net / settled) * 100 : null };
}

const firstTime = (values: (string | undefined)[]) => {
  for (const v of values) {
    const t = v ? Date.parse(v) : NaN;
    if (Number.isFinite(t)) return t;
  }
  return null;
};

/**
 * One roundup per receipt stamp: all and only the moves carrying that batchId.
 * A selection listed twice under one stamp is kept once, at its first locked
 * price. A selection that returns in a later roundup is flagged there as a
 * price update; roundups are never pooled into a combined total.
 */
export function buildRoundups(moves: DeskMove[]): Roundup[] {
  const groups = new Map<string, DeskMove[]>();
  for (const m of moves) {
    if (!m.batchId) continue;
    const rows = groups.get(m.batchId);
    if (rows) rows.push(m); else groups.set(m.batchId, [m]);
  }
  const list: Roundup[] = [];
  groups.forEach((rows, id) => {
    const byDetection = [...rows].sort((a, b) => Date.parse(a.after) - Date.parse(b.after));
    const seen = new Set<string>();
    const picks: DeskMove[] = [];
    for (const m of byDetection) {
      const k = selectionKey(m);
      if (seen.has(k)) continue;
      seen.add(k);
      picks.push(m);
    }
    picks.sort((a, b) => a.start.localeCompare(b.start) || a.player.localeCompare(b.player));
    const sent = firstTime(rows.map(m => m.alertedAt));
    const at = firstTime(rows.map(m => m.batchAt)) ?? sent ?? firstTime(rows.map(m => m.after)) ?? 0;
    list.push({ id, at, sent, confirmed: rows.some(m => m.notified || !!m.alertedAt), picks, firstSent: {} });
  });
  list.sort((a, b) => a.at - b.at || a.id.localeCompare(b.id));
  const first = new Map<string, number>();
  for (const r of list) {
    for (const m of r.picks) {
      const k = selectionKey(m);
      const prior = first.get(k);
      if (prior === undefined) first.set(k, r.at); else r.firstSent[k] = prior;
    }
  }
  return list;
}

/** Latest confirmed roundup, else simply the latest. */
export function defaultRoundup(list: Roundup[]): Roundup | null {
  for (let i = list.length - 1; i >= 0; i -= 1) if (list[i].confirmed) return list[i];
  return list.length ? list[list.length - 1] : null;
}
