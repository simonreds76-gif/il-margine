import Image from "next/image";
import styles from "./board.module.css";
import { isOpen, movementPoints, outcomeLabel, outcomeOf } from "./desk";
import type { DeskMove } from "./desk";
import type { Move } from "./types";

/**
 * Small shared pieces of the desk. No "use client" on purpose: page.tsx (server) uses the
 * venue helpers to resolve flags, the board (client) uses the same key to read them back.
 */

/* ---------- drop magnitude: one name, one format, everywhere ---------- */

/**
 * The desk's headline magnitude: the rise in implied probability between the earlier price
 * and the price at detection, in percentage points, always signed with two decimals ("+5.58 pp").
 * Implied probability is 1 ÷ decimal price with the margin left in. It is never the same
 * number as the price change in percent, which is always written with the word "price".
 */
export function pointsText(m: Move) {
  const v = movementPoints(m);
  if (!Number.isFinite(v)) return "—";
  const r = Number(v.toFixed(2));
  return (r > 0 ? "+" : r < 0 ? "-" : "") + Math.abs(r).toFixed(2) + " pp";
}
/** "47.6%": the implied probability of one decimal price, margin included. */
export function impliedText(p: number) {
  return Number.isFinite(p) && p > 0 ? (100 / p).toFixed(1) + "%" : "—";
}

const MARKET_NAMES: Record<string, string> = { winner: "Match winner", totals: "Total games", spreads: "Games handicap" };
/** Records without a market are match-winner records; an unknown market is left unnamed rather than guessed. */
export const marketName = (m: { market?: string }) => MARKET_NAMES[m.market ?? "winner"] ?? "";

/** One wording for how results arrive, used by the daily results and the roundup receipts. */
export const SETTLING_NOTE = "The cloud scan runs every 15 minutes. Pending results from the last seven days are rechecked roughly hourly once the scheduled start has passed, older ones once a day. A result is recorded only when a final score is available and matches the fixture; until then the selection stays pending.";

/* ---------- status: a dot and a word, not a badge ---------- */

export function State({ move, now, archive }: { move: DeskMove; now: number | null; archive: boolean }) {
  const outcome = outcomeOf(move.result);
  if (archive || outcome !== "pending") return <span className={styles.tone} data-tone={outcome}>{outcomeLabel(move)}</span>;
  const open = isOpen(move, now);
  if (open) return <span className={styles.tone} data-tone="open">Open</span>;
  const pastStart = now !== null && now >= Date.parse(move.start);
  return <span className={styles.tone} data-tone="closed">{pastStart ? "Start time passed" : "Odds unavailable"}</span>;
}

/* ---------- host-country flag ---------- */

export type Venue = { code: string; name: string; flag: string };
/** venueKey -> venue, built on the server from the shared tournament registry only. */
export type VenueMap = Record<string, Venue>;

/** The tournament part of a feed string: "ATP Challenger Helsinki - Quarter Finals" -> "Helsinki". */
export const hostOf = (league: string) => league.replace(/^(?:ATP(?:\s+Challenger)?|WTA(?:\s+125k?)?)\s+/i, "").split(" - ")[0].trim() || league;
/** One entry per feed string and start date, so an edition is never reused across dates. */
export const venueKey = (league: string, start: string, tour: string) => tour + "|" + league + "|" + start.slice(0, 10);

const hostCodes: Record<string, string> = {
  ar:"ARG", au:"AUS", br:"BRA", ca:"CAN", fi:"FIN", fr:"FRA", gr:"GRC", it:"ITA",
  jp:"JPN", pe:"PER", se:"SWE", sk:"SVK", tn:"TUN", tw:"TWN", us:"USA", uy:"URY",
};

/** 20 × 14 static flag, served as shipped (no optimizer, no transform). Renders nothing when the venue is unknown. */
export function VenueFlag({ venue }: { venue: Venue | null | undefined }) {
  if (!venue) return null;
  return <span className={styles.hostCountry} title={"Host country: " + venue.name}>
    <Image className={styles.flag} src={venue.flag} unoptimized width={20} height={14} alt={venue.name} />
    <span aria-hidden="true">{hostCodes[venue.code] ?? venue.code.toUpperCase()}</span>
  </span>;
}
